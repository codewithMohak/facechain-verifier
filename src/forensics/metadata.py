import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
from PIL import Image, ExifTags

EDITING_SOFTWARE_KEYWORDS = [
    "photoshop",
    "lightroom",
    "gimp",
    "canva",
    "snapseed",
    "pixelmator",
    "affinity",
    "paint.net",
    "vsco",
    "facetune",
    "fotor",
    "pixlr",
    "picsart",
    "meitu",
]


def _format_rational(val: Any) -> Any:
    """Format IFDRational or tuple to human-readable float/string. Returns None on divide-by-zero."""
    if hasattr(val, "numerator") and hasattr(val, "denominator"):
        if val.denominator == 0:
            return None
        return float(val.numerator) / float(val.denominator)
    if isinstance(val, tuple) and len(val) == 2:
        denom = val[1]
        return float(val[0]) / float(denom) if denom != 0 else None
    return val


def _convert_gps_to_decimal(coords: Any, ref: Optional[str]) -> Optional[float]:
    """Convert EXIF GPS tuple of rationals/numbers (degrees, minutes, seconds) to decimal degrees."""
    if not coords or len(coords) < 3:
        return None
    try:
        r0 = _format_rational(coords[0])
        r1 = _format_rational(coords[1])
        r2 = _format_rational(coords[2])
        if r0 is None or r1 is None or r2 is None:
            return None

        deg = float(r0)
        minute = float(r1)
        sec = float(r2)

        # Basic component validation
        if deg < 0 or minute < 0 or sec < 0:
            return None
        if minute >= 60.0 or sec >= 60.0:
            return None

        decimal = deg + (minute / 60.0) + (sec / 3600.0)
        ref_norm = str(ref).strip().upper() if ref else ""
        if ref_norm in ("S", "W"):
            decimal = -decimal
        return round(decimal, 6)
    except Exception:
        return None


