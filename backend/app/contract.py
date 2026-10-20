"""Contract PDF for Alterna Inversiones y Valores, S.G.I.I.C., S.A."""
from __future__ import annotations

import hashlib
import io
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen.canvas import Canvas

from . import settings
from .timeutil import MADRID, iso

PAGE = A4
MARGIN = 18 * mm


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _draw_header(c: Canvas, title: str, page_no: int, pages: int, digest: str) -> None:
    w, h = PAGE
    c.setStrokeColorRGB(0, 0, 0)
    c.setLineWidth(0.3)
    c.line(MARGIN, h - 14 * mm, w - MARGIN, h - 14 * mm)
    c.setFont("Times-Roman", 8)
    c.drawString(MARGIN, h - 10 * mm, settings.ENTITY["legal_name"])
    c.drawRightString(w - MARGIN, h - 10 * mm, "SINTÉTICO · no produce efectos")
    c.setFont("Times-Bold", 13)
    c.drawString(MARGIN, h - 22 * mm, title)
    c.setFont("Times-Roman", 8)
    c.line(MARGIN, 12 * mm, w - MARGIN, 12 * mm)
    c.drawString(MARGIN, 8 * mm, f"Página {page_no} de {pages}  ·  sha256 {digest[:16]}…")
    c.drawRightString(w - MARGIN, 8 * mm, settings.ENTITY["registry"])


def _wrap(c: Canvas, text: str, x: float, y: float, max_width: float, size: int = 9, leading: float = 12) -> float:
    c.setFont("Times-Roman", size)
    words = text.split()
    line = ""
    for word in words:
        trial = f"{line} {word}".strip()
        if c.stringWidth(trial, "Times-Roman", size) > max_width:
            c.drawString(x, y, line)
            y -= leading
            line = word
        else:
            line = trial
    if line:
        c.drawString(x, y, line)
        y -= leading
    return y


def render(case: dict, acceptance: dict | None = None) -> bytes:
    person = case.get("person") or {}
    name = " ".join(p for p in (person.get("nombres"), person.get("apellido1"), person.get("apellido2")) if p)
    suit = case.get("suitability") or {}
    profile = (suit.get("profile_detail") or {})
    service = {"asesoramiento": "Asesoramiento en materia de inversión",
               "gdc": "Gestión discrecional de carteras",
               "rto": "Recepción y transmisión de órdenes"}.get(case.get("service"), case.get("service") or "—")
    buf = io.BytesIO()
    c = Canvas(buf, pagesize=PAGE)
    digest_placeholder = "0" * 64
    pages_spec = [
        ("Contrato de prestación de servicios de inversión", _page_main),
        ("Anexo I · Evaluación de idoneidad", _page_suitability),
        ("Anexo II · Costes y gastos (ex ante)", _page_costs),
        ("Anexo III · Información precontractual y protección de datos", _page_pre),
        ("Anexo IV · Autocertificación CRS / FATCA", _page_crs),
        ("Anexo V · Evidencia de firma", _page_sign),
    ]
    if acceptance:
        pages_spec.append(("Aceptación de la entidad", _page_accept))
    pages = len(pages_spec)
    w = PAGE[0] - 2 * MARGIN
    ctx = {
        "name": name or "—",
        "person": person,
        "case": case,
        "service": service,
        "profile": profile,
        "suit": suit,
        "acceptance": acceptance,
        "width": w,
    }
    for i, (title, fn) in enumerate(pages_spec, start=1):
        if i > 1:
            c.showPage()
        _draw_header(c, title, i, pages, digest_placeholder)
        fn(c, ctx)
    c.save()
    first = buf.getvalue()
    # First pass used a placeholder hash. Stamp the real one on a second pass.
    digest = _sha(first)
    buf = io.BytesIO()
    c = Canvas(buf, pagesize=PAGE)
    for i, (title, fn) in enumerate(pages_spec, start=1):
        if i > 1:
            c.showPage()
        _draw_header(c, title, i, pages, digest)
        fn(c, ctx)
    c.save()
    return buf.getvalue()


