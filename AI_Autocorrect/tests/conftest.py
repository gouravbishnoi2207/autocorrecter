import importlib
import sys
from pathlib import Path

import pytest


@pytest.fixture()
def app_module(tmp_path, monkeypatch):
    database_path = tmp_path / "test_database.db"
    monkeypatch.setenv("AUTOCORRECT_DATABASE_PATH", str(database_path))
    monkeypatch.setenv("SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("ADMIN_EMAIL", "admin@example.com")
    monkeypatch.setenv("ADMIN_PASSWORD", "Admin@12345!")
    monkeypatch.setenv("ADMIN_NAME", "Test Admin")

    app_root = Path(__file__).resolve().parents[1]
    if str(app_root) not in sys.path:
        sys.path.insert(0, str(app_root))

    sys.modules.pop("app", None)
    module = importlib.import_module("app")
    module.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    return module


@pytest.fixture()
def client(app_module):
    return app_module.app.test_client()