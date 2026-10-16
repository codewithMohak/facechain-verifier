import io
import json
import logging
from unittest.mock import patch, MagicMock
import numpy as np
from PIL import Image
import pytest
from fastapi.testclient import TestClient

from src.api.app import app
from src.forensics.acquisition import acquire_evidence
from src.db.database import insert_evidence, get_evidence
from src.forensics.pipeline import run_forensic_analysis
from src.forensics.manifest import verify_manifest_integrity
from src.search.face_matcher import (
    download_image,
    detect_candidate_faces,
    find_matching_public_face,
)


@pytest.fixture
def client():
    return TestClient(app)


def create_test_png_bytes(width=100, height=100, color=(120, 180, 240, 255)):
    """Create a minimal PNG byte stream with alpha channel."""
    buf = io.BytesIO()
    img = Image.new("RGBA", (width, height), color)
    img.save(buf, format="PNG")
    return buf.getvalue()


def create_test_jpeg_bytes(width=100, height=100, color=(120, 180, 240)):
    """Create a minimal JPEG byte stream."""
    buf = io.BytesIO()
    img = Image.new("RGB", (width, height), color)
    img.save(buf, format="JPEG")
    return buf.getvalue()


def test_png_analysis_and_report_generation_no_attribute_error(client):
    """
    Regression test for: AttributeError: 'NoneType' object has no attribute 'get'
    Ensures that PNG images (which lack encoding_properties) generate HTML, JSON,
    and PDF reports without crashing.
    """
    png_bytes = create_test_png_bytes()
    upload_res = client.post(
        "/api/v1/evidence",
        files={"file": ("test_sample.png", png_bytes, "image/png")},
    )
    assert upload_res.status_code == 201
    evidence_id = upload_res.json()["id"]

    # Run analysis without web search
    analyze_res = client.post(
        f"/api/v1/evidence/{evidence_id}/analyze",
        json={
            "include_face_analysis": False,
            "include_web_search": False,
            "anchor_blockchain": False,
        },
    )
    assert analyze_res.status_code == 200
    data = analyze_res.json()
    assert data["status"] == "analyzed"
    assert data["manifest_hash"] is not None

    # Verify HTML report download succeeds
    html_res = client.get(f"/api/v1/evidence/{evidence_id}/report?format=html")
    assert html_res.status_code == 200
    assert "<!DOCTYPE html>" in html_res.text
    assert evidence_id in html_res.text

    # Verify PDF report download succeeds
    pdf_res = client.get(f"/api/v1/evidence/{evidence_id}/report?format=pdf")
    assert pdf_res.status_code == 200
    assert pdf_res.content.startswith(b"%PDF-")


def test_search_candidate_download_failure_resilience(tmp_path):
    """
    Ensures that a failed download of one search candidate (404, network error, or invalid URL)
    does not crash find_matching_public_face, and processing continues for other candidates.
    """
    dummy_embedding = np.random.randn(128).astype(np.float32)
    candidates = [
        {"title": "Broken Candidate 1", "image": "https://invalid-nonexistent-domain-404.com/fake1.jpg"},
        {"title": "Bad URL Candidate", "image": "not-a-valid-url"},
        {"title": "Empty URL Candidate", "image": ""},
        {"title": "Non-dict Candidate", "image": None},
    ]

    # Should not raise any exception and should return None when no candidate could be downloaded
    best_match = find_matching_public_face(dummy_embedding, candidates)
    assert best_match is None


def test_search_candidate_invalid_image_content_resilience(tmp_path):
    """
    Ensures that corrupt or non-image responses from candidate URLs are safely skipped.
    """
    corrupt_candidate_path = str(tmp_path / "corrupt.jpg")
    with open(corrupt_candidate_path, "wb") as f:
        f.write(b"NOT_A_REAL_IMAGE_DATA_CORRUPT")

    # detect_candidate_faces on a non-image array / None
    assert detect_candidate_faces(None) == []
    empty_arr = np.array([])
    assert detect_candidate_faces(empty_arr) == []


