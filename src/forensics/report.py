import html
import io
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    KeepTogether,
    HRFlowable,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfgen import canvas


class NumberedCanvas(canvas.Canvas):
    """Adds running headers and 'Page X of Y' footers to PDF documents."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_header_footer(num_pages)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

    def draw_header_footer(self, page_count):
        self.saveState()
        # Header (pages after first)
        if self._pageNumber > 1:
            self.setFont("Helvetica-Bold", 7)
            self.setFillColor(colors.HexColor("#64748b"))
            self.drawString(54, 755, "FACECHAIN FORENSICS — DIGITAL EVIDENCE REPORT")
            self.setStrokeColor(colors.HexColor("#e2e8f0"))
            self.setLineWidth(0.5)
            self.line(54, 750, 612 - 54, 750)

        # Footer
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748b"))
        self.drawString(54, 34, "FaceChain Forensics — Investigative Report (Not Judicial Proof)")
        self.drawRightString(612 - 54, 34, f"Page {self._pageNumber} of {page_count}")
        self.setStrokeColor(colors.HexColor("#e2e8f0"))
        self.setLineWidth(0.5)
        self.line(54, 46, 612 - 54, 46)
        self.restoreState()


def _safe_str(val: Any) -> str:
    """Safely convert any value to string, handling None and empty cases."""
    if val is None:
        return "N/A"
    return str(val)


def _safe_html(val: Any) -> str:
    """HTML escape dynamic user/metadata values to prevent XSS."""
    return html.escape(_safe_str(val))


def _safe_url(url: Optional[str]) -> Optional[str]:
    """Ensure URL is safe for anchor tags (only http and https allowed)."""
    if not url:
        return None
    url_clean = str(url).strip()
    if url_clean.startswith("http://") or url_clean.startswith("https://"):
        return url_clean
    return None


def generate_forensic_report(
    evidence_id: str,
    original_sha256: str,
    file_properties: Dict[str, Any],
    metadata_analysis: Dict[str, Any],
    image_analysis: Dict[str, Any],
    face_analysis: Optional[Dict[str, Any]],
    web_search_analysis: Optional[Dict[str, Any]],
    manifest: Dict[str, Any],
    manifest_hash: str,
    blockchain_details: Dict[str, Any],
    integrity_status: Dict[str, Any],
    output_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Builds the formal structured FaceChain Forensic Evidence Report.
    Also produces HTML and PDF versions when output_path is provided.
    """
    now_utc = datetime.now(timezone.utc).isoformat()

    # Formulate summary findings
    findings = []
    if metadata_analysis.get("suspicious_indicators"):
        for ind in metadata_analysis["suspicious_indicators"]:
            findings.append({
                "type": "metadata",
                "level": ind.get("severity", "medium"),
                "summary": ind.get("indicator"),
                "details": ind.get("detail"),
            })

    if image_analysis.get("observable_indicators"):
        for ind_text in image_analysis["observable_indicators"]:
            findings.append({
                "type": "image_manipulation",
                "level": "indicator",
                "summary": "Visual/Compression Indicator",
                "details": ind_text,
            })

    if face_analysis and face_analysis.get("face_detected"):
        findings.append({
            "type": "face_biometric",
            "level": "informational",
            "summary": f"Detected {face_analysis.get('face_count', 1)} face(s)",
            "details": f"Primary face detection confidence: {face_analysis.get('confidence', 0):.4f}",
        })

    if web_search_analysis and web_search_analysis.get("status") in (
        "EXACT_IMAGE_MATCH",
        "PUBLIC_FACE_MATCH",
    ):
        findings.append({
            "type": "public_search",
            "level": "corroboration",
            "summary": f"Public image match found ({web_search_analysis['status']})",
            "details": f"Source: {(web_search_analysis.get('best_match') or {}).get('source', 'Unknown')}",
        })

    limitations = [
        "Forensic results reflect computational indicators and mathematical compression patterns at time of analysis.",
        "Error Level Analysis (ELA) highlights compression rate variances; natural lighting, texture frequency, and sensor noise also generate high variance.",
        "EXIF metadata can be routinely stripped by messaging apps or deliberately modified without leaving detectable file damage.",
        "Face similarity scores produced by SFace are investigative biometrics and must never be treated as definitive proof of identity.",
        "Reverse image searches depend on third-party public indexing and are not exhaustive.",
        "GPS coordinates represent embedded EXIF metadata tags from the file and do not constitute independently verified physical location.",
        "This automated report does NOT provide a legal certification, judicial guarantee, or court admissibility determination.",
    ]

    report = {
        "report_id": f"rep_{evidence_id}",
        "schema_version": "1.0",
        "generated_at_utc": now_utc,
        "evidence": {
            "evidence_id": evidence_id,
            "original_file_hash_sha256": original_sha256,
            "file_properties": file_properties,
        },
        "metadata_analysis": {
            "format": metadata_analysis.get("format"),
            "dimensions": {
                "width": metadata_analysis.get("width"),
                "height": metadata_analysis.get("height"),
            },
            "camera": metadata_analysis.get("camera") or {},
            "capture_parameters": metadata_analysis.get("capture_parameters") or {},
            "timestamps": metadata_analysis.get("timestamps") or {},
            "gps": metadata_analysis.get("gps") or {},
            "missing_metadata": metadata_analysis.get("missing_metadata") or [],
            "suspicious_indicators": metadata_analysis.get("suspicious_indicators") or [],
        },
        "image_manipulation_analysis": {
            "format": image_analysis.get("format"),
            "ela_applicable": image_analysis.get("ela_applicable", False),
            "parameters": image_analysis.get("parameters"),
            "statistics": image_analysis.get("statistics"),
            "encoding_properties": image_analysis.get("encoding_properties"),
            "lossless_analysis": image_analysis.get("lossless_analysis"),
            "webp_properties": image_analysis.get("webp_properties"),
            "observable_indicators": image_analysis.get("observable_indicators", []),
            "methodology_note": image_analysis.get("methodology_note"),
        },
        "face_analysis": face_analysis,
        "web_search_analysis": web_search_analysis,
        "findings_summary": findings,
        "limitations_and_disclaimers": limitations,
        "integrity": {
            "manifest_hash": manifest_hash,
            "canonical_manifest": manifest,
            "verification_status": integrity_status,
        },
        "blockchain_anchoring": {
            "status": blockchain_details.get("status", "unanchored"),
            "network": "Ethereum Sepolia (ChainID: 11155111)",
            "transaction_hash": blockchain_details.get("transaction_hash"),
            "block_number": blockchain_details.get("block_number"),
            "anchored_at": blockchain_details.get("anchored_at"),
            "anchored_hash": blockchain_details.get("hash"),
            "verification": blockchain_details.get("verification", "NOT_RUN"),
        },
    }

    if output_path:
        out_p = Path(output_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)

        # 1. Save JSON report
        with open(out_p, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)

        # 2. Save HTML report
        html_path = out_p.with_suffix(".html")
        generate_html_report(report, str(html_path))

        # 3. Save PDF report
        pdf_path = out_p.with_suffix(".pdf")
        generate_pdf_report(report, str(pdf_path))

    return report


