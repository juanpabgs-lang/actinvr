from datetime import date

from app import cases, db, docsgen, documents, pipeline, seed
from app.checks import mrz
from app.personas import LIVE


def test_pipeline_on_live_persona(tmp_path):
    created = cases.create(dict(LIVE, seed="live-test", pseudonym="Rodrigo Iván Morales Trejo"))
    case_id = created["id"]
    person = LIVE["person"]
    expiry = date(2032, 6, 1)
    number = "G87654321"
    png = docsgen.passport_png(person, number, date(2024, 6, 1), expiry)
    payload = {"mrz": mrz.build_td3(f"{person['apellido1']} {person['apellido2']}", person["nombres"],
                                   number, date.fromisoformat(person["dob"]), "M", expiry)}
    analysis = documents.analyze("pasaporte", png, "pasaporte.png", person, today=date(2026, 10, 20), payload=payload)
    assert analysis.get("valid_mrz") or analysis.get("mrz")
    cases.add_document(case_id, "pasaporte", "pasaporte.png", "image/png", png, analysis)
    addr = docsgen.address_pdf(person, date(2026, 8, 20))
    addr_a = documents.analyze("domicilio", addr, "domicilio.pdf", person, today=date(2026, 10, 20))
    cases.add_document(case_id, "domicilio", "domicilio.pdf", "application/pdf", addr, addr_a)
    cases.save_data(case_id, {
        "gdpr_ack": True, "ai_ack": True, "precontract_ack": True, "stage": "firma",
        "answers": {"horizon": "6-10", "capacity": "wait", "experience": "funds",
                    "knowledge": "related", "income": "salary", "share": "mid", "sustainability": "no"},
        "first_transfer": {"same_holder": True, "equivalent_country": True, "arrived": True, "country": "MX"},
    })
    result = pipeline.run(case_id, summarize=False)
    assert result["risk"]["level"] in {"bajo", "medio", "alto"}
    assert result["screening"]["done"]
    assert result["mifid"]["suitability"]["profile"]
    pdf, digest = pipeline.build_contract(case_id)
    assert pdf.startswith(b"%PDF")
    assert len(digest) == 64
