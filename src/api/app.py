import os
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any
from pydantic import BaseModel

from fastapi import FastAPI, UploadFile, File, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse

from src.forensics.acquisition import acquire_evidence, AcquisitionError
from src.forensics.pipeline import run_forensic_analysis
from src.forensics.manifest import verify_manifest_integrity
from src.blockchain.service import (
    anchor_manifest_to_blockchain,
    verify_anchored_manifest,
    is_blockchain_enabled,
)
from src.blockchain.verify import verify_data
from src.db.database import (
    init_db,
    insert_evidence,
    get_evidence,
    list_evidence,
    update_evidence,
)

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(
    title="FaceChain Forensics API",
    description="Evidence acquisition, metadata extraction, Error Level Analysis, biometric verification, and blockchain anchoring.",
    version="1.0.0",
    lifespan=lifespan,
)

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AnalyzeRequest(BaseModel):
    include_face_analysis: bool = True
    include_web_search: bool = False
    anchor_blockchain: bool = False


class LegacyVerifyRequest(BaseModel):
    verification_data: Dict[str, Any]
    transaction_hash: str


@app.get("/api/v1/health")
def health_check():
    """System health check and configuration summary."""
    yunet_exists = os.path.exists("models/face_detection_yunet_2023mar.onnx")
    sface_exists = os.path.exists("models/face_recognition_sface_2021dec.onnx")
    return {
        "status": "healthy",
        "service": "FaceChain Forensics API",
        "version": "1.0.0",
        "blockchain": {
            "enabled": is_blockchain_enabled(),
            "network": "Ethereum Sepolia (ChainID: 11155111)",
        },
        "models": {
            "yunet_detector": yunet_exists,
            "sface_recognizer": sface_exists,
        },
    }


@app.post("/api/v1/evidence", status_code=status.HTTP_201_CREATED)
async def upload_evidence(file: UploadFile = File(...)):
    """
    Acquire and register new image evidence:
    - Supports JPEG, PNG, and WebP
    - Validates file format, size, and image integrity
    - Computes SHA-256 digest immediately
    - Stores unchanged original and creates working copy
    - Persists initial record in SQLite
    """
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file must have a valid filename.",
        )

    try:
        content = await file.read()
        evidence_meta = acquire_evidence(
            file_bytes=content,
            filename=file.filename,
        )
        insert_evidence(evidence_meta)
        created_record = get_evidence(evidence_meta["evidence_id"])
        return created_record
    except AcquisitionError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(err),
        )
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to acquire evidence: {err}",
        )


@app.get("/api/v1/evidence")
def list_evidence_records(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """List recent evidence items."""
    return list_evidence(limit=limit, offset=offset)


@app.get("/api/v1/evidence/{evidence_id}")
def get_evidence_record(evidence_id: str):
    """Retrieve an evidence record by ID."""
    record = get_evidence(evidence_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Evidence with ID '{evidence_id}' does not exist.",
        )
    return record


@app.post("/api/v1/evidence/{evidence_id}/analyze")
def analyze_evidence(
    evidence_id: str,
    req: AnalyzeRequest = AnalyzeRequest(),
):
    """
    Run forensic analysis on an evidence item:
    - Metadata extraction
    - ELA / image manipulation analysis
    - Face detection (optional)
    - Web reverse search (optional)
    - Manifest generation
    - Blockchain anchoring (optional)
    """
    record = get_evidence(evidence_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Evidence with ID '{evidence_id}' does not exist.",
        )

    try:
        updated = run_forensic_analysis(
            evidence_id=evidence_id,
            include_face_analysis=req.include_face_analysis,
            include_web_search=req.include_web_search,
            anchor_blockchain=req.anchor_blockchain,
        )
        return updated
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Forensic analysis failed: {err}",
        )


@app.get("/api/v1/evidence/{evidence_id}/report")
def get_evidence_report(
    evidence_id: str,
    format: str = Query("json", description="Report format: json, html, or pdf"),
    download: bool = Query(False, description="Whether to trigger file attachment download"),
):
    """
    Retrieve or download forensic evidence reports in JSON, HTML, or PDF formats.
    Maintains one consistent underlying forensic findings model across all formats.
    """
    record = get_evidence(evidence_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Evidence with ID '{evidence_id}' does not exist.",
        )

    report_path = record.get("report_path")
    if not report_path or not os.path.exists(report_path):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Forensic report has not been generated yet. Run analysis first.",
        )

    with open(report_path, "r", encoding="utf-8") as f:
        report_data = json.load(f)

    fmt = format.lower().strip()

    if fmt == "html":
        from src.forensics.report import generate_html_report

        html_path = Path(report_path).with_suffix(".html")
        if not html_path.exists():
            generate_html_report(report_data, str(html_path))

        if download:
            return FileResponse(
                str(html_path),
                media_type="text/html; charset=utf-8",
                filename=f"facechain_forensics_report_{evidence_id}.html",
            )
        with open(html_path, "r", encoding="utf-8") as hf:
            html_content = hf.read()
        return HTMLResponse(content=html_content)

    elif fmt == "pdf":
        from src.forensics.report import generate_pdf_report

        pdf_path = Path(report_path).with_suffix(".pdf")
        if not pdf_path.exists():
            generate_pdf_report(report_data, str(pdf_path))

        if download:
            return FileResponse(
                str(pdf_path),
                media_type="application/pdf",
                filename=f"facechain_forensics_report_{evidence_id}.pdf",
            )
        return FileResponse(
            str(pdf_path),
            media_type="application/pdf",
        )

    elif fmt == "json":
        if download:
            return FileResponse(
                report_path,
                media_type="application/json",
                filename=f"facechain_forensics_report_{evidence_id}.json",
            )
        return JSONResponse(content=report_data)

    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported report format '{format}'. Supported formats: json, html, pdf.",
        )


