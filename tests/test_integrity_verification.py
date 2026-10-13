import io
import json
from pathlib import Path
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from src.api.app import app
from src.db.database import get_evidence, update_evidence


@pytest.fixture
def client():
    return TestClient(app)


def create_jpeg_bytes() -> bytes:
    buf = io.BytesIO()
    img = Image.new("RGB", (64, 64), color=(180, 90, 40))
    img.save(buf, format="JPEG")
    return buf.getvalue()


def upload_and_analyze(client, anchor: bool = False):
    jpeg_bytes = create_jpeg_bytes()
    upload_res = client.post(
        "/api/v1/evidence",
        files={"file": ("verify_test.jpg", jpeg_bytes, "image/jpeg")},
    )
    assert upload_res.status_code == 201
    evidence_id = upload_res.json()["id"]

    analyze_res = client.post(
        f"/api/v1/evidence/{evidence_id}/analyze",
        json={
            "include_face_analysis": False,
            "include_web_search": False,
            "anchor_blockchain": anchor,
        },
    )
    assert analyze_res.status_code == 200
    return evidence_id, upload_res.json(), analyze_res.json()


def test_verify_all_local_checks_pass(client):
    evidence_id, _, analyzed = upload_and_analyze(client, anchor=False)
    
    verify_res = client.post(f"/api/v1/evidence/{evidence_id}/verify")
    assert verify_res.status_code == 200
    data = verify_res.json()

    assert data["evidence_id"] == evidence_id
    assert data["overall_status"] == "VERIFIED"
    assert data["local_integrity"]["verified"] is True
    assert data["local_integrity"]["file_hash_match"] is True
    assert data["local_integrity"]["manifest_hash_match"] is True

    # Granular checks
    checks = data["checks"]
    assert checks["local_file"]["checked"] is True
    assert checks["local_file"]["status"] == "passed"
    assert checks["local_file"]["match"] is True
    assert checks["local_file"]["expected_hash"] == analyzed["original_hash"]
    assert checks["local_file"]["actual_hash"] == analyzed["original_hash"]

    assert checks["manifest_digest"]["checked"] is True
    assert checks["manifest_digest"]["status"] == "passed"
    assert checks["manifest_digest"]["match"] is True
    assert checks["manifest_digest"]["expected_digest"] == analyzed["manifest_hash"]

    assert checks["blockchain_record"]["status"] == "warning"  # Unanchored is warning, not failed
    assert len(data["failure_reasons"]) == 0


def test_verify_tampered_local_file_detected(client):
    evidence_id, _, analyzed = upload_and_analyze(client, anchor=False)

    ev = get_evidence(evidence_id)
    assert ev is not None

    # Directly tamper the original stored file on disk
    orig_path = Path(ev["original_path"])
    assert orig_path.exists()
    orig_path.write_bytes(b"TAMPERED_CONTENT_CORRUPTED_EVIDENCE")

    verify_res = client.post(f"/api/v1/evidence/{evidence_id}/verify")
    assert verify_res.status_code == 200
    data = verify_res.json()

    assert data["overall_status"] == "TAMPERED"
    assert data["local_integrity"]["verified"] is False
    assert data["local_integrity"]["file_hash_match"] is False

    checks = data["checks"]
    assert checks["local_file"]["checked"] is True
    assert checks["local_file"]["status"] == "failed"
    assert checks["local_file"]["match"] is False
    assert checks["local_file"]["actual_hash"] != checks["local_file"]["expected_hash"]

    assert len(data["failure_reasons"]) >= 1
    assert any("Local original file SHA-256 digest does not match" in r for r in data["failure_reasons"])


