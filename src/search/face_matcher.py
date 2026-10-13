import os
import cv2
import requests
import numpy as np

from src.face.encoder import load_face_recognizer


# OpenCV SFace cosine similarity threshold.
# Higher means stricter matching.
COSINE_THRESHOLD = 0.363


def download_image(
    image_url,
    output_path
):
    """
    Download a candidate image from a public URL.
    """

    try:
        response = requests.get(
            image_url,
            timeout=15,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 "
                    "(Windows NT 10.0; Win64; x64)"
                )
            }
        )

        if not response.ok:
            return False

        content_type = response.headers.get(
            "Content-Type",
            ""
        )

        if "image" not in content_type:
            return False

        with open(
            output_path,
            "wb"
        ) as image_file:

            image_file.write(
                response.content
            )

        return True

    except requests.RequestException:
        return False


def detect_candidate_faces(
    image
):
    """
    Detect faces in a candidate image
    using the same YuNet detector.
    """

    detector_path = (
        "models/"
        "face_detection_yunet_2023mar.onnx"
    )

    if not os.path.exists(
        detector_path
    ):
        raise FileNotFoundError(
            f"YuNet model not found: "
            f"{detector_path}"
        )

    height, width = image.shape[:2]

    detector = cv2.FaceDetectorYN.create(
        detector_path,
        "",
        (width, height),
        0.6,
        0.3,
        5000
    )

    _, faces = detector.detect(
        image
    )

    if faces is None:
        return []

    return faces


def create_candidate_embedding(
    recognizer,
    image,
    face
):
    """
    Align a candidate face with full 5-point facial landmarks
    and generate an SFace embedding.
    """
    if isinstance(face, np.ndarray) and face.size >= 14:
        face_box = face[:14].astype(np.float32)
    elif isinstance(face, (list, tuple)) and len(face) >= 14:
        face_box = np.array(face[:14], dtype=np.float32)
    elif isinstance(face, dict) and "landmarks" in face and "bounding_box" in face:
        bb = face["bounding_box"]
        lm = face["landmarks"]
        face_box = np.array(
            [
                bb["x"], bb["y"], bb["width"], bb["height"],
                lm["right_eye"][0], lm["right_eye"][1],
                lm["left_eye"][0], lm["left_eye"][1],
                lm["nose"][0], lm["nose"][1],
                lm["right_mouth"][0], lm["right_mouth"][1],
                lm["left_mouth"][0], lm["left_mouth"][1],
            ],
            dtype=np.float32,
        )
    else:
        # Fallback to bounding box if landmarks are unavailable
        x = int(face[0])
        y = int(face[1])
        width = int(face[2])
        height = int(face[3])
        face_box = np.array([x, y, width, height], dtype=np.float32)

    try:
        aligned_face = recognizer.alignCrop(image, face_box)
        embedding = recognizer.feature(aligned_face)
        return embedding
    except cv2.error:
        return None


def compare_face_embeddings(
    recognizer,
    source_embedding,
    candidate_embedding
):
    """
    Compare two SFace embeddings using cosine similarity.
    Returns cosine similarity float in [-1.0, 1.0].
    """
    if source_embedding is None or candidate_embedding is None:
        return 0.0

    src_arr = np.asarray(source_embedding, dtype=np.float32)
    cand_arr = np.asarray(candidate_embedding, dtype=np.float32)

    if src_arr.size != 128 or cand_arr.size != 128:
        return 0.0

    if not np.all(np.isfinite(src_arr)) or not np.all(np.isfinite(cand_arr)):
        return 0.0

    if np.linalg.norm(src_arr) == 0 or np.linalg.norm(cand_arr) == 0:
        return 0.0

    src_2d = src_arr.reshape(1, 128)
    cand_2d = cand_arr.reshape(1, 128)

    score = recognizer.match(
        src_2d,
        cand_2d,
        cv2.FaceRecognizerSF_FR_COSINE
    )

    return float(score)


def find_matching_public_face(
    source_embedding,
    candidates
):
    """
    Download candidate public images, detect faces, generate SFace embeddings,
    and compare them against the source face.

    Returns the strongest candidate match with rich forensic context.
    """
    os.makedirs(
        "data/candidates",
        exist_ok=True
    )

    recognizer = load_face_recognizer()

    best_match = None
    candidate_number = 0

    for candidate in candidates:
        image_url = candidate.get("image")
        if not image_url:
            continue

        candidate_number += 1
        candidate_path = os.path.join(
            "data",
            "candidates",
            f"candidate_{candidate_number}.jpg"
        )

        print(
            f"\nChecking candidate {candidate_number}..."
        )

        downloaded = download_image(
            image_url,
            candidate_path
        )

        if not downloaded:
            print(
                "[!] Could not download candidate image."
            )
            continue

        candidate_image = cv2.imread(candidate_path)
        if candidate_image is None:
            print(
                "[!] Candidate image could not be loaded."
            )
            continue

        faces = detect_candidate_faces(candidate_image)
        if len(faces) == 0:
            print(
                "[!] No face detected in candidate."
            )
            continue

        print(
            f"[OK] Candidate contains {len(faces)} face(s)."
        )

        for face_idx, face in enumerate(faces):
            candidate_embedding = create_candidate_embedding(
                recognizer,
                candidate_image,
                face
            )

            if candidate_embedding is None:
                continue

            similarity = compare_face_embeddings(
                recognizer,
                source_embedding,
                candidate_embedding
            )

            print(
                f"    Face {face_idx + 1}/{len(faces)} similarity: {similarity:.4f}"
            )

            if best_match is None or similarity > best_match["similarity"]:
                is_match = similarity >= COSINE_THRESHOLD
                is_inconclusive = (0.30 <= similarity < COSINE_THRESHOLD)

                best_match = {
                    "similarity": similarity,
                    "is_match": is_match,
                    "is_inconclusive": is_inconclusive,
                    "match_verdict": (
                        "MATCH" if is_match else ("INCONCLUSIVE" if is_inconclusive else "NO_MATCH")
                    ),
                    "title": candidate.get("title"),
                    "source": candidate.get("source"),
                    "url": candidate.get("url") or candidate.get("link"),
                    "image": image_url,
                    "candidate_image": candidate_path,
                    "candidate_face_index": face_idx,
                    "candidate_face_count": len(faces),
                    "candidate_bounding_box": {
                        "x": int(face[0]),
                        "y": int(face[1]),
                        "width": int(face[2]),
                        "height": int(face[3]),
                    },
                    "candidate_confidence": float(face[14]) if len(face) > 14 else 1.0,
                }

    return best_match