def generate_html_report(report_data: Dict[str, Any], output_path: Optional[str] = None) -> str:
    """
    Renders a standalone, print-friendly, secure HTML forensic report.
    All dynamic user-controlled strings are strictly HTML-escaped.
    """
    ev = report_data.get("evidence") or {}
    ev_id = _safe_html(ev.get("evidence_id"))
    sha256 = _safe_html(ev.get("original_file_hash_sha256"))
    file_props = ev.get("file_properties") or {}
    gen_time = _safe_html(report_data.get("generated_at_utc"))

    meta = report_data.get("metadata_analysis") or {}
    cam = meta.get("camera") or {}
    timestamps = meta.get("timestamps") or {}
    gps = meta.get("gps") or {}
    missing_meta = meta.get("missing_metadata") or []
    suspicious_meta = meta.get("suspicious_indicators") or []

    img_an = report_data.get("image_manipulation_analysis") or {}
    face_an = report_data.get("face_analysis") or {}
    web_an = report_data.get("web_search_analysis") or {}
    findings = report_data.get("findings_summary") or []
    limitations = report_data.get("limitations_and_disclaimers") or []
    integrity = report_data.get("integrity") or {}
    blockchain = report_data.get("blockchain_anchoring") or {}
    manifest = integrity.get("canonical_manifest") or {}
    tool_versions = manifest.get("tool_versions") or {}

    # GPS rendering
    gps_status = gps.get("status", "unavailable")
    gps_lat = gps.get("latitude")
    gps_lon = gps.get("longitude")
    gps_alt = gps.get("altitude")
    safe_map_url = _safe_url(gps.get("map_url"))

    if gps_status == "valid" and gps_lat is not None and gps_lon is not None:
        gps_display = f"""
        <tr><th>GPS Status</th><td><span class="badge badge-success">Valid EXIF Geolocation</span></td></tr>
        <tr><th>Latitude</th><td><code>{_safe_html(gps_lat)}</code> ({_safe_html(gps.get('latitude_ref', 'N'))})</td></tr>
        <tr><th>Longitude</th><td><code>{_safe_html(gps_lon)}</code> ({_safe_html(gps.get('longitude_ref', 'E'))})</td></tr>
        <tr><th>Altitude</th><td>{_safe_html(gps_alt)} m</td></tr>
        <tr><th>Interactive Map</th><td><a href="{safe_map_url}" target="_blank" rel="noopener noreferrer">View on Google Maps</a></td></tr>
        <tr><th>Location Notice</th><td class="text-muted">{_safe_html(gps.get('source_notice'))}</td></tr>
        """
    elif gps_status == "invalid":
        gps_display = f"""
        <tr><th>GPS Status</th><td><span class="badge badge-warning">Invalid / Out of Range</span></td></tr>
        <tr><th>Notice</th><td>{_safe_html(gps.get('message', 'GPS coordinates exceed valid bounds.'))}</td></tr>
        """
    else:
        gps_display = """
        <tr><th>GPS Status</th><td><span class="badge badge-neutral">GPS metadata unavailable</span></td></tr>
        <tr><th>Notice</th><td class="text-muted">No embedded GPS tags present in image file. Location was not inferred.</td></tr>
        """

    # Findings rows
    findings_rows = ""
    for f in findings:
        badge_cls = "badge-info"
        if f.get("level") in ("medium", "high"):
            badge_cls = "badge-warning"
        findings_rows += f"""
        <tr>
            <td><span class="badge {badge_cls}">{_safe_html(f.get('type'))}</span></td>
            <td><strong>{_safe_html(f.get('summary'))}</strong></td>
            <td>{_safe_html(f.get('details'))}</td>
        </tr>
        """

    # Limitations list
    limits_html = "".join([f"<li>{_safe_html(lim)}</li>" for lim in limitations])

    # Missing metadata list
    missing_html = ""
    for m in missing_meta:
        missing_html += f"<li><strong>{_safe_html(m.get('field'))}:</strong> {_safe_html(m.get('detail'))}</li>"

    # Suspicious indicators list
    suspicious_html = ""
    for s in suspicious_meta:
        suspicious_html += f"<li><strong>{_safe_html(s.get('indicator'))}:</strong> {_safe_html(s.get('detail'))}</li>"

    # Blockchain row
    tx_hash = blockchain.get("transaction_hash")
    safe_tx_url = _safe_url(f"https://sepolia.etherscan.io/tx/{tx_hash}") if tx_hash else None
    tx_display = (
        f'<a href="{safe_tx_url}" target="_blank" rel="noopener noreferrer"><code>{_safe_html(tx_hash)}</code></a>'
        if safe_tx_url
        else "<code>N/A (Unanchored)</code>"
    )

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Forensic Report — {ev_id}</title>
<style>
    body {{
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        color: #1e293b;
        background: #f8fafc;
        margin: 0;
        padding: 30px 20px;
        line-height: 1.5;
    }}
    .container {{
        max-width: 960px;
        margin: 0 auto;
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 40px;
        box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05);
    }}
    .header {{
        border-bottom: 2px solid #0f172a;
        padding-bottom: 16px;
        margin-bottom: 24px;
        display: flex;
        justify-content: space-between;
        align-items: flex-end;
    }}
    h1 {{ margin: 0; font-size: 24px; color: #0f172a; }}
    h2 {{ font-size: 16px; color: #1e293b; border-bottom: 1px solid #cbd5e1; padding-bottom: 6px; margin-top: 28px; margin-bottom: 12px; }}
    table {{ width: 100%; border-collapse: collapse; margin-bottom: 16px; font-size: 13px; }}
    th, td {{ padding: 8px 12px; border-bottom: 1px solid #f1f5f9; text-align: left; vertical-align: top; }}
    th {{ width: 28%; font-weight: 600; color: #475569; background: #f8fafc; }}
    code {{ font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace; font-size: 12px; word-break: break-all; color: #0369a1; }}
    .badge {{ display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; text-transform: uppercase; }}
    .badge-success {{ background: #dcfce7; color: #166534; }}
    .badge-warning {{ background: #fef3c7; color: #92400e; }}
    .badge-info {{ background: #e0f2fe; color: #0369a1; }}
    .badge-neutral {{ background: #f1f5f9; color: #475569; }}
    .callout {{ background: #fffbeb; border-left: 4px solid #f59e0b; padding: 12px 16px; font-size: 13px; margin: 16px 0; border-radius: 0 4px 4px 0; }}
    .callout-info {{ background: #f0f9ff; border-left-color: #0284c7; }}
    ul {{ margin: 6px 0; padding-left: 20px; font-size: 13px; color: #334155; }}
    li {{ margin-bottom: 4px; }}
    .text-muted {{ color: #64748b; font-size: 12px; }}
    .footer {{ margin-top: 36px; padding-top: 16px; border-top: 1px solid #e2e8f0; font-size: 11px; color: #64748b; text-align: center; }}
    @media print {{
        body {{ background: #ffffff; padding: 0; }}
        .container {{ border: none; box-shadow: none; padding: 0; }}
        a {{ text-decoration: none; color: #0f172a; }}
    }}
</style>
</head>
<body>
<div class="container">
    <div class="header">
        <div>
            <h1>FaceChain Forensics — Official Evidence Report</h1>
            <div style="font-size: 12px; color: #64748b; margin-top: 4px;">Cryptographic Integrity & Forensic Analysis</div>
        </div>
        <div style="text-align: right; font-size: 12px; color: #475569;">
            <div><strong>Evidence ID:</strong> <code>{ev_id}</code></div>
            <div><strong>Generated (UTC):</strong> {gen_time}</div>
        </div>
    </div>

    <h2>1. Evidence Identification & File Properties</h2>
    <table>
        <tr><th>Original Filename</th><td>{_safe_html(file_props.get('filename'))}</td></tr>
        <tr><th>File Format & MIME</th><td>{_safe_html(file_props.get('format'))} ({_safe_html(file_props.get('mime_type'))})</td></tr>
        <tr><th>File Size</th><td>{_safe_html(file_props.get('file_size_bytes'))} bytes ({round(float(file_props.get('file_size_bytes', 0))/1024, 1)} KB)</td></tr>
        <tr><th>Dimensions</th><td>{_safe_html(file_props.get('width'))} &times; {_safe_html(file_props.get('height'))} px</td></tr>
        <tr><th>Original SHA-256 Digest</th><td><code>{sha256}</code></td></tr>
    </table>

    <h2>2. Cryptographic Manifest & Local Integrity</h2>
    <table>
        <tr><th>Manifest Version</th><td>{_safe_html(manifest.get('version', '1.0'))}</td></tr>
        <tr><th>Manifest Canonical SHA-256</th><td><code>{_safe_html(integrity.get('manifest_hash'))}</code></td></tr>
        <tr><th>File Hash Integrity Match</th><td>{('<span class="badge badge-success">VERIFIED</span>' if integrity.get('verification_status', {}).get('file_hash_match') else '<span class="badge badge-warning">TAMPER DETECTED</span>')}</td></tr>
        <tr><th>Manifest Digest Match</th><td>{('<span class="badge badge-success">VERIFIED</span>' if integrity.get('verification_status', {}).get('manifest_hash_match') else '<span class="badge badge-warning">DIGEST MISMATCH</span>')}</td></tr>
        <tr><th>Overall Local Verdict</th><td><strong>{_safe_html(integrity.get('verification_status', {}).get('status', 'VERIFIED'))}</strong></td></tr>
    </table>

    <h2>3. EXIF Metadata & Optical Properties</h2>
    <table>
        <tr><th>Camera Hardware</th><td>{_safe_html(cam.get('make', 'Unavailable'))} {_safe_html(cam.get('model', ''))}</td></tr>
        <tr><th>Camera Lens</th><td>{_safe_html(cam.get('lens_model', 'Unavailable'))}</td></tr>
        <tr><th>Software Tag</th><td>{_safe_html(cam.get('software', 'Unavailable'))}</td></tr>
        <tr><th>Capture Timestamp (Original)</th><td>{_safe_html(timestamps.get('original', 'Unavailable'))}</td></tr>
        <tr><th>Modified Timestamp</th><td>{_safe_html(timestamps.get('modified', 'Unavailable'))}</td></tr>
        <tr><th>Photographic Settings</th><td>ISO {_safe_html((meta.get('capture_parameters') or {}).get('iso', 'N/A'))}, {_safe_html((meta.get('capture_parameters') or {}).get('exposure_time', 'N/A'))}s, f/{_safe_html((meta.get('capture_parameters') or {}).get('f_number', 'N/A'))}</td></tr>
    </table>

    <h2>4. Geolocation (GPS) Metadata Analysis</h2>
    <table>
        {gps_display}
    </table>

    <h2>5. Image Manipulation & Compression (ELA)</h2>
    <table>
        <tr><th>Analysis Method</th><td>{('JPEG Error Level Analysis (Quality: ' + _safe_html((img_an.get('parameters') or {}).get('recompression_quality', 90)) + '%)' if img_an.get('ela_applicable') else 'Lossless Format / Chunk Structure Inspection')}</td></tr>
        <tr><th>Statistical Delta (Mean / Max)</th><td>{(_safe_html((img_an.get('statistics') or {}).get('mean_error')) + ' / ' + _safe_html((img_an.get('statistics') or {}).get('max_error')) if img_an.get('statistics') else 'N/A (Lossless)')}</td></tr>
        <tr><th>High-Contrast Pixels</th><td>{(_safe_html((img_an.get('statistics') or {}).get('high_contrast_percentage')) + '%' if img_an.get('statistics') else 'N/A')}</td></tr>
        <tr><th>Encoding Scheme</th><td>Progressive: {_safe_html((img_an.get('encoding_properties') or {}).get('progressive', 'N/A'))}, Subsampling: {_safe_html((img_an.get('encoding_properties') or {}).get('subsampling', 'N/A'))}</td></tr>
        <tr><th>Methodology Notes</th><td class="text-muted">{_safe_html(img_an.get('methodology_note'))}</td></tr>
    </table>

    <h2>6. Biometric Face Analysis & Public Search</h2>
    <table>
        <tr><th>Face Detection (YuNet)</th><td>{('Detected (' + _safe_html(face_an.get('face_count', 1)) + ' face(s))' if face_an and face_an.get('face_detected') else 'No human face detected')}</td></tr>
        <tr><th>Primary Face Confidence</th><td>{(_safe_html(round(float(face_an.get('confidence') or 0)*100, 2)) + '%' if face_an and face_an.get('confidence') is not None else 'N/A')}</td></tr>
        <tr><th>Facial Embedding Model</th><td>{_safe_html(face_an.get('embedding_model', 'OpenCV SFace 128-D'))}</td></tr>
        <tr><th>Reverse Search Status</th><td>{_safe_html(web_an.get('status', 'Not Run'))}</td></tr>
        <tr><th>Public Candidate Correlation</th><td>{_safe_html((web_an.get('best_match') or {}).get('title', 'None'))}</td></tr>
    </table>

    <h2>7. Ethereum Sepolia Blockchain Anchoring</h2>
    <table>
        <tr><th>Ledger Network</th><td>{_safe_html(blockchain.get('network'))}</td></tr>
        <tr><th>Anchoring Status</th><td><span class="badge {('badge-success' if blockchain.get('status') == 'confirmed' else 'badge-neutral')}">{_safe_html(blockchain.get('status'))}</span></td></tr>
        <tr><th>Transaction Hash</th><td>{tx_display}</td></tr>
        <tr><th>Confirmed Block Number</th><td>{_safe_html(blockchain.get('block_number', 'N/A'))}</td></tr>
        <tr><th>Anchored Manifest Digest</th><td><code>{_safe_html(blockchain.get('anchored_hash', integrity.get('manifest_hash')))}</code></td></tr>
    </table>

    <h2>8. Forensic Findings & Flagged Indicators</h2>
    <table>
        <thead>
            <tr><th>Category</th><th>Indicator</th><th>Forensic Detail</th></tr>
        </thead>
        <tbody>
            {findings_rows if findings_rows else '<tr><td colspan="3" class="text-muted">No suspicious anomalies or editing suite artifacts detected.</td></tr>'}
        </tbody>
    </table>

    <h2>9. Tools & Software Environment</h2>
    <table>
        <tr><th>FaceChain Forensics Engine</th><td>v{_safe_html(tool_versions.get('facechain_forensics', '1.0.0'))}</td></tr>
        <tr><th>OpenCV Core & Models</th><td>v{_safe_html(tool_versions.get('opencv'))} (YuNet 2023mar, SFace 2021dec)</td></tr>
        <tr><th>Imaging & Runtime</th><td>Pillow v{_safe_html(tool_versions.get('pillow'))}, Python {_safe_html(tool_versions.get('python'))}</td></tr>
    </table>

    <div class="callout">
        <strong>Forensic Limitations & Legal Caveats:</strong>
        <ul>
            {limits_html}
        </ul>
    </div>

    <div class="footer">
        FaceChain Forensics &bull; Cryptographic Evidence Verification System &bull; Generated on {gen_time}
    </div>
</div>
</body>
</html>"""

    if output_path:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_content)

    return html_content


def generate_pdf_report(report_data: Dict[str, Any], output_path: Optional[str] = None) -> bytes:
    """
    Renders a formal, print-quality PDF forensic report using ReportLab.
    Ensures long hashes, tables, and sections do not overflow page margins.
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54,
    )

    styles = getSampleStyleSheet()

    # Custom typography styles
    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#0f172a"),
        spaceAfter=4,
    )

    subtitle_style = ParagraphStyle(
        "ReportSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#64748b"),
        spaceAfter=14,
    )

    section_heading_style = ParagraphStyle(
        "SectionHeading",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=15,
        textColor=colors.HexColor("#0f172a"),
        spaceBefore=12,
        spaceAfter=6,
        keepWithNext=True,
    )

    cell_label_style = ParagraphStyle(
        "CellLabel",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#475569"),
    )

    cell_value_style = ParagraphStyle(
        "CellValue",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#1e293b"),
    )

    code_style = ParagraphStyle(
        "CodeText",
        parent=styles["Normal"],
        fontName="Courier",
        fontSize=7.5,
        leading=9.5,
        textColor=colors.HexColor("#0369a1"),
    )

    notice_style = ParagraphStyle(
        "NoticeText",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7.5,
        leading=10,
        textColor=colors.HexColor("#334155"),
    )

    story = []

    # Title & Header
    ev = report_data.get("evidence", {})
    ev_id = _safe_str(ev.get("evidence_id"))
    gen_time = _safe_str(report_data.get("generated_at_utc"))

    story.append(Paragraph("FaceChain Forensics — Official Evidence Report", title_style))
    story.append(Paragraph(f"Evidence ID: {ev_id} &bull; Generated (UTC): {gen_time}", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#0f172a"), spaceAfter=12))

    # Helper for building consistent 2-column key-value tables
    col_widths = [140, 364]

    def build_kv_table(data_rows):
        formatted = []
        for label, val in data_rows:
            p_val = Paragraph(val, code_style if "<code>" in val or len(val) > 40 and " " not in val else cell_value_style)
            formatted.append([Paragraph(label, cell_label_style), p_val])
        t = Table(formatted, colWidths=col_widths)
        t.setStyle(
            TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("LINEBELOW", (0, 0), (-1, -1), 0.5, colors.HexColor("#f1f5f9")),
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f8fafc")),
            ])
        )
        return t

    # 1. Evidence Identification & File Properties
    file_props = ev.get("file_properties") or {}
    story.append(Paragraph("1. Evidence Identification & File Properties", section_heading_style))
    ev_rows = [
        ("Original Filename", _safe_str(file_props.get("filename"))),
        ("Format & MIME Type", f"{_safe_str(file_props.get('format'))} ({_safe_str(file_props.get('mime_type'))})"),
        ("File Size", f"{_safe_str(file_props.get('file_size_bytes'))} bytes ({round(float(file_props.get('file_size_bytes', 0))/1024, 1)} KB)"),
        ("Dimensions", f"{_safe_str(file_props.get('width'))} x {_safe_str(file_props.get('height'))} px"),
        ("Original SHA-256", f"<code>{_safe_str(ev.get('original_file_hash_sha256'))}</code>"),
    ]
    story.append(build_kv_table(ev_rows))

    # 2. Manifest & Integrity Verification
    integrity = report_data.get("integrity") or {}
    ver_status = integrity.get("verification_status") or {}
    story.append(Paragraph("2. Evidence Manifest & Cryptographic Integrity", section_heading_style))
    man_rows = [
        ("Manifest Version", _safe_str((integrity.get("canonical_manifest") or {}).get("version", "1.0"))),
        ("Manifest SHA-256", f"<code>{_safe_str(integrity.get('manifest_hash'))}</code>"),
        ("File Hash Match", "VERIFIED (Untouched Original)" if ver_status.get("file_hash_match") else "TAMPER DETECTED"),
        ("Manifest Digest Match", "VERIFIED (Canonical Consistency)" if ver_status.get("manifest_hash_match") else "DIGEST MISMATCH"),
        ("Overall Integrity Verdict", f"<b>{_safe_str(ver_status.get('status', 'VERIFIED'))}</b>"),
    ]
    story.append(build_kv_table(man_rows))

    # 3. EXIF Metadata & Optical Properties
    meta = report_data.get("metadata_analysis") or {}
    cam = meta.get("camera") or {}
    timestamps = meta.get("timestamps") or {}
    story.append(Paragraph("3. EXIF Metadata & Capture Parameters", section_heading_style))
    meta_rows = [
        ("Camera Hardware", f"{_safe_str(cam.get('make', 'Unavailable'))} {_safe_str(cam.get('model', ''))}"),
        ("Lens Model", _safe_str(cam.get('lens_model', "Unavailable"))),
        ("Software String", _safe_str(cam.get('software', "Unavailable"))),
        ("DateTimeOriginal", _safe_str(timestamps.get('original', "Unavailable"))),
        ("DateTime (Modified)", _safe_str(timestamps.get('modified', "Unavailable"))),
        ("Exposure Settings", f"ISO {_safe_str((meta.get('capture_parameters') or {}).get('iso', 'N/A'))}, {_safe_str((meta.get('capture_parameters') or {}).get('exposure_time', 'N/A'))}s, f/{_safe_str((meta.get('capture_parameters') or {}).get('f_number', 'N/A'))}"),
    ]
    story.append(build_kv_table(meta_rows))

    # 4. Geolocation (GPS) Metadata
    gps = meta.get("gps") or {}
    story.append(Paragraph("4. Geolocation (GPS) Metadata Analysis", section_heading_style))
    gps_st = gps.get("status", "unavailable")
    if gps_st == "valid" and gps.get("latitude") is not None:
        gps_rows = [
            ("GPS Status", "VALID (Coordinates Extracted from EXIF)"),
            ("Latitude", f"<code>{gps.get('latitude')}</code> ({gps.get('latitude_ref', 'N')})"),
            ("Longitude", f"<code>{gps.get('longitude')}</code> ({gps.get('longitude_ref', 'E')})"),
            ("Altitude", f"{gps.get('altitude', 'N/A')} m"),
            ("Google Maps URL", f"<code>{_safe_str(gps.get('map_url'))}</code>"),
            ("Location Caveat", _safe_str(gps.get("source_notice"))),
        ]
    elif gps_st == "invalid":
        gps_rows = [
            ("GPS Status", "INVALID (Coordinates Out of Geographic Range)"),
            ("Detail", _safe_str(gps.get("message"))),
        ]
    else:
        gps_rows = [
            ("GPS Status", "UNAVAILABLE"),
            ("Detail", "GPS metadata unavailable in original image. Coordinates were not inferred."),
        ]
    story.append(build_kv_table(gps_rows))

    # 5. Image Manipulation & Error Level Analysis
    img_an = report_data.get("image_manipulation_analysis") or {}
    story.append(Paragraph("5. Image Manipulation & Compression Analysis (ELA)", section_heading_style))
    stats = img_an.get("statistics")
    ela_rows = [
        ("Analysis Method", "JPEG Error Level Analysis" if img_an.get("ela_applicable") else "Lossless Structure & Chunk Analysis"),
        ("Mean / Max Error Delta", f"{stats.get('mean_error', 'N/A')} / {stats.get('max_error', 'N/A')}" if stats else "N/A (Lossless)"),
        ("High-Contrast Pixels", f"{stats.get('high_contrast_percentage', 'N/A')}%" if stats else "N/A"),
        ("Encoding Properties", f"Progressive: {(img_an.get('encoding_properties') or {}).get('progressive', 'N/A')}, Subsampling: {(img_an.get('encoding_properties') or {}).get('subsampling', 'N/A')}"),
        ("Observable Findings", "; ".join(img_an.get("observable_indicators", ["None"]))),
    ]
    story.append(build_kv_table(ela_rows))

    # 6. Biometric Face Analysis & Public Search
    face_an = report_data.get("face_analysis") or {}
    web_an = report_data.get("web_search_analysis") or {}
    story.append(Paragraph("6. Biometric Face Verification & Public Search", section_heading_style))
    face_rows = [
        ("YuNet Face Detection", f"Detected ({face_an.get('face_count', 1)} face(s))" if face_an and face_an.get("face_detected") else "No human faces detected"),
        ("Detection Confidence", f"{round(float(face_an.get('confidence', 0))*100, 2)}%" if face_an and face_an.get("confidence") else "N/A"),
        ("Embedding Architecture", _safe_str(face_an.get("embedding_model", "OpenCV SFace 128-D Vector") if face_an else "N/A (Disabled)")),
        ("Public Web Search", _safe_str(web_an.get("status", "Not Run"))),
        ("Candidate Match Title", _safe_str((web_an.get("best_match") or {}).get("title", "None"))),
    ]
    story.append(build_kv_table(face_rows))

    # 7. Ethereum Sepolia Blockchain Ledger
    blockchain = report_data.get("blockchain_anchoring", {})
    story.append(Paragraph("7. Ethereum Sepolia Blockchain Ledger", section_heading_style))
    bc_rows = [
        ("Network", _safe_str(blockchain.get("network"))),
        ("Ledger State", _safe_str(blockchain.get("status", "unanchored")).upper()),
        ("Transaction Hash", f"<code>{_safe_str(blockchain.get('transaction_hash', 'N/A'))}</code>"),
        ("Block Number", _safe_str(blockchain.get("block_number", "N/A"))),
        ("Anchored Digest", f"<code>{_safe_str(blockchain.get('anchored_hash', integrity.get('manifest_hash')))}</code>"),
    ]
    story.append(build_kv_table(bc_rows))

    # 8. Tools & Software Environment
    manifest = integrity.get("canonical_manifest", {})
    tools = manifest.get("tool_versions", {})
    story.append(Paragraph("8. Tool Versions & Forensic Environment", section_heading_style))
    env_rows = [
        ("FaceChain Engine", f"v{_safe_str(tools.get('facechain_forensics', '1.0.0'))}"),
        ("Computer Vision", f"OpenCV v{_safe_str(tools.get('opencv'))} (YuNet 2023mar, SFace 2021dec)"),
        ("Runtime & Imaging", f"Pillow v{_safe_str(tools.get('pillow'))}, Python {_safe_str(tools.get('python'))}"),
    ]
    story.append(build_kv_table(env_rows))

    # 9. Forensic Limitations & Caveats
    story.append(Spacer(1, 10))
    story.append(Paragraph("Forensic Limitations & Investigative Notice", section_heading_style))
    for lim in report_data.get("limitations_and_disclaimers", []):
        story.append(Paragraph(f"&bull; {_safe_str(lim)}", notice_style))
        story.append(Spacer(1, 2))

    # Build PDF with NumberedCanvas
    doc.build(story, canvasmaker=NumberedCanvas)
    pdf_bytes = buf.getvalue()

    if output_path:
        with open(output_path, "wb") as f:
            f.write(pdf_bytes)

    return pdf_bytes
