from app import cases, seed


def test_seed_queue_readiness():
    ids = seed.populate(summarize=False)
    assert len(ids) == 9
    by_persona = {r["persona"]: r for r in cases.list_cases() if r["seeded"]}
    assert by_persona["limpia"]["readiness"] == "listo_para_decidir"
    assert by_persona["pep"]["approval_level"] == "direccion"
    assert by_persona["pasaporte_caducado"]["readiness"] == "bloqueado"
    assert by_persona["sanciones_descartada"]["readiness"] == "listo_para_decidir"
    rec = cases.load(by_persona["sanciones_descartada"]["id"])
    assert rec["result"]["screening"]["discarded"]
    assert not rec["result"]["screening"]["confirmed_hit"]
