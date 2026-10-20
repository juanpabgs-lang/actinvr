"""Append-only, hash-chained audit log.

Each event stores sha256(prev_hash + canonical_json(event)). SQLite triggers reject
UPDATE and DELETE, and verify() recomputes the whole chain, so any edit made by
going around the triggers is detected at the first altered event.

Events never carry personal data in clear: only identifiers, statuses, rule ids
and hashes. That lets the log outlive crypto-shredding of a client's data.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
import tempfile
from pathlib import Path

from . import db, settings
from .timeutil import iso

GENESIS = "0" * 64


def canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_hex(data: bytes | str) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def _event_hash(prev_hash: str, body: dict) -> str:
    return sha256_hex(prev_hash + canonical(body))


def append(c: sqlite3.Connection, actor: str, action: str, case_id: str | None = None,
           obj: str | None = None, details: dict | None = None) -> dict:
    row = c.execute("SELECT hash FROM audit ORDER BY seq DESC LIMIT 1").fetchone()
    prev_hash = row[0] if row else GENESIS
    body = {
        "ts": iso(),
        "actor": actor,
        "action": action,
        "case_id": case_id,
        "object": obj,
        "details": details or {},
    }
    h = _event_hash(prev_hash, body)
    cur = c.execute(
        "INSERT INTO audit(ts, actor, action, case_id, object, details, prev_hash, hash) "
        "VALUES(?,?,?,?,?,?,?,?)",
        (body["ts"], actor, action, case_id, obj, canonical(body["details"]), prev_hash, h),
    )
    return {"seq": cur.lastrowid, "hash": h, **body}


def record(actor: str, action: str, case_id: str | None = None, obj: str | None = None,
           details: dict | None = None) -> dict:
    with db.tx() as c:
        return append(c, actor, action, case_id, obj, details)


def _row_body(r: sqlite3.Row) -> dict:
    return {
        "ts": r["ts"],
        "actor": r["actor"],
        "action": r["action"],
        "case_id": r["case_id"],
        "object": r["object"],
        "details": json.loads(r["details"]),
    }


def verify(c: sqlite3.Connection | None = None) -> dict:
    c = c or db.conn()
    prev = GENESIS
    count = 0
    for r in c.execute("SELECT * FROM audit ORDER BY seq"):
        count += 1
        body = _row_body(r)
        if r["prev_hash"] != prev:
            return {"ok": False, "count": count, "first_bad_seq": r["seq"],
                    "reason": "El enlace con el evento anterior no coincide", "head": prev}
        expected = _event_hash(prev, body)
        if expected != r["hash"]:
            return {"ok": False, "count": count, "first_bad_seq": r["seq"],
                    "reason": "El contenido del evento no corresponde con su huella",
                    "stored_hash": r["hash"], "recomputed_hash": expected, "head": prev}
        prev = r["hash"]
    return {"ok": True, "count": count, "head": prev, "verified_at": iso()}


def head() -> dict:
    r = db.one("SELECT seq, hash, ts FROM audit ORDER BY seq DESC LIMIT 1")
    if not r:
        return {"seq": 0, "hash": GENESIS, "ts": None}
    return {"seq": r["seq"], "hash": r["hash"], "ts": r["ts"]}


def events(case_id: str | None = None, limit: int = 200, before: int | None = None) -> list[dict]:
    sql = "SELECT * FROM audit"
    clauses, params = [], []
    if case_id:
        clauses.append("case_id = ?")
        params.append(case_id)
    if before:
        clauses.append("seq < ?")
        params.append(before)
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY seq DESC LIMIT ?"
    params.append(limit)
    out = []
    for r in db.query(sql, tuple(params)):
        out.append({"seq": r["seq"], "hash": r["hash"], "prev_hash": r["prev_hash"], **_row_body(r)})
    return out


def tamper_demo() -> dict:
    """Edit one event in a throwaway copy of the database and show that verify() catches it.

    The live database is never touched: the copy is made with SQLite's backup API.
    """
    tmpdir = Path(tempfile.mkdtemp(prefix="audit-tamper-", dir=settings.VAR_DIR))
    copy_path = tmpdir / "copy.db"
    try:
        dst = sqlite3.connect(copy_path)
        db.conn().backup(dst)
        dst.row_factory = sqlite3.Row
        target = dst.execute(
            "SELECT seq, action, details FROM audit WHERE action LIKE 'decision.%' "
            "OR action LIKE 'screening.%' ORDER BY seq DESC LIMIT 1"
        ).fetchone() or dst.execute("SELECT seq, action, details FROM audit ORDER BY seq DESC LIMIT 1").fetchone()
        if target is None:
            return {"ok": False, "reason": "No hay eventos todavía"}
        blocked_message = None
        try:
            dst.execute("UPDATE audit SET details = ? WHERE seq = ?", ('{"manipulado":true}', target["seq"]))
        except sqlite3.DatabaseError as exc:
            blocked_message = str(exc)
        dst.execute("DROP TRIGGER audit_no_update")
        details = json.loads(target["details"])
        details["nota"] = "editado fuera de la aplicación"
        if "decision" in details:
            details["decision"] = "aprobado"
        dst.execute("UPDATE audit SET details = ? WHERE seq = ?", (canonical(details), target["seq"]))
        dst.commit()
        result = verify(dst)
        dst.close()
        return {
            "trigger_blocked_update": blocked_message,
            "tampered_seq": target["seq"],
            "tampered_action": target["action"],
            "verification_of_copy": result,
            "live_database": verify(),
        }
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