def test_verify_tampered_manifest_digest_detected(client):
    evidence_id, _, analyzed = upload_and_analyze(client, anchor=False)

    ev = get_evidence(evidence_id)
    assert ev is not None

    # Tamper the stored manifest record in the database
    tampered_manifest = dict(ev["manifest"])
    tampered_manifest["timestamps"] = dict(tampered_manifest.get("timestamps", {}))
    tampered_manifest["timestamps"]["tampered_extra"] = "2026-10-13T99:99:99Z"
    update_evidence(evidence_id, {"manifest_json": tampered_manifest})

    verify_res = client.post(f"/api/v1/evidence/{evidence_id}/verify")
    assert verify_res.status_code == 200
    data = verify_res.json()

    assert data["overall_status"] == "TAMPERED"
    assert data["local_integrity"]["verified"] is False
    assert data["local_integrity"]["manifest_hash_match"] is False

    checks = data["checks"]
    assert checks["manifest_digest"]["checked"] is True
    assert checks["manifest_digest"]["status"] == "failed"
    assert checks["manifest_digest"]["match"] is False
    assert any("manifest canonical hash does not match" in r.lower() for r in data["failure_reasons"])


def test_verify_blockchain_mismatch_detected(client):
    evidence_id, _, analyzed = upload_and_analyze(client, anchor=False)

    update_evidence(
        evidence_id,
        {
            "blockchain_status": "confirmed",
            "blockchain_tx_hash": "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
            "blockchain_block_number": 9999,
            "blockchain_anchored_at": "2026-10-13T12:00:00Z",
        },
    )

    # Mock blockchain verify to simulate on-chain digest mismatch
    with patch("src.api.app.verify_anchored_manifest") as mock_verify:
        mock_verify.return_value = {
            "verified": False,
            "status": "TAMPERED",
            "manifest_hash": analyzed["manifest_hash"],
            "on_chain_hash": "0xdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef",
            "transaction_hash": "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
            "block_number": 9999,
        }

        verify_res = client.post(f"/api/v1/evidence/{evidence_id}/verify")
        assert verify_res.status_code == 200
        data = verify_res.json()

        assert data["overall_status"] == "BLOCKCHAIN_MISMATCH"
        assert data["checks"]["blockchain_record"]["status"] == "failed"
        assert data["checks"]["blockchain_record"]["match"] is False
        assert any("Anchored hash on Sepolia does not match" in r for r in data["failure_reasons"])


def test_verify_blockchain_rpc_error_handling(client):
    evidence_id, _, analyzed = upload_and_analyze(client, anchor=False)

    update_evidence(
        evidence_id,
        {
            "blockchain_status": "confirmed",
            "blockchain_tx_hash": "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
        },
    )

    # Mock blockchain verify to simulate RPC node error / timeout
    with patch("src.api.app.verify_anchored_manifest") as mock_verify:
        mock_verify.return_value = {
            "verified": False,
            "status": "ERROR",
            "reason": "Infura/Alchemy RPC timeout connecting to Sepolia network",
            "transaction_hash": "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
        }

        verify_res = client.post(f"/api/v1/evidence/{evidence_id}/verify")
        assert verify_res.status_code == 200
        data = verify_res.json()

        assert data["overall_status"] == "BLOCKCHAIN_ERROR"
        assert data["checks"]["blockchain_record"]["status"] == "warning"
        assert "Infura/Alchemy RPC timeout" in data["checks"]["blockchain_record"]["error"]


def test_verify_unanalyzed_evidence_returns_400(client):
    jpeg_bytes = create_jpeg_bytes()
    upload_res = client.post(
        "/api/v1/evidence",
        files={"file": ("unready.jpg", jpeg_bytes, "image/jpeg")},
    )
    evidence_id = upload_res.json()["id"]

    verify_res = client.post(f"/api/v1/evidence/{evidence_id}/verify")
    assert verify_res.status_code == 400
    assert "Evidence has not been analyzed yet" in verify_res.json()["detail"]


