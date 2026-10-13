import io
import shutil
import pytest
from pathlib import Path
from PIL import Image
from src.forensics.acquisition import (
    validate_and_inspect_image,
    acquire_evidence,
    compute_sha256,
    AcquisitionError,
)


def create_test_image(format="JPEG", size=(100, 100), color=(255, 0, 0)) -> bytes:
    buf = io.BytesIO()
    img = Image.new("RGB", size, color=color)
    img.save(buf, format=format)
    return buf.getvalue()


def test_validate_valid_jpeg():
    raw = create_test_image("JPEG")
    res = validate_and_inspect_image(raw, "sample.jpg")
    assert res["format"] == "JPEG"
    assert res["width"] == 100
    assert res["height"] == 100
    assert res["mime_type"] == "image/jpeg"


def test_validate_valid_png():
    raw = create_test_image("PNG")
    res = validate_and_inspect_image(raw, "sample.png")
    assert res["format"] == "PNG"
    assert res["mime_type"] == "image/png"


def test_validate_valid_webp():
    raw = create_test_image("WEBP")
    res = validate_and_inspect_image(raw, "sample.webp")
    assert res["format"] == "WEBP"
    assert res["mime_type"] == "image/webp"


def test_validate_unsupported_extension():
    raw = create_test_image("JPEG")
    with pytest.raises(AcquisitionError, match="Unsupported file extension"):
        validate_and_inspect_image(raw, "sample.gif")


def test_validate_empty_file():
    with pytest.raises(AcquisitionError, match="empty"):
        validate_and_inspect_image(b"", "empty.jpg")


def test_validate_corrupted_file():
    corrupted = b"this is not a valid image payload"
    with pytest.raises(AcquisitionError, match="could not be decoded"):
        validate_and_inspect_image(corrupted, "bad.jpg")


def test_validate_size_exceeded():
    raw = create_test_image("JPEG")
    with pytest.raises(AcquisitionError, match="exceeds maximum"):
        validate_and_inspect_image(raw, "large.jpg", max_size_bytes=10)


def test_acquire_evidence(tmp_path):
    storage_root = str(tmp_path / "evidence")
    raw = create_test_image("JPEG", color=(0, 255, 0))
    expected_hash = compute_sha256(raw)

    result = acquire_evidence(
        file_bytes=raw,
        filename="input_photo.jpg",
        storage_root=storage_root,
    )

    assert result["evidence_id"].startswith("ev_")
    assert result["sha256"] == expected_hash
    assert result["original_filename"] == "input_photo.jpg"
    assert Path(result["original_path"]).exists()
    assert Path(result["working_path"]).exists()

    # Verify original file content matches byte-for-byte
    with open(result["original_path"], "rb") as f:
        assert f.read() == raw

    # Verify working copy content matches byte-for-byte
    with open(result["working_path"], "rb") as f:
        assert f.read() == raw
