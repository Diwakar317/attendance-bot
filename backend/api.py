from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, date, timezone
from pydantic import BaseModel

import os
import shutil
import traceback

from bot.database import SessionLocal
from bot.models import User, Attendance
from bot.config import (
    ALLOWED_MIME_TYPES,
    MAX_UPLOAD_SIZE_BYTES,
)
from bot.face import validate_face_image
from bot.logging_config import get_app_logger, get_security_logger
from bot.rate_limiter import login_limiter
from backend.auth_config import ADMIN_USERNAME, ADMIN_PASSWORD
from backend.auth import create_token, verify_token
from sqlalchemy import func

log = get_app_logger("api")
sec_log = get_security_logger()


# ---------- PATH SETUP ----------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REGISTERED_FACES_DIR = os.path.join(BASE_DIR, "bot", "registered_faces")


# ---------- Pydantic models ----------

class LoginRequest(BaseModel):
    username: str
    password: str


class MessageResponse(BaseModel):
    message: str


# ---------- APP ----------
app = FastAPI(title="Attendance Admin API")


# ---------- Global exception handler ----------

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    log.error(
        "Unhandled exception on %s %s: %s",
        request.method, request.url.path, exc,
        exc_info=True,
    )
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


# ---------- CORS ----------
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def disable_cache(request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    return response


# ---------- DATABASE ----------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------- Upload helpers ----------

def _validate_upload(file: UploadFile) -> None:
    """Validate MIME type and file size. Raises HTTPException on failure."""
    if file.content_type and file.content_type not in ALLOWED_MIME_TYPES:
        sec_log.warning(
            "action=upload_invalid_mime | filename=%s | mime=%s",
            file.filename, file.content_type,
        )
        raise HTTPException(400, f"Invalid file type: {file.content_type}. Allowed: JPEG, PNG, WebP")

    file.file.seek(0, 2)
    size = file.file.tell()
    file.file.seek(0)
    if size > MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(400, f"File too large ({size} bytes). Max {MAX_UPLOAD_SIZE_BYTES // (1024*1024)} MB")


def _save_and_validate_face(file: UploadFile, dest_path: str) -> None:
    """Save uploaded file to dest_path, validate it contains exactly 1 face.
    Deletes the file and raises HTTPException on failure."""
    with open(dest_path, "wb") as buf:
        shutil.copyfileobj(file.file, buf)

    ok, reason = validate_face_image(dest_path)
    if not ok:
        try:
            os.remove(dest_path)
        except OSError:
            pass
        log.warning("Face validation failed for %s: %s", dest_path, reason)
        raise HTTPException(400, reason)


# ---------- DASHBOARD ----------

@app.get("/dashboard")
def dashboard(admin=Depends(verify_token), db: Session = Depends(get_db)):

    now = datetime.now(timezone.utc)
    today = now.date()

    total_users = db.query(User).count()
    total_attendance = db.query(Attendance).count()

    # Today
    today_start = datetime.combine(today, datetime.min.time(), tzinfo=timezone.utc)
    today_end = today_start + timedelta(days=1)

    today_attendance = db.query(Attendance).filter(
        Attendance.check_in >= today_start,
        Attendance.check_in < today_end,
    ).count()

    active_users_today = db.query(
        func.count(func.distinct(Attendance.user_id))
    ).filter(
        Attendance.check_in >= today_start,
        Attendance.check_in < today_end,
    ).scalar()

    attendance_rate = (
        round((active_users_today / total_users) * 100, 2)
        if total_users > 0 else 0
    )

    # Weekly / Monthly
    week_start = today_start - timedelta(days=7)
    weekly_attendance = db.query(Attendance).filter(Attendance.check_in >= week_start).count()

    month_start = today_start.replace(day=1)
    monthly_attendance = db.query(Attendance).filter(Attendance.check_in >= month_start).count()

    # Last 7 days trend
    trend_data = []
    for i in range(7):
        day = today_start - timedelta(days=i)
        next_day = day + timedelta(days=1)
        count = db.query(Attendance).filter(
            Attendance.check_in >= day,
            Attendance.check_in < next_day,
        ).count()
        trend_data.append({"date": day.strftime("%Y-%m-%d"), "attendance": count})
    trend_data.reverse()

    return {
        "summary": {
            "total_users": total_users,
            "total_attendance": total_attendance,
            "today_attendance": today_attendance,
            "active_users_today": active_users_today,
            "attendance_rate_today": attendance_rate,
        },
        "time_metrics": {
            "weekly_attendance": weekly_attendance,
            "monthly_attendance": monthly_attendance,
        },
        "trend": trend_data,
    }


# ---------- GET USERS ----------
@app.get("/users")
def get_users(admin=Depends(verify_token), db: Session = Depends(get_db)):
    users = db.query(User).all()
    return [
        {
            "id": u.id,
            "name": u.name,
            "phone": u.phone,
            "telegram_id": u.telegram_id,
            "face_registered": u.face_registered,
        }
        for u in users
    ]


# ---------- CREATE USER WITH UP TO 3 FACES ----------
@app.post("/users", response_model=MessageResponse)
def create_user(
    admin=Depends(verify_token),
    name: str = Form(...),
    phone: str = Form(...),
    faces: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
):
    existing = db.query(User).filter(User.phone == phone).first()
    if existing:
        raise HTTPException(400, "User already exists")

    if len(faces) > 3:
        raise HTTPException(400, "Maximum 3 reference images allowed")

    user_dir = os.path.join(REGISTERED_FACES_DIR, phone)
    os.makedirs(user_dir, exist_ok=True)

    saved_count = 0
    for i, face in enumerate(faces, start=1):
        _validate_upload(face)
        face_path = os.path.join(user_dir, f"reference_{i}.jpg")
        try:
            _save_and_validate_face(face, face_path)
            saved_count += 1
        except HTTPException:
            # Clean up all previously saved faces for this user
            shutil.rmtree(user_dir, ignore_errors=True)
            raise

    user = User(
        name=name,
        phone=phone,
        telegram_id=None,
        face_registered=saved_count,
    )
    db.add(user)
    db.commit()

    log.info("action=user_created | admin=%s | phone=%s | faces=%d", admin, phone, saved_count)
    return {"message": f"User created with {saved_count} reference images"}


# ---------- DELETE USER ----------
@app.delete("/users/{user_id}", response_model=MessageResponse)
def delete_user(user_id: int, admin=Depends(verify_token), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found")

    db.query(Attendance).filter(Attendance.user_id == user_id).delete()

    face_dir = os.path.join(REGISTERED_FACES_DIR, user.phone)
    if os.path.exists(face_dir):
        shutil.rmtree(face_dir)

    db.delete(user)
    db.commit()

    log.info("action=user_deleted | admin=%s | user_id=%d | phone=%s", admin, user_id, user.phone)
    return {"message": "User deleted"}


# ---------- GET ATTENDANCE ----------
@app.get("/attendance")
def get_attendance(admin=Depends(verify_token), db: Session = Depends(get_db)):
    records = db.query(Attendance, User).join(User, Attendance.user_id == User.id).all()
    return [
        {
            "id": a.id,
            "name": u.name,
            "phone": u.phone,
            "check_in": a.check_in,
            "check_out": a.check_out,
        }
        for a, u in records
    ]


# ---------- GET USER FACE (first reference) ----------
@app.get("/users/{user_id}/face")
def get_user_face(user_id: int, admin=Depends(verify_token), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found")

    user_dir = os.path.join(REGISTERED_FACES_DIR, user.phone)
    if not os.path.exists(user_dir):
        raise HTTPException(404, "Face folder not found")

    reference_images = sorted([
        f for f in os.listdir(user_dir)
        if f.startswith("reference_") and f.endswith(".jpg")
    ])
    if not reference_images:
        raise HTTPException(404, "No reference images found")

    return FileResponse(os.path.join(user_dir, reference_images[0]))


# ---------- GET ALL FACES ----------
@app.get("/users/{user_id}/faces")
def get_all_faces(user_id: int, admin=Depends(verify_token), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found")

    user_dir = os.path.join(REGISTERED_FACES_DIR, user.phone)
    if not os.path.exists(user_dir):
        return {"faces": []}

    reference_images = sorted([
        f for f in os.listdir(user_dir)
        if f.startswith("reference_") and f.endswith(".jpg")
    ])
    return {"faces": [f"/users/{user_id}/face/{i+1}" for i in range(len(reference_images))]}


# ---------- USER ATTENDANCE ----------
@app.get("/users/{user_id}/attendance")
def get_user_attendance(user_id: int, admin=Depends(verify_token), db: Session = Depends(get_db)):
    records = db.query(Attendance).filter(Attendance.user_id == user_id).all()
    return [
        {
            "id": r.id,
            "check_in": r.check_in,
            "check_out": r.check_out,
            "lat": r.lat,
            "lon": r.lon,
        }
        for r in records
    ]


# ---------- ADD FACE ----------
@app.post("/users/{user_id}/face", response_model=MessageResponse)
def add_face(
    user_id: int,
    face: UploadFile = File(...),
    admin=Depends(verify_token),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found")

    _validate_upload(face)

    user_dir = os.path.join(REGISTERED_FACES_DIR, user.phone)
    os.makedirs(user_dir, exist_ok=True)

    existing = sorted([
        f for f in os.listdir(user_dir)
        if f.startswith("reference_") and f.endswith(".jpg")
    ])
    if len(existing) >= 3:
        raise HTTPException(400, "Maximum 3 reference images allowed")

    next_index = len(existing) + 1
    face_path = os.path.join(user_dir, f"reference_{next_index}.jpg")
    _save_and_validate_face(face, face_path)

    user.face_registered = next_index
    db.commit()

    log.info("action=face_added | admin=%s | user_id=%d | index=%d", admin, user_id, next_index)
    return {"message": f"Reference image {next_index} saved"}


# ---------- GET FACE BY INDEX ----------
@app.get("/users/{user_id}/face/{index}")
def get_face_by_index(
    user_id: int,
    index: int,
    # admin=Depends(verify_token),
    db: Session = Depends(get_db),
):
    if index < 1 or index > 3:
        raise HTTPException(400, "Index must be 1, 2, or 3")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found")

    face_path = os.path.join(REGISTERED_FACES_DIR, user.phone, f"reference_{index}.jpg")
    if not os.path.exists(face_path):
        raise HTTPException(404, "Face not found")

    return FileResponse(face_path)


# ---------- UPDATE FACE BY INDEX ----------
@app.put("/users/{user_id}/face/{index}", response_model=MessageResponse)
def update_face_by_index(
    user_id: int,
    index: int,
    face: UploadFile = File(...),
    admin=Depends(verify_token),
    db: Session = Depends(get_db),
):
    if index < 1 or index > 3:
        raise HTTPException(400, "Index must be 1, 2, or 3")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found")

    _validate_upload(face)

    face_path = os.path.join(REGISTERED_FACES_DIR, user.phone, f"reference_{index}.jpg")
    if not os.path.exists(face_path):
        raise HTTPException(404, f"Face {index} does not exist")

    _save_and_validate_face(face, face_path)

    log.info("action=face_updated | admin=%s | user_id=%d | index=%d", admin, user_id, index)
    return {"message": f"Face {index} updated successfully"}


# ---------- DELETE FACE BY INDEX ----------
@app.delete("/users/{user_id}/face/{index}", response_model=MessageResponse)
def delete_face_by_index(
    user_id: int,
    index: int,
    admin=Depends(verify_token),
    db: Session = Depends(get_db),
):
    if index < 1 or index > 3:
        raise HTTPException(400, "Index must be 1, 2, or 3")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found")

    user_dir = os.path.join(REGISTERED_FACES_DIR, user.phone)
    face_path = os.path.join(user_dir, f"reference_{index}.jpg")
    if not os.path.exists(face_path):
        raise HTTPException(404, f"Face {index} does not exist")

    os.remove(face_path)

    remaining = sorted([
        f for f in os.listdir(user_dir)
        if f.startswith("reference_") and f.endswith(".jpg")
    ])
    for i, fname in enumerate(remaining, start=1):
        old = os.path.join(user_dir, fname)
        new = os.path.join(user_dir, f"reference_{i}.jpg")
        if old != new:
            os.rename(old, new)

    user.face_registered = len(remaining)
    db.commit()

    log.info("action=face_deleted | admin=%s | user_id=%d | index=%d | remaining=%d", admin, user_id, index, len(remaining))
    return {"message": f"Face {index} deleted. {len(remaining)} face(s) remaining."}


# ---------- LOGIN ----------
@app.post("/login")
def login(data: LoginRequest, request: Request):
    client_ip = request.client.host if request.client else "unknown"

    if not login_limiter.is_allowed(client_ip):
        sec_log.warning("action=login_rate_limit | ip=%s", client_ip)
        raise HTTPException(429, "Too many login attempts. Try again later.")

    if data.username != ADMIN_USERNAME or data.password != ADMIN_PASSWORD:
        login_limiter.record(client_ip)
        sec_log.warning("action=login_failed | ip=%s | username=%s", client_ip, data.username)
        raise HTTPException(401, "Invalid credentials")

    token = create_token(data.username)
    sec_log.info("action=login_success | ip=%s | username=%s", client_ip, data.username)
    return {"access_token": token, "token_type": "bearer"}
