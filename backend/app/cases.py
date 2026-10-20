"""Encrypted case persistence and public views that never leak ciphertext."""
from __future__ import annotations

import hashlib
import json
import secrets
from typing import Any

from . import audit, db, vault
from .timeutil import iso, parse


def new_id(c) -> str:
    n = db.next_counter(c, "expediente")
    return f"EXP-26-{n:04d}"


def create(persona: dict, seeded: bool = False, submitted_at: str | None = None) -> dict:
    with db.tx() as c:
        case_id = new_id(c)
        now = iso()
        data = {
            "person": persona.get("person"),
            "occupation": persona.get("occupation"),
            "purpose": persona.get("purpose"),
            "initial_amount": persona.get("initial_amount"),
            "service": persona.get("service") or "asesoramiento",
            "route": persona.get("route") or "primer_ingreso",
            "own_account": True,
            "is_pep": bool(persona.get("is_pep")),
            "pep_declared": bool(persona.get("pep_declared")),
            "pep_role": persona.get("pep_role"),
            "answers": persona.get("answers") or {},
            "product": persona.get("product"),
            "gdpr_ack": False,
            "ai_ack": False,
            "stage": "bienvenida",
        }
        vault.create_key(case_id)
        c.execute(
            "INSERT INTO cases(id, pseudonym, persona, route, service, status, stage, "
            "created_at, updated_at, submitted_at, last_client_activity, seeded, synthetic, data_enc) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,1,?)",
            (case_id, persona.get("pseudonym") or _name(persona.get("person") or {}),
             persona.get("seed") or persona.get("id"), data["route"], data["service"],
             "borrador" if not seeded else "en_cola",
             "bienvenida", now, now, submitted_at, now, 1 if seeded else 0,
             vault.enc_json(case_id, data, "form")),
        )
        token = secrets.token_urlsafe(24)
        c.execute("INSERT INTO tokens(token_hash, case_id, created_at, expires_at) VALUES(?,?,?,?)",
                  (_th(token), case_id, now, "2099-01-01T00:00:00.000Z"))
        audit.append(c, "cliente", "expediente.creado", case_id, None,
                     {"seeded": seeded, "persona": persona.get("seed") or persona.get("id")})
    return {"id": case_id, "resume_token": token}


def _name(person: dict) -> str:
    return " ".join(p for p in (person.get("nombres"), person.get("apellido1"), person.get("apellido2")) if p)


