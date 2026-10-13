import io
import os
from pathlib import Path
from typing import Dict, Any, Optional
import numpy as np
from PIL import Image, ImageChops


def generate_ela(
    image_path: str,
    output_path: str,
    quality: int = 90,
    scale: int = 15,
) -> Dict[str, Any]:
    """
    Performs image manipulation analysis:
    - For JPEG: Computes Error Level Analysis (ELA) by re-saving at known quality,
      calculates statistical differences, scales the visualization, and extracts
      encoding properties.
    - For PNG: Explains why JPEG ELA is not methodologically valid for lossless formats,
      and performs lossless format/alpha channel inspection.
    - For WebP: Analyzes WebP compression format and characteristics.
    """
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Source image not found: {image_path}")

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    with Image.open(image_path) as img:
        img_format = img.format.upper() if img.format else "UNKNOWN"
        width, height = img.size
        mode = img.mode

        if img_format == "JPEG":
            return _analyze_jpeg_ela(img, output_path, quality, scale)
        elif img_format == "PNG":
            return _analyze_png(img, output_path)
        elif img_format == "WEBP":
            return _analyze_webp(img, output_path, quality, scale)
        else:
            return {
                "format": img_format,
                "ela_applicable": False,
                "ela_path": None,
                "methodology_note": f"Format '{img_format}' does not support standard JPEG Error Level Analysis.",
                "disclaimer": (
                    "Investigative notice: Error analysis is format-dependent. "
                    "Results are investigative indicators, not proof of manipulation."
                ),
            }


def _analyze_jpeg_ela(
    img: Image.Image,
    output_path: str,
    quality: int,
    scale: int,
) -> Dict[str, Any]:
    """Perform actual Error Level Analysis on a JPEG image."""
    # Convert to RGB for standardized comparison
    orig_rgb = img.convert("RGB")
    orig_arr = np.array(orig_rgb, dtype=np.float32)

    # Recompress at specified quality level in-memory
    buffer = io.BytesIO()
    orig_rgb.save(buffer, format="JPEG", quality=quality)
    buffer.seek(0)
    recompressed = Image.open(buffer).convert("RGB")
    recomp_arr = np.array(recompressed, dtype=np.float32)

    # Calculate absolute difference
    diff_arr = np.abs(orig_arr - recomp_arr)

    # Compute statistical metrics on difference
    mean_error = float(np.mean(diff_arr))
    max_error = float(np.max(diff_arr))
    std_error = float(np.std(diff_arr))
    median_error = float(np.median(diff_arr))

    # Calculate ratio of high error pixels (threshold > 10 in unscaled difference)
    high_contrast_pixels = float(np.sum(diff_arr > 10)) / float(diff_arr.size) * 100.0

    # Scale visualization for human inspection
    scaled_diff = np.clip(diff_arr * scale, 0, 255).astype(np.uint8)
    ela_image = Image.fromarray(scaled_diff)
    ela_image.save(output_path, format="JPEG", quality=95)

    # Extract JPEG encoding properties
    progressive = bool(img.info.get("progressive", False))
    subsampling = img.info.get("subsampling", "unknown")
    quantization_present = bool(getattr(img, "quantization", None))

    # Evaluate observable indicators
    indicators = []
    if high_contrast_pixels > 15.0:
        indicators.append(
            "Elevated error level variance detected (>15% high-contrast delta pixels). "
            "May indicate high-frequency details, sharp edges, or multi-generation compression."
        )
    else:
        indicators.append(
            "Error level variance is within normal uniform compression bounds across surfaces."
        )

    if progressive:
        indicators.append("Progressive JPEG encoding detected (common in web-optimized imagery).")

    return {
        "format": "JPEG",
        "ela_applicable": True,
        "ela_path": output_path,
        "parameters": {
            "recompression_quality": quality,
            "display_scale": scale,
        },
        "statistics": {
            "mean_error": round(mean_error, 4),
            "max_error": round(max_error, 4),
            "std_error": round(std_error, 4),
            "median_error": round(median_error, 4),
            "high_contrast_percentage": round(high_contrast_pixels, 2),
        },
        "encoding_properties": {
            "progressive": progressive,
            "subsampling": str(subsampling),
            "quantization_tables_present": quantization_present,
        },
        "observable_indicators": indicators,
        "methodology_note": (
            "JPEG Error Level Analysis visualizes the difference between the image and a re-saved copy. "
            "Higher error levels highlight areas saved at different compression rates or containing "
            "sharp high-frequency transitions."
        ),
        "disclaimer": (
            "Forensic Notice: Error Level Analysis results are investigative indicators, "
            "NOT definitive proof of manipulation. Natural edges, varying surface textures, "
            "and camera sensor noise also produce elevated error levels."
        ),
    }


