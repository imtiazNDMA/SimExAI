"""Keep application imports from initializing the development database."""
import os
import shutil
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

_TEST_DATA_DIR = Path(tempfile.mkdtemp(prefix="simexai_pytest_"))
os.environ["SIMEX_DB_PATH"] = str(_TEST_DATA_DIR / "bootstrap.db")

from backend import app as app_module
from backend import database


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "test.db")
    database.init_db()
    app_module._upload_jobs.clear()
    with TestClient(app_module.app) as test_client:
        yield test_client
    app_module._upload_jobs.clear()


def pytest_sessionfinish(session, exitstatus):
    shutil.rmtree(_TEST_DATA_DIR, ignore_errors=True)
