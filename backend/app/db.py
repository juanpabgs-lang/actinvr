"""SQLite storage. Personal data columns hold ciphertext only (see vault.py)."""
from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from . import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS cases (
  id TEXT PRIMARY KEY,
  pseudonym TEXT NOT NULL,
  persona TEXT,
  route TEXT NOT NULL DEFAULT 'primer_ingreso',
  service TEXT,
  status TEXT NOT NULL,
  stage TEXT NOT NULL DEFAULT 'bienvenida',
  risk_level TEXT,
  risk_score INTEGER,
  profile TEXT,
  approval_level TEXT,
  readiness TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  submitted_at TEXT,
  arrived_at TEXT,
  last_client_activity TEXT,
  seeded INTEGER NOT NULL DEFAULT 0,
  synthetic INTEGER NOT NULL DEFAULT 1,
  data_enc BLOB,
  result_enc BLOB,
  summary_call_id TEXT,
  contract_state TEXT NOT NULL DEFAULT 'sin_generar',
  contract_sha256 TEXT,
  relationship_end TEXT,
  shredded_at TEXT
);

CREATE TABLE IF NOT EXISTS documents (
  id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL REFERENCES cases(id),
  kind TEXT NOT NULL,
  filename TEXT,
  mime TEXT,
  size INTEGER,
  sha256 TEXT NOT NULL,
  uploaded_at TEXT NOT NULL,
  sim_ts TEXT,
  status TEXT NOT NULL,
  superseded INTEGER NOT NULL DEFAULT 0,
  meta_removed TEXT,
  analysis_enc BLOB
);
CREATE INDEX IF NOT EXISTS documents_case ON documents(case_id);

CREATE TABLE IF NOT EXISTS audit (
  seq INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL,
  actor TEXT NOT NULL,
  action TEXT NOT NULL,
  case_id TEXT,
  object TEXT,
  details TEXT NOT NULL,
  prev_hash TEXT NOT NULL,
  hash TEXT NOT NULL UNIQUE
);
CREATE INDEX IF NOT EXISTS audit_case ON audit(case_id);
CREATE TRIGGER IF NOT EXISTS audit_no_update BEFORE UPDATE ON audit
BEGIN SELECT RAISE(ABORT, 'registro de auditoria: solo se permite anadir'); END;
CREATE TRIGGER IF NOT EXISTS audit_no_delete BEFORE DELETE ON audit
BEGIN SELECT RAISE(ABORT, 'registro de auditoria: solo se permite anadir'); END;

CREATE TABLE IF NOT EXISTS decisions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  case_id TEXT NOT NULL REFERENCES cases(id),
  actor_id TEXT NOT NULL,
  role TEXT NOT NULL,
  kind TEXT NOT NULL,
  comment TEXT,
  ts TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS notifications (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  case_id TEXT NOT NULL REFERENCES cases(id),
  channel TEXT NOT NULL,
  body TEXT NOT NULL,
  ts TEXT NOT NULL,
  sim_ts TEXT
);

CREATE TABLE IF NOT EXISTS tokens (
  token_hash TEXT PRIMARY KEY,
  case_id TEXT NOT NULL REFERENCES cases(id),
  created_at TEXT NOT NULL,
  expires_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS otps (
  case_id TEXT PRIMARY KEY REFERENCES cases(id),
  code_hash TEXT NOT NULL,
  created_at TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  attempts INTEGER NOT NULL DEFAULT 0,
  verified_at TEXT
);

CREATE TABLE IF NOT EXISTS model_calls (
  id TEXT PRIMARY KEY,
  ts TEXT NOT NULL,
  purpose TEXT NOT NULL,
  case_id TEXT,
  model TEXT NOT NULL,
  digest TEXT,
  prompt_version TEXT NOT NULL,
  prompt_hash TEXT NOT NULL,
  input_hash TEXT NOT NULL,
  params TEXT NOT NULL,
  output_hash TEXT NOT NULL,
  duration_ms INTEGER,
  fallback INTEGER NOT NULL DEFAULT 0,
  io_enc BLOB
);

CREATE TABLE IF NOT EXISTS egress_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL,
  host TEXT,
  port INTEGER,
  kind TEXT NOT NULL,
  allowed INTEGER NOT NULL,
  origin TEXT
);

CREATE TABLE IF NOT EXISTS counters (
  name TEXT PRIMARY KEY,
  value INTEGER NOT NULL
);
"""

_local = threading.local()
_write_lock = threading.RLock()


def _open(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path, timeout=30, isolation_level=None, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA secure_delete=ON")
    return conn


def conn() -> sqlite3.Connection:
    c = getattr(_local, "conn", None)
    path = getattr(_local, "path", None)
    if c is None or path != settings.DB_PATH:
        c = _open(settings.DB_PATH)
        _local.conn = c
        _local.path = settings.DB_PATH
    return c


@contextmanager
def tx() -> Iterator[sqlite3.Connection]:
    with _write_lock:
        c = conn()
        c.execute("BEGIN IMMEDIATE")
        try:
            yield c
        except BaseException:
            c.execute("ROLLBACK")
            raise
        else:
            c.execute("COMMIT")


def init_db() -> None:
    settings.ensure_dirs()
    with _write_lock:
        conn().executescript(SCHEMA)


def close_thread_connection() -> None:
    c = getattr(_local, "conn", None)
    if c is not None:
        c.close()
        _local.conn = None


def next_counter(c: sqlite3.Connection, name: str) -> int:
    c.execute(
        "INSERT INTO counters(name, value) VALUES(?, 1) "
        "ON CONFLICT(name) DO UPDATE SET value = value + 1",
        (name,),
    )
    return c.execute("SELECT value FROM counters WHERE name = ?", (name,)).fetchone()[0]


def query(sql: str, params: tuple = ()) -> list[sqlite3.Row]:
    return conn().execute(sql, params).fetchall()


def one(sql: str, params: tuple = ()) -> sqlite3.Row | None:
    return conn().execute(sql, params).fetchone()
