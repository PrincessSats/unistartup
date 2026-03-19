"""
Sync S3/image utilities for forensics_image_metadata task type.

All functions here are synchronous and intended to run in threads via
asyncio.to_thread() from async callers.
"""
from __future__ import annotations

import io
import random
import struct
import logging
from typing import Optional

logger = logging.getLogger(__name__)

VALID_HIDE_IN: frozenset[str] = frozenset({
    "exif_image_description",
    "exif_user_comment",
    "xmp_description",
    "jpeg_comment",
    "exif_artist",
    "exif_copyright",
})

_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff", ".tif"}


class ForensicsError(RuntimeError):
    pass


def _get_task_s3_client():
    from app.config import settings
    from app.services.storage import get_s3_client
    return get_s3_client(
        access_key=settings.s3_task_access_key,
        secret_key=settings.s3_task_secret_key,
    )


def _task_bucket() -> str:
    from app.config import settings
    return settings.s3_task_bucket_name


def list_stock_images() -> list[str]:
    """List all image keys under forensic_stock/ in the task S3 bucket."""
    client = _get_task_s3_client()
    bucket = _task_bucket()
    try:
        resp = client.list_objects_v2(Bucket=bucket, Prefix="forensic_stock/")
    except Exception as exc:
        raise ForensicsError(f"Forensics: no stock images in forensic_stock/ — {exc}") from exc

    keys = []
    for obj in resp.get("Contents", []):
        key: str = obj["Key"]
        lower = key.lower()
        if any(lower.endswith(ext) for ext in _IMAGE_EXTENSIONS):
            keys.append(key)

    if not keys:
        raise ForensicsError(
            f"Forensics: no stock images in forensic_stock/ — bucket={bucket!r} returned 0 image objects"
        )
    return keys


def pick_random_stock_image() -> str:
    """Pick a random stock image key from S3."""
    keys = list_stock_images()
    return random.choice(keys)


def download_image(s3_key: str) -> bytes:
    """Download image bytes from the task S3 bucket."""
    client = _get_task_s3_client()
    bucket = _task_bucket()
    try:
        resp = client.get_object(Bucket=bucket, Key=s3_key)
        return resp["Body"].read()
    except Exception as exc:
        raise ForensicsError(f"Forensics: download failed for {s3_key} — {exc}") from exc


def inject_metadata(
    image_bytes: bytes,
    flag: str,
    hide_in: str,
    decoy_metadata: dict,
) -> bytes:
    """
    Open image with Pillow, inject flag into the specified metadata field,
    add decoy EXIF tags, and return JPEG bytes.
    """
    if hide_in not in VALID_HIDE_IN:
        raise ForensicsError(f"invalid hide_in: {hide_in!r}")

    try:
        from PIL import Image
        img = Image.open(io.BytesIO(image_bytes))
        img = img.convert("RGB")
    except Exception as exc:
        raise ForensicsError(f"Forensics: image processing failed — {exc}") from exc

    try:
        output = io.BytesIO()

        if hide_in == "jpeg_comment":
            exif_bytes = _build_exif_with_decoys(decoy_metadata)
            _save_jpeg_with_comment(img, output, flag, exif_bytes)
        elif hide_in == "xmp_description":
            exif_bytes = _build_exif_with_decoys(decoy_metadata)
            xmp_bytes = _build_xmp_with_flag(flag)
            img.save(output, format="JPEG", quality=90, exif=exif_bytes)
            raw = output.getvalue()
            output = io.BytesIO(_inject_xmp(raw, xmp_bytes))
        else:
            exif_bytes = _build_exif_with_flag_and_decoys(hide_in, flag, decoy_metadata)
            img.save(output, format="JPEG", quality=90, exif=exif_bytes)

        return output.getvalue()

    except ForensicsError:
        raise
    except Exception as exc:
        raise ForensicsError(f"Forensics: metadata injection into {hide_in} failed — {exc}") from exc


def upload_image(image_bytes: bytes, batch_id: str, variant_id: str) -> str:
    """Upload image bytes to forensics_artifacts/{batch_id}/{variant_id}.jpg, return s3_key."""
    client = _get_task_s3_client()
    bucket = _task_bucket()
    target_key = f"forensics_artifacts/{batch_id}/{variant_id}.jpg"
    try:
        client.put_object(
            Bucket=bucket,
            Key=target_key,
            Body=image_bytes,
            ContentType="image/jpeg",
        )
    except Exception as exc:
        raise ForensicsError(f"Forensics: upload to {target_key} failed — {exc}") from exc
    return target_key


