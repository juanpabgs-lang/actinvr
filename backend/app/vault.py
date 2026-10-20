"""Encryption at rest with one data key per client (envelope encryption).

- Each client gets a random AES-256 data key, stored wrapped by the installation's
  master key in a separate key database. In production the master key would live
  in Alterna's HSM or KMS.
- Every blob is AES-256-GCM with associated data that binds it to its owner and
  purpose, so ciphertexts cannot be swapped between records.
- Crypto-shredding: deleting a client's data key (with SQLite secure_delete)
  makes every document, form and model output of that client unreadable at once,
  while the audit chain, which holds only hashes, keeps verifying.
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from . import settings
from .timeutil import iso


class KeyShredded(Exception):
    pass


_lock = threading.RLock()
_cache: dict[str, bytes] = {}


def _keys_db() -> sqlite3.Connection:
    settings.ensure_dirs()
    c = sqlite3.connect(settings.KEYS_DB_PATH, timeout=30, isolation_level=None, check_same_thread=False)
    c.execute("PRAGMA secure_delete=ON")
    c.execute(
        "CREATE TABLE IF NOT EXISTS deks (owner TEXT PRIMARY KEY, nonce BLOB NOT NULL, "
        "wrapped BLOB NOT NULL, created_at TEXT NOT NULL)"
    )
    c.execute("CREATE TABLE IF NOT EXISTS shredded (owner TEXT PRIMARY KEY, shredded_at TEXT NOT NULL)")
    return c


def _master() -> bytes:
    path: Path = settings.MASTER_KEY_PATH
    if not path.exists():
        settings.ensure_dirs()
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as fh:
            fh.write(AESGCM.generate_key(bit_length=256))
    return path.read_bytes()


def create_key(owner: str) -> None:
    with _lock:
        c = _keys_db()
        try:
            if c.execute("SELECT 1 FROM deks WHERE owner = ?", (owner,)).fetchone():
                return
            dek = AESGCM.generate_key(bit_length=256)
            nonce = os.urandom(12)
            wrapped = AESGCM(_master()).encrypt(nonce, dek, f"dek:{owner}".encode())
            c.execute("INSERT INTO deks(owner, nonce, wrapped, created_at) VALUES(?,?,?,?)",
                      (owner, nonce, wrapped, iso()))
            c.execute("DELETE FROM shredded WHERE owner = ?", (owner,))
            _cache[owner] = dek
        finally:
            c.close()


def _dek(owner: str) -> bytes:
    with _lock:
        if owner in _cache:
            return _cache[owner]
        c = _keys_db()
        try:
            row = c.execute("SELECT nonce, wrapped FROM deks WHERE owner = ?", (owner,)).fetchone()
            if row is None:
                if c.execute("SELECT 1 FROM shredded WHERE owner = ?", (owner,)).fetchone():
                    raise KeyShredded(owner)
                raise KeyError(f"Sin clave para {owner}")
            dek = AESGCM(_master()).decrypt(row[0], row[1], f"dek:{owner}".encode())
            _cache[owner] = dek
            return dek
        finally:
            c.close()


def encrypt(owner: str, plaintext: bytes, aad: str) -> bytes:
    nonce = os.urandom(12)
    return nonce + AESGCM(_dek(owner)).encrypt(nonce, plaintext, f"{owner}|{aad}".encode())


def decrypt(owner: str, blob: bytes, aad: str) -> bytes:
    return AESGCM(_dek(owner)).decrypt(blob[:12], blob[12:], f"{owner}|{aad}".encode())


def enc_json(owner: str, obj, aad: str) -> bytes:
    return encrypt(owner, json.dumps(obj, ensure_ascii=False).encode("utf-8"), aad)


def dec_json(owner: str, blob: bytes | None, aad: str, default=None):
    if blob is None:
        return default
    return json.loads(decrypt(owner, blob, aad).decode("utf-8"))


def _file_path(owner: str, name: str) -> Path:
    return settings.VAULT_DIR / owner / f"{name}.bin"


def store_file(owner: str, name: str, data: bytes) -> Path:
    path = _file_path(owner, name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(encrypt(owner, data, f"file:{name}"))
    return path


def load_file(owner: str, name: str) -> bytes:
    return decrypt(owner, _file_path(owner, name).read_bytes(), f"file:{name}")


def key_state(owner: str) -> str:
    c = _keys_db()
    try:
        if c.execute("SELECT 1 FROM deks WHERE owner = ?", (owner,)).fetchone():
            return "activa"
        if c.execute("SELECT 1 FROM shredded WHERE owner = ?", (owner,)).fetchone():
            return "destruida"
        return "inexistente"
    finally:
        c.close()


def shred(owner: str) -> dict:
    with _lock:
        c = _keys_db()
        try:
            c.execute("DELETE FROM deks WHERE owner = ?", (owner,))
            ts = iso()
            c.execute("INSERT OR REPLACE INTO shredded(owner, shredded_at) VALUES(?,?)", (owner, ts))
            c.execute("VACUUM")
        finally:
            c.close()
        _cache.pop(owner, None)
    return {"owner": owner, "shredded_at": ts}


def reset_cache() -> None:
    with _lock:
        _cache.clear()
