import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from flask import Flask
from flask.testing import FlaskClient

from app import create_app
from app.anthropic_chat_client import AnthropicChatClient
from app.database import init_db, update_conversation
from app.llm_settings import LLMSettings
from app.openai_chat_client import OpenAIChatClient
from app.routes import get_chat_client

from app.chat import ChatResponse


@patch("app.routes.get_chat_client")
def test_chat_get(mock_chat_client: MagicMock, client: FlaskClient) -> None:
    # Arrange
    mock_chat_client.return_value.get_chat_completion.return_value = [
        ChatResponse(conversation_history=[], response="Test response")
    ]

    # Act
    with client:
        # First, visit the index page to initialize the conversation in the session
        client.get("/")
        response = client.get(
            "/chat?query=Test%20query",
            follow_redirects=True,
        )

    # Assert
    assert response.status_code == 200
    # The response from the chat endpoint is JSON, so we need to check for the
    # response in the JSON data.
    elements = response.data.rstrip(b"\n").split(b"\n\n")
    assert len(elements) == 2
    dicts = [
        json.loads(item.decode().removeprefix("data: ").strip()) for item in elements
    ]
    assert dicts[0]["response"] == "Test response"
    assert dicts[1]["status"] == "end"
    mock_chat_client.return_value.get_chat_completion.assert_called_once()


@patch("app.routes.get_chat_client")
def test_chat_without_prior_index_visit(
    mock_chat_client: MagicMock, client: FlaskClient
) -> None:
    mock_chat_client.return_value.get_chat_completion.return_value = []

    response = client.get("/chat?query=hello")

    assert response.status_code == 200
    with client.session_transaction() as sess:
        assert "conversation_id" in sess


@patch("app.routes.get_chat_client")
def test_chat_with_stale_conversation_id(
    mock_chat_client: MagicMock, client: FlaskClient
) -> None:
    mock_chat_client.return_value.get_chat_completion.return_value = []
    with client.session_transaction() as sess:
        sess["conversation_id"] = "does-not-exist"

    response = client.get("/chat?query=hello")

    assert response.status_code == 200
    history = mock_chat_client.return_value.get_chat_completion.call_args.args[0]
    assert history == [{"role": "user", "content": "hello"}]


def test_spotify_token_cache_is_per_session(client: FlaskClient) -> None:
    """Without a login, spotipy must not fall back to its shared `.cache` file."""
    with patch("app.routes.SpotifyOAuth") as mock_oauth:
        mock_oauth.return_value.validate_token.return_value = None
        client.get("/")

    cache_path = mock_oauth.call_args.kwargs["cache_handler"].cache_path
    with client.session_transaction() as sess:
        assert cache_path == f".spotify_cache/{sess['spotify_cache_id']}"


def test_spotify_callback_when_user_denies_access(client: FlaskClient) -> None:
    with patch("app.routes.SpotifyOAuth") as mock_oauth:
        response = client.get("/spotify/callback?error=access_denied")

    assert response.status_code == 302
    mock_oauth.return_value.get_access_token.assert_not_called()


def _app_with_llm(tmp_path: Path, settings: LLMSettings) -> Flask:
    app = create_app(
        {
            "TESTING": True,
            "DATABASE": str(tmp_path / "test.sqlite"),
            "LLM": settings,
        }
    )
    with app.app_context():
        init_db()
    return app


ANTHROPIC = LLMSettings(provider="anthropic", api_key="k", model="claude-opus-5-5")
OPENAI = LLMSettings(provider="openai", api_key="k", model="gpt-4o-mini")


def test_create_app_loads_llm_settings_from_config_file(
    tmp_path: Path, isolated_config_home: Path
) -> None:
    config_file = isolated_config_home / "flask-chatbot" / "config.toml"
    config_file.parent.mkdir()
    config_file.write_text('provider = "anthropic"\n[anthropic]\napi_key = "k"\n')

    app = create_app({"TESTING": True, "DATABASE": str(tmp_path / "db.sqlite")})

    assert app.config["LLM"].provider == "anthropic"


@pytest.mark.parametrize(
    ("settings", "client_class"),
    [(ANTHROPIC, AnthropicChatClient), (OPENAI, OpenAIChatClient)],
)
def test_get_chat_client_uses_configured_provider(
    tmp_path: Path, settings: LLMSettings, client_class: type
) -> None:
    app = _app_with_llm(tmp_path, settings)

    with app.app_context():
        assert isinstance(get_chat_client(), client_class)


def test_switching_provider_starts_new_conversation(tmp_path: Path) -> None:
    """Histories are stored in the provider's format and can't be sent to another."""
    openai_client = _app_with_llm(tmp_path, OPENAI).test_client()
    openai_client.get("/")
    with openai_client.session_transaction() as sess:
        old_conversation_id = sess["conversation_id"]

    anthropic_app = _app_with_llm(tmp_path, ANTHROPIC)
    anthropic_client = anthropic_app.test_client()
    # Same browser session, now served by an app configured for Anthropic
    with anthropic_client.session_transaction() as sess:
        sess["conversation_id"] = old_conversation_id
        sess["conversation_provider"] = "openai"
    anthropic_client.get("/")

    with anthropic_client.session_transaction() as sess:
        assert sess["conversation_id"] != old_conversation_id
        assert sess["conversation_provider"] == "anthropic"


def test_index_renders_text_of_block_based_history(tmp_path: Path) -> None:
    app = _app_with_llm(tmp_path, ANTHROPIC)
    client = app.test_client()
    client.get("/")
    with client.session_transaction() as sess:
        conversation_id = sess["conversation_id"]
    with app.app_context():
        update_conversation(
            conversation_id,
            [
                {"role": "user", "content": "Jazz please"},
                {
                    "role": "assistant",
                    "content": [
                        {"type": "thinking", "thinking": "", "signature": "sig"},
                        {"type": "text", "text": "Here is some jazz."},
                    ],
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "tool_result", "tool_use_id": "t", "content": "[]"}
                    ],
                },
            ],
        )

    html = client.get("/").get_data(as_text=True)

    assert "Here is some jazz." in html
    assert "signature" not in html
    assert "tool_result" not in html


def test_new_conversation_shows_welcome(client: FlaskClient) -> None:
    html = client.get("/").get_data(as_text=True)

    assert 'id="empty-state"' in html
    assert "suggestion" in html


def test_existing_conversation_hides_welcome(app: Flask) -> None:
    client = app.test_client()
    client.get("/")
    with client.session_transaction() as sess:
        conversation_id = sess["conversation_id"]
    with app.app_context():
        update_conversation(conversation_id, [{"role": "user", "content": "Hi"}])

    html = client.get("/").get_data(as_text=True)

    assert 'id="empty-state"' not in html