def _page_main(c: Canvas, ctx: dict) -> None:
    y = PAGE[1] - 32 * mm
    entity = settings.ENTITY
    blocks = [
        f"Entidad: {entity['legal_name']}. NIF {entity['nif']}. {entity['registry']}.",
        f"Domicilio: {entity['address']}. {entity['formerly']}.",
        f"Cliente (datos sintéticos): {ctx['name']}. Nacionalidad {ctx['person'].get('nationality') or '—'}.",
        f"Servicio: {ctx['service']}. Clasificación: cliente minorista (Ley 6/2023 art. 193).",
        "El contrato no produce efectos hasta la aceptación de la entidad, una vez practicada la diligencia debida. "
        "La firma del cliente no abre la relación de negocio por sí sola.",
        "El cliente declara actuar por cuenta propia y ser el titular real (Ley 10/2010 art. 4).",
        "FOGAIN: la entidad está adherida al Fondo General de Garantía de Inversiones. Cobertura [importe vigente: consultar fogain.com].",
        "Servicio de Atención al Cliente: [canal y plazos: según reglamento interno de Alterna].",
        "Idioma del contrato: español. El cliente ha recibido la información precontractual en soporte duradero antes de firmar.",
        "SINTÉTICO. Este documento no vincula a nadie. Los importes entre corchetes no son el tarifario de Alterna.",
    ]
    for block in blocks:
        y = _wrap(c, block, MARGIN, y, ctx["width"])
        y -= 4


def _page_suitability(c: Canvas, ctx: dict) -> None:
    y = PAGE[1] - 32 * mm
    profile = ctx["profile"]
    y = _wrap(c, ctx["suit"].get("declaration") or "Test de idoneidad no completado. El servicio de asesoramiento o GDC no se prestará (Ley 6/2023 art. 204.5).",
              MARGIN, y, ctx["width"])
    y -= 6
    if profile:
        y = _wrap(c, f"Perfil: {profile.get('label')}. Volatilidad máxima {profile.get('volatility')} %. "
                     f"Renta variable {profile.get('equity')}. Renta fija {profile.get('fixed_income')}.",
                  MARGIN, y, ctx["width"])
    y -= 8
    y = _wrap(c, "Preferencias de sostenibilidad: "
              + ("con preferencias." if ctx["suit"].get("sustainability") else "sin preferencias."),
              MARGIN, y, ctx["width"])
    y -= 8
    y = _wrap(c, "Esta declaración de idoneidad se entrega en soporte duradero antes de la prestación del servicio (art. 204.6).",
              MARGIN, y, ctx["width"])


def _page_costs(c: Canvas, ctx: dict) -> None:
    y = PAGE[1] - 32 * mm
    y = _wrap(c, "Costes y gastos asociados, en cumplimiento del Reglamento Delegado (UE) 2017/565 arts. 50 y 51. "
              "Los importes son marcadores. El tarifario vigente lo aporta Alterna.",
              MARGIN, y, ctx["width"])
    y -= 10
    rows = [
        ("Comisión de gestión / asesoramiento", "[ % anual sobre patrimonio : tarifario Alterna ]"),
        ("Comisión de intermediación", "[ por operación : tarifario Alterna ]"),
        ("Gastos del depositario", "[ según IIC subyacente ]"),
        ("Incentivos percibidos de terceros", "[ política de incentivos de Alterna ]"),
        ("Coste total estimado a 1 año, ejemplo 100.000 EUR", "[ cifra : por calcular ]"),
    ]
    c.setFont("Times-Roman", 9)
    for label, value in rows:
        c.drawString(MARGIN, y, label)
        c.drawRightString(PAGE[0] - MARGIN, y, value)
        y -= 16


def _page_pre(c: Canvas, ctx: dict) -> None:
    y = PAGE[1] - 32 * mm
    paras = [
        f"El cliente reconoce haber recibido la Información precontractual de {settings.ENTITY['legal_name']} (febrero de 2026) antes de quedar vinculado.",
        f"Responsable del tratamiento: {settings.ENTITY['legal_name']}, {settings.ENTITY['address']}. DPO: {settings.ENTITY['dpo_contact']}.",
        "Base jurídica principal del alta: art. 6.1.b RGPD (precontractual / contractual) y art. 6.1.c RGPD / Ley 10/2010 art. 32 bis (PBC).",
        "El cliente tiene derecho a no ser objeto de una decisión basada únicamente en el tratamiento automatizado (RGPD art. 22). La aceptación de este expediente la firma una persona.",
        "Conservación PBC: diez años desde el fin de la relación; acceso restringido a control interno a partir del quinto (Ley 10/2010 art. 25).",
        "Alterna no tiene previsto realizar transferencias internacionales de datos de clientes (anexo I de la precontractual, febrero 2026). Esta instalación se ejecuta en los servidores de la entidad.",
        "Autoridad de control: Agencia Española de Protección de Datos. Reclamaciones: Servicio de Atención al Cliente de Alterna y, en su caso, CNMV.",
        "[Transposición española de la Directiva (UE) 2023/2673 pendiente a 20 oct 2026. Se ofrece función de desistimiento en la pantalla del cliente.]",
    ]
    for p in paras:
        y = _wrap(c, p, MARGIN, y, ctx["width"])
        y -= 4


