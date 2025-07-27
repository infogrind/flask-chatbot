import pytest
from app import create_app
from app.database import init_db


@pytest.fixture
def app():
    """Create and configure a new app instance for each test."""
    app = create_app()
    app.config.update(
        {
            "TESTING": True,
        }
    )

    with app.app_context():
        init_db()

    yield app


@pytest.fixture
def client(app):
    """A test client for the app."""
    return app.test_client()
