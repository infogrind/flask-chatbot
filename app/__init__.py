import logging
import os
from flask import Flask
from config import Config


def create_app() -> Flask:
    """Create and configure the Flask application."""
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(Config)
    app.secret_key = "supersecretkey"  # TODO: Replace with a real secret key

    # ensure the instance folder exists
    os.makedirs(app.instance_path, exist_ok=True)

    app.config.from_mapping(
        DATABASE=os.path.join(app.instance_path, "flask-chatbot.sqlite"),
    )

    # Configure logging
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s [%(name)s]: %(message)s"
    )

    from . import database

    database.init_app(app)

    from .routes import bp as routes_bp

    app.register_blueprint(routes_bp)
    return app
