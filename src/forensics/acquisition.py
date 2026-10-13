import hashlib
import io
import os
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Tuple
from PIL import Image, UnidentifiedImageError

SUPPORTED_MIME_TYPES = {
    "image/jpeg": [".jpg", ".jpeg"],
    "image/png": [".png"],
    "image/webp": [".webp"],
}

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
DEFAULT_MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024  # 20 MB


class AcquisitionError(ValueError):
    """Raised when evidence acquisition validation fails."""
    pass


def validate_and_inspect_image(
    file_bytes: bytes,
    filename: str,
    max_size_bytes: int = DEFAULT_MAX_FILE_SIZE_BYTES,
) -> Dict[str, Any]:
    """
    Validate uploaded image data:
    1. Size within limit.
    2. Non-empty.
    3. Extension supported.
    4. Decode with Pillow to confirm genuine image data and valid format.
    """
    if not file_bytes:
        raise AcquisitionError("Uploaded file is empty (0 bytes).")

    if len(file_bytes) > max_size_bytes:
        max_mb = max_size_bytes / (1024 * 1024)
        raise AcquisitionError(
            f"File size exceeds maximum allowed threshold of {max_mb:.1f} MB."
        )

    # Sanitize and validate filename / extension
    raw_ext = Path(filename).suffix.lower()
    if raw_ext not in SUPPORTED_EXTENSIONS:
        raise AcquisitionError(
            f"Unsupported file extension '{raw_ext}'. "
            f"Supported extensions: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )

    # Decode image to verify genuine image content
    try:
        with Image.open(io.BytesIO(file_bytes)) as img:
            img_format = img.format.upper() if img.format else "UNKNOWN"
            width, height = img.size
            mode = img.mode

            if width <= 0 or height <= 0:
                raise AcquisitionError(f"Invalid image dimensions: {width}x{height}")

            # Verify format matches supported types
            expected_formats = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}
            if img_format not in expected_formats:
                raise AcquisitionError(
                    f"Decoded image format '{img_format}' is not supported. "
                    "Only JPEG, PNG, and WebP are allowed."
                )

            mime_type = expected_formats[img_format]

            return {
                "width": int(width),
                "height": int(height),
                "format": img_format,
                "color_mode": mode,
                "mime_type": mime_type,
            }
    except UnidentifiedImageError as err:
        raise AcquisitionError(
            f"File content could not be decoded as a valid image: {err}"
        ) from err
    except Exception as err:
        if isinstance(err, AcquisitionError):
            raise
        raise AcquisitionError(f"Image decoding failed: {err}") from err


def compute_sha256(data: bytes) -> str:
    """Compute SHA-256 digest of raw byte content."""
    return hashlib.sha256(data).hexdigest()


def acquire_evidence(
    file_bytes: bytes,
    filename: str,
    storage_root: str = "storage/evidence",
    max_size_bytes: int = DEFAULT_MAX_FILE_SIZE_BYTES,
) -> Dict[str, Any]:
    """
    Acquires new evidence:
    - Validates file
    - Generates unique evidence ID
    - Calculates SHA-256 hash of original file immediately
    - Preserves unchanged original in dedicated directory
    - Creates a separate working copy for forensic analysis
    - Records UTC acquisition timestamp
    """
    inspection = validate_and_inspect_image(file_bytes, filename, max_size_bytes)
    sha256_hash = compute_sha256(file_bytes)
    acquisition_utc = datetime.now(timezone.utc).isoformat()

    # Generate unique evidence ID (safe alphanumeric)
    evidence_id = f"ev_{uuid.uuid4().hex[:12]}"

    # Prepare storage directory
    evidence_dir = Path(storage_root) / evidence_id
    evidence_dir.mkdir(parents=True, exist_ok=True)

    # Determine extension
    ext = Path(filename).suffix.lower()
    if not ext:
        ext_map = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}
        ext = ext_map.get(inspection["format"], ".bin")

    original_path = evidence_dir / f"original{ext}"
    working_path = evidence_dir / f"working{ext}"

    # Write original unchanged
    with open(original_path, "wb") as f:
        f.write(file_bytes)

    # Make working copy
    shutil.copyfile(original_path, working_path)

    # Sanitize original filename (keep basename only)
    safe_filename = Path(filename).name

    return {
        "evidence_id": evidence_id,
        "original_filename": safe_filename,
        "file_size_bytes": len(file_bytes),
        "mime_type": inspection["mime_type"],
        "format": inspection["format"],
        "width": inspection["width"],
        "height": inspection["height"],
        "color_mode": inspection["color_mode"],
        "sha256": sha256_hash,
        "acquired_at_utc": acquisition_utc,
        "original_path": str(original_path),
        "working_path": str(working_path),
        "storage_dir": str(evidence_dir),
    }
