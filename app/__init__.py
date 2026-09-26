import logging
import os
from collections.abc import Mapping
from typing import Any

from flask import Flask

from config import Config


def create_app(test_config: Mapping[str, Any] | None = None) -> Flask:
    """Create and configure the Flask application.

    `test_config` overrides the default configuration, e.g. to point `DATABASE`
    at a temporary file in tests.
    """
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(Config)

    # ensure the instance folder exists
    os.makedirs(app.instance_path, exist_ok=True)

    app.config.from_mapping(
        DATABASE=os.path.join(app.instance_path, "flask-chatbot.sqlite"),
    )
    if test_config is not None:
        app.config.from_mapping(test_config)

    # Configure logging
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s [%(name)s]: %(message)s"
    )

    from . import database

    database.init_app(app)

    from .routes import bp as routes_bp

    app.register_blueprint(routes_bp)
    return app
