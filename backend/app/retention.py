"""Retention clock and crypto-shredding. AML: 10 years then delete; after 5 years, internal-control only."""
from __future__ import annotations

from datetime import datetime, timedelta

from . import audit, cases, db, vault
from .timeutil import UTC, iso, parse


def clock(case_id: str, as_of: datetime | None = None) -> dict:
    rec = cases.load(case_id)
    start = parse(rec["submitted_at"] or rec["created_at"])
    end = parse(rec["relationship_end"]) if rec["relationship_end"] else None
    origin = end or start
    now = as_of or datetime.now(UTC)
    age_days = (now - origin).days
    aml_until = origin + timedelta(days=3652)
    restrict_from = origin + timedelta(days=1826)
    mifid_until = origin + timedelta(days=1826)
    shredded = rec["shredded_at"] is not None
    if shredded:
        phase = "destruido"
    elif now >= aml_until:
        phase = "pendiente_eliminacion"
    elif now >= restrict_from:
        phase = "acceso_restringido"
    else:
        phase = "activo"
    return {
        "case_id": case_id,
        "phase": phase,
        "relationship_start": iso(start),
        "relationship_end": iso(end) if end else None,
        "aml_until": iso(aml_until),
        "restrict_from": iso(restrict_from),
        "mifid_until": iso(mifid_until),
        "age_days": age_days,
        "shredded_at": rec["shredded_at"],
        "cites": ["Ley 10/2010 art. 25", "RD 304/2014 art. 28.1", "Reglamento Delegado (UE) 2017/565 art. 76"],
    }


def simulate(case_id: str, years: float) -> dict:
    rec = cases.load(case_id)
    start = parse(rec["submitted_at"] or rec["created_at"])
    as_of = start + timedelta(days=int(years * 365.25))
    return clock(case_id, as_of=as_of)


def shred_case(case_id: str, actor: str) -> dict:
    rec = cases.load(case_id)
    out = vault.shred(case_id)
    with db.tx() as c:
        c.execute("UPDATE cases SET shredded_at = ?, data_enc = NULL, result_enc = NULL, updated_at = ? WHERE id = ?",
                  (out["shredded_at"], iso(), case_id))
        c.execute("UPDATE documents SET analysis_enc = NULL WHERE case_id = ?", (case_id,))
        audit.append(c, actor, "retencion.clave_destruida", case_id, None,
                     {"motivo": "simulación de fin de plazo o ejercicio de supresión"})
    return {"case_id": case_id, **out, "audit_survives": True, "pseudonym": rec["pseudonym"]}
