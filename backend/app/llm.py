"""Local model client. The model never decides; it drafts prose from facts already computed."""
from __future__ import annotations

import hashlib
import json
import time
import uuid
from typing import Callable

import httpx

from . import audit, db, settings, vault
from .timeutil import iso

PROMPT_VERSION = "resumen-revisor-2026.10"
HELP_PROMPT_VERSION = "ayuda-cliente-2026.10"
PARAMS = {"temperature": 0, "seed": 42, "num_ctx": 4096, "num_predict": 280}


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _system_summary() -> str:
    return (
        "Eres un redactor de expedientes de una SGIIC española. "
        "Escribes en español de España, en tercera persona, para un revisor humano. "
        "No decides. No recomiendas aprobar ni rechazar. "
        "Solo ordenas los hechos que te dan, citas el identificador de cada comprobación "
        "y señalas lo que falta. Máximo 180 palabras. Sin adjetivos de marketing."
    )


def _system_help() -> str:
    return (
        "Eres un asistente de una entidad de inversión. Hablas en español de México, de tú. "
        "Frases cortas. Sin jerga. Si no sabes algo, dilo. "
        "Nunca pides datos que no sean de esta pantalla. "
        "Recuerda que eres un sistema de inteligencia artificial y que una persona decide. "
        "Máximo 80 palabras."
    )


def template_summary(facts: dict) -> str:
    person = facts.get("person") or {}
    name = " ".join(p for p in (person.get("nombres"), person.get("apellido1"), person.get("apellido2")) if p) or "el cliente"
    risk = facts.get("risk") or {}
    screening = facts.get("screening") or {}
    findings = facts.get("findings") or []
    blocking = [f for f in findings if f.get("severity") == "bloqueante" and f.get("status") in {"fallo", "pendiente"}]
    lines = [
        f"Expediente de {name}. Vía {facts.get('route', 'primer_ingreso')}. "
        f"Servicio {facts.get('service', 'asesoramiento')}.",
        f"Riesgo {risk.get('level', 'sin calcular')} ({risk.get('score', '—')} puntos), "
        f"diligencia {risk.get('regime', '—')}. Autorización: {risk.get('approval_level', '—')}.",
    ]
    if screening.get("confirmed_hit"):
        lines.append("Hay una coincidencia confirmada en listas de sanciones. Ver PBC-SAN-01.")
    elif screening.get("candidates"):
        lines.append(f"{len(screening['candidates'])} candidato(s) en listas, pendientes de descarte por el revisor.")
    elif screening.get("discarded"):
        lines.append(f"{len(screening['discarded'])} candidato(s) descartados por fecha de nacimiento o nacionalidad.")
    if facts.get("is_pep"):
        lines.append("Persona con responsabilidad pública declarada o detectada (PBC-PEP-01).")
    if blocking:
        lines.append("Pendiente o en fallo: " + ", ".join(f['id'] for f in blocking[:8]) + ".")
    else:
        lines.append("Ninguna regla bloqueante en fallo o pendiente. El revisor puede decidir.")
    suit = facts.get("suitability") or {}
    if suit.get("profile"):
        lines.append(f"Perfil de inversor: {suit['profile']}.")
    return " ".join(lines)


def template_help(question: str) -> str:
    q = (question or "").lower()
    if "pasaporte" in q or "ine" in q:
        return ("El documento que nos sirve es el pasaporte vigente. "
                "La credencial INE la guardamos como complemento, no sustituye al pasaporte. "
                "Esto te lo dice un sistema de inteligencia artificial; una persona revisa el expediente.")
    if "comprobante" in q or "domicilio" in q:
        return ("Sirve un recibo de luz, agua, predial o un estado de cuenta a tu nombre, "
                "de los últimos tres meses. Eso es política interna, no un artículo de la ley. "
                "Una persona revisa el expediente.")
    if "pep" in q or "cargo" in q:
        return ("Si tú o tu pareja, padres o hijos tienen o tuvieron un cargo público importante, "
                "dilo. No cierra la cuenta: cambia quién tiene que firmar la aceptación. "
                "Una persona decide.")
    return ("Estoy aquí para explicar esta pantalla. No decido si te aceptan. "
            "Si algo no está claro, sigue las instrucciones de cada paso o espera a la mesa de Madrid.")


def model_status() -> dict:
    if not settings.MODEL_ENABLED:
        return {"available": False, "reason": "desactivado por configuración", "name": settings.MODEL_NAME,
                "pinned_digest": settings.MODEL_PINNED_DIGEST}
    try:
        with httpx.Client(timeout=2.0) as client:
            tags = client.get(f"http://{settings.MODEL_HOST}:{settings.MODEL_PORT}/api/tags")
            tags.raise_for_status()
            models = tags.json().get("models") or []
        match = next((m for m in models if m.get("name") == settings.MODEL_NAME), None)
        digest = (match or {}).get("digest", "")
        short = digest[:12] if digest else None
        return {
            "available": match is not None,
            "name": settings.MODEL_NAME,
            "digest": digest,
            "short_digest": short,
            "pinned_digest": settings.MODEL_PINNED_DIGEST,
            "digest_matches_pin": bool(short) and short == settings.MODEL_PINNED_DIGEST,
            "host": f"{settings.MODEL_HOST}:{settings.MODEL_PORT}",
            "license": "Apache 2.0",
            "provider": "Mistral AI (Ministral 3 3B)",
            "params": PARAMS,
        }
    except Exception as exc:
        return {"available": False, "reason": str(exc), "name": settings.MODEL_NAME,
                "pinned_digest": settings.MODEL_PINNED_DIGEST, "host": f"{settings.MODEL_HOST}:{settings.MODEL_PORT}"}


