import os
import cv2
import pytest
from src.face.detector import detect_faces, detect_and_crop_face
from src.face.encoder import encode_face


def test_face_detector_and_encoder_on_sample(tmp_path):
    sample_path = "data/hrithik.png"
    if not os.path.exists(sample_path):
        pytest.skip("Sample image data/hrithik.png not present.")

    # 1. Detection
    img, faces = detect_faces(sample_path)
    assert len(faces) >= 1

    # 2. Crop
    crop_dir = str(tmp_path / "crops")
    face_meta = detect_and_crop_face(sample_path, output_dir=crop_dir)
    assert face_meta["face_detected"] is True
    assert face_meta["confidence"] > 0.5
    assert os.path.exists(face_meta["face_crop_path"])

    # 3. Encoding
    embedding = encode_face(img, face_meta)
    assert embedding is not None
    assert embedding.shape[-1] == 128
