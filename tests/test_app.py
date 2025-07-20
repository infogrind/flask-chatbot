import json
from unittest.mock import patch

from app import create_app
from app.chat_client import ChatResponse


@patch("app.routes.chat_client")
def test_chat_post(mock_chat_client) -> None:
    # Arrange
    mock_chat_client.get_chat_completion.return_value = ChatResponse(
        conversation_history=[], response="Test response"
    )
    app = create_app()
    client = app.test_client()

    # Act
    with client:
        # First, visit the index page to initialize the conversation in the session
        client.get("/")
        response = client.post(
            "/chat",
            data=json.dumps({"query": "Test query"}),
            content_type="application/json",
            follow_redirects=True,
        )

    # Assert
    assert response.status_code == 200
    # The response from the chat endpoint is JSON, so we need to check for the
    # response in the JSON data.
    json_response = json.loads(response.data)
    assert json_response["response"] == "Test response"
    mock_chat_client.get_chat_completion.assert_called_once()
