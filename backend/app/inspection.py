"""Signed inspection pack: hashes, audit chain, rules, model register. No personal data in clear."""
from __future__ import annotations

import hashlib
import io
import json
import zipfile
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
)

from . import audit, db, settings
from .rules import engine
from .timeutil import iso


def _key() -> Ed25519PrivateKey:
    path = settings.SIGNING_KEY_PATH
    if path.exists():
        return Ed25519PrivateKey.from_private_bytes(path.read_bytes())
    settings.ensure_dirs()
    key = Ed25519PrivateKey.generate()
    path.write_bytes(key.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption()))
    path.chmod(0o600)
    return key


def public_key_hex() -> str:
    return _key().public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex()


def build() -> dict:
    settings.ensure_dirs()
    verified = audit.verify()
    head = audit.head()
    files = {
        "LEEME.txt": (
            "Paquete de inspección. SINTÉTICO.\n"
            "No contiene datos personales en claro. Cada expediente aparece como identificador, "
            "estados, huellas y citas. La cadena de auditoría se puede verificar con verify().\n"
            f"Generado: {iso()}\n"
        ).encode(),
        "entidad.json": json.dumps(settings.ENTITY, ensure_ascii=False, indent=2).encode(),
        "auditoria.json": json.dumps({"verify": verified, "head": head}, ensure_ascii=False, indent=2).encode(),
        "reglas.json": json.dumps(engine.all_packs(), ensure_ascii=False, indent=2).encode(),
        "modelos.json": json.dumps(
            [dict(r) for r in db.query(
                "SELECT id, ts, purpose, case_id, model, digest, prompt_version, prompt_hash, "
                "input_hash, output_hash, duration_ms, fallback FROM model_calls")],
            ensure_ascii=False, indent=2).encode(),
        "expedientes.json": json.dumps(
            [dict(r) for r in db.query(
                "SELECT id, pseudonym, route, service, status, risk_level, risk_score, profile, "
                "approval_level, readiness, submitted_at, contract_sha256, shredded_at FROM cases")],
            ensure_ascii=False, indent=2).encode(),
        "documentos.json": json.dumps(
            [dict(r) for r in db.query(
                "SELECT id, case_id, kind, sha256, uploaded_at, status, superseded FROM documents")],
            ensure_ascii=False, indent=2).encode(),
    }
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    archive = buf.getvalue()
    digest = hashlib.sha256(archive).hexdigest()
    signature = _key().sign(archive).hex()
    dest = settings.EXPORTS_DIR / f"inspeccion-{head['hash'][:12]}.zip"
    dest.write_bytes(archive)
    (dest.with_suffix(".sig")).write_text(json.dumps({
        "sha256": digest, "ed25519": signature, "public_key": public_key_hex(), "generated_at": iso(),
    }, indent=2), encoding="utf-8")
    return {
        "path": str(dest),
        "filename": dest.name,
        "sha256": digest,
        "signature": signature,
        "public_key": public_key_hex(),
        "bytes": len(archive),
        "generated_at": iso(),
        "audit": verified,
    }
