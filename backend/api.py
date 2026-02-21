from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

import os
import shutil

from bot.database import SessionLocal
from bot.models import User, Attendance
from backend.auth_config import ADMIN_USERNAME, ADMIN_PASSWORD
from backend.auth import create_token, verify_token


# ---------- PATH SETUP ----------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

REGISTERED_FACES_DIR = os.path.join(
    BASE_DIR,
    "bot",
    "registered_faces"
)


# ---------- APP ----------
app = FastAPI()


# ---------- CORS ----------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------- DATABASE ----------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()




# ---------- DASHBOARD ----------
@app.get("/dashboard")
def dashboard(admin=Depends(verify_token),db: Session = Depends(get_db)):

    total_users = db.query(User).count()

    total_attendance = db.query(Attendance).count()

    today_attendance = db.query(Attendance)\
        .filter(Attendance.check_in != None)\
        .count()

    return {
        "total_users": total_users,
        "total_attendance": total_attendance,
        "today_attendance": today_attendance
    }


# ---------- GET USERS ----------
@app.get("/users")
def get_users(admin=Depends(verify_token),db: Session = Depends(get_db)):

    users = db.query(User).all()

    return [
        {
            "id": u.id,
            "name": u.name,
            "phone": u.phone,
            "telegram_id": u.telegram_id,
            "face_registered": u.face_registered
        }
        for u in users
    ]


# ---------- CREATE USER WITH UP TO 3 FACES ----------
@app.post("/users")
def create_user(
    admin=Depends(verify_token),
    name: str = Form(...),
    phone: str = Form(...),
    faces: list[UploadFile] = File(...),
    db: Session = Depends(get_db)
):

    existing = db.query(User)\
        .filter(User.phone == phone)\
        .first()

    if existing:
        raise HTTPException(
            status_code=400,
            detail="User already exists"
        )

    if len(faces) > 3:
        raise HTTPException(
            status_code=400,
            detail="Maximum 3 reference images allowed"
        )

    user_dir = os.path.join(
        REGISTERED_FACES_DIR,
        phone
    )

    os.makedirs(user_dir, exist_ok=True)

    saved_count = 0

    for i, face in enumerate(faces, start=1):

        face_path = os.path.join(
            user_dir,
            f"reference_{i}.jpg"
        )

        with open(face_path, "wb") as buffer:
            shutil.copyfileobj(face.file, buffer)

        saved_count += 1

    user = User(
        name=name,
        phone=phone,
        telegram_id=None,
        face_registered=1 if saved_count > 0 else 0
    )

    db.add(user)
    db.commit()

    return {
        "message": f"User created with {saved_count} reference images"
    }


# ---------- DELETE USER ----------
@app.delete("/users/{user_id}")
def delete_user(user_id: int,admin=Depends(verify_token), db: Session = Depends(get_db)):

    user = db.query(User)\
        .filter(User.id == user_id)\
        .first()

    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    # Delete face folder
    face_dir = os.path.join(
        REGISTERED_FACES_DIR,
        user.phone
    )

    if os.path.exists(face_dir):
        shutil.rmtree(face_dir)

    db.delete(user)
    db.commit()

    return {
        "message": "User deleted"
    }


# ---------- GET ATTENDANCE ----------
@app.get("/attendance")
def get_attendance(admin=Depends(verify_token),db: Session = Depends(get_db)):

    records = db.query(
        Attendance,
        User
    ).join(
        User,
        Attendance.user_id == User.id
    ).all()

    return [
        {
            "id": a.id,
            "name": u.name,
            "phone": u.phone,
            "check_in": a.check_in,
            "check_out": a.check_out
        }
        for a, u in records
    ]


# ---------- GET USER FACE (preview first reference image) ----------
@app.get("/users/{user_id}/face")
def get_user_face(
    user_id: int,
    db: Session = Depends(get_db)
):

    user = db.query(User)\
        .filter(User.id == user_id)\
        .first()

    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    user_dir = os.path.join(
        REGISTERED_FACES_DIR,
        user.phone
    )

    if not os.path.exists(user_dir):
        raise HTTPException(
            status_code=404,
            detail="Face folder not found"
        )

    reference_images = sorted([
        f for f in os.listdir(user_dir)
        if f.startswith("reference_") and f.endswith(".jpg")
    ])

    if not reference_images:
        raise HTTPException(
            status_code=404,
            detail="No reference images found"
        )

    face_path = os.path.join(
        user_dir,
        reference_images[0]
    )

    return FileResponse(face_path)

@app.get("/users/{user_id}/faces")
def get_all_faces(
    user_id: int,
    db: Session = Depends(get_db)
):

    user = db.query(User)\
        .filter(User.id == user_id)\
        .first()

    if not user:
        raise HTTPException(404, "User not found")

    user_dir = os.path.join(
        REGISTERED_FACES_DIR,
        user.phone
    )

    if not os.path.exists(user_dir):
        return {"faces": []}

    reference_images = sorted([
        f for f in os.listdir(user_dir)
        if f.startswith("reference_") and f.endswith(".jpg")
    ])

    return {
        "faces": [
            f"/users/{user_id}/face/{i+1}"
            for i in range(len(reference_images))
        ]
    }

# ---------- USER ATTENDANCE ----------
@app.get("/users/{user_id}/attendance")
def get_user_attendance(
    user_id: int,
    admin=Depends(verify_token),
    db: Session = Depends(get_db)
):

    records = db.query(Attendance)\
        .filter(Attendance.user_id == user_id)\
        .all()

    return [
        {
            "id": r.id,
            "check_in": r.check_in,
            "check_out": r.check_out,
            "lat": r.lat,
            "lon": r.lon
        }
        for r in records
    ]

@app.post("/users/{user_id}/face")
def register_face(
    user_id: int,
    face: UploadFile = File(...),
    admin=Depends(verify_token),
    db: Session = Depends(get_db)
):

    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(404, "User not found")

    user_dir = os.path.join(
        REGISTERED_FACES_DIR,
        user.phone
    )

    os.makedirs(user_dir, exist_ok=True)

    # find existing reference images
    existing = sorted([
        f for f in os.listdir(user_dir)
        if f.startswith("reference_") and f.endswith(".jpg")
    ])

    if len(existing) >= 3:
        raise HTTPException(
            status_code=400,
            detail="Maximum 3 reference images allowed"
        )

    next_index = len(existing) + 1

    face_path = os.path.join(
        user_dir,
        f"reference_{next_index}.jpg"
    )

    with open(face_path, "wb") as buffer:
        shutil.copyfileobj(face.file, buffer)

    user.face_registered = 1
    db.commit()

    return {
        "message": f"Reference image {next_index} saved"
    }

@app.get("/users/{user_id}/face/{index}")
def get_face_by_index(
    user_id: int,
    index: int,
    db: Session = Depends(get_db)
):

    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(404, "User not found")

    face_path = os.path.join(
        REGISTERED_FACES_DIR,
        user.phone,
        f"reference_{index}.jpg"
    )

    if not os.path.exists(face_path):
        raise HTTPException(404, "Face not found")

    return FileResponse(face_path)


@app.post("/login")
def login(data: dict = Body(...)):

    username = data.get("username")
    password = data.get("password")

    if username != ADMIN_USERNAME or password != ADMIN_PASSWORD:
        raise HTTPException(401, "Invalid credentials")

    token = create_token(username)

    return {
        "access_token": token,
        "token_type": "bearer"
    }
