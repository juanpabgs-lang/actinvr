"""Local OCR (Tesseract, Spanish and English models) and PDF text extraction."""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from io import BytesIO

from PIL import Image
from pypdf import PdfReader

TESSERACT = shutil.which("tesseract")
MRZ_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789<"
_ACTIVE_PDF_MARKERS = (b"/JavaScript", b"/JS ", b"/JS(", b"/Launch", b"/EmbeddedFile", b"/RichMedia", b"/XFA")


def available() -> bool:
    return TESSERACT is not None


def version() -> str | None:
    if not TESSERACT:
        return None
    out = subprocess.run([TESSERACT, "--version"], capture_output=True, timeout=10, check=False)
    return (out.stdout or out.stderr).decode("utf-8", "replace").splitlines()[0]


def image_text(img: Image.Image, lang: str = "spa", psm: int = 6, whitelist: str | None = None,
               timeout: int = 30) -> str:
    if not TESSERACT:
        return ""
    with tempfile.NamedTemporaryFile(suffix=".png") as fh:
        img.save(fh.name, format="PNG")
        cmd = [TESSERACT, fh.name, "stdout", "-l", lang, "--psm", str(psm)]
        if whitelist:
            cmd += ["-c", f"tessedit_char_whitelist={whitelist}", "-c", "load_system_dawg=0", "-c", "load_freq_dawg=0"]
        env = {"PATH": os.environ.get("PATH", "/usr/bin"), "OMP_THREAD_LIMIT": "2"}
        out = subprocess.run(cmd, capture_output=True, timeout=timeout, check=False, env=env)
        return out.stdout.decode("utf-8", "replace")


def pdf_active_content(data: bytes) -> list[str]:
    return [m.decode().strip(" (") for m in _ACTIVE_PDF_MARKERS if m in data]


def pdf_text(data: bytes, max_pages: int = 10) -> str:
    reader = PdfReader(BytesIO(data))
    parts = []
    for page in reader.pages[:max_pages]:
        parts.append(page.extract_text() or "")
    return "\n".join(parts)


def pdf_page_count(data: bytes) -> int:
    return len(PdfReader(BytesIO(data)).pages)
