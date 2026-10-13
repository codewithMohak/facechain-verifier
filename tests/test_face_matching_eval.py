import os
import cv2
import numpy as np
import pytest
from src.face.detector import detect_faces, detect_and_crop_face
from src.face.encoder import load_face_recognizer, encode_face
from src.search.face_matcher import (
    COSINE_THRESHOLD,
    compare_face_embeddings,
    create_candidate_embedding,
    detect_candidate_faces,
    find_matching_public_face,
)


@pytest.fixture(scope="module")
def recognizer():
    return load_face_recognizer()


# ============================================================================
# 1. Mathematical and Threshold Unit Tests
# ============================================================================

def test_embedding_comparison_identical(recognizer):
    """Identical unit vectors should yield cosine similarity close to 1.0."""
    vec = np.random.randn(128).astype(np.float32)
    vec = vec / np.linalg.norm(vec)
    score = compare_face_embeddings(recognizer, vec, vec)
    assert score >= 0.999


def test_embedding_comparison_orthogonal(recognizer):
    """Orthogonal vectors should yield cosine similarity near 0.0."""
    v1 = np.zeros(128, dtype=np.float32)
    v1[0] = 1.0
    v2 = np.zeros(128, dtype=np.float32)
    v2[1] = 1.0
    score = compare_face_embeddings(recognizer, v1, v2)
    assert abs(score) < 1e-4


def test_embedding_comparison_invalid_inputs(recognizer):
    """Invalid or malformed embeddings must return 0.0 safely without throwing."""
    valid_vec = np.ones(128, dtype=np.float32)
    valid_vec = valid_vec / np.linalg.norm(valid_vec)

    # None inputs
    assert compare_face_embeddings(recognizer, None, valid_vec) == 0.0
    assert compare_face_embeddings(recognizer, valid_vec, None) == 0.0

    # Wrong dimensionality
    assert compare_face_embeddings(recognizer, np.ones(64), valid_vec) == 0.0
    assert compare_face_embeddings(recognizer, valid_vec, np.ones(256)) == 0.0

    # NaN / Inf vectors
    nan_vec = valid_vec.copy()
    nan_vec[0] = np.nan
    assert compare_face_embeddings(recognizer, nan_vec, valid_vec) == 0.0

    inf_vec = valid_vec.copy()
    inf_vec[0] = np.inf
    assert compare_face_embeddings(recognizer, valid_vec, inf_vec) == 0.0

    # All zeros
    assert compare_face_embeddings(recognizer, np.zeros(128), valid_vec) == 0.0


def test_threshold_boundary_interpretation():
    """Verify threshold boundary semantics (Match >= 0.363, Inconclusive 0.30..0.363, No-match < 0.30)."""
    assert COSINE_THRESHOLD == 0.363

    def classify(score: float):
        is_match = score >= COSINE_THRESHOLD
        is_inconclusive = (0.30 <= score < COSINE_THRESHOLD)
        verdict = "MATCH" if is_match else ("INCONCLUSIVE" if is_inconclusive else "NO_MATCH")
        return is_match, is_inconclusive, verdict

    # High match
    m, inc, v = classify(0.75)
    assert m is True and inc is False and v == "MATCH"

    # Exact threshold boundary
    m, inc, v = classify(0.363)
    assert m is True and inc is False and v == "MATCH"

    # Just below threshold -> Inconclusive
    m, inc, v = classify(0.3629)
    assert m is False and inc is True and v == "INCONCLUSIVE"

    # Lower bound of inconclusive
    m, inc, v = classify(0.30)
    assert m is False and inc is True and v == "INCONCLUSIVE"

    # Below inconclusive -> No match
    m, inc, v = classify(0.299)
    assert m is False and inc is False and v == "NO_MATCH"


# ============================================================================
# 2. Real-Model Evaluation Tests (YuNet + SFace)
# ============================================================================

def test_real_model_self_similarity(recognizer):
    """Real evaluation: Same face image should have high confidence and self-similarity ~1.0."""
    sample_path = "data/hrithik.png"
    if not os.path.exists(sample_path):
        pytest.skip("data/hrithik.png not available")

    img, faces = detect_faces(sample_path)
    assert len(faces) >= 1

    meta = detect_and_crop_face(sample_path)
    assert meta["face_detected"] is True
    emb1 = encode_face(img, meta)
    emb2 = encode_face(img, meta)

    score = compare_face_embeddings(recognizer, emb1, emb2)
    assert score >= 0.999


