import telebot
import os
from telebot.types import ReplyKeyboardMarkup, KeyboardButton
from sqlalchemy.exc import IntegrityError
from bot.database import SessionLocal
from bot.models import User, Attendance, UsedPhoto
from bot.config import BOT_TOKEN
from bot.face import verify_face
from bot.face import register_face
from bot.location import is_valid_location
from datetime import datetime, timezone

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

FACES_DIR = os.path.join(BASE_DIR, "registered_faces")


bot = telebot.TeleBot(BOT_TOKEN)

user_states = {}
admin_states = {}
ADMIN_IDS = [880412020]  # replace with your Telegram ID


# Clean leftover temp files on startup
for file in os.listdir():
    if file.startswith("temp_") and file.endswith(".jpg"):
        try:
            os.remove(file)
        except:
            pass
MAX_PHOTO_AGE_SECONDS = 60  # allow only photos taken in last 60 seconds

def is_live_camera_photo(message, file_path):
    """
    Returns (True, None) if valid
    Returns (False, reason) if invalid
    """

    # 1. Reject forwarded photos
    if message.forward_date is not None:
        return False, "Forwarded photos are not allowed. Take a live photo."

    # 2. Reject old Telegram photos
    telegram_time = int(message.date)  # unix timestamp
    current_time = int(datetime.now(timezone.utc).timestamp())

    if current_time - telegram_time > MAX_PHOTO_AGE_SECONDS:
        return False, "Photo is too old. Take a live photo now."

    # 3. Check EXIF metadata
    # try:
    #     img = Image.open(file_path)

    #     exif = img._getexif()

    #     if exif is not None:

    #         exif_data = {
    #             ExifTags.TAGS.get(tag): value
    #             for tag, value in exif.items()
    #         }

    #         # # Check camera make/model exists
    #         # if "Make" not in exif_data and "Model" not in exif_data:
    #         #     return False, "Photo must be taken using camera."

    # except:
    #     # Some Telegram photos strip EXIF, so don't reject solely on this
    #     pass

    return True, None

def get_db():
    return SessionLocal()

def normalize_phone(phone):
    phone = phone.strip()
    phone = phone.replace(" ", "")
    phone = phone.replace("-", "")

    if phone.startswith("+"):
        phone = phone[1:]

    # Convert 918840717494 → 8840717494
    if phone.startswith("91") and len(phone) == 12:
        phone = phone[2:]

    return phone


@bot.message_handler(commands=['start'])
def start(message):
    # print("Your Telegram ID:", message.from_user.id)
    bot.reply_to(
        message,
        "Welcome to Attendance Bot\nUse /checkin or /checkout"
    )


@bot.message_handler(commands=['checkin'])
def checkin(message):

    markup = ReplyKeyboardMarkup(resize_keyboard=True)

    button = KeyboardButton(
        "Share Phone Number",
        request_contact=True
    )

    markup.add(button)

    bot.send_message(
        message.chat.id,
        "Share your phone number",
        reply_markup=markup
    )

    user_states[message.from_user.id] = "WAIT_PHONE"

   
@bot.message_handler(content_types=['contact'])
def contact_handler(message):

    if user_states.get(message.from_user.id) != "WAIT_PHONE":
        bot.reply_to(
        message,
        "Please use /checkin before sharing phone number."
        )
        return

    # SECURITY: ensure user shares own contact
    if message.contact.user_id and message.contact.user_id != message.from_user.id:
        bot.reply_to(message, "Please share your own phone number.")
        return

    db = get_db()
    try:
        telegram_id = str(message.from_user.id)

        # phone = message.contact.phone_number
        phone = normalize_phone(message.contact.phone_number)


        user = db.query(User).filter_by(
            phone=phone
        ).first()
        if not user:

            from telebot.types import ReplyKeyboardRemove

            bot.send_message(
                message.chat.id,
                "You are not registered. Contact admin.",
                reply_markup=ReplyKeyboardRemove()
            )

            if message.from_user.id in user_states:
                del user_states[message.from_user.id]

            return
        # Prevent hijacking another account
        if user.telegram_id and user.telegram_id != telegram_id:
            bot.reply_to(message, "This phone is already linked to another Telegram account.")
            return
        
        # Check if telegram_id already linked to another row
        existing_user = db.query(User).filter_by(
            telegram_id=telegram_id
        ).first()

        if existing_user and existing_user.id != user.id:
            # merge records: delete duplicate telegram row
            db.delete(existing_user)
            db.commit()

        # now link safely
        user.telegram_id = telegram_id
        user.name = message.from_user.first_name

        db.commit()

        user_states[message.from_user.id] = "WAIT_LOCATION"

        from telebot.types import ReplyKeyboardRemove

        bot.send_message(
            message.chat.id,
            "Phone verified. Send live location.",
            reply_markup=ReplyKeyboardRemove()
        )

    finally:
        db.close()


