from flask import Flask
from config import Config


def create_app() -> Flask:
    """Create and configure the Flask application."""
    app = Flask(__name__, instance_relative_config=False)
    app.config.from_object(Config)

    from .routes import bp as routes_bp

    app.register_blueprint(routes_bp)
    return app
