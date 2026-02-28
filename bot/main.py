from bot.database import engine, Base, SessionLocal
from bot.models import UsedPhoto
from bot.logging_config import get_app_logger
from datetime import datetime, timezone, timedelta
import bot.handlers as handlers
import time
import telebot.apihelper

log = get_app_logger("main")

# Increase Telegram timeout limits
telebot.apihelper.READ_TIMEOUT = 60
telebot.apihelper.CONNECT_TIMEOUT = 60

# Create database tables
Base.metadata.create_all(bind=engine)
log.info("Database tables created / verified.")


def cleanup_used_photos():
    """Remove UsedPhoto records older than 30 days."""
    db = SessionLocal()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=30)
        deleted = db.query(UsedPhoto).filter(UsedPhoto.used_at < cutoff).delete()
        db.commit()
        log.info("Cleaned %d old used-photo records.", deleted)
    except Exception:
        db.rollback()
        log.error("Failed to clean used photos", exc_info=True)
    finally:
        db.close()


cleanup_used_photos()

log.info("Bot starting…")

while True:
    try:
        handlers.bot.infinity_polling(
            timeout=60,
            long_polling_timeout=60,
            skip_pending=True,
        )
    except Exception as e:
        log.error("Polling error: %s", e, exc_info=True)
        log.info("Reconnecting in 5 seconds…")
        time.sleep(5)
