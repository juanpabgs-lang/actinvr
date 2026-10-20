"""Mexican identifiers: CURP, RFC (persona física) and CLABE, plus IBAN."""
from __future__ import annotations

import re
import unicodedata
from datetime import date

from stdnum import iban as _iban
from stdnum.mx import curp as _curp
from stdnum.mx import rfc as _rfc

STATES = {
    "AS": "Aguascalientes", "BC": "Baja California", "BS": "Baja California Sur", "CC": "Campeche",
    "CL": "Coahuila", "CM": "Colima", "CS": "Chiapas", "CH": "Chihuahua", "DF": "Ciudad de México",
    "DG": "Durango", "GT": "Guanajuato", "GR": "Guerrero", "HG": "Hidalgo", "JC": "Jalisco",
    "MC": "Estado de México", "MN": "Michoacán", "MS": "Morelos", "NT": "Nayarit", "NL": "Nuevo León",
    "OC": "Oaxaca", "PL": "Puebla", "QT": "Querétaro", "QR": "Quintana Roo", "SP": "San Luis Potosí",
    "SL": "Sinaloa", "SR": "Sonora", "TC": "Tabasco", "TS": "Tamaulipas", "TL": "Tlaxcala",
    "VZ": "Veracruz", "YN": "Yucatán", "ZS": "Zacatecas", "NE": "Nacido en el extranjero",
}

# Synthetic catalogue for the demo. Production uses the official SPEI participant list.
BANKS = {
    "980": "Banco Ficticio del Norte (sintético)",
    "981": "Banca Sintética del Pacífico",
    "982": "Banco Demo del Bajío (sintético)",
    "983": "Financiera Ejemplo del Sureste (sintética)",
}

_PARTICLES = {"DE", "DEL", "LA", "LAS", "LOS", "Y", "MC", "MAC", "VON", "VAN", "DA", "DI", "DER"}
_SKIP_FIRST = {"MARIA", "MA", "MA.", "JOSE", "J", "J."}
_VOWELS = set("AEIOU")
_INCONVENIENT = {
    "BACA", "BAKA", "BUEI", "BUEY", "CACA", "CACO", "CAGA", "CAGO", "CAKA", "CAKO", "COGE", "COGI",
    "COJA", "COJE", "COJI", "COJO", "COLA", "CULO", "FALO", "FETO", "GETA", "GUEI", "GUEY", "JETA",
    "JOTO", "KACA", "KACO", "KAGA", "KAGO", "KAKA", "KAKO", "KOGE", "KOGI", "KOJA", "KOJE", "KOJI",
    "KOJO", "KOLA", "KULO", "LILO", "LOCA", "LOCO", "LOKA", "LOKO", "MAME", "MAMO", "MEAR", "MEAS",
    "MEON", "MIAR", "MION", "MOCO", "MOKO", "MULA", "MULO", "NACA", "NACO", "PEDA", "PEDO", "PENE",
    "PIPI", "PITO", "POPO", "PUTA", "PUTO", "QULO", "RATA", "ROBA", "ROBE", "ROBO", "RUIN", "SENO",
    "TETA", "VACA", "VAGA", "VAGO", "VAKA", "VUEI", "VUEY", "WUEI", "WUEY",
}


def _norm(text: str | None) -> str:
    text = unicodedata.normalize("NFKD", (text or "").upper().replace("Ñ", "X"))
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"[^A-Z ]", "", text).strip()


def _strip_particles(text: str) -> str:
    words = [w for w in _norm(text).split() if w not in _PARTICLES]
    return " ".join(words) or _norm(text)


def _first_name(nombres: str) -> str:
    words = _norm(nombres).split()
    if len(words) > 1 and words[0] in _SKIP_FIRST:
        return words[1]
    return words[0] if words else "X"


def _internal(word: str, wanted_vowel: bool) -> str:
    for ch in word[1:]:
        if (ch in _VOWELS) == wanted_vowel:
            return ch
    return "X"


def initials(apellido1: str, apellido2: str | None, nombres: str) -> str:
    a1 = _strip_particles(apellido1).replace(" ", "") or "X"
    a2 = _strip_particles(apellido2 or "").replace(" ", "")
    n = _first_name(nombres)
    out = a1[0] + _internal(a1, True) + (a2[0] if a2 else "X") + n[0]
    if out in _INCONVENIENT:
        out = out[0] + "X" + out[2:]
    return out


def consonants(apellido1: str, apellido2: str | None, nombres: str) -> str:
    a1 = _strip_particles(apellido1).replace(" ", "") or "X"
    a2 = _strip_particles(apellido2 or "").replace(" ", "") or "X"
    n = _first_name(nombres)
    return _internal(a1, False) + (_internal(a2, False) if a2 != "X" else "X") + _internal(n, False)


def build_curp(apellido1: str, apellido2: str | None, nombres: str, dob: date, sex: str,
               state: str, differentiator: str) -> str:
    body = (initials(apellido1, apellido2, nombres) + dob.strftime("%y%m%d") + sex + state
            + consonants(apellido1, apellido2, nombres) + differentiator)
    return body + _curp.calc_check_digit(body)


def _curp_birth(value: str) -> date:
    """CURP encodes a two-digit year. Years that would fall in the future are 1900s."""
    yy, mm, dd = int(value[4:6]), int(value[6:8]), int(value[8:10])
    this = date.today()
    year = 2000 + yy
    if date(year, mm, dd) > this:
        year -= 100
    return date(year, mm, dd)


