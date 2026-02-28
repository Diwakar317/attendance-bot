import telebot
import os
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from sqlalchemy.exc import IntegrityError
from bot.database import SessionLocal
from bot.models import User, Attendance, UsedPhoto
from bot.config import BOT_TOKEN
from bot.face import verify_face, register_face
from bot.location import is_valid_location
from bot.logging_config import get_app_logger, get_security_logger
from bot.rate_limiter import face_verify_limiter, checkin_limiter
from datetime import datetime, timezone

log = get_app_logger("bot")
sec_log = get_security_logger()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FACES_DIR = os.path.join(BASE_DIR, "registered_faces")

bot = telebot.TeleBot(BOT_TOKEN)

user_states = {}
admin_states = {}
ADMIN_IDS = list(map(int, os.getenv("ADMIN_IDS", "").split(",")))

# Clean leftover temp files on startup
for _f in os.listdir():
    if _f.startswith("temp_") and _f.endswith(".jpg"):
        try:
            os.remove(_f)
        except OSError:
            pass

MAX_PHOTO_AGE_SECONDS = 60


def is_live_camera_photo(message, file_path):
    """Returns (True, None) if valid or (False, reason) if invalid."""
    if message.forward_date is not None:
        return False, "Forwarded photos are not allowed. Take a live photo."

    telegram_time = int(message.date)
    current_time = int(datetime.now(timezone.utc).timestamp())

    if current_time - telegram_time > MAX_PHOTO_AGE_SECONDS:
        return False, "Photo is too old. Take a live photo now."

    return True, None


def get_db():
    return SessionLocal()


def normalize_phone(phone):
    phone = phone.strip().replace(" ", "").replace("-", "")
    if phone.startswith("+"):
        phone = phone[1:]
    if phone.startswith("91") and len(phone) == 12:
        phone = phone[2:]
    return phone


def _safe_cleanup(path: str) -> None:
    """Delete a temp file if it exists, swallow errors."""
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except OSError:
        pass


# ── /start ──────────────────────────────────────────────────────

@bot.message_handler(commands=["start"])
def start(message):
    bot.reply_to(message, "Welcome to Attendance Bot\nUse /checkin or /checkout")


# ── /checkin ────────────────────────────────────────────────────

@bot.message_handler(commands=["checkin"])
def checkin(message):
    uid = message.from_user.id

    if not checkin_limiter.hit(str(uid)):
        sec_log.warning("action=checkin_rate_limit | telegram_id=%s", uid)
        bot.reply_to(message, "Too many check-in attempts. Please wait a few minutes.")
        return

    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(KeyboardButton("Share Phone Number", request_contact=True))
    bot.send_message(message.chat.id, "Share your phone number", reply_markup=markup)
    user_states[uid] = "WAIT_PHONE"
    log.info("action=checkin_started | telegram_id=%s", uid)


# ── Contact handler ─────────────────────────────────────────────

@bot.message_handler(content_types=["contact"])
def contact_handler(message):
    uid = message.from_user.id

    if user_states.get(uid) != "WAIT_PHONE":
        bot.reply_to(message, "Please use /checkin before sharing phone number.")
        return

    if message.contact.user_id and message.contact.user_id != uid:
        sec_log.warning("action=foreign_contact | telegram_id=%s", uid)
        bot.reply_to(message, "Please share your own phone number.")
        return

    db = get_db()
    try:
        telegram_id = str(uid)
        phone = normalize_phone(message.contact.phone_number)

        user = db.query(User).filter_by(phone=phone).first()
        if not user:
            bot.send_message(
                message.chat.id,
                "You are not registered. Contact admin.",
                reply_markup=ReplyKeyboardRemove(),
            )
            user_states.pop(uid, None)
            return

        if user.telegram_id and user.telegram_id != telegram_id:
            sec_log.warning(
                "action=phone_hijack_attempt | phone=%s | existing_tid=%s | attacker_tid=%s",
                phone, user.telegram_id, telegram_id,
            )
            bot.reply_to(message, "This phone is already linked to another Telegram account.")
            return

        existing_user = db.query(User).filter_by(telegram_id=telegram_id).first()
        if existing_user and existing_user.id != user.id:
            db.delete(existing_user)
            db.commit()

        user.telegram_id = telegram_id
        user.name = message.from_user.first_name
        db.commit()

        user_states[uid] = "WAIT_LOCATION"
        bot.send_message(
            message.chat.id,
            "Phone verified. Send live location.",
            reply_markup=ReplyKeyboardRemove(),
        )
        log.info("action=phone_verified | telegram_id=%s | phone=%s", uid, phone)
    except Exception:
        log.error("Unexpected error in contact_handler", exc_info=True)
        bot.reply_to(message, "An error occurred. Please try again.")
    finally:
        db.close()


