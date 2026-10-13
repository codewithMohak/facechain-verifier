import hashlib
import json
import pytest
from src.forensics.manifest import (
    build_evidence_manifest,
    verify_manifest_integrity,
)
from src.utils.hashing import generate_hash


def test_manifest_construction_and_canonicalization(tmp_path):
    dummy_file = tmp_path / "original.jpg"
    file_bytes = b"sample_original_file_bytes_for_forensic_testing"
    dummy_file.write_bytes(file_bytes)
    file_hash = hashlib.sha256(file_bytes).hexdigest()

    acquisition_meta = {
        "acquired_at_utc": "2026-10-13T12:00:00+00:00",
        "original_filename": "photo.jpg",
        "file_size_bytes": len(file_bytes),
        "mime_type": "image/jpeg",
        "format": "JPEG",
        "width": 640,
        "height": 480,
    }

    analysis_findings = {
        "metadata_summary": {"format": "JPEG", "has_exif": True},
        "image_manipulation_summary": {"ela_applicable": True},
    }

    timestamps = {
        "acquired_at": "2026-10-13T12:00:00+00:00",
        "analyzed_at": "2026-10-13T12:05:00+00:00",
    }

    manifest, manifest_hash = build_evidence_manifest(
        evidence_id="ev_test_123",
        original_file_hash=file_hash,
        acquisition_meta=acquisition_meta,
        analysis_findings=analysis_findings,
        timestamps=timestamps,
    )

    # 1. Manifest must NOT contain its own digest or blockchain details
    assert "manifest_hash" not in manifest
    assert "blockchain" not in manifest
    assert "transaction_hash" not in manifest

    # 2. Canonical serialization consistency check
    expected_hash = generate_hash(manifest)
    assert manifest_hash == expected_hash

    # 3. Integrity verification succeeds with untouched data
    res = verify_manifest_integrity(
        original_file_path=str(dummy_file),
        manifest=manifest,
        expected_manifest_hash=manifest_hash,
        current_analysis_findings=analysis_findings,
    )
    assert res["verified"] is True
    assert res["status"] == "VERIFIED"


def test_manifest_tamper_detection(tmp_path):
    dummy_file = tmp_path / "original.jpg"
    file_bytes = b"unmodified_image_data"
    dummy_file.write_bytes(file_bytes)
    file_hash = hashlib.sha256(file_bytes).hexdigest()

    acquisition_meta = {"acquired_at_utc": "2026-10-13T12:00:00+00:00"}
    analysis_findings = {"status": "ok"}
    timestamps = {"acquired_at": "2026-10-13T12:00:00+00:00"}

    manifest, manifest_hash = build_evidence_manifest(
        evidence_id="ev_tamper_test",
        original_file_hash=file_hash,
        acquisition_meta=acquisition_meta,
        analysis_findings=analysis_findings,
        timestamps=timestamps,
    )

    # Tamper with file
    dummy_file.write_bytes(b"tampered_image_data")

    res = verify_manifest_integrity(
        original_file_path=str(dummy_file),
        manifest=manifest,
        expected_manifest_hash=manifest_hash,
    )
    assert res["verified"] is False
    assert res["status"] == "TAMPERED"
    assert res["file_hash_match"] is False
