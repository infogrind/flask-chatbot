from pathlib import Path

from flask import Flask

from app import create_app


def test_create_app_accepts_test_config(tmp_path: Path) -> None:
    db_path = str(tmp_path / "test.sqlite")

    app = create_app({"TESTING": True, "DATABASE": db_path})

    assert app.testing
    assert app.config["DATABASE"] == db_path


def test_fixture_app_does_not_use_instance_database(app: Flask) -> None:
    assert not app.config["DATABASE"].startswith(app.instance_path)


def test_secret_key_is_not_hardcoded() -> None:
    app = create_app({"TESTING": True})

    assert app.secret_key
    assert app.secret_key != "supersecretkey"
