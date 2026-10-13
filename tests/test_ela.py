import pytest
from pathlib import Path
from PIL import Image
from src.forensics.ela import generate_ela


def test_jpeg_ela_generation(tmp_path):
    img_path = tmp_path / "test.jpg"
    ela_out_path = tmp_path / "ela_output.jpg"

    # Create a JPEG image with high-frequency noise / pattern
    img = Image.new("RGB", (128, 128), color=(200, 200, 200))
    # Draw some contrast
    for x in range(30, 90):
        for y in range(30, 90):
            img.putpixel((x, y), (10, 20, 30))
    img.save(img_path, format="JPEG", quality=95)

    res = generate_ela(str(img_path), str(ela_out_path), quality=90, scale=15)

    assert res["format"] == "JPEG"
    assert res["ela_applicable"] is True
    assert ela_out_path.exists()
    assert "statistics" in res
    assert res["statistics"]["max_error"] >= 0
    assert "encoding_properties" in res
    assert "disclaimer" in res


def test_png_lossless_handling(tmp_path):
    img_path = tmp_path / "test.png"
    ela_out_path = tmp_path / "ela_png.jpg"

    img = Image.new("RGBA", (100, 100), color=(100, 150, 200, 128))
    img.save(img_path, format="PNG")

    res = generate_ela(str(img_path), str(ela_out_path))

    assert res["format"] == "PNG"
    assert res["ela_applicable"] is False
    assert res["ela_path"] is None
    assert "lossless_analysis" in res
    assert res["lossless_analysis"]["alpha_properties"]["has_alpha_channel"] is True
    assert "methodology_note" in res
    assert "DEFLATE" in res["methodology_note"]


def test_webp_handling(tmp_path):
    img_path = tmp_path / "test.webp"
    ela_out_path = tmp_path / "ela_webp.jpg"

    img = Image.new("RGB", (80, 80), color=(50, 100, 150))
    img.save(img_path, format="WEBP")

    res = generate_ela(str(img_path), str(ela_out_path))

    assert res["format"] == "WEBP"
    assert res["ela_applicable"] is False
    assert "webp_properties" in res