def _th(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def resolve_token(token: str) -> str | None:
    row = db.one("SELECT case_id FROM tokens WHERE token_hash = ?", (_th(token),))
    return row["case_id"] if row else None


def load(case_id: str) -> dict:
    row = db.one("SELECT * FROM cases WHERE id = ?", (case_id,))
    if not row:
        raise KeyError(case_id)
    data = vault.dec_json(case_id, row["data_enc"], "form", default={}) or {}
    result = vault.dec_json(case_id, row["result_enc"], "result", default={}) or {}
    rec = dict(row)
    rec["data"] = data
    rec["result"] = result
    return rec


def save_data(case_id: str, patch: dict, actor: str = "cliente") -> dict:
    with db.tx() as c:
        row = c.execute("SELECT data_enc, stage FROM cases WHERE id = ?", (case_id,)).fetchone()
        if not row:
            raise KeyError(case_id)
        data = vault.dec_json(case_id, row["data_enc"], "form", default={}) or {}
        data.update(patch)
        now = iso()
        c.execute("UPDATE cases SET data_enc = ?, stage = ?, route = ?, service = ?, "
                  "updated_at = ?, last_client_activity = ? WHERE id = ?",
                  (vault.enc_json(case_id, data, "form"), data.get("stage") or row["stage"],
                   data.get("route"), data.get("service"), now, now, case_id))
        audit.append(c, actor, "expediente.actualizado", case_id, None,
                     {"campos": sorted(patch.keys()), "stage": data.get("stage")})
    return load(case_id)


def save_result(case_id: str, result: dict | None = None, extras: dict | None = None) -> None:
    extras = extras or {}
    assignments = ["updated_at = ?"]
    values: list = [iso()]
    if result is not None:
        assignments.append("result_enc = ?")
        values.append(vault.enc_json(case_id, result, "result"))
    mapping = {
        "risk_level": "risk_level", "risk_score": "risk_score", "profile": "profile",
        "approval_level": "approval_level", "readiness": "readiness",
        "summary_call_id": "summary_call_id", "contract_state": "contract_state",
        "contract_sha256": "contract_sha256",
    }
    for key, column in mapping.items():
        if key in extras and extras[key] is not None:
            assignments.append(f"{column} = ?")
            values.append(extras[key])
    if extras.get("status"):
        assignments.append("status = ?")
        values.append(extras["status"])
    values.append(case_id)
    with db.tx() as c:
        c.execute(f"UPDATE cases SET {', '.join(assignments)} WHERE id = ?", tuple(values))


def mark_submitted(case_id: str, submitted_at: str | None = None) -> None:
    with db.tx() as c:
        now = iso()
        c.execute("UPDATE cases SET status = ?, submitted_at = ?, arrived_at = ?, updated_at = ? WHERE id = ?",
                  ("en_cola", submitted_at or now, now, now, case_id))
        audit.append(c, "cliente", "expediente.enviado", case_id, None, {})


def add_document(case_id: str, kind: str, filename: str, mime: str, data: bytes,
                 analysis: dict, sim_ts: str | None = None) -> str:
    doc_id = f"DOC-{secrets.token_hex(4)}"
    vault.store_file(case_id, doc_id, analysis.pop("bytes_clean", None) or data)
    digest = hashlib.sha256(data).hexdigest()
    with db.tx() as c:
        if kind in {"domicilio", "pasaporte"}:
            c.execute("UPDATE documents SET superseded = 1 WHERE case_id = ? AND kind = ? AND superseded = 0",
                      (case_id, kind))
        c.execute(
            "INSERT INTO documents(id, case_id, kind, filename, mime, size, sha256, uploaded_at, sim_ts, "
            "status, meta_removed, analysis_enc) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (doc_id, case_id, kind, filename, mime, len(data), digest, iso(), sim_ts,
             analysis.get("status") or "ok", json.dumps(analysis.get("meta_removed") or [], ensure_ascii=False),
             vault.enc_json(case_id, analysis, f"doc:{doc_id}")),
        )
        audit.append(c, "cliente", "documento.subido", case_id, doc_id,
                     {"kind": kind, "sha256": digest, "status": analysis.get("status"),
                      "issues": analysis.get("issues")})
    return doc_id


def documents(case_id: str) -> list[dict]:
    out = []
    for r in db.query("SELECT * FROM documents WHERE case_id = ? ORDER BY uploaded_at", (case_id,)):
        rec = dict(r)
        rec["analysis"] = vault.dec_json(case_id, r["analysis_enc"], f"doc:{r['id']}", default={})
        rec.pop("analysis_enc", None)
        out.append(rec)
    return out


def public_case(rec: dict, include_data: bool = False) -> dict:
    person = (rec.get("data") or {}).get("person") or {}
    view = {
        "id": rec["id"],
        "pseudonym": rec["pseudonym"],
        "persona": rec["persona"],
        "route": rec["route"],
        "service": rec["service"],
        "status": rec["status"],
        "stage": rec["stage"],
        "risk_level": rec["risk_level"],
        "risk_score": rec["risk_score"],
        "profile": rec["profile"],
        "approval_level": rec["approval_level"],
        "readiness": rec["readiness"],
        "created_at": rec["created_at"],
        "updated_at": rec["updated_at"],
        "submitted_at": rec["submitted_at"],
        "arrived_at": rec["arrived_at"],
        "seeded": bool(rec["seeded"]),
        "synthetic": True,
        "contract_state": rec["contract_state"],
        "contract_sha256": rec["contract_sha256"],
        "shredded_at": rec["shredded_at"],
        "initials": "".join(p[0] for p in (rec["pseudonym"] or "").split()[:2]),
    }
    if include_data:
        view["data"] = rec.get("data")
        view["result"] = rec.get("result")
    else:
        view["country"] = person.get("country")
    return view


def list_cases() -> list[dict]:
    rows = db.query("SELECT * FROM cases ORDER BY COALESCE(submitted_at, created_at)")
    out = []
    for r in rows:
        rec = dict(r)
        if rec.get("shredded_at"):
            rec["data"], rec["result"] = {}, {}
            out.append(rec)
            continue
        try:
            rec["data"] = vault.dec_json(r["id"], r["data_enc"], "form", default={}) if r["data_enc"] else {}
            rec["result"] = vault.dec_json(r["id"], r["result_enc"], "result", default={}) if r["result_enc"] else {}
        except vault.KeyShredded:
            rec["data"], rec["result"] = {}, {}
        out.append(rec)
    return out