def validate_curp(value: str, apellido1: str | None = None, apellido2: str | None = None,
                  nombres: str | None = None, dob: date | None = None, sex: str | None = None) -> dict:
    v = re.sub(r"\s", "", (value or "").upper())
    checks = []
    structure_ok = bool(re.fullmatch(r"[A-Z][AEIOUX][A-Z]{2}\d{6}[HMX][A-Z]{2}[B-DF-HJ-NP-TV-Z]{3}[A-Z\d]\d", v))
    checks.append({"id": "formato", "label": "Formato de 18 caracteres", "ok": structure_ok})
    digit_ok = False
    birth = gender = None
    if structure_ok:
        try:
            _curp.validate(v)
            digit_ok = True
        except _curp.InvalidChecksum:
            digit_ok = False
        except Exception:
            structure_ok = False
        checks.append({"id": "digito", "label": "Dígito verificador", "ok": digit_ok})
        checks.append({"id": "entidad", "label": "Entidad de nacimiento reconocida", "ok": v[11:13] in STATES})
        try:
            birth = _curp_birth(v)
            gender = "H" if v[10] == "H" else ("M" if v[10] == "M" else v[10])
        except Exception:
            birth = None
    if dob and birth:
        checks.append({"id": "fecha", "label": "Fecha de nacimiento coincide", "ok": birth == dob})
    if sex and gender:
        checks.append({"id": "sexo", "label": "Sexo coincide", "ok": gender == sex})
    if apellido1 and nombres and structure_ok:
        expected = initials(apellido1, apellido2, nombres)
        checks.append({"id": "iniciales", "label": "Letras iniciales coherentes con el nombre",
                       "ok": v[:4] == expected, "expected": expected, "soft": True})
    hard_ok = all(c["ok"] for c in checks if not c.get("soft"))
    return {
        "value": v,
        "valid": structure_ok and digit_ok,
        "consistent": hard_ok,
        "warnings": [c for c in checks if c.get("soft") and not c["ok"]],
        "checks": checks,
        "birth_date": birth.isoformat() if birth else None,
        "state": STATES.get(v[11:13]) if structure_ok else None,
        "remote_lookup": "No consultado: sin conexión a RENAPO desde esta instalación",
    }


def build_rfc(apellido1: str, apellido2: str | None, nombres: str, dob: date, homoclave: str) -> str:
    body = initials(apellido1, apellido2, nombres) + dob.strftime("%y%m%d") + homoclave
    return body + _rfc.calc_check_digit(body)


def validate_rfc(value: str, apellido1: str | None = None, apellido2: str | None = None,
                 nombres: str | None = None, dob: date | None = None) -> dict:
    v = re.sub(r"[\s-]", "", (value or "").upper())
    checks = []
    try:
        _rfc.validate(v)
        structure_ok = len(v) == 13
    except Exception:
        structure_ok = False
    checks.append({"id": "formato", "label": "Formato de persona física (13 caracteres)", "ok": structure_ok})
    if structure_ok:
        digit_ok = v[-1] == _rfc.calc_check_digit(v[:-1])
        checks.append({"id": "digito", "label": "Dígito verificador de la homoclave", "ok": digit_ok, "soft": True})
        if dob:
            checks.append({"id": "fecha", "label": "Fecha de nacimiento coincide", "ok": v[4:10] == dob.strftime("%y%m%d")})
        if apellido1 and nombres:
            expected = initials(apellido1, apellido2, nombres)
            checks.append({"id": "iniciales", "label": "Letras iniciales coherentes con el nombre",
                           "ok": v[:4] == expected, "expected": expected, "soft": True})
    hard_ok = all(c["ok"] for c in checks if not c.get("soft"))
    return {
        "value": v,
        "valid": structure_ok,
        "consistent": hard_ok,
        "warnings": [c for c in checks if c.get("soft") and not c["ok"]],
        "checks": checks,
    }


_CLABE_WEIGHTS = (3, 7, 1)


def clabe_check_digit(first17: str) -> str:
    total = sum((int(d) * _CLABE_WEIGHTS[i % 3]) % 10 for i, d in enumerate(first17))
    return str((10 - total % 10) % 10)


def build_clabe(bank: str, plaza: str, account: str) -> str:
    body = f"{bank}{plaza}{account}"
    return body + clabe_check_digit(body)


def validate_clabe(value: str) -> dict:
    v = re.sub(r"\D", "", value or "")
    fmt = len(v) == 18
    digit = fmt and clabe_check_digit(v[:17]) == v[17]
    bank = BANKS.get(v[:3]) if fmt else None
    return {
        "value": v,
        "valid": fmt and digit,
        "checks": [
            {"id": "formato", "label": "18 dígitos", "ok": fmt},
            {"id": "digito", "label": "Dígito de control", "ok": bool(digit)},
            {"id": "banco", "label": "Banco reconocido en el catálogo", "ok": bank is not None},
        ],
        "bank_code": v[:3] if fmt else None,
        "bank": bank,
        "plaza": v[3:6] if fmt else None,
        "masked": f"{v[:3]} ••• •••• {v[-4:]}" if fmt else None,
    }


def validate_iban(value: str) -> dict:
    v = re.sub(r"\s", "", (value or "").upper())
    ok = _iban.is_valid(v)
    return {"value": v, "valid": ok, "country": v[:2] if ok else None,
            "checks": [{"id": "mod97", "label": "Dígitos de control (ISO 13616, mod 97)", "ok": ok}]}
