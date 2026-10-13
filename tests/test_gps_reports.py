import io
import os
import pytest
from PIL import Image
from fastapi.testclient import TestClient
from src.api.app import app
from src.forensics.metadata import parse_gps_coordinates, _convert_gps_to_decimal
from src.forensics.manifest import build_evidence_manifest
from src.forensics.report import (
    generate_forensic_report,
    generate_html_report,
    generate_pdf_report,
)


@pytest.fixture
def client():
    return TestClient(app)


# ============================================================================
# 1. GPS Extraction & Validation Unit Tests
# ============================================================================

def test_gps_dms_conversion_northern_eastern():
    """Valid DMS coordinates in Northern and Eastern hemispheres."""
    # 37° 46' 29.88" N -> 37 + 46/60 + 29.88/3600 = 37.774967
    raw_lat = ((37, 1), (46, 1), (2988, 100))
    dec_lat = _convert_gps_to_decimal(raw_lat, "N")
    assert dec_lat is not None
    assert round(dec_lat, 4) == 37.7750

    # 122° 25' 9.84" E -> 122.4194
    raw_lon = ((122, 1), (25, 1), (984, 100))
    dec_lon = _convert_gps_to_decimal(raw_lon, "E")
    assert dec_lon is not None
    assert round(dec_lon, 4) == 122.4194


def test_gps_dms_conversion_southern_western():
    """Southern ('S') and Western ('W') references must negate the decimal degrees."""
    # 33° 51' 35.9" S (Sydney) -> -33.859972
    raw_lat = ((33, 1), (51, 1), (359, 10))
    dec_lat = _convert_gps_to_decimal(raw_lat, "S")
    assert dec_lat is not None
    assert dec_lat < 0
    assert round(dec_lat, 2) == -33.86

    # 70° 40' 0.0" W (Santiago) -> -70.666667
    raw_lon = ((70, 1), (40, 1), (0, 1))
    dec_lon = _convert_gps_to_decimal(raw_lon, "W")
    assert dec_lon is not None
    assert dec_lon < 0
    assert round(dec_lon, 2) == -70.67


def test_gps_range_validation():
    """Coordinates outside valid geographic bounds must be marked 'invalid'."""
    # Latitude > 90
    invalid_gps = {
        "GPSLatitude": ((95, 1), (0, 1), (0, 1)),
        "GPSLatitudeRef": "N",
        "GPSLongitude": ((10, 1), (0, 1), (0, 1)),
        "GPSLongitudeRef": "E",
    }
    res = parse_gps_coordinates(invalid_gps)
    assert res["status"] == "invalid"
    assert res["available"] is False
    assert res["latitude"] is None

    # Longitude > 180
    invalid_lon = {
        "GPSLatitude": ((40, 1), (0, 1), (0, 1)),
        "GPSLatitudeRef": "N",
        "GPSLongitude": ((195, 1), (0, 1), (0, 1)),
        "GPSLongitudeRef": "E",
    }
    res_lon = parse_gps_coordinates(invalid_lon)
    assert res_lon["status"] == "invalid"
    assert res_lon["available"] is False


def test_gps_unavailable_and_malformed():
    """Missing or empty GPS tags return 'unavailable' status with clear notice."""
    empty_res = parse_gps_coordinates({})
    assert empty_res["status"] == "unavailable"
    assert empty_res["available"] is False
    assert empty_res["message"] == "GPS metadata unavailable"

    # Malformed tuple / divide by zero in denominator
    malformed = {
        "GPSLatitude": ((37, 0), (46, 1), (0, 1)),  # Denominator 0
        "GPSLatitudeRef": "N",
        "GPSLongitude": ((122, 1), (25, 1), (0, 1)),
        "GPSLongitudeRef": "W",
    }
    res_malformed = parse_gps_coordinates(malformed)
    # Handled without raising an exception
    assert res_malformed["status"] in ("invalid", "unavailable")


