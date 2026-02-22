import os
from dotenv import load_dotenv
load_dotenv()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DATABASE_URL = f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'attendance.db')}"

BOT_TOKEN = os.getenv("BOT_TOKEN")
# OFFICE_LAT = 26.845146 
# OFFICE_LON = 81.021508 
OFFICE_LAT = 26.879208 
OFFICE_LON = 81.016411
OFFICE_RADIUS_METERS = 50