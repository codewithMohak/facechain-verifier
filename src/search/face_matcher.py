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
    Align a candidate face and generate
    an SFace embedding.
    """

    x = int(face[0])
    y = int(face[1])
    width = int(face[2])
    height = int(face[3])

    face_box = np.array(
        [
            x,
            y,
            width,
            height
        ],
        dtype=np.float32
    )

    try:

        aligned_face = (
            recognizer.alignCrop(
                image,
                face_box
            )
        )

        embedding = (
            recognizer.feature(
                aligned_face
            )
        )

        return embedding

    except cv2.error:
        return None


def compare_face_embeddings(
    recognizer,
    source_embedding,
    candidate_embedding
):
    """
    Compare two SFace embeddings using
    cosine similarity.
    """

    score = recognizer.match(
        source_embedding,
        candidate_embedding,
        cv2.FaceRecognizerSF_FR_COSINE
    )

    return float(score)


def find_matching_public_face(
    source_embedding,
    candidates
):
    """
    Download candidate public images,
    detect faces, generate SFace embeddings,
    and compare them against the source face.

    Returns the strongest verified candidate.
    """

    os.makedirs(
        "data/candidates",
        exist_ok=True
    )

    recognizer = (
        load_face_recognizer()
    )

    best_match = None

    candidate_number = 0

    for candidate in candidates:

        image_url = candidate.get(
            "image"
        )

        if not image_url:
            continue

        candidate_number += 1

        candidate_path = os.path.join(
            "data",
            "candidates",
            f"candidate_{candidate_number}.jpg"
        )

        print(
            f"\nChecking candidate "
            f"{candidate_number}..."
        )

        downloaded = download_image(
            image_url,
            candidate_path
        )

        if not downloaded:

            print(
                "[!] Could not download "
                "candidate image."
            )

            continue

        candidate_image = cv2.imread(
            candidate_path
        )

        if candidate_image is None:

            print(
                "[!] Candidate image could "
                "not be loaded."
            )

            continue

        faces = detect_candidate_faces(
            candidate_image
        )

        if len(faces) == 0:

            print(
                "[!] No face detected "
                "in candidate."
            )

            continue

        print(
            f"[✓] Candidate contains "
            f"{len(faces)} face(s)."
        )

        for face in faces:

            candidate_embedding = (
                create_candidate_embedding(
                    recognizer,
                    candidate_image,
                    face
                )
            )

            if candidate_embedding is None:
                continue

            similarity = (
                compare_face_embeddings(
                    recognizer,
                    source_embedding,
                    candidate_embedding
                )
            )

            print(
                f"    Face similarity: "
                f"{similarity:.4f}"
            )

            if (
                best_match is None
                or similarity >
                best_match["similarity"]
            ):

                best_match = {

                    "similarity":
                        similarity,

                    "is_match":
                        similarity >=
                        COSINE_THRESHOLD,

                    "title":
                        candidate.get(
                            "title"
                        ),

                    "source":
                        candidate.get(
                            "source"
                        ),

                    "url":
                        candidate.get(
                            "link"
                        ),

                    "image":
                        image_url,

                    "candidate_image":
                        candidate_path
                }

    return best_match