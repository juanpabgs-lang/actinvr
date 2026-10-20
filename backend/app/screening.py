"""Screen names against the local synthetic lists.

A candidate match is never closed on the name alone. Date of birth or nationality
must contradict the list entry before the candidate is discarded. The list file
and its sha256 are recorded so a reviewer can replay the exact version used.
"""
from __future__ import annotations

import csv
import hashlib
import io
import re
from datetime import date
from pathlib import Path

from rapidfuzz import fuzz

from . import settings
from .checks.match import norm
from .timeutil import iso

LISTS = {
    "UE-FSF": ("eu_fsf.csv", "Mapa de sanciones financieras de la UE (formato)"),
    "ONU": ("un_consolidated.csv", "Lista consolidada del Consejo de Seguridad (formato)"),
    "OFAC-SDN": ("ofac_sdn.csv", "Specially Designated Nationals (formato)"),
    "UIF-MX": ("uif_mx.csv", "Personas bloqueadas UIF México (formato)"),
    "PEP-SINT": ("pep_synthetic.csv", "Personas con responsabilidad pública (sintético)"),
}

NAME_THRESHOLD = 85


def _rows(path: Path) -> tuple[str, list[dict]]:
    raw = path.read_text(encoding="utf-8")
    digest = hashlib.sha256(raw.encode()).hexdigest()
    lines = [line for line in raw.splitlines() if line and not line.startswith("#")]
    if lines and lines[0].startswith("schema:"):
        lines[0] = lines[0].split(":", 1)[1].strip()
    reader = csv.DictReader(io.StringIO("\n".join(lines)), delimiter=";")
    rows = []
    for row in reader:
        rows.append({k: (v if isinstance(v, str) else (v[0] if v else "")) for k, v in row.items() if k})
    return digest, rows


def _name_from_row(row: dict) -> str:
    for keys in (
        ("nombre", "apellidos"),
        ("first_name", "second_name", "third_name"),
        ("sdn_name",),
        ("nombre", "primer_apellido", "segundo_apellido"),
    ):
        if all(k in row for k in keys):
            return " ".join(row.get(k) or "" for k in keys)
    parts = [v for k, v in row.items() if k and isinstance(v, str) and v]
    return " ".join(parts)


def _dob(row: dict) -> str | None:
    for key in ("fecha_nacimiento", "date_of_birth"):
        if row.get(key) and row[key].strip():
            return row[key].strip()
    remarks = row.get("remarks") or ""
    m = re.search(r"DOB\s+(\d{2}\s+\w+\s+\d{4})", remarks, re.I)
    if m:
        return m.group(1)
    return None


def _nationality(row: dict) -> str | None:
    for key in ("nacionalidad", "nationality"):
        if row.get(key) and row[key].strip():
            return row[key].strip().upper()
    remarks = (row.get("remarks") or "").upper()
    m = re.search(r"NATIONALITY\s+([A-Z ]+)", remarks)
    return m.group(1).strip() if m else None


def _discard(person: dict, row: dict) -> tuple[bool, str | None]:
    declared_dob = person.get("dob")
    declared_nat = (person.get("nationality") or "").upper()
    listed_dob = _dob(row)
    listed_nat = _nationality(row)
    if declared_dob and listed_dob:
        try:
            listed = date.fromisoformat(listed_dob) if "-" in listed_dob else None
        except ValueError:
            listed = None
        declared = date.fromisoformat(declared_dob) if isinstance(declared_dob, str) else declared_dob
        if listed and declared and listed != declared:
            return True, "fecha de nacimiento distinta"
    if declared_nat and listed_nat:
        aliases = {"MX": "MEXICO", "MEX": "MEXICO", "ES": "SPAIN", "ESP": "SPAIN", "RU": "RUSSIA"}
        a = aliases.get(declared_nat, declared_nat)
        b = aliases.get(listed_nat, listed_nat)
        if a != b and declared_nat not in listed_nat and listed_nat not in a:
            return True, "nacionalidad distinta"
    return False, None


def screen(person: dict) -> dict:
    query = norm(f"{person.get('nombres', '')} {person.get('apellido1', '')} {person.get('apellido2', '')}")
    candidates, discarded, versions = [], [], []
    for list_id, (filename, label) in LISTS.items():
        path = settings.LISTS_DIR / filename
        digest, rows = _rows(path)
        versions.append({"id": list_id, "label": label, "file": filename, "sha256": digest, "rows": len(rows)})
        for row in rows:
            listed_name = _name_from_row(row)
            score = fuzz.token_sort_ratio(query, norm(listed_name))
            if score < NAME_THRESHOLD:
                continue
            drop, reason = _discard(person, row)
            item = {
                "list": list_id,
                "listed_name": listed_name.strip(),
                "score": round(score, 1),
                "dob": _dob(row),
                "nationality": _nationality(row),
                "reference": row.get("referencia") or row.get("reference_number") or row.get("ent_num") or row.get("folio"),
                "synthetic": True,
            }
            if drop:
                discarded.append({**item, "reason": reason})
            else:
                candidates.append(item)
    confirmed = [c for c in candidates if c["score"] >= 95 and c.get("dob") and str(person.get("dob")) == str(c["dob"])]
    return {
        "done": True,
        "query_hash": hashlib.sha256(query.encode()).hexdigest()[:16],
        "candidates": candidates,
        "discarded": discarded,
        "confirmed_hit": bool(confirmed),
        "confirmed": confirmed,
        "lists": versions,
        "screened_at": iso(),
        "note": "Listas sintéticas. Un candidato no se cierra sin fecha de nacimiento o nacionalidad que lo descarte.",
    }


def pep_screen(person: dict, declared: bool) -> dict:
    result = screen(person)
    pep_hits = [c for c in result["candidates"] if c["list"] == "PEP-SINT"]
    return {
        "declared": declared,
        "list_hits": pep_hits,
        "is_pep": declared or bool(pep_hits),
        "source": "declaración del cliente" if declared else ("lista sintética" if pep_hits else None),
    }
