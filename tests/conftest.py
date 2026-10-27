"""Use an isolated, Alembic-migrated SQLite database for every test run."""
from __future__ import annotations

import atexit
import os
import shutil
import tempfile
from pathlib import Path


_TEST_DATA = Path(tempfile.mkdtemp(prefix="brandguard-pytest-"))
_TEST_DATABASE = _TEST_DATA / "brandguard-tests.sqlite3"
os.environ.update({
    "ENVIRONMENT": "development",
    "DATABASE_URL": f"sqlite:///{_TEST_DATABASE}",
    "DEMO_MODE": "true",
    "LLM_PROVIDER": "mock",
    "CHROMA_PERSIST_DIR": str(_TEST_DATA / "chroma"),
    "ASSET_STORAGE_DIR": str(_TEST_DATA / "uploads"),
})

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402

from backend.app.config import get_settings  # noqa: E402

get_settings.cache_clear()
command.upgrade(Config(str(Path(__file__).resolve().parents[1] / "alembic.ini")), "head")

atexit.register(shutil.rmtree, _TEST_DATA, ignore_errors=True)