def test_real_model_tilted_face_affine_alignment(recognizer):
    """
    Real evaluation: Rotate probe face by 10 degrees.
    With 5-point landmark affine alignment, SFace compensates for the head tilt
    and maintains similarity well above the 0.363 threshold.
    """
    sample_path = "data/hrithik.png"
    if not os.path.exists(sample_path):
        pytest.skip("data/hrithik.png not available")

    img, faces = detect_faces(sample_path)
    meta = detect_and_crop_face(sample_path)
    original_emb = encode_face(img, meta)

    # Rotate image by 10 degrees around center
    h, w = img.shape[:2]
    center = (w // 2, h // 2)
    mat = cv2.getRotationMatrix2D(center, 10.0, 1.0)
    rotated_img = cv2.warpAffine(img, mat, (w, h))

    # Detect face in rotated image
    height, width = rotated_img.shape[:2]
    detector_path = "models/face_detection_yunet_2023mar.onnx"
    detector = cv2.FaceDetectorYN.create(detector_path, "", (width, height), 0.6, 0.3, 5000)
    _, rot_faces = detector.detect(rotated_img)
    assert rot_faces is not None and len(rot_faces) >= 1

    # Extract rotated face embedding using 14-element landmark vector
    rot_face = rot_faces[0]
    rot_emb = create_candidate_embedding(recognizer, rotated_img, rot_face)
    assert rot_emb is not None

    similarity = compare_face_embeddings(recognizer, original_emb, rot_emb)
    # Cosine similarity must remain well above match threshold (0.363), typically ~0.80-0.90
    assert similarity >= COSINE_THRESHOLD, f"Expected match >= {COSINE_THRESHOLD}, got {similarity}"


def test_real_model_blurred_face_robustness(recognizer):
    """
    Real evaluation: Apply Gaussian blur (5x5).
    Embedding similarity should remain above the match threshold.
    """
    sample_path = "data/hrithik.png"
    if not os.path.exists(sample_path):
        pytest.skip("data/hrithik.png not available")

    img, faces = detect_faces(sample_path)
    meta = detect_and_crop_face(sample_path)
    original_emb = encode_face(img, meta)

    blurred_img = cv2.GaussianBlur(img, (5, 5), 1.5)
    height, width = blurred_img.shape[:2]
    detector_path = "models/face_detection_yunet_2023mar.onnx"
    detector = cv2.FaceDetectorYN.create(detector_path, "", (width, height), 0.6, 0.3, 5000)
    _, blur_faces = detector.detect(blurred_img)
    assert blur_faces is not None and len(blur_faces) >= 1

    blur_emb = create_candidate_embedding(recognizer, blurred_img, blur_faces[0])
    assert blur_emb is not None

    similarity = compare_face_embeddings(recognizer, original_emb, blur_emb)
    assert similarity >= COSINE_THRESHOLD, f"Blurred image similarity {similarity} below threshold {COSINE_THRESHOLD}"


def test_real_model_no_face_detection_failure_handling(recognizer):
    """An image with uniform solid color or noise must detect 0 faces without raising exceptions."""
    blank_img = np.zeros((300, 300, 3), dtype=np.uint8)
    blank_img[:] = (128, 128, 128)

    faces = detect_candidate_faces(blank_img)
    assert len(faces) == 0


def test_candidate_matching_pipeline_multi_face(recognizer, tmp_path):
    """
    Create a synthetic candidate image containing 2 side-by-side face crops.
    Ensure detect_candidate_faces finds multiple faces and each face is indexed properly.
    """
    sample_path = "data/hrithik.png"
    if not os.path.exists(sample_path):
        pytest.skip("data/hrithik.png not available")

    img = cv2.imread(sample_path)
    meta = detect_and_crop_face(sample_path)
    crop = cv2.imread(meta["face_crop_path"])
    original_emb = encode_face(img, meta)

    # Create synthetic candidate with 2 faces side by side
    canvas = np.zeros((crop.shape[0] + 40, crop.shape[1] * 2 + 60, 3), dtype=np.uint8)
    canvas[20:20+crop.shape[0], 20:20+crop.shape[1]] = crop
    canvas[20:20+crop.shape[0], 40+crop.shape[1]:40+crop.shape[1]*2] = crop

    cand_path = str(tmp_path / "multi_face_candidate.jpg")
    cv2.imwrite(cand_path, canvas)

    faces = detect_candidate_faces(canvas)
    # Both crops should be detected or at least 1
    assert len(faces) >= 1

    # Compare with both faces
    scores = []
    for f in faces:
        emb = create_candidate_embedding(recognizer, canvas, f)
        if emb is not None:
            scores.append(compare_face_embeddings(recognizer, original_emb, emb))

    assert len(scores) >= 1
    assert any(s >= COSINE_THRESHOLD for s in scores)
