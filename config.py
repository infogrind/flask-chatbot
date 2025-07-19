import os

from dotenv import load_dotenv

load_dotenv()


class Config:
    """Base configuration for the Flask app, loading from environment."""

    FLASK_ENV: str = os.getenv("FLASK_ENV", "production")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    SPOTIFY_CLIENT_ID: str = os.getenv("SPOTIFY_CLIENT_ID", "")
    SPOTIFY_CLIENT_SECRET: str = os.getenv("SPOTIFY_CLIENT_SECRET", "")