def extract_metadata_field(image_bytes: bytes, hide_in: str) -> Optional[str]:
    """
    Extract the value from the specified metadata field.
    Returns None if the field is absent or unreadable.
    """
    if hide_in not in VALID_HIDE_IN:
        return None

    try:
        if hide_in == "jpeg_comment":
            return _extract_jpeg_comment(image_bytes)
        elif hide_in == "xmp_description":
            return _extract_xmp_description(image_bytes)
        else:
            return _extract_exif_field(image_bytes, hide_in)
    except Exception as exc:
        logger.debug("extract_metadata_field(%s) error: %s", hide_in, exc)
        return None


# ── EXIF field tag IDs ────────────────────────────────────────────────────────

_EXIF_TAG_MAP: dict[str, tuple[int, str]] = {
    # (piexif IFD key, tag_id) — IFD is "0th", "Exif", etc.
    "exif_image_description": ("0th", 270),   # ImageDescription
    "exif_user_comment":      ("Exif", 37510), # UserComment
    "exif_artist":            ("0th", 315),    # Artist
    "exif_copyright":         ("0th", 33432),  # Copyright
}

_DECOY_TAG_MAP: dict[str, tuple[str, int]] = {
    "camera_make":    ("0th",  271),   # Make
    "camera_model":   ("0th",  272),   # Model
    "software":       ("0th",  305),   # Software
    "date_time":      ("0th",  306),   # DateTime
    "author_name":    ("0th",  315),   # Artist (shared with exif_artist)
    "copyright_text": ("0th",  33432), # Copyright (shared with exif_copyright)
    "lens_model":     ("Exif", 42036), # LensModel
    "iso_speed":      ("Exif", 34855), # ISOSpeedRatings
}


def _build_exif_with_decoys(decoy_metadata: dict) -> bytes:
    """Build EXIF bytes with only decoy fields (no flag)."""
    return _build_exif_bytes(flag=None, hide_in=None, decoy_metadata=decoy_metadata)


def _build_exif_with_flag_and_decoys(hide_in: str, flag: str, decoy_metadata: dict) -> bytes:
    """Build EXIF bytes with flag in the specified field plus decoy fields."""
    return _build_exif_bytes(flag=flag, hide_in=hide_in, decoy_metadata=decoy_metadata)


def _build_exif_bytes(
    flag: Optional[str],
    hide_in: Optional[str],
    decoy_metadata: dict,
) -> bytes:
    import piexif

    exif_dict: dict = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}}

    # Inject flag into target field
    if flag and hide_in and hide_in in _EXIF_TAG_MAP:
        ifd, tag_id = _EXIF_TAG_MAP[hide_in]
        if hide_in == "exif_user_comment":
            # UserComment requires 8-byte charset prefix
            encoded = b"ASCII\x00\x00\x00" + flag.encode("ascii", errors="replace")
        else:
            encoded = flag.encode("utf-8")
        exif_dict[ifd][tag_id] = encoded

    # Inject decoy fields
    _inject_decoys(exif_dict, decoy_metadata, skip_tag=_EXIF_TAG_MAP.get(hide_in or ""))

    try:
        return piexif.dump(exif_dict)
    except Exception as exc:
        raise ForensicsError(f"Forensics: metadata injection into {hide_in} failed — piexif dump error: {exc}") from exc


def _inject_decoys(exif_dict: dict, decoy_metadata: dict, skip_tag: Optional[tuple] = None) -> None:
    """Write decoy fields into exif_dict, skipping the tag already used for the flag."""
    for field_name, value in decoy_metadata.items():
        if field_name not in _DECOY_TAG_MAP:
            continue
        ifd, tag_id = _DECOY_TAG_MAP[field_name]
        # Don't overwrite the flag field
        if skip_tag and skip_tag == (ifd, tag_id):
            continue
        encoded = str(value).encode("utf-8")
        exif_dict[ifd][tag_id] = encoded


def _build_xmp_with_flag(flag: str) -> bytes:
    """Build a minimal XMP packet with dc:description containing the flag."""
    xmp_str = (
        '<?xpacket begin="\xef\xbb\xbf" id="W5M0MpCehiHzreSzNTczkc9d"?>'
        '<x:xmpmeta xmlns:x="adobe:ns:meta/" x:xmptk="Adobe XMP Core">'
        '<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
        '<rdf:Description rdf:about="" xmlns:dc="http://purl.org/dc/elements/1.1/">'
        f'<dc:description><rdf:Alt><rdf:li xml:lang="x-default">{flag}</rdf:li></rdf:Alt></dc:description>'
        '</rdf:Description>'
        '</rdf:RDF>'
        '</x:xmpmeta>'
        '<?xpacket end="w"?>'
    )
    return xmp_str.encode("utf-8")


