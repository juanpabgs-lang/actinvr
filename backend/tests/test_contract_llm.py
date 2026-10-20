from app import contract, llm, settings


def test_contract_pdf_is_synthetic_and_names_alterna():
    case = {
        "person": {"nombres": "Ana", "apellido1": "Ramírez", "apellido2": "Soto", "nationality": "MX", "rfc": "RASA880722A12"},
        "service": "asesoramiento",
        "suitability": {"declaration": "Perfil moderado.", "profile": "moderado",
                        "profile_detail": {"label": "Moderado", "volatility": 8, "equity": (0, 30), "fixed_income": (70, 100)},
                        "sustainability": False},
        "crs": {"residence": "MX", "only_mx_es": True},
        "fatca": {"us_person": False},
        "signature": {"signed_at": "2026-10-20T06:12:00.000Z", "code_hash": "abc123", "document_hash": "def456"},
    }
    data, digest = contract.render_with_hash(case)
    assert data.startswith(b"%PDF")
    assert len(digest) == 64
    assert digest != "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    from io import BytesIO
    from pypdf import PdfReader
    text = "\n".join((p.extract_text() or "") for p in PdfReader(BytesIO(data)).pages)
    assert "Alterna Inversiones y Valores" in text
    assert "SINTÉTICO" in text or "SINTETICO" in text
    assert "Aceptación de la entidad" not in text

    accepted, _ = contract.render_with_hash(case, {"decision": "aceptado", "actor_name": "Lucía Méndez",
                                                  "role": "direccion", "case_id": "EXP-1",
                                                  "ts": "2026-10-20T07:10:00.000Z"})
    accepted_text = "\n".join((p.extract_text() or "") for p in PdfReader(BytesIO(accepted)).pages)
    assert "Aceptación de la entidad" in accepted_text
    assert "Lucía Méndez" in accepted_text


def test_llm_fallback_and_register_shape():
    settings.MODEL_ENABLED = False
    facts = {
        "person": {"nombres": "Ana", "apellido1": "Ramírez", "apellido2": "Soto"},
        "route": "primer_ingreso",
        "service": "asesoramiento",
        "risk": {"level": "bajo", "score": 6, "regime": "normal", "approval_level": "cumplimiento"},
        "screening": {"discarded": [{"list": "UE-FSF"}]},
        "findings": [],
        "suitability": {"profile": "moderado"},
    }
    out = llm.draft_summary(facts)
    assert out["fallback"] is True
    assert "Ana" in out["text"]
    help_out = llm.help_answer("¿me sirve la INE?")
    assert help_out["ai_disclosure"] is True
    assert "pasaporte" in help_out["text"].lower()
    status = llm.model_status()
    assert status["available"] is False
    settings.MODEL_ENABLED = True
