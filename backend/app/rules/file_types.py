"""Decide what a file really is from its bytes, never from the client's filename or Content-Type."""
import json
import re

ALLOWED_TYPES = {
    "application/pdf": ".pdf",
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
    "application/geo+json": ".geojson",
    "application/vnd.google-earth.kml+xml": ".kml",
}

GEOSPATIAL_TYPES = frozenset({"application/geo+json", "application/vnd.google-earth.kml+xml"})


def sniff(data: bytes) -> str | None:
    """Return the detected MIME type if it is one we accept, else None."""
    if data.startswith(b"%PDF-"):
        return "application/pdf"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if len(data) > 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return None
    head = text.lstrip()[:2000]
    if head.startswith("{"):
        try:
            obj = json.loads(text)
        except json.JSONDecodeError:
            return None
        return "application/geo+json" if isinstance(obj, dict) and "type" in obj else None
    if (head.startswith("<?xml") or head.startswith("<kml")) and re.search(r"<kml[\s>]", head):
        return "application/vnd.google-earth.kml+xml"
    return None


_UNSAFE = re.compile(r"[^\w\s.\-()]+", re.UNICODE)


def safe_filename(name: str | None, mime: str) -> str:
    base = (name or "file").replace("\\", "/").split("/")[-1]
    base = _UNSAFE.sub("_", base).strip(" .") or "file"
    stem = base.rsplit(".", 1)[0][:150]
    return f"{stem}{ALLOWED_TYPES[mime]}"
