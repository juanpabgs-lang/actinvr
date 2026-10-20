from datetime import date

from app import mifid, risk, screening
from app.rules import engine


def test_rule_packs_load_and_evaluate():
    packs = engine.all_packs()
    assert {p["pack"] for p in packs} == {"ES-PBC", "MiFID-ALTERNA"}
    assert sum(len(p["rules"]) for p in packs) >= 25

    clean = {
        "person": {"nombres": "Ana", "country": "MX"},
        "documents": {"pasaporte": {"present": True, "valid": True, "expired": False}},
        "route": "primer_ingreso",
        "first_transfer": {"same_holder": True, "equivalent_country": True, "arrived": True},
        "own_account": True,
        "purpose": "inversión",
        "occupation": "ingeniera",
        "gdpr_ack": True,
        "ai_ack": True,
        "precontract_ack": True,
        "service": "asesoramiento",
        "suitability": {"complete": True, "profile": "moderado", "sustainability": False},
        "screening": {"done": True, "candidates": 0, "discarded": 1},
    }
    findings = engine.evaluate(clean)
    assert engine.blocking(findings) == []

    expired = dict(clean, documents={"pasaporte": {"present": True, "valid": False, "expired": True},
                                     "ine": {"present": True}})
    assert any(f["id"] == "PBC-ID-02" and f["status"] == "fallo" for f in engine.evaluate(expired))

    ine_only = dict(clean, documents={"ine": {"present": True}, "pasaporte": {}})
    ids = {f["id"] for f in engine.evaluate(ine_only) if f["status"] == "fallo"}
    assert "PBC-ID-03" in ids

    disc = dict(clean, identity_discrepancy=True, discrepancy_field="apellido2")
    assert any(f["id"] == "PBC-ID-05" and f["status"] == "fallo" for f in engine.evaluate(disc))


def test_screening_discards_on_dob_keeps_true_hit():
    person = {"nombres": "Elena", "apellido1": "Vásquez", "apellido2": "Ríos",
              "dob": "1994-02-17", "nationality": "MX"}
    out = screening.screen(person)
    assert out["done"]
    assert out["discarded"]
    assert not out["confirmed_hit"]
    assert all(d["reason"] for d in out["discarded"])

    hit = screening.screen({**person, "dob": "1968-04-11"})
    assert hit["confirmed_hit"]
    assert hit["confirmed"][0]["list"] in {"UE-FSF", "ONU", "OFAC-SDN", "UIF-MX"}


def test_risk_scorecard_and_pep_approval():
    base = {
        "person": {"country": "MX"},
        "route": "primer_ingreso",
        "initial_amount": 40_000,
        "first_transfer": {"same_holder": True, "equivalent_country": True},
        "screening": {"done": True},
    }
    low = risk.score(base)
    assert low["regime"] == "normal"
    assert low["approval_level"] == "cumplimiento"

    pep = risk.score({**base, "is_pep": True, "initial_amount": 250_000})
    assert pep["regime"] == "reforzada"
    assert pep["approval_level"] == "direccion"
    assert any("14.5.b" in m for m in pep["measures"])
    assert pep["score"] == sum(f["points"] for f in pep["factors"])


def test_suitability_profiles_and_manuscript():
    answers = {
        "horizon": "10+", "capacity": "buy", "experience": "complex",
        "knowledge": "finance", "income": "salary", "share": "low",
        "sustainability": "yes",
    }
    suit = mifid.suitability(answers)
    assert suit["complete"] and suit["profile"] == "agresivo"
    assert suit["sustainability"] is True

    conservative = {**answers, "horizon": "0-2", "capacity": "sell", "experience": "none",
                    "knowledge": "other", "share": "high"}
    assert mifid.suitability(conservative)["profile"] == "conservador"

    appr = mifid.appropriateness({"experience": "none", "knowledge": "other"},
                                 {"name": "Opción sobre IBEX", "complex": True})
    assert appr["convenient"] is False
    assert appr["manuscript_required"] == mifid.MANUSCRIPT_NOT_CONVENIENT
    assert mifid.classify()["category"] == "minorista"
