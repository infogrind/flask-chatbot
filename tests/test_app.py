import json
from unittest.mock import patch

from app import create_app
from app.chat_client import ChatResponse


@patch("app.routes.chat_client")
def test_chat_get(mock_chat_client) -> None:
    # Arrange
    mock_chat_client.get_chat_completion.return_value = [
        ChatResponse(conversation_history=[], response="Test response")
    ]
    app = create_app()
    client = app.test_client()

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
    print("Hundwyler: %s" % elements)
    dicts = [
        json.loads(item.decode().removeprefix("data: ").strip()) for item in elements
    ]
    assert dicts[0]["response"] == "Test response"
    assert dicts[1]["status"] == "end"
    mock_chat_client.get_chat_completion.assert_called_once()
