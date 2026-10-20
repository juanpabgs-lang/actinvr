"""HTTP API on :8013. Personal data never appears in logs or audit details."""
from __future__ import annotations

import hashlib
import json
import os
import secrets
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, Form, Header, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response

from . import (
    audit,
    cases,
    content,
    db,
    documents,
    egress,
    inspection,
    llm,
    pipeline,
    retention,
    seed,
    settings,
    staff,
    vault,
)
from .personas import LIVE, SEEDS, live_choices
from .timeutil import clock_payload, iso


def _persist_egress(entry: dict) -> None:
    try:
        with db.tx() as c:
            c.execute(
                "INSERT INTO egress_log(ts, host, port, kind, allowed, origin) VALUES(?,?,?,?,?,?)",
                (entry["ts"], entry.get("host"), entry.get("port"), entry["kind"],
                 1 if entry["allowed"] else 0, "guardia"),
            )
            if not entry["allowed"]:
                audit.append(c, "sistema", "salida.bloqueada", None, None,
                             {"host": entry.get("host"), "port": entry.get("port"), "kind": entry["kind"]})
    except Exception:
        pass


@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings.ensure_dirs()
    db.init_db()
    egress.install(persist=_persist_egress)
    if not db.one("SELECT 1 FROM audit LIMIT 1"):
        audit.record("sistema", "sistema.inicio", details={"demo": True, "synthetic": True})
    if os.environ.get("ONB_SEED", "1") == "1":
        seed.populate(summarize=os.environ.get("ONB_SUMMARY", "template") == "llm")
    yield


