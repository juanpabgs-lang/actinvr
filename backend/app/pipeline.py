"""Deterministic overnight file: documents → screening → risk → MiFID → rules → summary → contract."""
from __future__ import annotations

from datetime import date

from . import cases, contract, documents, llm, mifid, risk, screening, vault
from .rules import engine
from .timeutil import iso


def snapshot_from(rec: dict, docs: list[dict] | None = None) -> dict:
    data = rec.get("data") or {}
    person = data.get("person") or {}
    docs = docs if docs is not None else cases.documents(rec["id"])
    by_kind: dict = {}
    for doc in docs:
        if doc.get("superseded"):
            continue
        analysis = doc.get("analysis") or {}
        by_kind[doc["kind"]] = {
            "present": True,
            "valid": analysis.get("valid_mrz") or analysis.get("status") == "ok",
            "expired": analysis.get("expired"),
            "issues": analysis.get("issues") or [],
            "analysis": analysis,
        }
    answers = data.get("answers") or {}
    suit = mifid.suitability(answers) if data.get("service") in {"asesoramiento", "gdc", None} else {}
    appr = {}
    if data.get("service") == "rto":
        appr = mifid.appropriateness(answers, data.get("product") or {"name": "instrumento", "complex": False})
        if data.get("manuscript") and appr.get("manuscript_required"):
            appr["manuscript"] = appr["manuscript_required"]
    xfer = data.get("first_transfer") or {
        "same_holder": True, "equivalent_country": True,
        "arrived": data.get("route") == "primer_ingreso",
        "country": "MX", "masked_account": (person.get("clabe") or "")[:3] + " ··· ···· " + (person.get("clabe") or "")[-4:],
    }
    video = data.get("video_id") or ({"passed": True, "provider": "Proveedor de videoidentificación (simulado)",
                                      "authorization": "SEPBLAC autorización general (simulado)",
                                      "liveness": "superado (sintético)"} if data.get("route") == "video_id" else {})
    identity_disc = any("nombre" in (by_kind.get(k, {}).get("issues") or []) and "parcial" not in i
                        for k, v in by_kind.items() for i in (v.get("issues") or []) if i == "nombre")
    return {
        "person": person,
        "documents": by_kind,
        "route": data.get("route") or rec.get("route"),
        "service": data.get("service") or rec.get("service"),
        "own_account": data.get("own_account", True),
        "purpose": data.get("purpose"),
        "occupation": data.get("occupation"),
        "occupation_documented": bool(data.get("occupation_documented") or data.get("occupation")),
        "initial_amount": data.get("initial_amount") or 0,
        "source_of_funds": {"documented": "origen_fondos" in by_kind or float(data.get("initial_amount") or 0) < 100_000,
                            "kind": data.get("sof_kind")},
        "source_of_wealth": {"documented": bool(data.get("is_pep"))},
        "is_pep": data.get("is_pep"),
        "pep_declared": data.get("pep_declared"),
        "pep_hit": False,
        "first_transfer": xfer,
        "video_id": video,
        "gdpr_ack": data.get("gdpr_ack"),
        "ai_ack": data.get("ai_ack"),
        "precontract_ack": data.get("precontract_ack") or data.get("stage") in {"firma", "hecho", "enviado"},
        "suitability": suit,
        "appropriateness": appr,
        "identity_discrepancy": identity_disc,
        "crs": data.get("crs") or {"residence": person.get("country"), "only_mx_es": True},
        "fatca": data.get("fatca") or {"us_person": False},
    }


def run(case_id: str, summarize: bool = True) -> dict:
    rec = cases.load(case_id)
    docs = cases.documents(case_id)
    snap = snapshot_from(rec, docs)
    screen = screening.screen(snap["person"])
    pep = screening.pep_screen(snap["person"], bool(snap.get("pep_declared") or snap.get("is_pep")))
    snap["screening"] = {**screen, "candidates": len(screen["candidates"]),
                         "discarded": len(screen["discarded"])}
    snap["is_pep"] = pep["is_pep"]
    snap["pep_hit"] = bool(pep["list_hits"]) and not snap.get("pep_declared")
    risk_out = risk.score(snap)
    findings = engine.evaluate({**snap, "screening": screen, "high_risk": risk_out["level"] == "alto"})
    blocking = engine.blocking(findings)
    passport = (snap["documents"].get("pasaporte") or {})
    if passport.get("expired") or (snap["documents"].get("ine") and not passport.get("present") and not passport.get("valid")):
        readiness = "bloqueado"
    elif any(f["id"] == "PBC-ID-05" and f["status"] == "fallo" for f in findings):
        readiness = "requiere_presencial"
    elif blocking:
        readiness = "faltan_datos"
    else:
        readiness = "listo_para_decidir"

    facts = {
        "person": {"nombres": snap["person"].get("nombres"), "apellido1": snap["person"].get("apellido1"),
                   "apellido2": snap["person"].get("apellido2")},
        "route": snap["route"], "service": snap["service"],
        "risk": risk_out, "screening": screen, "findings": findings,
        "suitability": snap.get("suitability"), "is_pep": snap.get("is_pep"),
    }
    summary = llm.draft_summary(facts, case_id=case_id) if summarize else {
        "text": llm.template_summary(facts), "fallback": True, "call_id": None,
        "prompt_version": llm.PROMPT_VERSION, "model": "plantilla",
    }
    result = {
        "identity": _identity_view(snap),
        "address": (snap["documents"].get("domicilio") or {}),
        "tax": {"curp": (snap["person"].get("curp") and True), "rfc": (snap["person"].get("rfc") and True),
                "crs": snap.get("crs"), "fatca": snap.get("fatca")},
        "account": snap.get("first_transfer"),
        "video_id": snap.get("video_id"),
        "screening": screen,
        "pep": pep,
        "risk": risk_out,
        "mifid": {"classification": mifid.classify(), "suitability": snap.get("suitability"),
                  "appropriateness": snap.get("appropriateness")},
        "findings": findings,
        "blocking": blocking,
        "readiness": readiness,
        "client_messages": engine.client_messages(findings),
        "summary": summary,
        "ran_at": iso(),
    }
    extras = {
        "risk_level": risk_out["level"], "risk_score": risk_out["score"],
        "profile": (snap.get("suitability") or {}).get("profile"),
        "approval_level": risk_out["approval_level"], "readiness": readiness,
        "summary_call_id": summary.get("call_id"),
    }
    cases.save_result(case_id, result, extras)
    return result


def build_contract(case_id: str, acceptance: dict | None = None) -> tuple[bytes, str]:
    rec = cases.load(case_id)
    data = rec.get("data") or {}
    result = rec.get("result") or {}
    payload = {
        **data,
        "suitability": (result.get("mifid") or {}).get("suitability") or mifid.suitability(data.get("answers") or {}),
        "signature": data.get("signature"),
    }
    pdf, digest = contract.render_with_hash(payload, acceptance)
    vault.store_file(case_id, "contrato", pdf)
    cases.save_result(case_id, extras={
        "contract_state": "aceptado" if acceptance else "firmado_cliente" if data.get("signature") else "generado",
        "contract_sha256": digest,
    })
    return pdf, digest


def _identity_view(snap: dict) -> dict:
    passport = snap["documents"].get("pasaporte") or {}
    ine = snap["documents"].get("ine") or {}
    return {
        "pasaporte": passport, "ine": ine,
        "fehaciente": bool(passport.get("valid") and not passport.get("expired")),
        "route": snap["route"],
    }
