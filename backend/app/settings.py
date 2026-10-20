"""Runtime configuration. Everything here stays on the host: no remote config, no telemetry."""
from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
APP_DIR = BASE_DIR / "app"
VAR_DIR = Path(os.environ.get("ONB_VAR_DIR", BASE_DIR / "var"))
DB_PATH = VAR_DIR / "onboarding.db"
KEYS_DB_PATH = VAR_DIR / "keys" / "keys.db"
MASTER_KEY_PATH = VAR_DIR / "keys" / "master.key"
SIGNING_KEY_PATH = VAR_DIR / "keys" / "inspection_ed25519.pem"
VAULT_DIR = VAR_DIR / "vault"
SAMPLES_DIR = VAR_DIR / "samples"
EXPORTS_DIR = VAR_DIR / "exports"
RULES_DIR = APP_DIR / "rules"
LISTS_DIR = APP_DIR / "screening_lists"

DEMO_MODE = os.environ.get("ONB_DEMO_MODE", "1") == "1"

MODEL_HOST = os.environ.get("ONB_MODEL_HOST", "127.0.0.1")
MODEL_PORT = int(os.environ.get("ONB_MODEL_PORT", "11434"))
MODEL_NAME = os.environ.get("ONB_MODEL", "ministral-3:3b")
MODEL_PINNED_DIGEST = os.environ.get("ONB_MODEL_DIGEST", "f04aa1c738f6")
MODEL_ENABLED = os.environ.get("ONB_MODEL_ENABLED", "1") == "1"

UPLOAD_MAX_BYTES = 10 * 1024 * 1024

ENTITY = {
    "legal_name": "Alterna Inversiones y Valores, S.G.I.I.C., S.A.",
    "short_name": "Alterna",
    "nif": "A42939678",
    "registry": "Registro de SGIIC de la CNMV nº 282",
    "address": "C/ Marqués de la Ensenada 4, 2ª planta, 28004 Madrid",
    "formerly": "Antes Actinver Inversiones y Valores",
    "group_note": "Procede del grupo Actinver; separada de Corporación Actinver en 2021",
    "supervisors": ["CNMV", "SEPBLAC"],
    "guarantee_fund": "Fondo General de Garantía de Inversiones (FOGAIN)",
    "dpo_contact": "dpo@alternainversiones.es",
    "source": "Información precontractual de Alterna (febrero de 2026)",
}

TENANTS = {
    "alterna": {
        "id": "alterna",
        "brand": "Alterna Inversiones y Valores",
        "brand_short": "Alterna",
        "brand_note": None,
    },
    "actinver": {
        "id": "actinver",
        "brand": "Actinver · Madrid",
        "brand_short": "Actinver",
        "brand_note": "Marca visible configurable. La entidad contratante sigue siendo Alterna Inversiones y Valores, S.G.I.I.C., S.A.",
    },
}
TENANT = TENANTS.get(os.environ.get("ONB_TENANT", "alterna"), TENANTS["alterna"])

VENDOR = {
    "name": "Norfront",
    "statement": "Norfront es una empresa de Delaware con su equipo en Madrid.",
    "certifications": "Sin certificaciones SOC 2 ni ISO 27001.",
    "pentest": "Sin prueba de penetración independiente realizada.",
    "inspection_contact": "[Contacto de guardia de Norfront para inspecciones: por definir]",
    "inspection_sla": "[Tiempo de respuesta en inspección: por acordar]",
}


def ensure_dirs() -> None:
    for d in (VAR_DIR, KEYS_DB_PATH.parent, VAULT_DIR, SAMPLES_DIR, EXPORTS_DIR):
        d.mkdir(parents=True, exist_ok=True)
    os.chmod(KEYS_DB_PATH.parent, 0o700)