def test_report_downloads_json_html_pdf(client):
    evidence_id, _, analyzed = upload_and_analyze(client, anchor=False)

    # 1. Download JSON
    res_json = client.get(f"/api/v1/evidence/{evidence_id}/report?format=json&download=true")
    assert res_json.status_code == 200
    assert "application/json" in res_json.headers["content-type"]
    assert f'filename="facechain_forensics_report_{evidence_id}.json"' in res_json.headers["content-disposition"]
    json_body = res_json.json()
    assert json_body["evidence"]["evidence_id"] == evidence_id
    assert "findings_summary" in json_body

    # 2. Download HTML
    res_html = client.get(f"/api/v1/evidence/{evidence_id}/report?format=html&download=true")
    assert res_html.status_code == 200
    assert "text/html" in res_html.headers["content-type"]
    assert f'filename="facechain_forensics_report_{evidence_id}.html"' in res_html.headers["content-disposition"]
    html_text = res_html.text
    assert "<!DOCTYPE html>" in html_text
    assert evidence_id in html_text

    # 3. Download PDF
    res_pdf = client.get(f"/api/v1/evidence/{evidence_id}/report?format=pdf&download=true")
    assert res_pdf.status_code == 200
    assert "application/pdf" in res_pdf.headers["content-type"]
    assert f'filename="facechain_forensics_report_{evidence_id}.pdf"' in res_pdf.headers["content-disposition"]
    # PDF starts with %PDF- header magic bytes
    assert res_pdf.content.startswith(b"%PDF-")


def test_report_download_unanalyzed_returns_400(client):
    jpeg_bytes = create_jpeg_bytes()
    upload_res = client.post(
        "/api/v1/evidence",
        files={"file": ("unready_report.jpg", jpeg_bytes, "image/jpeg")},
    )
    evidence_id = upload_res.json()["id"]

    for fmt in ["json", "html", "pdf"]:
        res = client.get(f"/api/v1/evidence/{evidence_id}/report?format={fmt}&download=true")
        assert res.status_code == 400
        assert "Forensic report has not been generated yet" in res.json()["detail"]


def test_report_download_invalid_format_returns_400(client):
    evidence_id, _, _ = upload_and_analyze(client, anchor=False)

    res = client.get(f"/api/v1/evidence/{evidence_id}/report?format=docx&download=true")
    assert res.status_code == 400
    assert "Unsupported report format" in res.json()["detail"]


def test_verify_blockchain_correct_digest_with_normalization(client):
    evidence_id, _, analyzed = upload_and_analyze(client, anchor=False)

    update_evidence(
        evidence_id,
        {
            "blockchain_status": "confirmed",
            "blockchain_tx_hash": "0xabc1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
            "blockchain_block_number": 12345,
            "blockchain_anchored_at": "2026-10-13T12:00:00Z",
        },
    )

    # Simulate on-chain hash with different casing and 0x prefix to test normalization
    raw_manifest_hash = analyzed["manifest_hash"]
    with patch("src.blockchain.service.get_anchored_hash") as mock_get_hash:
        mock_get_hash.return_value = raw_manifest_hash.upper()

        verify_res = client.post(f"/api/v1/evidence/{evidence_id}/verify")
        assert verify_res.status_code == 200
        data = verify_res.json()

        assert data["overall_status"] == "VERIFIED"
        assert data["checks"]["blockchain_record"]["status"] == "passed"
        assert data["checks"]["blockchain_record"]["match"] is True
        assert data["checks"]["blockchain_record"]["on_chain_hash"] == raw_manifest_hash.lower()


