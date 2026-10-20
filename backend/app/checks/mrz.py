"""Machine Readable Zone per ICAO Doc 9303: TD3 (passport, 2x44) and TD1 (ID card, 3x30)."""
from __future__ import annotations

import re
import unicodedata
from datetime import date

FILLER = "<"
_WEIGHTS = (7, 3, 1)

_TO_DIGIT = str.maketrans({"O": "0", "Q": "0", "D": "0", "U": "0", "I": "1", "L": "1", "Z": "2",
                           "S": "5", "B": "8", "G": "6", "T": "7", "A": "4"})
_TO_ALPHA = str.maketrans({"0": "O", "1": "I", "2": "Z", "5": "S", "8": "B", "6": "G", "4": "A", "7": "T"})


def _value(ch: str) -> int:
    if ch.isdigit():
        return int(ch)
    if "A" <= ch <= "Z":
        return ord(ch) - 55
    return 0


def check_digit(field: str) -> str:
    return str(sum(_value(c) * _WEIGHTS[i % 3] for i, c in enumerate(field)) % 10)


def transliterate(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.upper())
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^A-Z ]", " ", text.replace("-", " ").replace("'", ""))
    return re.sub(r"\s+", " ", text).strip()


def _pad(s: str, n: int) -> str:
    return (s + FILLER * n)[:n]


def name_field(surnames: str, given: str, width: int) -> str:
    return _pad(f"{transliterate(surnames).replace(' ', FILLER)}{FILLER * 2}"
                f"{transliterate(given).replace(' ', FILLER)}", width)


def yymmdd(d: date) -> str:
    return d.strftime("%y%m%d")


def _date(value: str, kind: str) -> date | None:
    if not re.fullmatch(r"\d{6}", value):
        return None
    yy, mm, dd = int(value[:2]), int(value[2:4]), int(value[4:])
    this_yy = date.today().year % 100
    if kind == "birth":
        century = 1900 if yy > this_yy else 2000
    else:
        century = 2000 if yy < 70 else 1900
    try:
        return date(century + yy, mm, dd)
    except ValueError:
        return None


def build_td3(surnames: str, given: str, number: str, dob: date, sex: str, expiry: date,
              nationality: str = "MEX", issuer: str = "MEX", personal: str = "") -> list[str]:
    line1 = _pad(f"P{FILLER}{issuer}" + name_field(surnames, given, 39), 44)
    num = _pad(number, 9)
    pers = _pad(personal, 14)
    pers_cd = check_digit(pers) if personal else FILLER
    line2 = (num + check_digit(num) + nationality + yymmdd(dob) + check_digit(yymmdd(dob)) + sex
             + yymmdd(expiry) + check_digit(yymmdd(expiry)) + pers + pers_cd)
    line2 += check_digit(line2[0:10] + line2[13:20] + line2[21:43])
    return [line1, line2]


def build_td1(surnames: str, given: str, number: str, dob: date, sex: str, expiry: date,
              optional1: str = "", optional2: str = "", nationality: str = "MEX", issuer: str = "MEX",
              doc_code: str = "ID") -> list[str]:
    num = _pad(number, 9)
    line1 = _pad(f"{doc_code}{issuer}{num}{check_digit(num)}{_pad(optional1, 15)}", 30)
    line2 = (yymmdd(dob) + check_digit(yymmdd(dob)) + sex + yymmdd(expiry) + check_digit(yymmdd(expiry))
             + nationality + _pad(optional2, 11))
    line2 += check_digit(line1[5:30] + line2[0:7] + line2[8:15] + line2[18:29])
    line3 = name_field(surnames, given, 30)
    return [line1, line2, line3]


def _names(field: str) -> tuple[str, str]:
    field = re.sub(r"[KC]{3,}$", lambda m: FILLER * len(m.group()), field)
    surname, _, given = field.partition(FILLER * 2)
    return surname.replace(FILLER, " ").strip(), given.replace(FILLER, " ").strip()


def _fix(segment: str, kind: str) -> str:
    if kind == "digit":
        return segment.translate(_TO_DIGIT)
    if kind == "alpha":
        return segment.translate(_TO_ALPHA)
    return segment