def _analyze_png(img: Image.Image, output_path: str) -> Dict[str, Any]:
    """Analyze PNG lossless structure, chunks, and transparency."""
    mode = img.mode
    has_alpha = mode in ("RGBA", "LA") or "transparency" in img.info

    alpha_stats = None
    if has_alpha:
        try:
            alpha_channel = np.array(img.split()[-1])
            fully_transparent = float(np.sum(alpha_channel == 0)) / float(alpha_channel.size) * 100.0
            fully_opaque = float(np.sum(alpha_channel == 255)) / float(alpha_channel.size) * 100.0
            partial_transparency = 100.0 - fully_transparent - fully_opaque

            alpha_stats = {
                "has_alpha_channel": True,
                "fully_opaque_pct": round(fully_opaque, 2),
                "fully_transparent_pct": round(fully_transparent, 2),
                "semi_transparent_pct": round(partial_transparency, 2),
            }
        except Exception:
            alpha_stats = {"has_alpha_channel": True}
    else:
        alpha_stats = {"has_alpha_channel": False}

    # Inspect PNG chunks and text metadata
    text_chunks = {}
    if hasattr(img, "text") and img.text:
        text_chunks = {k: str(v) for k, v in img.text.items()}

    info_keys = [k for k in img.info.keys() if k != "icc_profile"]

    indicators = [
        "Lossless PNG format: Standard DCT-based JPEG Error Level Analysis is not methodologically valid.",
    ]
    if has_alpha and alpha_stats.get("semi_transparent_pct", 0) > 0:
        indicators.append(
            f"Alpha channel contains semi-transparent gradients ({alpha_stats['semi_transparent_pct']}%), "
            "consistent with digital cutout, alpha blending, or composited elements."
        )
    elif has_alpha:
        indicators.append("Alpha channel present with binary opacity distribution.")

    return {
        "format": "PNG",
        "ela_applicable": False,
        "ela_path": None,
        "lossless_analysis": {
            "color_mode": mode,
            "alpha_properties": alpha_stats,
            "png_chunks_detected": info_keys,
            "text_metadata_entries": text_chunks,
            "interlaced": bool(img.info.get("interlace", False)),
        },
        "observable_indicators": indicators,
        "methodology_note": (
            "PNG utilizes lossless DEFLATE compression rather than lossy DCT quantization. "
            "Applying JPEG recompression to PNG creates synthetic re-encoding artifacts that do "
            "not reflect the image's original compression history. Analysis focuses on chunk "
            "structures and alpha-channel composition."
        ),
        "disclaimer": (
            "Forensic Notice: Lossless structural indicators are investigative properties. "
            "They do not provide an automated authenticity verdict."
        ),
    }


def _analyze_webp(
    img: Image.Image,
    output_path: str,
    quality: int,
    scale: int,
) -> Dict[str, Any]:
    """Analyze WebP format characteristics."""
    mode = img.mode
    has_alpha = mode in ("RGBA", "LA")
    is_animated = bool(getattr(img, "is_animated", False))

    indicators = [
        "WebP format detected: WebP supports both lossy VP8 and lossless VP8L encoding.",
    ]
    if is_animated:
        indicators.append("Animated WebP container detected.")

    return {
        "format": "WEBP",
        "ela_applicable": False,
        "ela_path": None,
        "webp_properties": {
            "mode": mode,
            "has_alpha": has_alpha,
            "is_animated": is_animated,
            "frame_count": getattr(img, "n_frames", 1),
        },
        "observable_indicators": indicators,
        "methodology_note": (
            "Standard JPEG Error Level Analysis is calibrated for JPEG 8x8 DCT quantization matrices. "
            "WebP employs VP8 intra-prediction block transforms (lossy) or VP8L spatial transform filters (lossless), "
            "so standard JPEG ELA metrics are not directly applicable."
        ),
        "disclaimer": (
            "Forensic Notice: Format properties are provided as investigative context. "
            "No automated authenticity score is applied."
        ),
    }
