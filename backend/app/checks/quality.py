"""Image intake: format sniffing, metadata stripping and capture-quality checks."""
from __future__ import annotations

from io import BytesIO

from PIL import Image, ImageFilter, ImageOps, ImageStat

MIN_LONG_SIDE = 1000
MIN_SHARPNESS = 120.0
MAX_GLARE = 0.04

_MAGIC = {
    b"\xff\xd8\xff": "image/jpeg",
    b"\x89PNG\r\n\x1a\n": "image/png",
    b"%PDF-": "application/pdf",
}


def sniff(data: bytes) -> str | None:
    for magic, mime in _MAGIC.items():
        if data.startswith(magic):
            return mime
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def strip_metadata(data: bytes) -> tuple[bytes, Image.Image, list[str]]:
    """Re-encode the image from pixels only, dropping EXIF (GPS, device), XMP and ICC blocks."""
    img = Image.open(BytesIO(data))
    removed = []
    exif = img.getexif()
    if exif:
        names = {0x010F: "fabricante", 0x0110: "modelo", 0x0132: "fecha", 0x8825: "GPS", 0x9003: "fecha original"}
        found = [names.get(tag, None) for tag in exif.keys()]
        if 0x8825 in exif:
            found.append("GPS")
        removed.extend(sorted({f for f in found if f}))
        if not removed:
            removed.append("EXIF")
    if "xmp" in img.info or "XML:com.adobe.xmp" in img.info:
        removed.append("XMP")
    if "icc_profile" in img.info:
        removed.append("perfil ICC")
    img = ImageOps.exif_transpose(img).convert("RGB")
    clean = Image.new("RGB", img.size)
    clean.paste(img)
    buf = BytesIO()
    clean.save(buf, format="PNG", optimize=True)
    return buf.getvalue(), clean, removed


def assess(img: Image.Image) -> dict:
    w, h = img.size
    gray = img.convert("L")
    if max(w, h) > 1400:
        scale = 1400 / max(w, h)
        gray = gray.resize((int(w * scale), int(h * scale)))
    lap = gray.filter(ImageFilter.Kernel((3, 3), [0, 1, 0, 1, -4, 1, 0, 1, 0], scale=1, offset=128))
    sharpness = ImageStat.Stat(lap).var[0]
    hist = gray.histogram()
    total = sum(hist) or 1
    glare = sum(hist[251:]) / total
    brightness = ImageStat.Stat(gray).mean[0]
    issues = []
    if max(w, h) < MIN_LONG_SIDE:
        issues.append("resolucion")
    if sharpness < MIN_SHARPNESS:
        issues.append("borrosa")
    if glare > MAX_GLARE:
        issues.append("reflejo")
    if brightness < 60:
        issues.append("oscura")
    return {
        "width": w,
        "height": h,
        "sharpness": round(sharpness, 1),
        "glare": round(glare, 4),
        "brightness": round(brightness, 1),
        "issues": issues,
        "ok": not issues,
    }
