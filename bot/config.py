import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DATABASE_URL = f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'attendance.db')}"

BOT_TOKEN = "8064164125:AAGVMWfBcZFVdDFTLsvWzWOjs92gJMrqkWk"

OFFICE_LAT = 26.845146
OFFICE_LON = 81.021508
# OFFICE_LAT = 26.805146
# OFFICE_LON = 81.021508
OFFICE_RADIUS_METERS = 50

# DATABASE_URL = "sqlite:///../instance/attendance.db"


