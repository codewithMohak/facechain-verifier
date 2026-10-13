import os
import cv2
import numpy as np


MODEL_PATH = (
    "models/"
    "face_recognition_sface_2021dec.onnx"
)


def load_face_recognizer():
    """
    Load the OpenCV SFace recognition model.
    """

    if not os.path.exists(MODEL_PATH):
        raise FileNotFoundError(
            f"SFace model not found: {MODEL_PATH}"
        )

    recognizer = cv2.FaceRecognizerSF.create(
        MODEL_PATH,
        ""
    )

    return recognizer


def encode_face(
    image,
    face_data
):
    """
    Align the detected face and generate
    an SFace embedding.
    """

    recognizer = load_face_recognizer()

    if "raw_face" in face_data and face_data["raw_face"] is not None:
        face_box = np.asarray(face_data["raw_face"][:14], dtype=np.float32)
    elif "landmarks" in face_data and "bounding_box" in face_data:
        bb = face_data["bounding_box"]
        lm = face_data["landmarks"]
        face_box = np.array(
            [
                bb["x"],
                bb["y"],
                bb["width"],
                bb["height"],
                lm["right_eye"][0],
                lm["right_eye"][1],
                lm["left_eye"][0],
                lm["left_eye"][1],
                lm["nose"][0],
                lm["nose"][1],
                lm["right_mouth"][0],
                lm["right_mouth"][1],
                lm["left_mouth"][0],
                lm["left_mouth"][1],
            ],
            dtype=np.float32,
        )
    else:
        bounding_box = face_data.get("bounding_box", {})
        face_box = np.array(
            [
                bounding_box.get("x", 0),
                bounding_box.get("y", 0),
                bounding_box.get("width", 0),
                bounding_box.get("height", 0),
            ],
            dtype=np.float32,
        )

    # Align face using SFace.
    aligned_face = recognizer.alignCrop(image, face_box)

    # Generate the face embedding.
    embedding = (
        recognizer.feature(
            aligned_face
        )
    )

    return embedding


def save_embedding(
    embedding,
    output_path="data/face_embedding.npy"
):
    """
    Save the generated face embedding.
    """

    os.makedirs(
        os.path.dirname(output_path) or ".",
        exist_ok=True
    )

    np.save(
        output_path,
        embedding
    )

    return output_path