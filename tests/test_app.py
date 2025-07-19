from unittest.mock import patch
from app import create_app


@patch("app.routes.chat_client")
def test_chat_post(mock_chat_client) -> None:
    # Arrange
    mock_chat_client.get_chat_completion.return_value = "Test response"
    app = create_app()
    client = app.test_client()

    # Act
    with client:
        # First, visit the index page to initialize the conversation in the session
        client.get("/")
        response = client.post(
            "/chat", data={"query": "Test query"}, follow_redirects=True
        )

    # Assert
    assert response.status_code == 200
    assert b"Test query" in response.data
    assert b"Test response" in response.data
    mock_chat_client.get_chat_completion.assert_called_once()
