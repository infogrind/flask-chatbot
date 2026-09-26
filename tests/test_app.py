import json
from unittest.mock import MagicMock, patch

from flask.testing import FlaskClient

from app.chat_client import ChatResponse


@patch("app.routes.chat_client")
def test_chat_get(mock_chat_client: MagicMock, client: FlaskClient) -> None:
    # Arrange
    mock_chat_client.get_chat_completion.return_value = [
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
    mock_chat_client.get_chat_completion.assert_called_once()


@patch("app.routes.chat_client")
def test_chat_without_prior_index_visit(
    mock_chat_client: MagicMock, client: FlaskClient
) -> None:
    mock_chat_client.get_chat_completion.return_value = []

    response = client.get("/chat?query=hello")

    assert response.status_code == 200
    with client.session_transaction() as sess:
        assert "conversation_id" in sess


@patch("app.routes.chat_client")
def test_chat_with_stale_conversation_id(
    mock_chat_client: MagicMock, client: FlaskClient
) -> None:
    mock_chat_client.get_chat_completion.return_value = []
    with client.session_transaction() as sess:
        sess["conversation_id"] = "does-not-exist"

    response = client.get("/chat?query=hello")

    assert response.status_code == 200
    history = mock_chat_client.get_chat_completion.call_args.args[0]
    assert history == [{"role": "user", "content": "hello"}]


def test_spotify_token_cache_is_per_session(client: FlaskClient) -> None:
    """Without a login, spotipy must not fall back to its shared `.cache` file."""
    with patch("app.routes.SpotifyOAuth") as mock_oauth:
        mock_oauth.return_value.validate_token.return_value = None
        client.get("/")

    cache_path = mock_oauth.call_args.kwargs["cache_handler"].cache_path
    with client.session_transaction() as sess:
        assert cache_path == f".spotify_cache/{sess['spotify_cache_id']}"
