from flask import Flask
from config import Config


def create_app() -> Flask:
    """Create and configure the Flask application."""
    app = Flask(__name__, instance_relative_config=False)
    app.config.from_object(Config)
    app.secret_key = "supersecretkey"  # TODO: Replace with a real secret key

    from .routes import bp as routes_bp

    app.register_blueprint(routes_bp)
    return app
