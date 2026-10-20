"""Run the deterministic checks on an uploaded or generated document."""
from __future__ import annotations

import re
from datetime import date, timedelta
from io import BytesIO

from PIL import Image

from .checks import match, mrz, mx_ids, ocr, quality
from .timeutil import months_between

ADDRESS_POLICY_MONTHS = 3


def _find_date(text: str) -> date | None:
    for pattern in (r"(\d{4})-(\d{2})-(\d{2})", r"(\d{1,2})/(\d{1,2})/(\d{4})"):
        m = re.search(pattern, text)
        if not m:
            continue
        try:
            if pattern.startswith(r"(\d{4})"):
                return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        except ValueError:
            continue
    return None


def analyze(kind: str, data: bytes, filename: str, person: dict, today: date | None = None,
            payload: dict | None = None) -> dict:
    today = today or date.today()
    mime = quality.sniff(data) or "application/octet-stream"
    result: dict = {"kind": kind, "filename": filename, "mime": mime, "size": len(data),
                    "issues": [], "messages": []}

    if mime.startswith("image/"):
        clean, img, removed = quality.strip_metadata(data)
        result["meta_removed"] = removed
        result["quality"] = quality.assess(img)
        if not result["quality"]["ok"]:
            result["issues"].extend(result["quality"]["issues"])
            result["messages"].append(_quality_message(result["quality"]["issues"]))
        text = ocr.image_text(img, lang="spa+eng", psm=6)
        if kind in {"pasaporte", "ine"}:
            width, count = (44, 2) if kind == "pasaporte" else (30, 3)
            lines = mrz.extract_lines(text, width, count)
            parsed = None
            source = "ocr"
            if lines:
                parsed = mrz.parse_td3(lines) if kind == "pasaporte" else mrz.parse_td1(lines)
            if (not parsed or not parsed.get("valid")) and payload and payload.get("mrz"):
                raw = payload["mrz"]
                parsed = mrz.parse_td3(raw) if kind == "pasaporte" else mrz.parse_td1(raw)
                source = "reconstruccion"
            result["ocr_text"] = text
            result["mrz"] = parsed
            result["mrz_source"] = source
            if not parsed:
                result["issues"].append("mrz")
                result["messages"].append("No pudimos leer la zona de la máquina. Toma la foto de nuevo, de frente y sin recortar el borde de abajo.")
            else:
                _apply_id(result, parsed, person, today, kind)
        result["bytes_clean"] = clean
    elif mime == "application/pdf":
        active = ocr.pdf_active_content(data)
        if active:
            result["issues"].append("pdf_activo")
            result["messages"].append("Este PDF trae contenido activo. Súbenos una copia solo con el texto o una foto.")
        text = ocr.pdf_text(data)
        result["ocr_text"] = text
        result["pages"] = ocr.pdf_page_count(data)
        if kind == "domicilio":
            _apply_address(result, text, person, today)
        elif kind == "origen_fondos":
            result["status"] = "ok"
            result["messages"].append("Documento de origen de fondos recibido. Una persona lo lee.")
        else:
            result["status"] = "ok"
    else:
        result["issues"].append("formato")
        result["messages"].append("El archivo no es una foto ni un PDF.")

    if "status" not in result:
        result["status"] = "ok" if not result["issues"] else "aviso" if set(result["issues"]) <= {"borrosa", "reflejo", "reconstruccion"} else "fallo"
    return result


def _quality_message(issues: list[str]) -> str:
    parts = {
        "resolucion": "la foto se ve pequeña",
        "borrosa": "la foto está borrosa",
        "reflejo": "hay un reflejo que tapa datos",
        "oscura": "la foto está muy oscura",
    }
    return "Toma otra foto: " + ", ".join(parts.get(i, i) for i in issues) + "."


def _apply_id(result: dict, parsed: dict, person: dict, today: date, kind: str) -> None:
    result["valid_mrz"] = parsed.get("valid")
    if not parsed.get("valid"):
        result["issues"].append("mrz_digitos")
        result["messages"].append("Los dígitos de control de la zona de la máquina no cuadran.")
    expiry = parsed.get("expiry_date")
    result["expiry"] = expiry.isoformat() if expiry else None
    if expiry and expiry < today:
        result["expired"] = True
        result["issues"].append("caducado")
        result["messages"].append("Este documento ya caducó. Necesitamos uno vigente.")
    else:
        result["expired"] = False
    observed = f"{parsed.get('given_names') or ''} {parsed.get('surnames') or ''}"
    result["name_match"] = match.name_match(person, observed)
    if result["name_match"]["verdict"] == "no_coincide":
        result["issues"].append("nombre")
        result["messages"].append("El nombre del documento no coincide con el que nos diste.")
    elif result["name_match"]["verdict"] == "parcial":
        result["issues"].append("nombre_parcial")
        result["messages"].append(result["name_match"]["detail"])
    if kind == "pasaporte":
        result["fehaciente"] = not result.get("expired") and parsed.get("valid")
    elif kind == "ine":
        result["fehaciente"] = False
        result["messages"].append("La credencial INE la guardamos como complemento. El documento que nos sirve es el pasaporte.")


def _apply_address(result: dict, text: str, person: dict, today: date) -> None:
    issued = _find_date(text)
    result["issued"] = issued.isoformat() if issued else None
    if issued:
        age = months_between(issued, today)
        result["age_months"] = round(age, 1)
        if age > ADDRESS_POLICY_MONTHS:
            result["issues"].append("domicilio_antiguo")
            result["messages"].append(
                f"Este comprobante tiene más de {ADDRESS_POLICY_MONTHS} meses. "
                "Pídenos uno más reciente. Eso es política interna, no un artículo de la ley."
            )
    else:
        result["issues"].append("sin_fecha")
        result["messages"].append("No vimos la fecha del comprobante. Súbenos uno donde se lea el día.")
    result["address_match"] = match.address_match(person.get("address") or {}, text)
    if result["address_match"]["verdict"] == "no_coincide":
        result["issues"].append("domicilio_nombre")
        result["messages"].append("La dirección del comprobante no coincide con la que nos diste.")
    name = match.name_match(person, text)
    result["holder_match"] = name
    if name["verdict"] == "no_coincide":
        result["issues"].append("titular")
        result["messages"].append("El comprobante no está a tu nombre.")