# ── Location handler ─────────────────────────────────────────────

@bot.message_handler(content_types=["location"])
def location_handler(message):
    uid = message.from_user.id

    if message.location.live_period is None:
        bot.reply_to(message, "Please send LIVE location, not static location")
        return

    if user_states.get(uid) != "WAIT_LOCATION":
        bot.reply_to(message, "Please use /checkin before sending location.")
        return

    lat = message.location.latitude
    lon = message.location.longitude

    if not is_valid_location(lat, lon):
        log.info("action=location_rejected | telegram_id=%s | lat=%s lon=%s", uid, lat, lon)
        bot.reply_to(message, "Not in office location")
        return

    user_states[uid] = ("WAIT_PHOTO", lat, lon, datetime.now(timezone.utc).timestamp())
    log.info("action=location_accepted | telegram_id=%s", uid)
    bot.reply_to(message, "Send your photo")


# ── Photo handler ────────────────────────────────────────────────

@bot.message_handler(content_types=["photo"])
def photo_handler(message):
    uid = message.from_user.id

    # ── Admin face registration ──
    if uid in admin_states:
        _handle_admin_face(message)
        return

    # ── User check-in photo ──
    state = user_states.get(uid)
    if not state or not isinstance(state, tuple) or state[0] != "WAIT_PHOTO":
        bot.reply_to(message, "Please use /checkin before sending photo.")
        return

    lat, lon, location_time = state[1], state[2], state[3]
    MAX_DELAY = 30

    if datetime.now(timezone.utc).timestamp() - location_time > MAX_DELAY:
        bot.reply_to(
            message,
            "Photo must be taken immediately after sending live location. Please check in again.",
        )
        user_states.pop(uid, None)
        return

    file_info = bot.get_file(message.photo[-1].file_id)
    downloaded = bot.download_file(file_info.file_path)
    path = os.path.join(BASE_DIR, f"temp_{uid}.jpg")

    with open(path, "wb") as f:
        f.write(downloaded)

    valid, reason = is_live_camera_photo(message, path)
    if not valid:
        sec_log.warning("action=non_live_photo | telegram_id=%s | reason=%s", uid, reason)
        bot.reply_to(message, reason)
        _safe_cleanup(path)
        user_states.pop(uid, None)
        return

    db = get_db()
    try:
        user = db.query(User).filter_by(telegram_id=str(uid)).first()
        if not user:
            bot.reply_to(message, "User not registered")
            return

        # Anti-replay
        photo_unique_id = message.photo[-1].file_unique_id
        used = UsedPhoto(
            file_unique_id=photo_unique_id,
            user_id=user.id,
            used_at=datetime.now(timezone.utc),
        )
        db.add(used)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            sec_log.warning("action=photo_replay | telegram_id=%s | file_uid=%s", uid, photo_unique_id)
            bot.reply_to(message, "This photo was already used. Please take a new live photo.")
            return

        # Check face folder
        phone = normalize_phone(user.phone)
        user_dir = os.path.join(FACES_DIR, phone)
        if not os.path.exists(user_dir) or not any(
            f.startswith("reference_") and f.endswith(".jpg") for f in os.listdir(user_dir)
        ):
            bot.reply_to(message, "Face not registered. Contact admin.")
            return

        # Rate-limited face verification
        if not face_verify_limiter.is_allowed(str(uid)):
            sec_log.warning("action=face_verify_rate_limit | telegram_id=%s", uid)
            bot.reply_to(message, "Too many verification attempts. Please wait.")
            return
        face_verify_limiter.record(str(uid))

        verified = verify_face(phone, path)
        if not verified:
            sec_log.warning("action=face_mismatch | telegram_id=%s | phone=%s", uid, phone)
            bot.reply_to(message, "Face not recognized")
            return

        # Prevent duplicate check-in (use date column)
        today = datetime.now(timezone.utc).date()
        existing = db.query(Attendance).filter_by(
            user_id=user.id, date=today
        ).first()

        if existing:
            bot.reply_to(message, "Already checked in today")
            return

        attendance = Attendance(
            user_id=user.id,
            check_in=datetime.now(timezone.utc),
            lat=lat,
            lon=lon,
            date=today,
        )
        db.add(attendance)
        db.commit()

        log.info("action=checkin_success | telegram_id=%s | user_id=%d", uid, user.id)
        bot.reply_to(message, "Check-in successful")

    except Exception:
        log.error("Unexpected error in photo_handler", exc_info=True)
        bot.reply_to(message, "An error occurred. Please try again.")
    finally:
        db.close()
        _safe_cleanup(path)
        user_states.pop(uid, None)