def test_gps_privacy_off_chain():
    """Manifest canonicalization must not include raw GPS latitude or longitude."""
    manifest_dict, m_hash = build_evidence_manifest(
        evidence_id="ev_test123",
        original_file_hash="a" * 64,
        acquisition_meta={"original_filename": "test.jpg", "file_size_bytes": 1000},
        analysis_findings={"metadata": {"gps_available": True}},
        timestamps={"acquired_at": "2026-10-13T12:00:00Z", "analyzed_at": "2026-10-13T12:01:00Z"},
    )
    # Manifest must record analysis hash and acquisition, never precise GPS coordinates
    manifest_str = str(manifest_dict)
    assert "latitude" not in manifest_str
    assert "longitude" not in manifest_str


# ============================================================================
# 2. Forensic Report Generation (HTML & PDF)
# ============================================================================

def create_sample_report_dict(with_gps: bool = True, xss_payload: bool = False):
    """Build a structured report dictionary matching the forensic report model."""
    filename = "<script>alert('pwned')</script>.jpg" if xss_payload else "evidence_sample.jpg"
    cam_make = "<img src=x onerror=alert(1)>" if xss_payload else "Nikon"

    gps_dict = {
        "status": "valid" if with_gps else "unavailable",
        "available": with_gps,
        "latitude": 37.774929 if with_gps else None,
        "longitude": -122.419416 if with_gps else None,
        "latitude_ref": "N",
        "longitude_ref": "W",
        "altitude": 15.0 if with_gps else None,
        "map_url": "https://www.google.com/maps?q=37.774929,-122.419416" if with_gps else None,
        "source_notice": "Embedded metadata only",
    }

    return {
        "evidence": {
            "evidence_id": "ev_test_12345",
            "original_file_hash_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            "file_properties": {
                "filename": filename,
                "format": "JPEG",
                "mime_type": "image/jpeg",
                "file_size_bytes": 10240,
                "width": 800,
                "height": 600,
            },
        },
        "generated_at_utc": "2026-10-13T12:00:00Z",
        "metadata_analysis": {
            "camera": {"make": cam_make, "model": "D850", "lens_model": "24-70mm", "software": "v1.0"},
            "timestamps": {"original": "2026-10-10 10:00:00", "modified": "2026-10-10 10:00:00"},
            "capture_parameters": {"iso": 100, "exposure_time": "1/250", "f_number": 2.8},
            "gps": gps_dict,
            "missing_metadata": [],
            "suspicious_indicators": [],
        },
        "image_manipulation_analysis": {
            "ela_applicable": True,
            "statistics": {"mean_error": 4.2, "max_error": 68.0, "high_contrast_percentage": 0.15},
            "parameters": {"recompression_quality": 90},
            "observable_indicators": ["Uniform JPEG quantization grid"],
        },
        "face_analysis": {
            "face_detected": True,
            "face_count": 1,
            "confidence": 0.985,
            "embedding_model": "OpenCV SFace 128-D",
        },
        "web_search_analysis": {
            "status": "Completed",
            "candidates_found": 1,
            "best_match": {"title": "Sample Public Profile", "url": "https://example.com/photo.jpg"},
        },
        "findings_summary": [
            {"type": "METADATA_INTEGRITY", "level": "low", "summary": "Camera metadata intact", "details": "Nikon D850 tags present"}
        ],
        "limitations_and_disclaimers": [
            "Forensic analysis is probabilistic and does not establish court admissibility automatically."
        ],
        "integrity": {
            "manifest_hash": "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
            "verification_status": {
                "status": "VERIFIED",
                "file_hash_match": True,
                "manifest_hash_match": True,
            },
            "canonical_manifest": {"version": "1.0", "tool_versions": {"facechain_forensics": "1.0.0", "opencv": "5.0.0", "pillow": "12.3.0", "python": "3.13"}},
        },
        "blockchain_anchoring": {
            "network": "Ethereum Sepolia (ChainID: 11155111)",
            "status": "confirmed",
            "transaction_hash": "0x2bfe4e03287a1234654bc2cce3119b9c75c45067f24d15000000000000000000",
            "block_number": 7500123,
            "anchored_hash": "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
        },
    }