def _complete(system: str, user: str) -> tuple[str, dict]:
    status = model_status()
    if not status.get("available"):
        raise RuntimeError(status.get("reason") or "modelo no disponible")
    payload = {
        "model": settings.MODEL_NAME,
        "stream": False,
        "options": PARAMS,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
    }
    with httpx.Client(timeout=45.0) as client:
        resp = client.post(f"http://{settings.MODEL_HOST}:{settings.MODEL_PORT}/api/chat", json=payload)
        resp.raise_for_status()
        data = resp.json()
    text = (data.get("message") or {}).get("content") or ""
    return text.strip(), {"eval_count": data.get("eval_count"), "eval_duration": data.get("eval_duration")}


def _store_call(purpose: str, case_id: str | None, prompt_version: str, system: str, user: str,
                output: str, fallback: bool, duration_ms: int, digest: str | None) -> str:
    call_id = f"MC-{uuid.uuid4().hex[:12]}"
    io = {"system": system, "user": user, "output": output}
    io_enc = None
    if case_id:
        try:
            io_enc = vault.enc_json(case_id, io, f"model:{call_id}")
        except Exception:
            io_enc = None
    with db.tx() as c:
        c.execute(
            "INSERT INTO model_calls(id, ts, purpose, case_id, model, digest, prompt_version, "
            "prompt_hash, input_hash, params, output_hash, duration_ms, fallback, io_enc) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (call_id, iso(), purpose, case_id, settings.MODEL_NAME, digest, prompt_version,
             _hash(system), _hash(user), json.dumps(PARAMS, sort_keys=True), _hash(output),
             duration_ms, 1 if fallback else 0, io_enc),
        )
        audit.append(c, "modelo", f"modelo.{purpose}", case_id, call_id,
                     {"fallback": fallback, "digest": digest, "prompt_version": prompt_version,
                      "prompt_hash": _hash(system), "input_hash": _hash(user), "output_hash": _hash(output)})
    return call_id


def draft_summary(facts: dict, case_id: str | None = None) -> dict:
    user = json.dumps(facts, ensure_ascii=False, sort_keys=True)[:4000]
    started = time.perf_counter()
    status = model_status()
    try:
        text, _meta = _complete(_system_summary(), user)
        fallback = False
    except Exception:
        text, fallback = template_summary(facts), True
    duration = int((time.perf_counter() - started) * 1000)
    call_id = _store_call("resumen", case_id, PROMPT_VERSION, _system_summary(), user, text,
                          fallback, duration, status.get("digest") or status.get("pinned_digest"))
    return {"text": text, "fallback": fallback, "call_id": call_id, "prompt_version": PROMPT_VERSION,
            "model": settings.MODEL_NAME, "digest": status.get("short_digest") or settings.MODEL_PINNED_DIGEST}


def help_answer(question: str, context: dict | None = None, case_id: str | None = None) -> dict:
    user = f"Pregunta: {question}\nContexto: {json.dumps(context or {}, ensure_ascii=False)[:800]}"
    started = time.perf_counter()
    status = model_status()
    try:
        text, _meta = _complete(_system_help(), user)
        fallback = False
    except Exception:
        text, fallback = template_help(question), True
    duration = int((time.perf_counter() - started) * 1000)
    call_id = _store_call("ayuda", case_id, HELP_PROMPT_VERSION, _system_help(), user, text,
                          fallback, duration, status.get("digest") or status.get("pinned_digest"))
    return {"text": text, "fallback": fallback, "call_id": call_id, "ai_disclosure": True}


def reproduce(call_id: str) -> dict:
    row = db.one("SELECT * FROM model_calls WHERE id = ?", (call_id,))
    if not row:
        raise KeyError(call_id)
    if not row["case_id"] or row["io_enc"] is None:
        return {"call_id": call_id, "error": "No hay entrada cifrada para reproducir"}
    io = vault.dec_json(row["case_id"], row["io_enc"], f"model:{call_id}")
    started = time.perf_counter()
    try:
        text, _meta = _complete(io["system"], io["user"])
        fallback = False
    except Exception:
        text, fallback = io.get("output"), True
    return {
        "call_id": call_id,
        "original_output_hash": row["output_hash"],
        "reproduced_output_hash": _hash(text or ""),
        "matches": _hash(text or "") == row["output_hash"],
        "fallback": fallback,
        "duration_ms": int((time.perf_counter() - started) * 1000),
        "params": json.loads(row["params"]),
        "prompt_version": row["prompt_version"],
        "digest": row["digest"],
    }


def register() -> list[dict]:
    rows = db.query("SELECT id, ts, purpose, case_id, model, digest, prompt_version, prompt_hash, "
                    "input_hash, output_hash, duration_ms, fallback FROM model_calls ORDER BY ts DESC LIMIT 50")
    return [dict(r) for r in rows]