@app.post("/api/v1/evidence/{evidence_id}/verify")
def verify_evidence_integrity(evidence_id: str):
    """
    Recompute and verify evidence integrity:
    1. Verifies SHA-256 of original file against manifest.
    2. Recomputes manifest digest.
    3. If anchored to Sepolia, retrieves and verifies on-chain payload.
    """
    record = get_evidence(evidence_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Evidence with ID '{evidence_id}' does not exist.",
        )

    manifest = record.get("manifest")
    manifest_hash = record.get("manifest_hash")

    if not manifest or not manifest_hash:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Evidence has not been analyzed yet (no manifest found).",
        )

    local_check = verify_manifest_integrity(
        original_file_path=record["original_path"],
        manifest=manifest,
        expected_manifest_hash=manifest_hash,
    )

    blockchain_check = None
    tx_hash = record.get("blockchain_tx_hash")
    if tx_hash:
        blockchain_check = verify_anchored_manifest(
            manifest_hash=manifest_hash,
            transaction_hash=tx_hash,
            anchored_at=record.get("blockchain_anchored_at"),
            analyzed_at=record.get("analyzed_at"),
        )
    else:
        blockchain_check = {
            "verified": False,
            "status": "UNANCHORED",
            "reason": "Evidence manifest is not anchored to Ethereum Sepolia.",
            "manifest_hash": manifest_hash,
            "transaction_hash": None,
        }

    overall_status = "VERIFIED"
    failure_reasons = []

    if not local_check.get("file_hash_match"):
        failure_reasons.append("Local original file SHA-256 digest does not match manifest.")
    if not local_check.get("manifest_hash_match"):
        failure_reasons.append("Recomputed manifest canonical hash does not match stored manifest digest.")
    if local_check.get("reason"):
        failure_reasons.append(local_check["reason"])

    if not local_check["verified"]:
        overall_status = "TAMPERED"
    elif tx_hash and blockchain_check:
        if blockchain_check.get("status") == "ERROR":
            overall_status = "BLOCKCHAIN_ERROR"
            failure_reasons.append(f"Sepolia RPC error: {blockchain_check.get('reason')}")
        elif blockchain_check.get("status") == "OUTDATED_ANCHOR":
            overall_status = "BLOCKCHAIN_MISMATCH"
            failure_reasons.append(blockchain_check.get("reason") or "Sepolia transaction anchors an outdated manifest digest from prior analysis.")
        elif blockchain_check.get("status") == "MALFORMED":
            overall_status = "BLOCKCHAIN_MISMATCH"
            failure_reasons.append(blockchain_check.get("reason") or "Sepolia transaction payload is malformed.")
        elif blockchain_check.get("status") == "NOT_FOUND":
            overall_status = "BLOCKCHAIN_MISMATCH"
            failure_reasons.append(blockchain_check.get("reason") or "Sepolia transaction not found on ledger.")
        elif not blockchain_check.get("verified"):
            overall_status = "BLOCKCHAIN_MISMATCH"
            failure_reasons.append(blockchain_check.get("reason") or "Anchored hash on Sepolia does not match local manifest digest.")

    checks = {
        "local_file": {
            "checked": True,
            "status": "passed" if local_check.get("file_hash_match") else "failed",
            "matched": bool(local_check.get("file_hash_match")),
            "match": bool(local_check.get("file_hash_match")),
            "expected_hash": local_check.get("original_file_hash"),
            "actual_hash": local_check.get("actual_file_hash"),
        },
        "manifest_digest": {
            "checked": True,
            "status": "passed" if local_check.get("manifest_hash_match") else "failed",
            "matched": bool(local_check.get("manifest_hash_match")),
            "match": bool(local_check.get("manifest_hash_match")),
            "expected_hash": local_check.get("expected_manifest_hash"),
            "actual_hash": local_check.get("recomputed_manifest_hash"),
            "expected_digest": local_check.get("expected_manifest_hash"),
            "actual_digest": local_check.get("recomputed_manifest_hash"),
        },
        "blockchain_record": {
            "checked": True if tx_hash else False,
            "status": (
                "passed" if (blockchain_check and blockchain_check.get("verified"))
                else ("failed" if (blockchain_check and blockchain_check.get("status") in ("TAMPERED", "MISMATCH", "FAILED", "OUTDATED_ANCHOR", "MALFORMED", "NOT_FOUND"))
                else ("warning" if (blockchain_check and blockchain_check.get("status") in ("ERROR", "UNANCHORED"))
                else "unverified"))
            ),
            "state": (blockchain_check.get("status") if blockchain_check else "UNANCHORED"),
            "match": bool(blockchain_check.get("verified")) if blockchain_check else False,
            "matched": bool(blockchain_check.get("verified")) if blockchain_check else False,
            "transaction_hash": tx_hash,
            "on_chain_hash": blockchain_check.get("on_chain_hash") if blockchain_check else None,
            "manifest_hash": manifest_hash,
            "details": blockchain_check.get("reason"),
            "error": blockchain_check.get("reason") if (blockchain_check and blockchain_check.get("status") in ("ERROR", "MALFORMED", "NOT_FOUND")) else None,
        },
    }

    return {
        "evidence_id": evidence_id,
        "overall_status": overall_status,
        "local_integrity": local_check,
        "blockchain_verification": blockchain_check,
        "checks": checks,
        "failure_reasons": failure_reasons,
        "verified_at": datetime.now(timezone.utc).isoformat(),
    }