# ── Admin face registration helper ──────────────────────────────

def _handle_admin_face(message):
    uid = message.from_user.id
    phone = normalize_phone(admin_states[uid])

    file_info = bot.get_file(message.photo[-1].file_id)
    downloaded = bot.download_file(file_info.file_path)

    user_dir = os.path.join(FACES_DIR, phone)
    os.makedirs(user_dir, exist_ok=True)

    temp_path = os.path.join(BASE_DIR, f"temp_admin_{phone}.jpg")
    with open(temp_path, "wb") as f:
        f.write(downloaded)

    success = register_face(phone, temp_path)
    _safe_cleanup(temp_path)

    if success:
        face_count = len([
            f for f in os.listdir(user_dir)
            if f.startswith("reference_") and f.endswith(".jpg")
        ])

        db = get_db()
        try:
            user = db.query(User).filter_by(phone=phone).first()
            if not user:
                user = User(phone=phone, telegram_id=None, name="Employee", face_registered=face_count)
                db.add(user)
            else:
                user.face_registered = face_count
            db.commit()
        finally:
            db.close()

        log.info("action=admin_face_registered | admin=%s | phone=%s | count=%d", uid, phone, face_count)

        if face_count < 3:
            bot.reply_to(message, f"Face {face_count}/3 registered for {phone}. Send another photo or wait.")
        else:
            bot.reply_to(message, f"All 3 faces registered for {phone}.")
            del admin_states[uid]
    else:
        bot.reply_to(message, "No face detected or max 3 faces reached")


# ── /checkout ───────────────────────────────────────────────────

@bot.message_handler(commands=["checkout"])
def checkout(message):
    uid = message.from_user.id
    db = get_db()
    try:
        user = db.query(User).filter_by(telegram_id=str(uid)).first()
        if not user:
            bot.reply_to(message, "User not registered")
            return

        # Safe checkout: find today's record with no check_out
        attendance = db.query(Attendance).filter_by(
            user_id=user.id, check_out=None
        ).filter(
            Attendance.date == datetime.now(timezone.utc).date()
        ).first()

        if attendance:
            attendance.check_out = datetime.now(timezone.utc)
            db.commit()
            log.info("action=checkout_success | telegram_id=%s | user_id=%d", uid, user.id)
            bot.reply_to(message, "Checkout successful")
        else:
            bot.reply_to(message, "No active check-in")
    except Exception:
        log.error("Unexpected error in checkout", exc_info=True)
        bot.reply_to(message, "An error occurred. Please try again.")
    finally:
        db.close()


# ── /register_face (admin) ──────────────────────────────────────

@bot.message_handler(commands=["register_face"])
def register_face_command(message):
    uid = message.from_user.id
    if uid not in ADMIN_IDS:
        sec_log.warning("action=unauthorized_register_face | telegram_id=%s", uid)
        bot.reply_to(message, "Unauthorized")
        return

    parts = message.text.split()
    if len(parts) != 2:
        bot.reply_to(message, "Usage: /register_face PHONE_NUMBER")
        return

    phone = normalize_phone(parts[1])
    admin_states[uid] = phone
    log.info("action=admin_register_face_start | admin=%s | phone=%s", uid, phone)
    bot.reply_to(message, f"Send face photo for phone {phone}")


# ── Fallback ────────────────────────────────────────────────────

@bot.message_handler(func=lambda message: True)
def fallback_handler(message):
    uid = message.from_user.id
    state = user_states.get(uid)

    if state == "WAIT_PHONE":
        bot.reply_to(message, "Please share your phone number using the button.")
        return
    elif state == "WAIT_LOCATION":
        bot.reply_to(message, "Please send LIVE location using Telegram location sharing.")
        return
    elif isinstance(state, tuple) and state[0] == "WAIT_PHOTO":
        bot.reply_to(message, "Please take and send a live photo using your camera.")
        return

    bot.reply_to(message, "Use /checkin to mark attendance or /checkout to end attendance.")
