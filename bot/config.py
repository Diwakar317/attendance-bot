import os
from dotenv import load_dotenv
load_dotenv()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL not set")

BOT_TOKEN = os.getenv("BOT_TOKEN")

OFFICE_LAT = float(os.getenv("OFFICE_LAT"))
OFFICE_LON = float(os.getenv("OFFICE_LON"))
OFFICE_RADIUS_METERS = int(os.getenv("OFFICE_RADIUS_METERS", 50))

# Session enforcement: "true" = allow multiple admin sessions
ALLOW_MULTIPLE_SESSIONS = os.getenv("ALLOW_MULTIPLE_SESSIONS", "true").lower() == "true"

# Max upload file size in bytes (default 5 MB)
MAX_UPLOAD_SIZE_BYTES = int(os.getenv("MAX_UPLOAD_SIZE_MB", 5)) * 1024 * 1024

# Allowed image MIME types for face uploads
ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}