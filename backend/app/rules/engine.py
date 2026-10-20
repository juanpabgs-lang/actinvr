"""Load versioned rule packs and evaluate them against a case snapshot."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

from .. import settings

PACKS = {
    "ES-PBC": "es_pbc_2026_10.yaml",
    "MiFID-ALTERNA": "mifid_alterna.yaml",
}


@lru_cache
def load_pack(name: str) -> dict:
    path = settings.RULES_DIR / PACKS[name]
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def all_packs() -> list[dict]:
    return [load_pack(name) for name in PACKS]


def _rule(pack: dict, rule_id: str) -> dict:
    for rule in pack["rules"]:
        if rule["id"] == rule_id:
            return rule
    raise KeyError(rule_id)


def _hit(pack: dict, rule_id: str, status: str, evidence: dict | None = None) -> dict:
    rule = _rule(pack, rule_id)
    return {
        "id": rule["id"],
        "pack": f"{pack['pack']} v{pack['version']}",
        "title": rule["title"],
        "cites": rule["cites"],
        "severity": rule["severity"],
        "status": status,
        "client": rule.get("client"),
        "reviewer": rule.get("reviewer"),
        "evidence": evidence or {},
    }


def evaluate(snapshot: dict) -> list[dict]:
    pbc = load_pack("ES-PBC")
    mif = load_pack("MiFID-ALTERNA")
    person = snapshot.get("person") or {}
    docs = snapshot.get("documents") or {}
    route = snapshot.get("route") or "primer_ingreso"
    service = snapshot.get("service") or "asesoramiento"
    findings: list[dict] = []

    findings.append(_hit(pbc, "PBC-ID-01", "ok" if person.get("nombres") else "pendiente"))

    passport = docs.get("pasaporte") or {}
    ine = docs.get("ine") or {}
    if passport.get("valid") and not passport.get("expired"):
        findings.append(_hit(pbc, "PBC-ID-02", "ok", {"documento": "pasaporte"}))
    elif passport.get("expired"):
        findings.append(_hit(pbc, "PBC-ID-02", "fallo", {"motivo": "pasaporte caducado"}))
    elif ine.get("present") and not passport.get("present"):
        findings.append(_hit(pbc, "PBC-ID-03", "fallo", {"documento": "solo INE"}))
        findings.append(_hit(pbc, "PBC-ID-02", "fallo", {"motivo": "falta pasaporte"}))
    else:
        findings.append(_hit(pbc, "PBC-ID-02", "pendiente"))

    if route in {"primer_ingreso", "video_id", "qeas"}:
        findings.append(_hit(pbc, "PBC-ID-04", "ok"))

    if snapshot.get("identity_discrepancy"):
        findings.append(_hit(pbc, "PBC-ID-05", "fallo", {"campo": snapshot.get("discrepancy_field")}))

    if route == "primer_ingreso":
        xfer = snapshot.get("first_transfer") or {}
        ok = bool(xfer.get("same_holder") and xfer.get("equivalent_country") and xfer.get("arrived"))
        findings.append(_hit(pbc, "PBC-NP-01", "ok" if ok else "pendiente", xfer))
    elif route == "video_id":
        video = snapshot.get("video_id") or {}
        findings.append(_hit(pbc, "PBC-NP-02", "ok" if video.get("passed") else "pendiente", video))
    elif route == "qeas":
        findings.append(_hit(pbc, "PBC-NP-03", "ok" if snapshot.get("qeas") else "pendiente"))

    findings.append(_hit(pbc, "PBC-TR-01", "ok" if snapshot.get("own_account") else "pendiente"))
    findings.append(_hit(pbc, "PBC-PR-01", "ok" if snapshot.get("purpose") and snapshot.get("occupation") else "pendiente"))

    amount = float((snapshot.get("initial_amount") or 0))
    sof = snapshot.get("source_of_funds") or {}
    if amount >= 100_000 or snapshot.get("high_risk"):
        findings.append(_hit(pbc, "PBC-OR-01", "ok" if sof.get("documented") else "pendiente",
                             {"importe": amount, "umbral": 100000}))

    if snapshot.get("is_pep") or snapshot.get("pep_hit"):
        findings.append(_hit(pbc, "PBC-PEP-01", "ok" if snapshot.get("pep_declared") else "aviso",
                             {"origen_patrimonio": bool((snapshot.get("source_of_wealth") or {}).get("documented"))}))

    screening = snapshot.get("screening") or {}
    if screening.get("confirmed_hit"):
        findings.append(_hit(pbc, "PBC-SAN-01", "fallo", screening))
    elif screening.get("done"):
        findings.append(_hit(pbc, "PBC-SAN-01", "ok", {"candidatos": screening.get("candidates", 0),
                                                       "descartados": screening.get("discarded", 0)}))
    else:
        findings.append(_hit(pbc, "PBC-SAN-01", "pendiente"))

    findings.append(_hit(pbc, "PBC-SAN-02", "ok"))
    findings.append(_hit(pbc, "PBC-CON-01", "ok"))
    findings.append(_hit(pbc, "PBC-DAT-01", "ok" if snapshot.get("gdpr_ack") else "pendiente"))
    if snapshot.get("special_exam"):
        findings.append(_hit(pbc, "PBC-DAT-02", "ok"))
    if snapshot.get("incomplete_cdd"):
        findings.append(_hit(pbc, "PBC-DIR-01", "aviso"))

    findings.append(_hit(mif, "MIF-CL-01", "ok"))
    if service in {"asesoramiento", "gdc"}:
        suit = snapshot.get("suitability") or {}
        findings.append(_hit(mif, "MIF-ID-01", "ok" if suit.get("complete") else "pendiente"))
        findings.append(_hit(mif, "MIF-ID-02", "ok" if suit.get("profile") else "pendiente",
                             {"perfil": suit.get("profile")}))
        findings.append(_hit(mif, "MIF-ID-03", "ok" if "sustainability" in suit else "pendiente"))
    if service == "rto":
        appr = snapshot.get("appropriateness") or {}
        findings.append(_hit(mif, "MIF-CO-01", "ok" if appr.get("done") else "pendiente"))
        if appr.get("complex") and not appr.get("convenient"):
            findings.append(_hit(mif, "MIF-CO-02", "ok" if appr.get("manuscript") else "pendiente"))
    findings.append(_hit(mif, "MIF-PRE-01", "ok" if snapshot.get("precontract_ack") else "pendiente"))
    findings.append(_hit(mif, "MIF-REG-01", "ok"))
    findings.append(_hit(mif, "MIF-IA-01", "ok" if snapshot.get("ai_ack") else "pendiente"))
    findings.append(_hit(mif, "MIF-DIS-01", "ok"))
    return findings


def blocking(findings: list[dict]) -> list[dict]:
    return [f for f in findings if f["severity"] == "bloqueante" and f["status"] in {"fallo", "pendiente"}]


def client_messages(findings: list[dict]) -> list[dict]:
    return [{"id": f["id"], "status": f["status"], "text": f["client"]}
            for f in findings if f.get("client") and f["status"] in {"fallo", "pendiente", "aviso"}]
