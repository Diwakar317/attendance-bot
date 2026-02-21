from bot.database import engine, Base, SessionLocal
from bot.models import UsedPhoto
from datetime import datetime, timezone, timedelta
import bot.handlers as handlers
import time
import telebot.apihelper
# Increase Telegram timeout limits
telebot.apihelper.READ_TIMEOUT = 60
telebot.apihelper.CONNECT_TIMEOUT = 60

# Create database tables
Base.metadata.create_all(bind=engine)

# Cleanup old used photos (older than 30 days)
def cleanup_used_photos():

    db = SessionLocal()

    try:
        db.query(UsedPhoto).filter(
            UsedPhoto.used_at <
            datetime.now(timezone.utc) - timedelta(days=30)
        ).delete()

        db.commit()

        print("Old used photos cleaned")

    finally:
        db.close()


# Run cleanup at startup
cleanup_used_photos()

print("Bot running...")

# Auto-reconnect polling loop
while True:
    try:
        handlers.bot.infinity_polling(
            timeout=60,
            long_polling_timeout=60,
            skip_pending=True
        )
    except Exception as e:
        print("Polling error:", e)
        print("Reconnecting in 5 seconds...")
        time.sleep(5)
