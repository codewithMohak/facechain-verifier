import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional

import cv2

from src.db.database import get_evidence, update_evidence
from src.forensics.metadata import extract_metadata
from src.forensics.ela import generate_ela
from src.forensics.manifest import build_evidence_manifest, verify_manifest_integrity
from src.forensics.report import generate_forensic_report
from src.blockchain.service import anchor_manifest_to_blockchain, is_blockchain_enabled


def run_forensic_analysis(
    evidence_id: str,
    include_face_analysis: bool = True,
    include_web_search: bool = False,
    anchor_blockchain: bool = False,
    db_path: str = "data/forensics.db",
) -> Dict[str, Any]:
    """
    Executes the full forensic analysis pipeline on an acquired evidence item:
    1. Metadata extraction & consistency checking
    2. Image manipulation / ELA analysis
    3. Optional YuNet face detection & SFace encoding
    4. Optional Google Lens reverse search
    5. Versioned evidence manifest creation
    6. Optional Sepolia blockchain anchoring
    7. JSON report generation
    8. Database record update
    """
    record = get_evidence(evidence_id, db_path=db_path)
    if not record:
        raise ValueError(f"Evidence ID '{evidence_id}' not found.")

    working_path = record["working_path"]
    storage_dir = Path(working_path).parent

    if not os.path.exists(working_path):
        raise FileNotFoundError(f"Working copy not found at: {working_path}")

    # 1. Metadata Analysis (extracted directly from untouched original evidence)
    original_path = record.get("original_path")
    meta_source_path = original_path if (original_path and os.path.exists(original_path)) else working_path
    metadata_res = extract_metadata(meta_source_path)

    # 2. Image Manipulation / ELA Analysis
    ela_output_path = str(storage_dir / "ela.jpg")
    image_analysis_res = generate_ela(working_path, ela_output_path)
    actual_ela_path = image_analysis_res.get("ela_path")

    # 3. Existing Face Analysis (YuNet + SFace)
    face_res = None
    face_crop_path = None
    embedding = None

    if include_face_analysis:
        try:
            from src.face.detector import detect_and_crop_face
            from src.face.encoder import encode_face

            # Use dedicated face crop path in evidence directory
            crop_dir = str(storage_dir)
            face_meta = detect_and_crop_face(working_path, output_dir=crop_dir)
            face_crop_path = face_meta.get("face_crop_path")

            # Encode embedding
            img_bgr = cv2.imread(working_path)
            if img_bgr is not None:
                embedding = encode_face(img_bgr, face_meta)
                dim = int(embedding.shape[-1]) if embedding is not None else 128
            else:
                dim = 128

            face_res = {
                "face_detected": True,
                "face_count": face_meta.get("face_count", 1),
                "confidence": face_meta.get("confidence", 0.0),
                "bounding_box": face_meta.get("bounding_box"),
                "crop_box": face_meta.get("crop_box"),
                "landmarks": face_meta.get("landmarks"),
                "face_crop_path": face_crop_path,
                "embedding_model": "OpenCV SFace",
                "embedding_dimensions": dim,
                "disclaimer": (
                    "Investigative Notice: Face similarity biometrics and detection bounding boxes "
                    "are investigative aids. They do NOT constitute definitive proof of human identity."
                ),
            }
        except ValueError as val_err:
            # Typically "No face detected in the image."
            face_res = {
                "face_detected": False,
                "face_count": 0,
                "message": str(val_err),
            }
        except Exception as face_err:
            face_res = {
                "face_detected": False,
                "face_count": 0,
                "error": f"Face analysis failed: {face_err}",
            }

    # 4. Optional Reverse Image Search (Google Lens)
    web_res = None
    if include_web_search:
        try:
            from src.search.lens import (
                prepare_image_for_search,
                search_with_google_lens,
                extract_best_match,
            )
            from src.search.face_matcher import find_matching_public_face

            search_img_path = str(storage_dir / "search_img.jpg")
            prepared = prepare_image_for_search(working_path, search_img_path)
            lens_raw = search_with_google_lens(prepared)
            best_match = extract_best_match(lens_raw)

            public_face_match = None
            match_status = "NO_MATCH"

            if best_match["match_type"] == "exact":
                match_status = "EXACT_IMAGE_MATCH"
                public_face_match = {
                    "public_face_found": True,
                    "verification_method": "exact_image_match",
                    "title": best_match["title"],
                    "source": best_match["source"],
                    "url": best_match["url"],
                }
            elif best_match["match_type"] == "visual":
                match_status = "VISUAL_MATCH_ONLY"
                candidates = best_match.get("visual_matches", [])
                if candidates and embedding is not None:
                    public_face_match = find_matching_public_face(embedding, candidates)
                    if public_face_match and public_face_match.get("is_match"):
                        match_status = "PUBLIC_FACE_MATCH"

            web_res = {
                "status": match_status,
                "best_match": best_match,
                "public_face_match": public_face_match,
                "third_party_disclosure": (
                    "Notice: Image search uploads a compressed version to SerpApi / Google Lens, "
                    "a third-party indexing service."
                ),
            }
        except Exception as web_err:
            web_res = {
                "status": "SEARCH_FAILED",
                "error": str(web_err),
                "third_party_disclosure": (
                    "Notice: Image search uploads a compressed version to SerpApi / Google Lens, "
                    "a third-party indexing service."
                ),
            }

    # 5. Canonical Analysis Findings for Manifest Hashing
    analysis_findings = {
        "metadata_summary": {
            "format": metadata_res.get("format"),
            "width": metadata_res.get("width"),
            "height": metadata_res.get("height"),
            "has_exif": metadata_res.get("has_exif"),
            "camera_make": metadata_res.get("camera", {}).get("make"),
            "camera_model": metadata_res.get("camera", {}).get("model"),
            "software": metadata_res.get("camera", {}).get("software"),
            "gps_available": metadata_res.get("gps", {}).get("available"),
            "suspicious_count": len(metadata_res.get("suspicious_indicators", [])),
        },
        "image_manipulation_summary": {
            "format": image_analysis_res.get("format"),
            "ela_applicable": image_analysis_res.get("ela_applicable"),
            "statistics": image_analysis_res.get("statistics"),
        },
        "face_summary": {
            "detected": bool(face_res and face_res.get("face_detected")),
            "face_count": face_res.get("face_count", 0) if face_res else 0,
        },
        "web_search_summary": {
            "status": web_res.get("status") if web_res else "NOT_RUN",
        },
    }

    analyzed_at_utc = datetime.now(timezone.utc).isoformat()
    timestamps = {
        "acquired_at": record["created_at"],
        "analyzed_at": analyzed_at_utc,
    }

    acquisition_meta = {
        "acquired_at_utc": record["created_at"],
        "original_filename": record["filename"],
        "file_size_bytes": record["file_size"],
        "mime_type": record["mime_type"],
        "format": metadata_res.get("format"),
        "width": metadata_res.get("width"),
        "height": metadata_res.get("height"),
    }

    # Build versioned evidence manifest
    manifest_dict, manifest_hash = build_evidence_manifest(
        evidence_id=evidence_id,
        original_file_hash=record["original_hash"],
        acquisition_meta=acquisition_meta,
        analysis_findings=analysis_findings,
        timestamps=timestamps,
    )

    # 6. Optional Blockchain Anchoring
    blockchain_info = {
        "status": record.get("blockchain_status", "unanchored"),
        "transaction_hash": record.get("blockchain_tx_hash"),
        "block_number": record.get("blockchain_block_number"),
        "anchored_at": record.get("blockchain_anchored_at"),
        "hash": manifest_hash,
        "verification": "NOT_RUN",
    }

    if anchor_blockchain:
        anchored_res = anchor_manifest_to_blockchain(manifest_hash, wait_for_receipt=True)
        blockchain_info = {
            **blockchain_info,
            **anchored_res,
        }
    elif record.get("blockchain_status") == "confirmed" and record.get("manifest_hash") != manifest_hash:
        # Evidence was re-analyzed without re-anchoring; prior on-chain transaction anchors an older manifest
        blockchain_info["status"] = "outdated"
        blockchain_info["hash"] = record.get("manifest_hash")

    # Verify manifest integrity right after building
    integrity_status = verify_manifest_integrity(
        original_file_path=record["original_path"],
        manifest=manifest_dict,
        expected_manifest_hash=manifest_hash,
        current_analysis_findings=analysis_findings,
    )

    # 7. Generate Full Forensic Report JSON
    report_output_path = str(storage_dir / "report.json")
    report_dict = generate_forensic_report(
        evidence_id=evidence_id,
        original_sha256=record["original_hash"],
        file_properties={
            "filename": record["filename"],
            "file_size_bytes": record["file_size"],
            "mime_type": record["mime_type"],
            "width": metadata_res.get("width"),
            "height": metadata_res.get("height"),
            "format": metadata_res.get("format"),
            "color_mode": metadata_res.get("color_mode"),
        },
        metadata_analysis=metadata_res,
        image_analysis=image_analysis_res,
        face_analysis=face_res,
        web_search_analysis=web_res,
        manifest=manifest_dict,
        manifest_hash=manifest_hash,
        blockchain_details=blockchain_info,
        integrity_status=integrity_status,
        output_path=report_output_path,
    )

    # 8. Update SQLite record
    updates = {
        "status": "analyzed",
        "analyzed_at": analyzed_at_utc,
        "ela_path": actual_ela_path,
        "face_crop_path": face_crop_path,
        "metadata_json": metadata_res,
        "image_analysis_json": image_analysis_res,
        "face_analysis_json": face_res,
        "web_search_json": web_res,
        "manifest_json": manifest_dict,
        "manifest_hash": manifest_hash,
        "report_path": report_output_path,
        "blockchain_status": blockchain_info.get("status", "unanchored"),
        "blockchain_tx_hash": blockchain_info.get("transaction_hash"),
        "blockchain_block_number": blockchain_info.get("block_number"),
        "blockchain_anchored_at": blockchain_info.get("anchored_at"),
        "blockchain_error": blockchain_info.get("error"),
    }
    update_evidence(evidence_id, updates, db_path=db_path)

    return get_evidence(evidence_id, db_path=db_path)