@bot.message_handler(content_types=['location'])
def location_handler(message):
    if message.location.live_period is None:
        bot.reply_to(message, "Please send LIVE location, not static location")
        return
        
    if user_states.get(message.from_user.id) != "WAIT_LOCATION":
        bot.reply_to(
        message,
        "Please use /checkin before sending location."
        )
        return

    lat = message.location.latitude
    lon = message.location.longitude

    if not is_valid_location(lat, lon):
        bot.reply_to(message, "Not in office location")
        return

    # user_states[message.from_user.id] = ("WAIT_PHOTO", lat, lon, datetime.now().timestamp())
    user_states[message.from_user.id] = (
    "WAIT_PHOTO",
    lat,
    lon,
    datetime.now(timezone.utc).timestamp()
    )


    bot.reply_to(message, "Send your photo")


@bot.message_handler(content_types=['photo'])
def photo_handler(message):
    # ADMIN FACE REGISTRATION
    if message.from_user.id in admin_states:

        # phone = admin_states[message.from_user.id]
        phone = normalize_phone(admin_states[message.from_user.id])


        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded = bot.download_file(file_info.file_path)

        user_dir = os.path.join(FACES_DIR, phone)
        
        os.makedirs(user_dir, exist_ok=True)
        
        temp_path = os.path.join(BASE_DIR, f"temp_admin_{phone}.jpg")


        with open(temp_path, "wb") as f:
            f.write(downloaded)

        success = register_face(phone, temp_path)

        os.remove(temp_path)

        # path = f"{user_dir}/reference.jpg"

        # with open(path, "wb") as f:
        #     f.write(downloaded)

        # success = register_face(phone, path)

        if success:

            db = get_db()
            try:
                user = db.query(User).filter_by(phone=phone).first()

                if not user:
                    user = User(
                        phone=phone,
                        telegram_id=None,
                        name="Employee",
                        face_registered=1
                    )
                    db.add(user)
                else:
                    user.face_registered = 1

                db.commit()

            finally:
                db.close()

            # count number of faces now stored
            face_count = len([
                f for f in os.listdir(user_dir)
                if f.startswith("reference_") and f.endswith(".jpg")
            ])

            if face_count < 3:
                bot.reply_to(
                    message,
                    f"Face {face_count}/3 registered for {phone}. Send another photo or wait."
                )
            else:
                bot.reply_to(
                    message,
                    f"All 3 faces registered for {phone}."
                )
                del admin_states[message.from_user.id]

        else:
            bot.reply_to(message, "No face detected or max 3 faces reached")


        return

    #USER Photo handler
    state = user_states.get(message.from_user.id)

    if not state or state[0] != "WAIT_PHOTO":
        bot.reply_to(
        message,
        "Please use /checkin before sending photo."
        )
        return

    # lat, lon = state[1], state[2]
    lat, lon, location_time = state[1], state[2], state[3]

    MAX_DELAY = 30  # seconds

    current_time = datetime.now(timezone.utc).timestamp()

    if current_time - location_time > MAX_DELAY:
        
        bot.reply_to(
            message,
            "Photo must be taken immediately after sending live location. Please check in again."
        )

        if message.from_user.id in user_states:
            del user_states[message.from_user.id]

        return


    file_info = bot.get_file(message.photo[-1].file_id)

    downloaded = bot.download_file(file_info.file_path)

    path = f"temp_{message.from_user.id}.jpg"

    with open(path, "wb") as f:
        f.write(downloaded)
    
    # SECURITY CHECK: ensure live camera photo
    valid, reason = is_live_camera_photo(message, path)

    if not valid:

        bot.reply_to(message, reason)

        if os.path.exists(path):
            os.remove(path)

        if message.from_user.id in user_states:
            del user_states[message.from_user.id]

        return
    
    db = get_db()

    try:

        user = db.query(User).filter_by(
            telegram_id=str(message.from_user.id)
        ).first()

        if not user:

            bot.reply_to(message, "User not registered")

            if os.path.exists(path):
                os.remove(path)

            user_states.pop(message.from_user.id, None)
            return


        # BLOCK PHOTO REUSE FIRST
        photo_unique_id = message.photo[-1].file_unique_id

        used = UsedPhoto(
            file_unique_id=photo_unique_id,
            used_at=datetime.now(timezone.utc)
        )

        db.add(used)

        try:

            db.commit()

        except IntegrityError:

            db.rollback()

            bot.reply_to(
                message,
                "This photo was already used. Please take a new live photo."
            )

            if os.path.exists(path):
                os.remove(path)

            user_states.pop(message.from_user.id, None)
            return
        
        # CHECK FACE FILE EXISTS
        phone = normalize_phone(user.phone)

        user_dir = os.path.join(FACES_DIR, phone)

        if not os.path.exists(user_dir):

            bot.reply_to(message, "Face not registered. Contact admin.")

            if os.path.exists(path):
                os.remove(path)

            user_states.pop(message.from_user.id, None)
            return


        reference_images = [
            f for f in os.listdir(user_dir)
            if f.startswith("reference_") and f.endswith(".jpg")
        ]

        if len(reference_images) == 0:

            bot.reply_to(message, "Face not registered. Contact admin.")

            if os.path.exists(path):
                os.remove(path)

            user_states.pop(message.from_user.id, None)
            return


        # # CHECK FACE FILE EXISTS
        # phone = normalize_phone(user.phone)

        # face_path = f"registered_faces/{phone}/reference.jpg"

        # if not os.path.exists(face_path):

        #     bot.reply_to(message, "Face not registered. Contact admin.")

        #     if os.path.exists(path):
        #         os.remove(path)

        #     user_states.pop(message.from_user.id, None)
        #     return


        # VERIFY FACE ONLY ONCE
        verified = verify_face(phone, path)

        if not verified:

            bot.reply_to(message, "Face not recognized")

            if os.path.exists(path):
                os.remove(path)

            user_states.pop(message.from_user.id, None)
            return


        # CHECK ACTIVE ATTENDANCE
        existing = db.query(Attendance)\
            .filter_by(user_id=user.id, check_out=None)\
            .first()

        if existing:

            bot.reply_to(message, "Already checked in today")

            if os.path.exists(path):
                os.remove(path)

            user_states.pop(message.from_user.id, None)
            return


        # SAVE ATTENDANCE
        attendance = Attendance(
            user_id=user.id,
            check_in=datetime.now(timezone.utc),
            lat=lat,
            lon=lon
        )

        db.add(attendance)

        db.commit()


        bot.reply_to(message, "Check-in successful")


    finally:

        db.close()

        if os.path.exists(path):
            os.remove(path)

        user_states.pop(message.from_user.id, None)


