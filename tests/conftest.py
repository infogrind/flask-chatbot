from collections.abc import Iterator
from pathlib import Path

import pytest
from flask import Flask
from flask.testing import FlaskClient

from app import create_app
from app.database import init_db


@pytest.fixture(autouse=True)
def isolated_config_home(
    tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> Path:
    """Keeps tests from reading the developer's real LLM config file."""
    config_home = tmp_path_factory.mktemp("config")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config_home))
    return config_home


@pytest.fixture
def app(tmp_path: Path) -> Iterator[Flask]:
    """Create an app instance backed by a throwaway database for each test."""
    app = create_app({"TESTING": True, "DATABASE": str(tmp_path / "test.sqlite")})

    with app.app_context():
        init_db()

    yield app


@pytest.fixture
def client(app: Flask) -> FlaskClient:
    """A test client for the app."""
    return app.test_client()