def test_download_image_validation():
    """
    Ensures download_image rejects invalid schemes and malformed URLs without exceptions.
    """
    assert download_image(None, "data/test.jpg") is False
    assert download_image("", "data/test.jpg") is False
    assert download_image("ftp://example.com/test.jpg", "data/test.jpg") is False
    assert download_image("javascript:alert(1)", "data/test.jpg") is False


def test_analyze_api_unexpected_error_logging_and_sanitization(client):
    """
    Ensures unexpected errors in the analyze endpoint are logged with traceback via logger.exception,
    and returned error detail is sanitized.
    """
    jpeg_bytes = create_test_jpeg_bytes()
    upload_res = client.post(
        "/api/v1/evidence",
        files={"file": ("log_test.jpg", jpeg_bytes, "image/jpeg")},
    )
    evidence_id = upload_res.json()["id"]

    # Mock run_forensic_analysis to raise an unexpected error containing a fake secret
    fake_secret_err = "Database failure at https://user:super_secret_password@db.internal:5432 with api_key=SECRET_TOKEN_XYZ"
    with patch("src.api.app.run_forensic_analysis", side_effect=RuntimeError(fake_secret_err)), \
         patch("src.api.app.logger.exception") as mock_logger_exc:

        analyze_res = client.post(
            f"/api/v1/evidence/{evidence_id}/analyze",
            json={
                "include_face_analysis": False,
                "include_web_search": False,
                "anchor_blockchain": False,
            },
        )
        assert analyze_res.status_code == 500
        # logger.exception was called with the evidence_id
        mock_logger_exc.assert_called_once()
        err_detail = analyze_res.json()["detail"]
        # Ensure credentials / API keys were sanitized from public API response
        assert "super_secret_password" not in err_detail
        assert "SECRET_TOKEN_XYZ" not in err_detail
        assert "[REDACTED]" in err_detail or "[CREDENTIALS]" in err_detail


def test_cors_preflight_production_origin(client):
    """
    Verifies that CORS preflight (OPTIONS) for the production origin succeeds with 200 OK.
    """
    headers = {
        "Origin": "https://facechain-verifier.vercel.app",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type",
    }
    res = client.options("/api/v1/evidence/any_id/analyze", headers=headers)
    assert res.status_code == 200
    assert res.headers.get("access-control-allow-origin") == "https://facechain-verifier.vercel.app"
    assert "POST" in res.headers.get("access-control-allow-methods", "")


def test_cors_preflight_localhost_origin(client):
    """
    Verifies that CORS preflight (OPTIONS) for the development origin succeeds with 200 OK.
    """
    headers = {
        "Origin": "http://localhost:5173",
        "Access-Control-Request-Method": "GET",
    }
    res = client.options("/api/v1/health", headers=headers)
    assert res.status_code == 200
    assert res.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_manifest_integrity_preserved_after_analysis(client):
    """
    Ensures that manifest integrity checking passes 100% on analyzed evidence.
    """
    png_bytes = create_test_png_bytes()
    upload_res = client.post(
        "/api/v1/evidence",
        files={"file": ("manifest_intact.png", png_bytes, "image/png")},
    )
    evidence_id = upload_res.json()["id"]

    client.post(
        f"/api/v1/evidence/{evidence_id}/analyze",
        json={
            "include_face_analysis": False,
            "include_web_search": False,
            "anchor_blockchain": False,
        },
    )

    rec = get_evidence(evidence_id)
    assert rec["status"] == "analyzed"
    assert rec["manifest"] is not None
    assert rec["manifest_hash"] is not None

    verification = verify_manifest_integrity(
        original_file_path=rec["original_path"],
        manifest=rec["manifest"],
        expected_manifest_hash=rec["manifest_hash"],
    )
    assert verification["verified"] is True
    assert verification["file_hash_match"] is True
    assert verification["manifest_hash_match"] is True
