import io
import pytest
from pathlib import Path
from PIL import Image, ExifTags
from src.forensics.metadata import extract_metadata


def test_extract_metadata_without_exif(tmp_path):
    img_path = tmp_path / "plain.jpg"
    img = Image.new("RGB", (200, 150), color=(100, 150, 200))
    img.save(img_path, format="JPEG")

    meta = extract_metadata(str(img_path))
    assert meta["format"] == "JPEG"
    assert meta["width"] == 200
    assert meta["height"] == 150
    assert meta["has_exif"] is False
    assert len(meta["missing_metadata"]) >= 2
    assert "Forensic Notice" in meta["disclaimer"]


def test_extract_metadata_with_software_suspicion(tmp_path):
    img_path = tmp_path / "photoshop_edited.jpg"
    img = Image.new("RGB", (300, 200), color=(50, 50, 50))

    # Add EXIF with Photoshop Software tag
    exif = img.getexif()
    # Software tag ID is 305
    exif[305] = "Adobe Photoshop 2024 (Windows)"
    exif[271] = "Canon"  # Make
    exif[272] = "Canon EOS R5"  # Model
    img.save(img_path, format="JPEG", exif=exif)

    meta = extract_metadata(str(img_path))
    assert meta["camera"]["make"] == "Canon"
    assert meta["camera"]["model"] == "Canon EOS R5"
    assert meta["camera"]["software"] == "Adobe Photoshop 2024 (Windows)"

    # Check suspicious indicator detection
    indicators = meta["suspicious_indicators"]
    assert len(indicators) >= 1
    assert any("Editing Software" in ind["indicator"] for ind in indicators)


def test_extract_metadata_nonexistent_file():
    with pytest.raises(FileNotFoundError):
        extract_metadata("does_not_exist.jpg")