def parse_gps_coordinates(gps_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parses, converts, and validates GPS EXIF metadata:
    - Converts DMS to signed decimal degrees.
    - Applies hemisphere directions (N/S, E/W).
    - Validates latitude in [-90, 90] and longitude in [-180, 180].
    - Categorizes status as 'valid', 'invalid', or 'unavailable'.
    """
    if not gps_dict:
        return {
            "status": "unavailable",
            "available": False,
            "latitude": None,
            "longitude": None,
            "altitude": None,
            "map_url": None,
            "message": "GPS metadata unavailable",
            "source_notice": "Coordinates represent embedded EXIF metadata, not independently verified physical location.",
        }

    raw_lat = gps_dict.get("GPSLatitude")
    lat_ref = gps_dict.get("GPSLatitudeRef")
    raw_lon = gps_dict.get("GPSLongitude")
    lon_ref = gps_dict.get("GPSLongitudeRef")
    raw_alt = gps_dict.get("GPSAltitude")
    alt_ref = gps_dict.get("GPSAltitudeRef")

    if raw_lat is None or raw_lon is None:
        return {
            "status": "unavailable",
            "available": False,
            "latitude": None,
            "longitude": None,
            "altitude": None,
            "map_url": None,
            "message": "GPS metadata unavailable",
            "source_notice": "Coordinates represent embedded EXIF metadata, not independently verified physical location.",
        }

    lat_ref_str = str(lat_ref).strip().upper() if lat_ref else "N"
    lon_ref_str = str(lon_ref).strip().upper() if lon_ref else "E"

    dec_lat = _convert_gps_to_decimal(raw_lat, lat_ref_str)
    dec_lon = _convert_gps_to_decimal(raw_lon, lon_ref_str)

    # Range validation: latitude in [-90, 90], longitude in [-180, 180]
    lat_valid = dec_lat is not None and -90.0 <= dec_lat <= 90.0
    lon_valid = dec_lon is not None and -180.0 <= dec_lon <= 180.0

    if not lat_valid or not lon_valid:
        return {
            "status": "invalid",
            "available": False,
            "latitude": None,
            "longitude": None,
            "altitude": None,
            "map_url": None,
            "message": "Invalid GPS coordinates out of geographical range [-90, 90] / [-180, 180]",
            "source_notice": "Coordinates represent embedded EXIF metadata, not independently verified physical location.",
        }

    dec_alt = None
    if raw_alt is not None:
        try:
            alt_val = float(_format_rational(raw_alt))
            if alt_ref and str(alt_ref) == "1":
                alt_val = -alt_val
            dec_alt = round(alt_val, 2)
        except Exception:
            dec_alt = None

    return {
        "status": "valid",
        "available": True,
        "latitude": dec_lat,
        "longitude": dec_lon,
        "altitude": dec_alt,
        "latitude_ref": lat_ref_str,
        "longitude_ref": lon_ref_str,
        "map_url": f"https://www.google.com/maps?q={dec_lat},{dec_lon}",
        "message": f"GPS coordinates extracted from EXIF metadata: {dec_lat}, {dec_lon}",
        "source_notice": "Coordinates represent embedded EXIF metadata, not independently verified physical location.",
    }


def extract_metadata(image_path: str) -> Dict[str, Any]:
    """
    Extracts metadata from an image file:
    - Basic image attributes
    - EXIF tags and IFDs (Exif, GPSInfo)
    - Camera & lens details
    - Timestamps
    - GPS geolocation (decimal degrees)
    - Missing metadata vs suspicious indicators
    - Forensic disclaimers
    """
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image file not found: {image_path}")

    path_obj = Path(image_path)
    file_stat = path_obj.stat()

    raw_exif_dict: Dict[str, Any] = {}
    gps_dict: Dict[str, Any] = {}
    exif_ifd_dict: Dict[str, Any] = {}

    dimensions = (0, 0)
    img_format = "UNKNOWN"
    img_mode = "UNKNOWN"
    has_icc_profile = False

    with Image.open(image_path) as img:
        dimensions = img.size
        img_format = img.format.upper() if img.format else "UNKNOWN"
        img_mode = img.mode
        has_icc_profile = "icc_profile" in img.info

        exif_obj = img.getexif() if hasattr(img, "getexif") else None
        if exif_obj:
            # Primary EXIF tags
            for tag_id, val in exif_obj.items():
                tag_name = ExifTags.TAGS.get(tag_id, f"Tag_{tag_id}")
                if isinstance(val, bytes):
                    try:
                        val = val.decode("utf-8", errors="replace").strip("\x00")
                    except Exception:
                        val = f"<bytes: len={len(val)}>"
                raw_exif_dict[tag_name] = _format_rational(val)

            # Sub-IFD: Exif
            try:
                exif_sub = exif_obj.get_ifd(ExifTags.IFD.Exif)
                for tag_id, val in exif_sub.items():
                    tag_name = ExifTags.TAGS.get(tag_id, f"ExifTag_{tag_id}")
                    if isinstance(val, bytes):
                        try:
                            val = val.decode("utf-8", errors="replace").strip("\x00")
                        except Exception:
                            val = f"<bytes: len={len(val)}>"
                    exif_ifd_dict[tag_name] = _format_rational(val)
            except Exception:
                pass

            # Sub-IFD: GPSInfo
            try:
                gps_sub = exif_obj.get_ifd(ExifTags.IFD.GPSInfo)
                for tag_id, val in gps_sub.items():
                    tag_name = ExifTags.GPSTAGS.get(tag_id, f"GPSTag_{tag_id}")
                    gps_dict[tag_name] = val
            except Exception:
                pass

    # Merge main and sub-ifd for convenient lookup
    all_tags = {**raw_exif_dict, **exif_ifd_dict}

    # Extract camera parameters
    make = all_tags.get("Make")
    model = all_tags.get("Model")
    software = all_tags.get("Software")
    lens_make = all_tags.get("LensMake")
    lens_model = all_tags.get("LensModel")

    # Timestamps
    dt_original = all_tags.get("DateTimeOriginal")
    dt_digitized = all_tags.get("DateTimeDigitized")
    dt_modified = all_tags.get("DateTime")

    # Photographic parameters
    exposure_time = all_tags.get("ExposureTime")
    f_number = all_tags.get("FNumber")
    iso = all_tags.get("ISOSpeedRatings") or all_tags.get("PhotographicSensitivity")
    focal_length = all_tags.get("FocalLength")
    flash = all_tags.get("Flash")
    white_balance = all_tags.get("WhiteBalance")

    # GPS coordinates
    gps_info = parse_gps_coordinates(gps_dict)

    # Analysis of missing metadata vs suspicious metadata
    missing_items: List[Dict[str, str]] = []
    suspicious_indicators: List[Dict[str, str]] = []

    # Check for missing camera / capture metadata
    if not make and not model:
        missing_items.append({
            "field": "Camera Make/Model",
            "category": "unavailable",
            "detail": "No camera hardware identifiers found in EXIF tags (common for stripped or web-shared media).",
        })

    if not dt_original:
        missing_items.append({
            "field": "DateTimeOriginal",
            "category": "unavailable",
            "detail": "Original capture timestamp is absent.",
        })

    if gps_info["status"] == "unavailable":
        missing_items.append({
            "field": "GPS Geolocation",
            "category": "unavailable",
            "detail": "GPS metadata unavailable",
        })
    elif gps_info["status"] == "invalid":
        suspicious_indicators.append({
            "indicator": "Invalid / Out-of-Range GPS Metadata",
            "severity": "medium",
            "detail": gps_info["message"],
        })

    if not lens_model:
        missing_items.append({
            "field": "Lens Information",
            "category": "unavailable",
            "detail": "Lens model / optical hardware parameters are not recorded.",
        })

    # Check for suspicious metadata / inconsistencies
    if software:
        software_lower = str(software).lower()
        for kw in EDITING_SOFTWARE_KEYWORDS:
            if kw in software_lower:
                suspicious_indicators.append({
                    "indicator": "Editing Software String Detected",
                    "severity": "medium",
                    "detail": (
                        f"Software tag '{software}' contains editing keyword '{kw}', "
                        "indicating post-processing or re-export through an image editor."
                    ),
                })
                break

    # Timestamp discrepancies
    if dt_original and dt_modified and str(dt_original) != str(dt_modified):
        suspicious_indicators.append({
            "indicator": "Capture vs Modification Timestamp Mismatch",
            "severity": "low",
            "detail": (
                f"DateTimeOriginal ({dt_original}) does not match DateTime ({dt_modified}), "
                "indicating the file was modified or re-saved at a later time."
            ),
        })

    has_exif = bool(raw_exif_dict or exif_ifd_dict or gps_dict)

    return {
        "format": img_format,
        "width": dimensions[0],
        "height": dimensions[1],
        "color_mode": img_mode,
        "has_icc_profile": has_icc_profile,
        "file_size_bytes": file_stat.st_size,
        "has_exif": has_exif,
        "camera": {
            "make": make,
            "model": model,
            "software": software,
            "lens_make": lens_make,
            "lens_model": lens_model,
        },
        "capture_parameters": {
            "exposure_time": exposure_time,
            "f_number": f_number,
            "iso": iso,
            "focal_length": focal_length,
            "flash": flash,
            "white_balance": white_balance,
        },
        "timestamps": {
            "original": dt_original,
            "digitized": dt_digitized,
            "modified": dt_modified,
            "filesystem_ctime": datetime.fromtimestamp(file_stat.st_ctime).isoformat(),
            "filesystem_mtime": datetime.fromtimestamp(file_stat.st_mtime).isoformat(),
        },
        "gps": gps_info,
        "missing_metadata": missing_items,
        "suspicious_indicators": suspicious_indicators,
        "raw_exif_count": len(all_tags),
        "disclaimer": (
            "Forensic Notice: Metadata availability varies significantly across cameras, "
            "platforms, and communication channels. Stripped metadata is routine for social media "
            "and messaging applications. Metadata presence does not guarantee authenticity, "
            "nor does absence confirm tampering."
        ),
    }
