import os
import shutil
from deepface import DeepFace

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FACES_DIR = os.path.join(BASE_DIR, "bot", "registered_faces")


MODEL_NAME = "SFace"
DETECTOR = "opencv"

print("[INIT] Loading face recognition model...")
DeepFace.build_model(MODEL_NAME)
print("[INIT] Model loaded.")

os.makedirs(FACES_DIR, exist_ok=True)



def register_face(phone, image_path):

    print(f"[FACE REGISTER] Registering face for user {phone}...")

    user_dir = os.path.join(FACES_DIR, str(phone))
    os.makedirs(user_dir, exist_ok=True)

    try:

        existing = sorted([
            f for f in os.listdir(user_dir)
            if f.startswith("reference_") and f.endswith(".jpg")
        ])

        next_index = len(existing) + 1

        if next_index > 3:
            print(f"[FACE REGISTER] User {phone} already has 3 reference images")
            return False

        reference_path = os.path.join(
            user_dir,
            f"reference_{next_index}.jpg"
        )

        shutil.copy(image_path, reference_path)

        print(f"[FACE REGISTER] Validating reference image {next_index}...")

        faces = DeepFace.extract_faces(
            img_path=reference_path,
            detector_backend=DETECTOR,
            enforce_detection=True,
            align=True   # improvement
        )

        if len(faces) != 1:
            os.remove(reference_path)
            print(f"[FACE REGISTER] Invalid face count ({len(faces)}) ❌")
            return False

        print(f"[FACE REGISTER] Reference image {next_index} saved ✅")

        return True

    except Exception as e:

        print(f"[FACE REGISTER] Error: {e}")

        if 'reference_path' in locals() and os.path.exists(reference_path):
            os.remove(reference_path)

        return False


def verify_face(phone, image_path):

    print(f"[FACE VERIFY] Verifying face for user {phone}...")

    user_dir = os.path.join(FACES_DIR, str(phone))

    if not os.path.exists(user_dir):
        print("[FACE VERIFY] User folder not found ❌")
        return False

    reference_images = sorted([
        os.path.join(user_dir, f)
        for f in os.listdir(user_dir)
        if f.startswith("reference_") and f.endswith(".jpg")
    ])

    if not reference_images:
        print("[FACE VERIFY] No reference images found ❌")
        return False

    try:

        for ref in reference_images:

            print(f"[FACE VERIFY] Comparing with {os.path.basename(ref)}...")

            result = DeepFace.verify(
                img1_path=ref,
                img2_path=image_path,

                model_name=MODEL_NAME,
                detector_backend=DETECTOR,

                distance_metric="cosine",

                enforce_detection=True,
                align=True,      # improvement
                silent=True
            )

            if result.get("verified", False):

                print(f"[FACE VERIFY] Match found ✅")
                return True

        print("[FACE VERIFY] No match found ❌")

        return False

    except Exception as e:

        print(f"[FACE VERIFY] Error: {e}")

        return False
