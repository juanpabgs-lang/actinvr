"""Name and address matching tuned for Mexican naming (two surnames, compound given names)."""
from __future__ import annotations

import re
import unicodedata

from rapidfuzz import fuzz


def norm(text: str | None) -> str:
    text = unicodedata.normalize("NFKD", (text or "").upper())
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^A-Z0-9 ]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def full_name(person: dict) -> str:
    return " ".join(p for p in (person.get("nombres"), person.get("apellido1"), person.get("apellido2")) if p)


def name_match(person: dict, observed: str) -> dict:
    """Compare declared name parts with a name read from a document."""
    nombres, a1, a2 = norm(person.get("nombres")), norm(person.get("apellido1")), norm(person.get("apellido2"))
    obs = norm(observed)
    obs_tokens = set(obs.split())
    declared = norm(full_name(person))
    score = fuzz.token_sort_ratio(declared, obs)
    has_given = all(t in obs_tokens for t in nombres.split())
    has_a1 = all(t in obs_tokens for t in a1.split())
    has_a2 = bool(a2) and all(t in obs_tokens for t in a2.split())
    if has_given and has_a1 and (has_a2 or not a2):
        verdict, detail = "coincide", "Nombre y apellidos coinciden"
    elif has_given and has_a1 and a2 and not has_a2:
        verdict, detail = "parcial", "Falta el segundo apellido en el documento"
    elif score >= 92:
        verdict, detail = "coincide", "Coincidencia con diferencias menores de escritura"
    elif score >= 75:
        verdict, detail = "parcial", "Coincidencia parcial del nombre"
    else:
        verdict, detail = "no_coincide", "El nombre no coincide con el declarado"
    return {"verdict": verdict, "score": round(score, 1), "detail": detail, "observed": observed.strip()}


def address_match(addr: dict, observed_text: str) -> dict:
    obs = norm(observed_text)
    cp = re.sub(r"\D", "", addr.get("cp") or "")
    cp_found = bool(cp) and cp in re.sub(r"[^0-9 ]", " ", obs).split()
    street = norm(f"{addr.get('calle', '')} {addr.get('numero', '')}")
    colonia = norm(addr.get("colonia"))
    street_score = fuzz.partial_ratio(street, obs) if street else 0
    colonia_score = fuzz.partial_ratio(colonia, obs) if colonia else 0
    score = round((street_score * 0.6 + colonia_score * 0.4), 1)
    if cp_found and score >= 85:
        verdict = "coincide"
    elif cp_found and score >= 65:
        verdict = "parcial"
    else:
        verdict = "no_coincide"
    return {"verdict": verdict, "score": score, "postal_code_found": cp_found,
            "street_score": round(street_score, 1), "colonia_score": round(colonia_score, 1)}
