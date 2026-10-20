import socket
import sqlite3
import threading

import httpx
import pytest

from app import audit, db, egress, vault


def test_audit_chain_verifies_and_rejects_edits():
    for i in range(3):
        audit.record("sistema", "prueba.evento", details={"i": i})
    result = audit.verify()
    assert result["ok"] and result["count"] >= 3

    with pytest.raises(sqlite3.DatabaseError):
        with db.tx() as c:
            c.execute("UPDATE audit SET actor = 'otro' WHERE seq = 1")
    with pytest.raises(sqlite3.DatabaseError):
        with db.tx() as c:
            c.execute("DELETE FROM audit WHERE seq = 1")
    assert audit.verify()["ok"]


def test_tamper_demo_detects_edit_on_copy_only():
    audit.record("analista", "decision.revisado", case_id="EXP-T", details={"decision": "rechazado"})
    out = audit.tamper_demo()
    assert out["trigger_blocked_update"]
    assert out["verification_of_copy"]["ok"] is False
    assert out["verification_of_copy"]["first_bad_seq"] == out["tampered_seq"]
    assert out["live_database"]["ok"] is True


def test_egress_blocks_external_and_allows_loopback():
    with pytest.raises(OSError):
        socket.create_connection(("8.8.8.8", 53), timeout=2)
    with pytest.raises(socket.gaierror):
        socket.getaddrinfo("example.com", 443)
    with pytest.raises(Exception):
        httpx.get("https://api.openai.com/v1/models", timeout=2)

    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    port = server.getsockname()[1]
    t = threading.Thread(target=lambda: server.accept()[0].close(), daemon=True)
    t.start()
    client = socket.create_connection(("127.0.0.1", port), timeout=2)
    client.close()
    server.close()

    results = egress.leak_test()
    assert results and all(r["outcome"] == "bloqueado" for r in results)
    assert egress.status()["blocked"] >= len(results)


def test_vault_roundtrip_aad_and_shredding():
    vault.create_key("EXP-V")
    blob = vault.enc_json("EXP-V", {"nombre": "SINTETICO"}, "form")
    assert vault.dec_json("EXP-V", blob, "form") == {"nombre": "SINTETICO"}
    with pytest.raises(Exception):
        vault.dec_json("EXP-V", blob, "otro-proposito")

    vault.store_file("EXP-V", "doc1", b"contenido")
    assert vault.load_file("EXP-V", "doc1") == b"contenido"

    vault.shred("EXP-V")
    vault.reset_cache()
    assert vault.key_state("EXP-V") == "destruida"
    with pytest.raises(vault.KeyShredded):
        vault.load_file("EXP-V", "doc1")
