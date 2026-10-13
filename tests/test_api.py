import io
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from src.api.app import app


@pytest.fixture
def client():
    return TestClient(app)


def create_jpeg_bytes() -> bytes:
    buf = io.BytesIO()
    img = Image.new("RGB", (64, 64), color=(200, 100, 50))
    img.save(buf, format="JPEG")
    return buf.getvalue()


def test_health_check(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "blockchain" in data
    assert "models" in data


def test_upload_invalid_file_rejected(client):
    # Upload text file claiming to be jpg
    response = client.post(
        "/api/v1/evidence",
        files={"file": ("fake.jpg", b"not a real jpeg", "image/jpeg")},
    )
    assert response.status_code == 400
    assert "decoded" in response.json()["detail"].lower()


def test_upload_and_forensic_pipeline(client):
    # 1. Upload valid JPEG
    jpeg_bytes = create_jpeg_bytes()
    upload_res = client.post(
        "/api/v1/evidence",
        files={"file": ("evidence_test.jpg", jpeg_bytes, "image/jpeg")},
    )
    assert upload_res.status_code == 201
    evidence = upload_res.json()
    evidence_id = evidence["id"]
    assert evidence["original_hash"] is not None
    assert evidence["status"] == "acquired"

    # 2. Get by ID
    get_res = client.get(f"/api/v1/evidence/{evidence_id}")
    assert get_res.status_code == 200
    assert get_res.json()["id"] == evidence_id

    # 3. List
    list_res = client.get("/api/v1/evidence")
    assert list_res.status_code == 200
    assert any(item["id"] == evidence_id for item in list_res.json())

    # 4. Analyze without web search (local analysis only)
    analyze_res = client.post(
        f"/api/v1/evidence/{evidence_id}/analyze",
        json={
            "include_face_analysis": False,
            "include_web_search": False,
            "anchor_blockchain": False,
        },
    )
    assert analyze_res.status_code == 200
    analyzed_data = analyze_res.json()
    assert analyzed_data["status"] == "analyzed"
    assert analyzed_data["manifest_hash"] is not None
    assert analyzed_data["manifest"] is not None
    assert analyzed_data["image_analysis"]["ela_applicable"] is True

    # 5. Get Report JSON
    report_res = client.get(f"/api/v1/evidence/{evidence_id}/report")
    assert report_res.status_code == 200
    report_json = report_res.json()
    assert report_json["evidence"]["evidence_id"] == evidence_id
    assert "findings_summary" in report_json
    assert "limitations_and_disclaimers" in report_json

    # 6. Verify integrity
    verify_res = client.post(f"/api/v1/evidence/{evidence_id}/verify")
    assert verify_res.status_code == 200
    verify_json = verify_res.json()
    assert verify_json["overall_status"] == "VERIFIED"
    assert verify_json["local_integrity"]["verified"] is True

    # 7. Get file stream
    file_res = client.get(f"/api/v1/evidence/{evidence_id}/files/original")
    assert file_res.status_code == 200
    assert len(file_res.content) == len(jpeg_bytes)