def test_html_report_generation_and_xss_protection():
    """HTML report should render all sections and escape malicious XSS injection payloads."""
    report_data = create_sample_report_dict(with_gps=True, xss_payload=True)
    html_output = generate_html_report(report_data)

    assert "<!DOCTYPE html>" in html_output
    assert "ev_test_12345" in html_output
    assert "Google Maps" in html_output

    # XSS Protection check: raw scripts or img error triggers must NOT appear unescaped
    assert "<script>alert('pwned')</script>" not in html_output
    assert "&lt;script&gt;alert(" in html_output
    assert "<img src=x onerror=alert(1)>" not in html_output
    assert "&lt;img src=x onerror=alert(1)&gt;" in html_output


def test_html_report_gps_unavailable_mode():
    """HTML report must gracefully present unavailable GPS state."""
    report_data = create_sample_report_dict(with_gps=False)
    html_output = generate_html_report(report_data)

    assert "GPS metadata unavailable" in html_output
    assert "No embedded GPS tags present in image file" in html_output


def test_pdf_report_generation_valid_bytes():
    """PDF report must generate valid PDF bytes starting with %PDF."""
    report_data = create_sample_report_dict(with_gps=True)
    pdf_bytes = generate_pdf_report(report_data)

    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 1000
    assert pdf_bytes.startswith(b"%PDF")


def test_pdf_report_generation_no_gps_or_optional_sections():
    """PDF generator must handle missing/disabled optional sections without error."""
    report_data = create_sample_report_dict(with_gps=False)
    report_data["face_analysis"] = None
    report_data["web_search_analysis"] = None
    report_data["blockchain_anchoring"] = {"status": "unanchored"}

    pdf_bytes = generate_pdf_report(report_data)
    assert isinstance(pdf_bytes, bytes)
    assert pdf_bytes.startswith(b"%PDF")


# ============================================================================
# 3. API Multi-Format Report Endpoints
# ============================================================================

def test_api_report_format_negotiation(client):
    """Verify GET /api/v1/evidence/{id}/report format query parameter."""
    # 1. Upload sample evidence
    buf = io.BytesIO()
    img = Image.new("RGB", (64, 64), color=(100, 150, 200))
    img.save(buf, format="JPEG")
    upload_res = client.post(
        "/api/v1/evidence",
        files={"file": ("report_test.jpg", buf.getvalue(), "image/jpeg")},
    )
    assert upload_res.status_code == 201
    evidence_id = upload_res.json()["id"]

    # 2. Analyze
    client.post(
        f"/api/v1/evidence/{evidence_id}/analyze",
        json={"include_face_analysis": False, "include_web_search": False, "anchor_blockchain": False},
    )

    # 3. Test JSON format (default)
    res_default = client.get(f"/api/v1/evidence/{evidence_id}/report")
    assert res_default.status_code == 200
    assert "application/json" in res_default.headers["content-type"]
    assert res_default.json()["evidence"]["evidence_id"] == evidence_id

    # 4. Test explicit format=json
    res_json = client.get(f"/api/v1/evidence/{evidence_id}/report?format=json")
    assert res_json.status_code == 200
    assert "application/json" in res_json.headers["content-type"]

    # 5. Test format=html
    res_html = client.get(f"/api/v1/evidence/{evidence_id}/report?format=html")
    assert res_html.status_code == 200
    assert "text/html" in res_html.headers["content-type"]
    assert "<!DOCTYPE html>" in res_html.text
    assert evidence_id in res_html.text

    # 6. Test format=pdf
    res_pdf = client.get(f"/api/v1/evidence/{evidence_id}/report?format=pdf")
    assert res_pdf.status_code == 200
    assert "application/pdf" in res_pdf.headers["content-type"]
    assert res_pdf.content.startswith(b"%PDF")

    # 7. Test download headers
    res_pdf_dl = client.get(f"/api/v1/evidence/{evidence_id}/report?format=pdf&download=true")
    assert res_pdf_dl.status_code == 200
    assert "attachment" in res_pdf_dl.headers.get("content-disposition", "")
    assert f"facechain_forensics_report_{evidence_id}.pdf" in res_pdf_dl.headers.get("content-disposition", "")

    # 8. Test unsupported format error handling
    res_bad = client.get(f"/api/v1/evidence/{evidence_id}/report?format=docx")
    assert res_bad.status_code == 400
    assert "unsupported report format" in res_bad.json()["detail"].lower()