def _page_crs(c: Canvas, ctx: dict) -> None:
    y = PAGE[1] - 32 * mm
    crs = ctx["case"].get("crs") or {}
    fatca = ctx["case"].get("fatca") or {}
    y = _wrap(c, f"Residencia fiscal declarada: {crs.get('residence') or ctx['person'].get('country') or '—'}. "
              f"NIF/RFC: {ctx['person'].get('rfc') or '—'}.",
              MARGIN, y, ctx["width"])
    y -= 6
    y = _wrap(c, f"El cliente {'' if crs.get('only_mx_es') else 'no '}declara ser residente fiscal únicamente en México o España.",
              MARGIN, y, ctx["width"])
    y -= 6
    y = _wrap(c, f"FATCA: {('persona estadounidense' if fatca.get('us_person') else 'no es persona estadounidense')}.",
              MARGIN, y, ctx["width"])
    y -= 8
    y = _wrap(c, "Autocertificación emitida a los efectos del Common Reporting Standard y del FATCA. "
              "La entidad comunicará los datos a la Administración tributaria cuando la ley lo exija.",
              MARGIN, y, ctx["width"])


def _page_sign(c: Canvas, ctx: dict) -> None:
    y = PAGE[1] - 32 * mm
    sig = ctx["case"].get("signature") or {}
    y = _wrap(c, "Firma electrónica simple mediante contraseña de un solo uso enviada por un canal simulado. "
              "[Proveedor SMS real: no hay. El código se muestra en pantalla en esta demo.]",
              MARGIN, y, ctx["width"])
    y -= 8
    rows = [
        ("Titular", ctx["name"]),
        ("Fecha (UTC)", sig.get("signed_at") or "—"),
        ("Canal", "OTP simulado"),
        ("Huella del código (sha256)", (sig.get("code_hash") or "—")[:32] + ("…" if sig.get("code_hash") else "")),
        ("Huella del contrato", (sig.get("document_hash") or "—")[:32] + ("…" if sig.get("document_hash") else "")),
        ("Expresión manuscrita (art. 205.6)", sig.get("manuscript") or "no procede"),
    ]
    c.setFont("Times-Roman", 9)
    for label, value in rows:
        c.drawString(MARGIN, y, label)
        c.setFont("Times-Bold", 9)
        c.drawString(MARGIN + 70 * mm, y, str(value)[:70])
        c.setFont("Times-Roman", 9)
        y -= 14


def _page_accept(c: Canvas, ctx: dict) -> None:
    y = PAGE[1] - 32 * mm
    acc = ctx["acceptance"] or {}
    y = _wrap(c, "La entidad acepta el establecimiento de la relación de negocio tras la diligencia debida y la revisión humana.",
              MARGIN, y, ctx["width"])
    y -= 10
    rows = [
        ("Decisión", acc.get("decision") or "—"),
        ("Firmante", acc.get("actor_name") or acc.get("actor_id") or "—"),
        ("Función", acc.get("role") or "—"),
        ("Segundo firmante", acc.get("second_name") or "—"),
        ("Fecha", acc.get("ts") or "—"),
        ("Expediente", acc.get("case_id") or "—"),
    ]
    c.setFont("Times-Roman", 9)
    for label, value in rows:
        c.drawString(MARGIN, y, label)
        c.setFont("Times-Bold", 9)
        c.drawString(MARGIN + 50 * mm, y, str(value))
        c.setFont("Times-Roman", 9)
        y -= 14
    y -= 8
    y = _wrap(c, "Sin esta página el contrato no está aceptado. La firma del cliente, por sí sola, no abre la cuenta.",
              MARGIN, y, ctx["width"])


def render_with_hash(case: dict, acceptance: dict | None = None) -> tuple[bytes, str]:
    data = render(case, acceptance)
    return data, _sha(data)
