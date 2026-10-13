import json
import sqlite3
import os
from pathlib import Path
from typing import Dict, Any, List, Optional

DEFAULT_DB_PATH = "data/forensics.db"


def get_db_connection(db_path: str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Create and return a configured SQLite connection."""
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str = DEFAULT_DB_PATH) -> None:
    """Initialize the SQLite database schema."""
    with get_db_connection(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS evidence (
                id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                file_size INTEGER NOT NULL,
                mime_type TEXT NOT NULL,
                original_hash TEXT NOT NULL,
                original_path TEXT NOT NULL,
                working_path TEXT NOT NULL,
                ela_path TEXT,
                face_crop_path TEXT,
                created_at TEXT NOT NULL,
                analyzed_at TEXT,
                status TEXT NOT NULL DEFAULT 'acquired',
                metadata_json TEXT,
                image_analysis_json TEXT,
                face_analysis_json TEXT,
                web_search_json TEXT,
                manifest_json TEXT,
                manifest_hash TEXT,
                report_path TEXT,
                blockchain_status TEXT NOT NULL DEFAULT 'unanchored',
                blockchain_tx_hash TEXT,
                blockchain_block_number INTEGER,
                blockchain_anchored_at TEXT,
                blockchain_error TEXT
            )
            """
        )
        conn.commit()


def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    """Convert an SQLite Row to a Python dictionary, decoding JSON columns."""
    d = dict(row)
    json_fields = [
        "metadata_json",
        "image_analysis_json",
        "face_analysis_json",
        "web_search_json",
        "manifest_json",
    ]
    for field in json_fields:
        if d.get(field):
            try:
                d[field[:-5]] = json.loads(d[field])
            except Exception:
                d[field[:-5]] = None
        else:
            d[field[:-5]] = None
    return d


def insert_evidence(evidence: Dict[str, Any], db_path: str = DEFAULT_DB_PATH) -> None:
    """Insert a newly acquired evidence record."""
    init_db(db_path)
    with get_db_connection(db_path) as conn:
        conn.execute(
            """
            INSERT INTO evidence (
                id, filename, file_size, mime_type, original_hash,
                original_path, working_path, created_at, status, blockchain_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                evidence["evidence_id"],
                evidence["original_filename"],
                evidence["file_size_bytes"],
                evidence["mime_type"],
                evidence["sha256"],
                evidence["original_path"],
                evidence["working_path"],
                evidence["acquired_at_utc"],
                "acquired",
                "unanchored",
            ),
        )
        conn.commit()


def update_evidence(
    evidence_id: str,
    updates: Dict[str, Any],
    db_path: str = DEFAULT_DB_PATH,
) -> None:
    """Update an evidence record with new analysis, manifest, or blockchain state."""
    init_db(db_path)
    allowed_columns = {
        "status",
        "analyzed_at",
        "ela_path",
        "face_crop_path",
        "metadata_json",
        "image_analysis_json",
        "face_analysis_json",
        "web_search_json",
        "manifest_json",
        "manifest_hash",
        "report_path",
        "blockchain_status",
        "blockchain_tx_hash",
        "blockchain_block_number",
        "blockchain_anchored_at",
        "blockchain_error",
    }

    set_clauses = []
    params = []

    for k, v in updates.items():
        if k in allowed_columns:
            set_clauses.append(f"{k} = ?")
            if isinstance(v, (dict, list)):
                params.append(json.dumps(v))
            else:
                params.append(v)

    if not set_clauses:
        return

    params.append(evidence_id)
    query = f"UPDATE evidence SET {', '.join(set_clauses)} WHERE id = ?"

    with get_db_connection(db_path) as conn:
        conn.execute(query, params)
        conn.commit()


def get_evidence(
    evidence_id: str,
    db_path: str = DEFAULT_DB_PATH,
) -> Optional[Dict[str, Any]]:
    """Fetch an evidence record by ID."""
    init_db(db_path)
    with get_db_connection(db_path) as conn:
        cursor = conn.execute("SELECT * FROM evidence WHERE id = ?", (evidence_id,))
        row = cursor.fetchone()
        return _row_to_dict(row) if row else None


def list_evidence(
    limit: int = 50,
    offset: int = 0,
    db_path: str = DEFAULT_DB_PATH,
) -> List[Dict[str, Any]]:
    """Fetch recent evidence records ordered by creation date."""
    init_db(db_path)
    with get_db_connection(db_path) as conn:
        cursor = conn.execute(
            "SELECT * FROM evidence ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        )
        rows = cursor.fetchall()
        return [_row_to_dict(r) for r in rows]
