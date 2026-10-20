"""Synthetic identity and address documents, watermarked SINTÉTICO. No real brands, no photographs."""
from __future__ import annotations

from datetime import date
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen.canvas import Canvas

from .checks import mrz, mx_ids

FONT_DIR = Path("/usr/share/fonts/truetype/dejavu")
SANS = FONT_DIR / "DejaVuSans.ttf"
MONO = FONT_DIR / "DejaVuSansMono.ttf"


def _font(path: Path, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(path), size)


def _watermark(draw: ImageDraw.ImageDraw, size: tuple[int, int]) -> None:
    w, h = size
    font = _font(SANS, 42)
    draw.text((w * 0.18, h * 0.42), "SINTÉTICO", font=font, fill=(200, 40, 40, 90))


def _silhouette(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], hue: tuple[int, int, int]) -> None:
    x0, y0, x1, y1 = box
    cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
    r = (x1 - x0) // 3
    draw.ellipse((cx - r, y0 + 12, cx + r, y0 + 12 + 2 * r), fill=hue)
    draw.pieslice((x0 + 8, cy - 10, x1 - 8, y1 - 8), 200, 340, fill=hue)


def passport_png(person: dict, number: str, issued: date, expiry: date) -> bytes:
    w, h = 1400, 980
    img = Image.new("RGB", (w, h), (236, 232, 220))
    draw = ImageDraw.Draw(img)
    draw.rectangle((20, 20, w - 20, h - 20), outline=(20, 20, 20), width=3)
    draw.rectangle((20, 20, w - 20, 90), fill=(80, 20, 20))
    draw.text((40, 36), "PASAPORTE  ·  ESTADOS UNIDOS MEXICANOS  ·  SINTÉTICO",
              font=_font(SANS, 22), fill=(250, 250, 245))
    _silhouette(draw, (60, 130, 360, 520), (90, 90, 95))
    lines = [
        f"Apellidos  {person['apellido1']} {person.get('apellido2') or ''}",
        f"Nombre  {person['nombres']}",
        f"Nacionalidad  MEXICANA",
        f"Fecha de nacimiento  {person['dob']}",
        f"Sexo  {person.get('sex')}",
        f"Número  {number}",
        f"Expedición  {issued.isoformat()}    Caducidad  {expiry.isoformat()}",
        "Este documento no existe. No usar fuera de la demostración.",
    ]
    y = 140
    for line in lines:
        draw.text((400, y), line, font=_font(SANS, 22), fill=(20, 20, 20))
        y += 44
    mrz_lines = mrz.build_td3(
        f"{person['apellido1']} {person.get('apellido2') or ''}".strip(),
        person["nombres"], number, date.fromisoformat(person["dob"]),
        "F" if person.get("sex") == "M" else "M", expiry,
    )
    draw.rectangle((40, 720, w - 40, 940), fill=(20, 20, 20))
    mono = _font(MONO, 28)
    draw.text((60, 760), mrz_lines[0], font=mono, fill=(240, 240, 230))
    draw.text((60, 820), mrz_lines[1], font=mono, fill=(240, 240, 230))
    _watermark(draw, (w, h))
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def ine_png(person: dict, number: str, expiry: date) -> bytes:
    w, h = 1400, 880
    img = Image.new("RGB", (w, h), (230, 235, 240))
    draw = ImageDraw.Draw(img)
    draw.rectangle((16, 16, w - 16, h - 16), outline=(10, 40, 80), width=4)
    draw.text((40, 36), "CREDENCIAL PARA VOTAR  ·  INE  ·  SINTÉTICO  ·  no es un documento oficial",
              font=_font(SANS, 20), fill=(10, 40, 80))
    _silhouette(draw, (50, 100, 340, 430), (70, 90, 110))
    y = 110
    for line in (
        f"{person['nombres']}",
        f"{person['apellido1']} {person.get('apellido2') or ''}",
        f"CURP {person.get('curp') or '—'}",
        f"Nacimiento {person['dob']}",
        f"Vigencia {expiry.isoformat()}",
    ):
        draw.text((380, y), line, font=_font(SANS, 24), fill=(10, 20, 30))
        y += 48
    lines = mrz.build_td1(
        f"{person['apellido1']} {person.get('apellido2') or ''}".strip(),
        person["nombres"], number, date.fromisoformat(person["dob"]),
        "F" if person.get("sex") == "M" else "M", expiry, optional1=(person.get("curp") or "")[:15],
    )
    draw.rectangle((30, 560, w - 30, 850), fill=(15, 25, 40))
    mono = _font(MONO, 26)
    for i, line in enumerate(lines):
        draw.text((50, 590 + i * 70), line, font=mono, fill=(230, 230, 220))
    _watermark(draw, (w, h))
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def address_pdf(person: dict, issued: date, issuer: str = "Servicio Municipal de Energía (sintético)") -> bytes:
    buf = BytesIO()
    c = Canvas(buf, pagesize=A4)
    w, h = A4
    c.setFont("Times-Bold", 14)
    c.drawString(20 * mm, h - 20 * mm, issuer)
    c.setFont("Times-Roman", 9)
    c.drawString(20 * mm, h - 26 * mm, "COMPROBANTE DE DOMICILIO  ·  SINTÉTICO  ·  no es una factura real")
    addr = person.get("address") or {}
    c.setFont("Times-Roman", 11)
    y = h - 45 * mm
    for line in (
        f"Titular: {person['nombres']} {person['apellido1']} {person.get('apellido2') or ''}",
        f"Calle {addr.get('calle')} {addr.get('numero')}",
        f"Col. {addr.get('colonia')}  C.P. {addr.get('cp')}",
        f"{addr.get('alcaldia')}, {addr.get('ciudad')}",
        f"Periodo de facturación: {(issued.replace(day=1)).isoformat()} a {issued.isoformat()}",
        f"Fecha de emisión: {issued.isoformat()}",
        "Importe: $ 842.00 MXN (cifra inventada)",
        "SINTÉTICO. Sin marca comercial. Sin datos de una persona real.",
    ):
        c.drawString(20 * mm, y, line)
        y -= 8 * mm
    c.save()
    return buf.getvalue()


def funds_pdf(person: dict, kind: str, amount_eur: int, issued: date) -> bytes:
    buf = BytesIO()
    c = Canvas(buf, pagesize=A4)
    w, h = A4
    titles = {
        "nomina": "Constancia de ingresos (sintética)",
        "venta": "Contrato de compraventa (sintético)",
        "ahorro": "Certificado de posición (sintético)",
        "herencia": "Escritura de adjudicación (sintética)",
    }
    c.setFont("Times-Bold", 14)
    c.drawString(20 * mm, h - 20 * mm, titles.get(kind, "Origen de fondos (sintético)"))
    c.setFont("Times-Roman", 11)
    y = h - 40 * mm
    for line in (
        f"Interesado: {person['nombres']} {person['apellido1']} {person.get('apellido2') or ''}",
        f"Concepto: {kind}",
        f"Importe aproximado: {amount_eur:,} EUR (cifra de demostración)".replace(",", "."),
        f"Fecha: {issued.isoformat()}",
        "SINTÉTICO. No acredita un origen real de fondos.",
    ):
        c.drawString(20 * mm, y, line)
        y -= 9 * mm
    c.save()
    return buf.getvalue()