def _inject_xmp(jpeg_bytes: bytes, xmp_bytes: bytes) -> bytes:
    """Insert XMP APP1 marker into JPEG bytes after the SOI marker."""
    if len(jpeg_bytes) < 2 or jpeg_bytes[:2] != b"\xff\xd8":
        raise ForensicsError("Forensics: metadata injection into xmp_description failed — not a valid JPEG")

    ns = b"http://ns.adobe.com/xap/1.0/\x00"
    payload = ns + xmp_bytes
    marker_len = 2 + len(payload)  # 2 bytes for the length field itself
    xmp_segment = b"\xff\xe1" + struct.pack(">H", marker_len) + payload

    # Insert after SOI
    return jpeg_bytes[:2] + xmp_segment + jpeg_bytes[2:]


def _save_jpeg_with_comment(img, output: io.BytesIO, comment: str, exif_bytes: bytes) -> None:
    """Save JPEG with a JPEG COM marker containing the comment."""
    from PIL import Image
    # Save to a temp buffer first
    tmp = io.BytesIO()
    img.save(tmp, format="JPEG", quality=90, exif=exif_bytes)
    raw = tmp.getvalue()

    # Insert COM marker after SOI
    comment_data = comment.encode("latin-1", errors="replace")
    com_len = 2 + len(comment_data)
    com_segment = b"\xff\xfe" + struct.pack(">H", com_len) + comment_data
    result = raw[:2] + com_segment + raw[2:]
    output.write(result)


def _extract_jpeg_comment(image_bytes: bytes) -> Optional[str]:
    """Extract the first JPEG COM (0xFFFE) marker value."""
    i = 0
    data = image_bytes
    if len(data) < 2 or data[0:2] != b"\xff\xd8":
        return None
    i = 2
    while i < len(data) - 3:
        if data[i] != 0xff:
            break
        marker = data[i + 1]
        if marker == 0xfe:
            length = struct.unpack(">H", data[i + 2: i + 4])[0]
            content = data[i + 4: i + 2 + length]
            return content.decode("latin-1", errors="replace")
        elif marker == 0xda:
            break  # Start of scan — stop
        else:
            if i + 4 > len(data):
                break
            length = struct.unpack(">H", data[i + 2: i + 4])[0]
            i += 2 + length
    return None


def _extract_xmp_description(image_bytes: bytes) -> Optional[str]:
    """Extract dc:description value from XMP APP1 block in a JPEG."""
    import re as _re
    ns = b"http://ns.adobe.com/xap/1.0/\x00"
    idx = image_bytes.find(ns)
    if idx == -1:
        return None
    xmp_start = idx + len(ns)
    # Find the end packet marker
    xmp_end_marker = b"<?xpacket end"
    xmp_end_idx = image_bytes.find(xmp_end_marker, xmp_start)
    if xmp_end_idx == -1:
        xmp_bytes = image_bytes[xmp_start:]
    else:
        xmp_bytes = image_bytes[xmp_start: xmp_end_idx + 30]

    xmp_text = xmp_bytes.decode("utf-8", errors="replace")
    # Extract <rdf:li xml:lang="x-default">...</rdf:li> inside dc:description
    match = _re.search(r'<dc:description>.*?<rdf:li[^>]*>([^<]+)</rdf:li>', xmp_text, _re.DOTALL)
    if match:
        return match.group(1).strip()
    # Fallback: plain text after dc:description tag
    match = _re.search(r'<dc:description>\s*([^<]+)', xmp_text)
    if match:
        return match.group(1).strip()
    return None


def _extract_exif_field(image_bytes: bytes, hide_in: str) -> Optional[str]:
    """Extract the flag from an EXIF field using piexif."""
    import piexif

    try:
        exif_dict = piexif.load(image_bytes)
    except Exception:
        return None

    if hide_in not in _EXIF_TAG_MAP:
        return None

    ifd, tag_id = _EXIF_TAG_MAP[hide_in]
    value = exif_dict.get(ifd, {}).get(tag_id)
    if value is None:
        return None

    if isinstance(value, bytes):
        if hide_in == "exif_user_comment" and len(value) >= 8:
            # Strip the 8-byte charset prefix
            return value[8:].decode("ascii", errors="replace").rstrip("\x00")
        return value.decode("utf-8", errors="replace").rstrip("\x00")
    return str(value)
