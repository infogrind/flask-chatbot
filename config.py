import os
import secrets

from dotenv import load_dotenv

load_dotenv()


class Config:
    """Base configuration for the Flask app, loading from environment."""

    FLASK_ENV: str = os.getenv("FLASK_ENV", "production")
    # Without `SECRET_KEY`, a random key is used and sessions don't survive restarts.
    SECRET_KEY: str = os.getenv("SECRET_KEY") or secrets.token_hex(32)
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    SPOTIFY_CLIENT_ID: str = os.getenv("SPOTIFY_CLIENT_ID", "")
    SPOTIFY_CLIENT_SECRET: str = os.getenv("SPOTIFY_CLIENT_SECRET", "")