@bot.message_handler(commands=['checkout'])
def checkout(message):

    db = get_db()
    try:
        user = db.query(User).filter_by(
            telegram_id=str(message.from_user.id)
        ).first()
        if not user:
            bot.reply_to(message, "User not registered")
            return
        attendance = db.query(Attendance)\
            .filter_by(user_id=user.id)\
            .order_by(Attendance.id.desc())\
            .first()

        if attendance and not attendance.check_out:

            attendance.check_out = datetime.now(timezone.utc)

            db.commit()

            bot.reply_to(message, "Checkout successful")

        else:
            bot.reply_to(message, "No active check-in")
    finally:
        db.close()

@bot.message_handler(commands=['register_face'])
def register_face_command(message):

    if message.from_user.id not in ADMIN_IDS:
        bot.reply_to(message, "Unauthorized")
        return

    parts = message.text.split()

    if len(parts) != 2:
        bot.reply_to(message, "Usage: /register_face PHONE_NUMBER")
        return

    phone = normalize_phone(parts[1])


    admin_states[message.from_user.id] = phone

    bot.reply_to(
        message,
        f"Send face photo for phone {phone}"
    )


@bot.message_handler(func=lambda message: True)
def fallback_handler(message):

    user_id = message.from_user.id
    state = user_states.get(user_id)

    # User in phone step
    if state == "WAIT_PHONE":
        bot.reply_to(
            message,
            "Please share your phone number using the button."
        )
        return

    # User in location step
    elif state == "WAIT_LOCATION":
        bot.reply_to(
            message,
            "Please send LIVE location using Telegram location sharing."
        )
        return

    # User in photo step
    elif isinstance(state, tuple) and state[0] == "WAIT_PHOTO":
        bot.reply_to(
            message,
            "Please take and send a live photo using your camera."
        )
        return

    # Default fallback
    bot.reply_to(
        message,
        "Use /checkin to mark attendance or /checkout to end attendance."
    )
