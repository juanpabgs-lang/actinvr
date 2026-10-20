import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("ONB_VAR_DIR", tempfile.mkdtemp(prefix="onb-test-"))
os.environ.setdefault("ONB_MODEL_ENABLED", "0")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402

from app import db, egress  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _guard_and_db():
    egress.install()
    db.init_db()
    yield
