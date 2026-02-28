import os
import shutil
import threading
from deepface import DeepFace
from bot.logging_config import get_app_logger, get_security_logger

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FACES_DIR = os.path.join(BASE_DIR, "bot", "registered_faces")
os.makedirs(FACES_DIR, exist_ok=True)

MODEL_NAME = "SFace"
DETECTOR = "opencv"

log = get_app_logger("face")
sec_log = get_security_logger()

# ── Lazy singleton model loader (thread-safe) ──────────────────

_model_lock = threading.Lock()
_model_loaded = False


def _ensure_model() -> None:
    """Load the DeepFace model once per process in a thread-safe way."""
    global _model_loaded
    if _model_loaded:
        return
    with _model_lock:
        if _model_loaded:
            return
        log.info("Loading face recognition model (%s)…", MODEL_NAME)
        DeepFace.build_model(MODEL_NAME)
        _model_loaded = True
        log.info("Face recognition model loaded.")


def validate_face_image(image_path: str) -> tuple[bool, str]:
    """
    Validate that an image contains exactly one face.
    Returns (True, "") on success or (False, reason) on failure.
    """
    _ensure_model()
    try:
        faces = DeepFace.extract_faces(
            img_path=image_path,
            detector_backend=DETECTOR,
            enforce_detection=False,
            align=True,
        )
        if len(faces) == 0:
            return False, "No face detected in image"
        if len(faces) > 1:
            return False, f"Multiple faces detected ({len(faces)}); upload one face per image"
        return True, ""
    except Exception as e:
        log.warning("Face validation error: %s", e)
        return False, "Could not detect a face in the image"


def register_face(phone: str, image_path: str) -> bool:
    """
    Validate and copy a face image into the user's reference folder.
    Returns True on success.
    """
    _ensure_model()
    log.info("Registering face for user %s", phone)

    user_dir = os.path.join(FACES_DIR, str(phone))
    os.makedirs(user_dir, exist_ok=True)

    try:
        existing = sorted([
            f for f in os.listdir(user_dir)
            if f.startswith("reference_") and f.endswith(".jpg")
        ])

        next_index = len(existing) + 1
        if next_index > 3:
            log.warning("User %s already has 3 reference images", phone)
            return False

        reference_path = os.path.join(user_dir, f"reference_{next_index}.jpg")
        shutil.copy(image_path, reference_path)

        log.info("Validating reference image %d for %s", next_index, phone)

        ok, reason = validate_face_image(reference_path)
        if not ok:
            os.remove(reference_path)
            log.warning("Face validation failed for %s: %s", phone, reason)
            return False

        log.info("Reference image %d saved for %s", next_index, phone)
        return True

    except Exception as e:
        log.error("Face registration error for %s: %s", phone, e, exc_info=True)
        if "reference_path" in locals() and os.path.exists(reference_path):
            os.remove(reference_path)
        return False


def verify_face(phone: str, image_path: str) -> bool:
    """
    Compare an image against all reference images for a user.
    Returns True if any reference matches.
    """
    _ensure_model()
    log.info("Verifying face for user %s", phone)

    user_dir = os.path.join(FACES_DIR, str(phone))
    if not os.path.exists(user_dir):
        sec_log.warning("action=face_verify_no_folder | phone=%s", phone)
        return False

    reference_images = sorted([
        os.path.join(user_dir, f)
        for f in os.listdir(user_dir)
        if f.startswith("reference_") and f.endswith(".jpg")
    ])

    if not reference_images:
        sec_log.warning("action=face_verify_no_refs | phone=%s", phone)
        return False

    try:
        for ref in reference_images:
            log.debug("Comparing with %s", os.path.basename(ref))
            result = DeepFace.verify(
                img1_path=ref,
                img2_path=image_path,
                model_name=MODEL_NAME,
                detector_backend=DETECTOR,
                distance_metric="cosine",
                enforce_detection=True,
                align=True,
                silent=True,
            )
            if result.get("verified", False):
                log.info("Face match found for %s", phone)
                return True

        sec_log.warning("action=face_verify_no_match | phone=%s", phone)
        return False

    except Exception as e:
        log.error("Face verification error for %s: %s", phone, e, exc_info=True)
        return False
