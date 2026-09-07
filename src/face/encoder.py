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

    bounding_box = face_data[
        "bounding_box"
    ]

    landmarks = face_data[
        "landmarks"
    ]

    # YuNet bounding box.
    x = bounding_box["x"]
    y = bounding_box["y"]
    width = bounding_box["width"]
    height = bounding_box["height"]

    face_box = np.array(
        [
            x,
            y,
            width,
            height
        ],
        dtype=np.float32
    )

    # Align face using SFace.
    aligned_face = (
        recognizer.alignCrop(
            image,
            face_box
        )
    )

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