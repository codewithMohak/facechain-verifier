import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Tuple
import cv2
import PIL
from src.utils.hashing import generate_hash


def build_evidence_manifest(
    evidence_id: str,
    original_file_hash: str,
    acquisition_meta: Dict[str, Any],
    analysis_findings: Dict[str, Any],
    timestamps: Dict[str, str],
) -> Tuple[Dict[str, Any], str]:
    """
    Constructs a versioned evidence manifest.
    CRITICAL CONSTRAINTS:
    - The manifest does NOT include its own digest/hash.
    - The manifest does NOT include blockchain transaction metadata or status.
    - No PII, facial embeddings, or image binary data are included.

    Returns:
        (manifest_dict, manifest_hash)
    """
    # Create canonical analysis hash from findings
    analysis_hash = generate_hash(analysis_findings)

    manifest_dict = {
        "version": "1.0",
        "evidence_id": evidence_id,
        "original_file_hash": original_file_hash,
        "acquisition": {
            "acquired_at_utc": acquisition_meta.get("acquired_at_utc"),
            "filename": acquisition_meta.get("original_filename"),
            "file_size_bytes": acquisition_meta.get("file_size_bytes"),
            "mime_type": acquisition_meta.get("mime_type"),
            "format": acquisition_meta.get("format"),
            "dimensions": {
                "width": acquisition_meta.get("width"),
                "height": acquisition_meta.get("height"),
            },
        },
        "analysis_hash": analysis_hash,
        "tool_versions": {
            "facechain_forensics": "1.0.0",
            "opencv": str(cv2.__version__),
            "pillow": str(PIL.__version__),
            "python": sys.version.split()[0],
            "models": {
                "face_detector": "face_detection_yunet_2023mar.onnx",
                "face_recognizer": "face_recognition_sface_2021dec.onnx",
            },
        },
        "timestamps": {
            "acquired_at": timestamps.get("acquired_at"),
            "analyzed_at": timestamps.get("analyzed_at"),
            "manifest_created_at": datetime.now(timezone.utc).isoformat(),
        },
    }

    manifest_hash = generate_hash(manifest_dict)
    return manifest_dict, manifest_hash


def verify_manifest_integrity(
    original_file_path: str,
    manifest: Dict[str, Any],
    expected_manifest_hash: str,
    current_analysis_findings: Dict[str, Any] = None,
) -> Dict[str, Any]:
    """
    Verifies the integrity of an evidence item against its manifest:
    1. Recomputes original file SHA-256 and compares to manifest['original_file_hash'].
    2. Recomputes manifest hash and compares to expected_manifest_hash.
    3. If current_analysis_findings provided, verifies analysis_hash matches.
    """
    import hashlib

    # 1. Check original file existence and hash
    if not os.path.exists(original_file_path):
        return {
            "verified": False,
            "status": "TAMPERED",
            "reason": f"Original file not found at path: {original_file_path}",
            "file_hash_match": False,
            "manifest_hash_match": False,
        }

    with open(original_file_path, "rb") as f:
        actual_file_hash = hashlib.sha256(f.read()).hexdigest()

    file_hash_match = actual_file_hash == manifest.get("original_file_hash")

    # 2. Recompute manifest hash
    recomputed_manifest_hash = generate_hash(manifest)
    manifest_hash_match = recomputed_manifest_hash == expected_manifest_hash

    # 3. Check analysis hash if provided
    analysis_hash_match = True
    if current_analysis_findings is not None:
        recomputed_analysis_hash = generate_hash(current_analysis_findings)
        analysis_hash_match = recomputed_analysis_hash == manifest.get("analysis_hash")

    is_verified = file_hash_match and manifest_hash_match and analysis_hash_match

    return {
        "verified": is_verified,
        "status": "VERIFIED" if is_verified else "TAMPERED",
        "file_hash_match": file_hash_match,
        "manifest_hash_match": manifest_hash_match,
        "analysis_hash_match": analysis_hash_match,
        "original_file_hash": manifest.get("original_file_hash"),
        "actual_file_hash": actual_file_hash,
        "expected_manifest_hash": expected_manifest_hash,
        "recomputed_manifest_hash": recomputed_manifest_hash,
    }