app = FastAPI(title="Alterna onboarding", docs_url=None, redoc_url=None, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _staff(x_staff_id: str | None) -> dict:
    if not x_staff_id:
        return staff.STAFF[0]
    try:
        return staff.get(x_staff_id)
    except KeyError:
        raise HTTPException(400, "persona de la mesa no reconocida")


def _case(case_id: str) -> dict:
    try:
        return cases.load(case_id)
    except (KeyError, vault.KeyShredded):
        raise HTTPException(404, "expediente no encontrado o clave destruida")


@app.get("/api/status")
def status():
    return {
        "ok": True,
        "entity": settings.ENTITY,
        "tenant": settings.TENANT,
        "vendor": settings.VENDOR,
        "model": llm.model_status(),
        "egress": {k: v for k, v in egress.status().items() if k != "recent_blocked"},
        "audit": audit.verify(),
        "clock": clock_payload(),
        "synthetic": True,
    }


@app.get("/api/clock")
def clock():
    return clock_payload()


@app.get("/api/personas")
def personas():
    return live_choices()


@app.post("/api/client/start")
def client_start(body: dict):
    persona_id = (body or {}).get("persona") or "live"
    if persona_id == "live":
        persona = dict(LIVE, seed="live")
    else:
        persona = next((dict(s) for s in SEEDS if s["seed"] == persona_id), None)
        if not persona:
            raise HTTPException(400, "persona no reconocida")
    created = cases.create(persona)
    rec = cases.load(created["id"])
    return {"id": created["id"], "resume_token": created["resume_token"], "case": cases.public_case(rec, include_data=True)}


@app.get("/api/client/{case_id}")
def client_get(case_id: str, token: str | None = None):
    if token and cases.resolve_token(token) != case_id:
        raise HTTPException(403, "token")
    rec = _case(case_id)
    docs = cases.documents(case_id)
    return {"case": cases.public_case(rec, include_data=True),
            "documents": [{k: d[k] for k in ("id", "kind", "filename", "status", "uploaded_at") if k in d} | {"analysis": _client_analysis(d.get("analysis") or {})} for d in docs]}


def _client_analysis(analysis: dict) -> dict:
    return {k: analysis.get(k) for k in ("kind", "status", "issues", "messages", "expired", "name_match", "address_match", "quality") if k in analysis or True}


@app.patch("/api/client/{case_id}")
def client_patch(case_id: str, body: dict, token: str | None = None):
    if token and cases.resolve_token(token) != case_id:
        raise HTTPException(403, "token")
    allowed = {"person", "occupation", "purpose", "initial_amount", "service", "route", "answers",
               "own_account", "is_pep", "pep_declared", "pep_role", "gdpr_ack", "ai_ack",
               "precontract_ack", "crs", "fatca", "stage", "source_of_wealth", "sof_kind",
               "product", "manuscript", "first_transfer"}
    patch = {k: v for k, v in (body or {}).items() if k in allowed}
    rec = cases.save_data(case_id, patch)
    return {"case": cases.public_case(rec, include_data=True)}


@app.post("/api/client/{case_id}/documents")
async def client_upload(case_id: str, kind: str = Form(...), file: UploadFile = File(...), token: str | None = Form(None)):
    if token and cases.resolve_token(token) != case_id:
        raise HTTPException(403, "token")
    data = await file.read()
    if len(data) > settings.UPLOAD_MAX_BYTES:
        raise HTTPException(413, "archivo demasiado grande")
    rec = _case(case_id)
    analysis = documents.analyze(kind, data, file.filename or "archivo", (rec["data"] or {}).get("person") or {})
    doc_id = cases.add_document(case_id, kind, file.filename or "archivo", analysis.get("mime") or file.content_type or "", data, analysis)
    return {"id": doc_id, "analysis": _client_analysis(analysis)}


@app.post("/api/client/{case_id}/sample/{kind}")
def client_sample(case_id: str, kind: str):
    from datetime import date

    from . import docsgen

    rec = _case(case_id)
    person = (rec["data"] or {}).get("person") or {}
    if kind == "pasaporte":
        expiry = date(2032, 6, 1)
        number = f"G{abs(hash(case_id)) % 100000000:08d}"
        data = docsgen.passport_png(person, number, date(2024, 6, 1), expiry)
        from .checks import mrz
        payload = {"mrz": mrz.build_td3(f"{person.get('apellido1','')} {person.get('apellido2') or ''}".strip(),
                                       person.get("nombres", ""), number, date.fromisoformat(person["dob"]),
                                       "F" if person.get("sex") == "M" else "M", expiry)}
        filename, mime = "pasaporte.png", "image/png"
    elif kind == "ine":
        number = f"ID{abs(hash(case_id)) % 100000000:08d}"
        data = docsgen.ine_png(person, number, date(2030, 1, 1))
        from .checks import mrz
        payload = {"mrz": mrz.build_td1(f"{person.get('apellido1','')} {person.get('apellido2') or ''}".strip(),
                                       person.get("nombres", ""), number, date.fromisoformat(person["dob"]),
                                       "F" if person.get("sex") == "M" else "M", date(2030, 1, 1))}
        filename, mime = "ine.png", "image/png"
    elif kind == "domicilio":
        data = docsgen.address_pdf(person, date(2026, 8, 20))
        payload, filename, mime = None, "domicilio.pdf", "application/pdf"
    elif kind == "origen_fondos":
        data = docsgen.funds_pdf(person, "nomina", int((rec["data"] or {}).get("initial_amount") or 40000), date(2026, 7, 1))
        payload, filename, mime = None, "origen.pdf", "application/pdf"
    else:
        raise HTTPException(400, "tipo")
    analysis = documents.analyze(kind, data, filename, person, payload=payload)
    doc_id = cases.add_document(case_id, kind, filename, mime, data, analysis)
    return {"id": doc_id, "analysis": _client_analysis(analysis)}


@app.post("/api/client/{case_id}/otp")
def client_otp(case_id: str):
    rec = _case(case_id)
    code = f"{secrets.randbelow(1000000):06d}"
    digest = hashlib.sha256(code.encode()).hexdigest()
    with db.tx() as c:
        c.execute("INSERT OR REPLACE INTO otps(case_id, code_hash, created_at, expires_at, attempts) VALUES(?,?,?,?,0)",
                  (case_id, digest, iso(), "2099-01-01T00:00:00.000Z"))
        c.execute("INSERT INTO notifications(case_id, channel, body, ts, sim_ts) VALUES(?,?,?,?,?)",
                  (case_id, "sms_simulado", "Tu código de firma está listo. Este mensaje no lleva tus datos.", iso(), iso()))
        audit.append(c, "cliente", "otp.emitido", case_id, None, {"canal": "simulado"})
    phone = ((rec["data"] or {}).get("person") or {}).get("phone") or ""
    return {"code": code, "channel": "simulado", "masked_phone": phone[:4] + " ··· " + phone[-3:] if phone else "",
            "note": "[Proveedor SMS: no hay. El código se muestra aquí.]"}


@app.post("/api/client/{case_id}/sign")
def client_sign(case_id: str, body: dict):
    rec = _case(case_id)
    row = db.one("SELECT * FROM otps WHERE case_id = ?", (case_id,))
    if not row:
        raise HTTPException(400, "pide primero el código")
    if hashlib.sha256((body or {}).get("code", "").encode()).hexdigest() != row["code_hash"]:
        raise HTTPException(400, "código incorrecto")
    manuscript = (body or {}).get("manuscript")
    rec["data"]["signature"] = {"signed_at": iso(), "code_hash": row["code_hash"], "manuscript": manuscript, "simulated": True}
    rec["data"]["stage"] = "hecho"
    rec["data"]["precontract_ack"] = True
    cases.save_data(case_id, rec["data"])
    result = pipeline.run(case_id, summarize=True)
    pdf, digest = pipeline.build_contract(case_id)
    rec["data"]["signature"]["document_hash"] = digest
    cases.save_data(case_id, rec["data"])
    cases.mark_submitted(case_id)
    return {"sha256": digest, "readiness": result["readiness"], "bytes": len(pdf)}


@app.post("/api/client/{case_id}/withdraw")
def client_withdraw(case_id: str):
    rec = cases.save_data(case_id, {"stage": "desistido"})
    with db.tx() as c:
        c.execute("UPDATE cases SET status = ?, updated_at = ? WHERE id = ?", ("desistido", iso(), case_id))
        audit.append(c, "cliente", "contrato.desistido", case_id, None,
                     {"base": "Directiva (UE) 2023/2673 [transposición ES pendiente]"})
    return {"status": "desistido", "case": cases.public_case(rec)}


@app.post("/api/client/{case_id}/help")
def client_help(case_id: str, body: dict):
    rec = _case(case_id)
    out = llm.help_answer((body or {}).get("question") or "", {"stage": rec.get("stage")}, case_id)
    return out


@app.get("/api/client/{case_id}/contract")
def client_contract(case_id: str):
    try:
        data = vault.load_file(case_id, "contrato")
    except Exception:
        raise HTTPException(404, "contrato aún no generado")
    return Response(data, media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="{case_id}-contrato.pdf"'})


@app.get("/api/desk/staff")
def desk_staff():
    return staff.STAFF


@app.get("/api/desk/queue")
def desk_queue():
    items = []
    for rec in cases.list_cases():
        if rec["status"] in {"borrador"}:
            continue
        items.append(cases.public_case(rec))
    counts = {}
    for it in items:
        counts[it["status"]] = counts.get(it["status"], 0) + 1
        counts[it.get("readiness") or "sin"] = counts.get(it.get("readiness") or "sin", 0) + 1
    return {"items": items, "counts": counts, "clock": clock_payload()}


@app.get("/api/desk/{case_id}")
def desk_case(case_id: str, x_staff_id: str | None = Header(None, alias="X-Staff-Id")):
    who = _staff(x_staff_id)
    rec = _case(case_id)
    if who["role"] != "inspector":
        audit.record(who["id"], "expediente.abierto", case_id, details={"rol": who["role"]})
    docs = cases.documents(case_id)
    events = audit.events(case_id, limit=80)
    decisions = [dict(r) for r in db.query("SELECT * FROM decisions WHERE case_id = ? ORDER BY ts", (case_id,))]
    return {
        "staff": who,
        "case": cases.public_case(rec, include_data=who["role"] != "inspector"),
        "documents": [{k: d.get(k) for k in ("id", "kind", "filename", "status", "sha256", "uploaded_at", "sim_ts", "superseded")}
                      | {"analysis": d.get("analysis") if who["role"] != "inspector" else {"status": d.get("status")}}
                      for d in docs],
        "audit": events,
        "decisions": decisions,
        "can": sorted(staff.CAN[who["role"]]),
        "retention": retention.clock(case_id),
    }


@app.get("/api/desk/{case_id}/document/{doc_id}")
def desk_document(case_id: str, doc_id: str, x_staff_id: str | None = Header(None, alias="X-Staff-Id")):
    who = _staff(x_staff_id)
    if who["role"] == "inspector":
        raise HTTPException(403, "el inspector ve huellas, no el documento")
    try:
        data = vault.load_file(case_id, doc_id)
    except Exception:
        raise HTTPException(404, "documento")
    row = db.one("SELECT mime, filename FROM documents WHERE id = ?", (doc_id,))
    return Response(data, media_type=(row["mime"] if row else "application/octet-stream"),
                    headers={"Content-Disposition": f'inline; filename="{row["filename"] if row else doc_id}"'})


@app.post("/api/desk/{case_id}/decide")
def desk_decide(case_id: str, body: dict, x_staff_id: str | None = Header(None, alias="X-Staff-Id")):
    who = _staff(x_staff_id)
    kind = (body or {}).get("kind")
    if kind not in staff.CAN[who["role"]]:
        raise HTTPException(403, "esta función no puede tomar esa decisión")
    rec = _case(case_id)
    required = rec.get("approval_level") or "cumplimiento"
    if kind == "aceptar" and not staff.can_accept(who["role"], required):
        raise HTTPException(403, f"este expediente pide autorización de {required}")
    previous = [dict(r) for r in db.query("SELECT * FROM decisions WHERE case_id = ?", (case_id,))]
    if kind == "aceptar":
        recs = [d for d in previous if d["kind"] == "recomendar" and d["actor_id"] != who["id"]]
        if not recs:
            raise HTTPException(400, "hace falta una recomendación previa de otra persona (cuatro ojos)")
    with db.tx() as c:
        c.execute("INSERT INTO decisions(case_id, actor_id, role, kind, comment, ts) VALUES(?,?,?,?,?,?)",
                  (case_id, who["id"], who["role"], kind, (body or {}).get("comment"), iso()))
        status = {"aceptar": "aceptado", "rechazar": "rechazado", "pedir_mas": "en_espera", "recomendar": rec["status"]}.get(kind, rec["status"])
        c.execute("UPDATE cases SET status = ?, updated_at = ? WHERE id = ?", (status, iso(), case_id))
        audit.append(c, who["id"], f"decision.{kind}", case_id, None,
                     {"rol": who["role"], "requerido": required})
    if kind == "aceptar":
        second = previous[-1] if previous else {}
        pipeline.build_contract(case_id, {
            "decision": "aceptado", "actor_id": who["id"], "actor_name": who["name"],
            "role": who["role"], "second_name": staff.ROLES.get(second.get("actor_id"), {}).get("name"),
            "ts": iso(), "case_id": case_id,
        })
    return {"status": status, "required": required}


@app.get("/api/compliance/data-map")
def data_map():
    return {"flows": content.DATA_MAP, "egress": egress.status()}


@app.post("/api/compliance/leak-test")
def leak_test():
    results = egress.leak_test()
    audit.record("sistema", "salida.prueba", details={"resultados": len(results),
                                                     "bloqueados": sum(1 for r in results if r["outcome"] == "bloqueado")})
    return {"results": results, "egress": egress.status()}


@app.get("/api/compliance/audit")
def audit_get(case_id: str | None = None):
    return {"verify": audit.verify(), "head": audit.head(), "events": audit.events(case_id)}


@app.post("/api/compliance/audit/verify")
def audit_verify():
    return audit.verify()


@app.post("/api/compliance/audit/tamper")
def audit_tamper():
    return audit.tamper_demo()


@app.get("/api/compliance/models")
def models():
    return {"status": llm.model_status(), "calls": llm.register()}


@app.post("/api/compliance/models/{call_id}/reproduce")
def models_repro(call_id: str):
    try:
        return llm.reproduce(call_id)
    except KeyError:
        raise HTTPException(404, "llamada")


@app.get("/api/compliance/rules")
def rules():
    from .rules import engine
    return engine.all_packs()


@app.get("/api/compliance/retention/{case_id}")
def retention_get(case_id: str, years: float | None = None):
    if years is not None:
        return retention.simulate(case_id, years)
    return retention.clock(case_id)


@app.post("/api/compliance/retention/{case_id}/shred")
def retention_shred(case_id: str, x_staff_id: str | None = Header(None, alias="X-Staff-Id")):
    who = _staff(x_staff_id)
    if who["role"] not in {"cumplimiento", "direccion"}:
        raise HTTPException(403, "solo cumplimiento o dirección")
    return retention.shred_case(case_id, who["id"])


@app.post("/api/compliance/inspection")
def inspection_build():
    out = inspection.build()
    audit.record("sistema", "inspeccion.exportada", details={"sha256": out["sha256"]})
    return {k: v for k, v in out.items() if k != "path"}


@app.get("/api/compliance/inspection/file")
def inspection_file():
    files = sorted(settings.EXPORTS_DIR.glob("inspeccion-*.zip"))
    if not files:
        raise HTTPException(404, "exporta primero")
    return FileResponse(files[-1], filename=files[-1].name, media_type="application/zip")


@app.get("/api/compliance/finreg")
def finreg():
    return FINREG_WITH_META()


@app.get("/api/compliance/dora")
def dora():
    return {"title": "Preguntas que cualquier proveedor de IA tiene que responder",
            "note": "Columna en blanco para el otro proveedor. No se nombra a nadie.",
            "rows": content.DORA}


@app.get("/api/platform")
def platform():
    return {"modules": content.PLATFORM, "foundation": [
        "Cadena de auditoría", "Bóveda por cliente", "Guardia de salida",
        "Reglas versionadas", "Modelo local", "Paquete de inspección",
    ]}


def FINREG_WITH_META():
    return {"questions": content.FINREG, "vendor": settings.VENDOR, "entity": settings.ENTITY}