@app.post("/api/v1/evidence/{evidence_id}/anchor")
def anchor_evidence(
    evidence_id: str,
    wait_for_receipt: bool = Query(True),
):
    """
    Optionally anchor the evidence manifest SHA-256 hash onto Ethereum Sepolia.
    """
    record = get_evidence(evidence_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Evidence with ID '{evidence_id}' does not exist.",
        )

    manifest_hash = record.get("manifest_hash")
    if not manifest_hash:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Evidence has not been analyzed yet. Run analysis first to produce manifest.",
        )

    # Check if already confirmed for THIS specific current manifest digest
    if (
        record.get("blockchain_status") == "confirmed"
        and record.get("blockchain_tx_hash")
        and record.get("blockchain_anchored_at")
        and (record.get("analyzed_at") is None or record.get("blockchain_anchored_at") >= record.get("analyzed_at"))
    ):
        return {
            "status": "confirmed",
            "message": "Evidence is already anchored and confirmed on Sepolia for this manifest digest.",
            "transaction_hash": record.get("blockchain_tx_hash"),
            "block_number": record.get("blockchain_block_number"),
            "anchored_at": record.get("blockchain_anchored_at"),
            "hash": manifest_hash,
        }

    anchored_res = anchor_manifest_to_blockchain(
        manifest_hash=manifest_hash,
        wait_for_receipt=wait_for_receipt,
    )

    updates = {
        "blockchain_status": anchored_res.get("status", "unanchored"),
        "blockchain_tx_hash": anchored_res.get("transaction_hash"),
        "blockchain_block_number": anchored_res.get("block_number"),
        "blockchain_anchored_at": anchored_res.get("anchored_at"),
        "blockchain_error": anchored_res.get("error"),
    }
    update_evidence(evidence_id, updates)

    return get_evidence(evidence_id)


@app.get("/api/v1/evidence/{evidence_id}/files/{file_type}")
def get_evidence_file(evidence_id: str, file_type: str):
    """
    Safely stream an evidence file (original, working, ela, face_crop).
    Enforces strict path traversal defenses.
    """
    record = get_evidence(evidence_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Evidence with ID '{evidence_id}' does not exist.",
        )

    file_map = {
        "original": record.get("original_path"),
        "working": record.get("working_path"),
        "ela": record.get("ela_path"),
        "face_crop": record.get("face_crop_path"),
        "report": record.get("report_path"),
    }

    target_path_str = file_map.get(file_type)
    if not target_path_str or not os.path.exists(target_path_str):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Requested file '{file_type}' is not available for evidence '{evidence_id}'.",
        )

    # Security check: Ensure target path is strictly within the evidence's storage directory
    evidence_dir = Path(record["original_path"]).parent.resolve()
    target_path = Path(target_path_str).resolve()

    try:
        target_path.relative_to(evidence_dir)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: Path traversal detected.",
        )

    # Determine media type
    suffix = target_path.suffix.lower()
    media_types = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".json": "application/json",
    }
    media_type = media_types.get(suffix, "application/octet-stream")

    return FileResponse(str(target_path), media_type=media_type)


@app.post("/api/v1/legacy/verify")
def verify_legacy_record(req: LegacyVerifyRequest):
    """
    Preserve legacy verification functionality:
    Verifies existing legacy verification records against Sepolia transactions.
    """
    try:
        is_verified = verify_data(
            req.verification_data,
            req.transaction_hash,
        )
        return {
            "verified": is_verified,
            "status": "VERIFIED" if is_verified else "TAMPERED",
            "transaction_hash": req.transaction_hash,
        }
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Legacy verification failed: {err}",
        )