def test_verify_blockchain_outdated_anchor(client):
    evidence_id, _, analyzed = upload_and_analyze(client, anchor=False)

    # Set anchored_at PRIOR to analyzed_at
    update_evidence(
        evidence_id,
        {
            "blockchain_status": "confirmed",
            "blockchain_tx_hash": "0xabc1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
            "blockchain_block_number": 12345,
            "blockchain_anchored_at": "2026-10-13T10:00:00Z",
            "analyzed_at": "2026-10-13T12:00:00Z",
        },
    )

    # Simulate on-chain hash that was anchored at 10:00:00Z for an earlier manifest
    earlier_hash = "1111111111111111111111111111111111111111111111111111111111111111"
    with patch("src.blockchain.service.get_anchored_hash") as mock_get_hash:
        mock_get_hash.return_value = earlier_hash

        verify_res = client.post(f"/api/v1/evidence/{evidence_id}/verify")
        assert verify_res.status_code == 200
        data = verify_res.json()

        assert data["overall_status"] == "BLOCKCHAIN_MISMATCH"
        assert data["checks"]["blockchain_record"]["status"] == "failed"
        assert data["checks"]["blockchain_record"]["state"] == "OUTDATED_ANCHOR"
        assert data["checks"]["blockchain_record"]["match"] is False
        assert any("Outdated Anchor" in r for r in data["failure_reasons"])


def test_verify_blockchain_malformed_transaction_payload(client):
    evidence_id, _, analyzed = upload_and_analyze(client, anchor=False)

    update_evidence(
        evidence_id,
        {
            "blockchain_status": "confirmed",
            "blockchain_tx_hash": "0xabc1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
        },
    )

    # Simulate ValueError from verify.py when on-chain payload is corrupt/malformed
    with patch("src.blockchain.service.get_anchored_hash") as mock_get_hash:
        mock_get_hash.side_effect = ValueError("The transaction does not contain a valid FaceChain hash prefix.")

        verify_res = client.post(f"/api/v1/evidence/{evidence_id}/verify")
        assert verify_res.status_code == 200
        data = verify_res.json()

        assert data["overall_status"] == "BLOCKCHAIN_MISMATCH"
        assert data["checks"]["blockchain_record"]["status"] == "failed"
        assert data["checks"]["blockchain_record"]["state"] == "MALFORMED"
        assert data["checks"]["blockchain_record"]["match"] is False
        assert any("Malformed on-chain payload" in r for r in data["failure_reasons"])


def test_verify_blockchain_missing_transaction_not_found(client):
    evidence_id, _, analyzed = upload_and_analyze(client, anchor=False)

    update_evidence(
        evidence_id,
        {
            "blockchain_status": "confirmed",
            "blockchain_tx_hash": "0xnonexistent_tx_hash_0000000000000000000000000000000000000000",
        },
    )

    # Simulate transaction not found
    with patch("src.blockchain.service.get_anchored_hash") as mock_get_hash:
        mock_get_hash.side_effect = Exception("Transaction '0xnonexistent' not found on ledger.")

        verify_res = client.post(f"/api/v1/evidence/{evidence_id}/verify")
        assert verify_res.status_code == 200
        data = verify_res.json()

        assert data["overall_status"] == "BLOCKCHAIN_MISMATCH"
        assert data["checks"]["blockchain_record"]["status"] == "failed"
        assert data["checks"]["blockchain_record"]["state"] == "NOT_FOUND"
        assert data["checks"]["blockchain_record"]["match"] is False
        assert any("not found" in r.lower() for r in data["failure_reasons"])


def test_normalize_digest_bytes_functionality():
    from src.blockchain.service import normalize_digest_bytes

    # Standard lowercase 64-hex
    b1 = normalize_digest_bytes("bfd570015cde5d87892a2bc0a041c1f7fa8b0e3272345736c9cb0ff645b79cf3")
    assert b1 is not None and len(b1) == 32

    # With 0x prefix and uppercase
    b2 = normalize_digest_bytes("0xBFD570015CDE5D87892A2BC0A041C1F7FA8B0E3272345736C9CB0FF645B79CF3")
    assert b1 == b2

    # Invalid length or non-hex
    assert normalize_digest_bytes("tooshort") is None
    assert normalize_digest_bytes("zzzd570015cde5d87892a2bc0a041c1f7fa8b0e3272345736c9cb0ff645b79cf3") is None
    assert normalize_digest_bytes("") is None
    assert normalize_digest_bytes(None) is None