def _check(field: str, digit: str, label: str, optional: bool = False) -> dict:
    if optional and set(field) <= {FILLER} and digit in (FILLER, "0"):
        return {"field": label, "ok": True, "skipped": True}
    return {"field": label, "ok": check_digit(field) == digit, "expected": check_digit(field), "found": digit}


def parse_td3(lines: list[str]) -> dict:
    l1, l2 = _pad(lines[0], 44), _pad(lines[1], 44)
    l1 = _fix(l1[:5], "alpha") + l1[5:]
    l2 = (l2[0:9] + _fix(l2[9], "digit") + _fix(l2[10:13], "alpha") + _fix(l2[13:20], "digit")
          + l2[20] + _fix(l2[21:28], "digit") + l2[28:42] + l2[42] + _fix(l2[43], "digit"))
    surnames, given = _names(l1[5:44])
    checks = [
        _check(l2[0:9], l2[9], "número de documento"),
        _check(l2[13:19], l2[19], "fecha de nacimiento"),
        _check(l2[21:27], l2[27], "fecha de caducidad"),
        _check(l2[28:42], l2[42], "dato personal", optional=True),
        _check(l2[0:10] + l2[13:20] + l2[21:43], l2[43], "dígito compuesto"),
    ]
    return {
        "format": "TD3",
        "lines": [l1, l2],
        "doc_type": l1[0],
        "issuer": l1[2:5],
        "surnames": surnames,
        "given_names": given,
        "number": l2[0:9].replace(FILLER, ""),
        "nationality": l2[10:13],
        "birth_date": (_date(l2[13:19], "birth") or None),
        "sex": {"M": "H", "F": "M"}.get(l2[20], l2[20]),
        "expiry_date": (_date(l2[21:27], "expiry") or None),
        "checks": checks,
        "valid": all(c["ok"] for c in checks),
    }


def parse_td1(lines: list[str]) -> dict:
    l1, l2, l3 = (_pad(x, 30) for x in lines[:3])
    l1 = _fix(l1[:5], "alpha") + l1[5:14] + _fix(l1[14], "digit") + l1[15:]
    l2 = (_fix(l2[0:7], "digit") + l2[7] + _fix(l2[8:15], "digit") + _fix(l2[15:18], "alpha")
          + l2[18:29] + _fix(l2[29], "digit"))
    surnames, given = _names(l3)
    checks = [
        _check(l1[5:14], l1[14], "número de documento"),
        _check(l2[0:6], l2[6], "fecha de nacimiento"),
        _check(l2[8:14], l2[14], "fecha de caducidad"),
        _check(l1[5:30] + l2[0:7] + l2[8:15] + l2[18:29], l2[29], "dígito compuesto"),
    ]
    return {
        "format": "TD1",
        "lines": [l1, l2, l3],
        "doc_type": l1[0:2],
        "issuer": l1[2:5],
        "surnames": surnames,
        "given_names": given,
        "number": l1[5:14].replace(FILLER, ""),
        "nationality": l2[15:18],
        "birth_date": _date(l2[0:6], "birth"),
        "sex": {"M": "H", "F": "M"}.get(l2[7], l2[7]),
        "expiry_date": _date(l2[8:14], "expiry"),
        "checks": checks,
        "valid": all(c["ok"] for c in checks),
    }


def extract_lines(text: str, width: int, count: int) -> list[str] | None:
    """Pick the MRZ lines out of raw OCR text."""
    candidates = []
    for raw in text.splitlines():
        line = raw.upper().replace(" ", "").replace("«", FILLER).replace("‹", FILLER)
        line = re.sub(r"[^A-Z0-9<]", "", line)
        if len(line) >= width - 6 and (FILLER in line or sum(ch.isdigit() for ch in line) >= 6):
            candidates.append(line)
    if len(candidates) < count:
        return None
    picked = candidates[-count:]
    return [(ln + FILLER * width)[:width] if len(ln) < width else ln[:width] for ln in picked]
