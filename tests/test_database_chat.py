import json
from unittest.mock import MagicMock, patch

from flask import Flask

from app.chat_client import ChatResponse
from app.database import get_db


def test_conversation_lifecycle(client, app: Flask):
    """
    Tests the full lifecycle of a conversation in the database.
    1.  Initial visit creates a conversation.
    2.  Chatting updates the conversation history.
    3.  Re-visiting the page shows the correct history.
    4.  Clearing the chat deletes the conversation.
    """
    # Mock the chat client's streaming function
    mock_chat_client = MagicMock()
    mock_chat_client.get_chat_completion.return_value = iter(
        [
            ChatResponse(
                conversation_history=[
                    {"role": "user", "content": "hello"},
                    {"role": "assistant", "content": "hi there"},
                ],
                response="hi there",
            )
        ]
    )

    with patch("app.routes.chat_client", mock_chat_client):
        # 1. Initial visit
        response = client.get("/")
        assert response.status_code == 200
        with client.session_transaction() as sess:
            assert "conversation_id" in sess
            conversation_id = sess["conversation_id"]

        with app.app_context():
            db = get_db()
            cur = db.execute(
                "SELECT history FROM conversation WHERE id = ?", (conversation_id,)
            )
            row = cur.fetchone()
            assert row is not None
            assert json.loads(row["history"]) == []

        # 2. Send a chat message
        response = client.get("/chat?query=hello")
        # Consume the generator
        list(response.iter_encoded())

        with app.app_context():
            db = get_db()
            cur = db.execute(
                "SELECT history FROM conversation WHERE id = ?", (conversation_id,)
            )
            row = cur.fetchone()
            assert row is not None
            expected_history = [
                {"role": "user", "content": "hello"},
                {"role": "assistant", "content": "hi there"},
            ]
            assert json.loads(row["history"]) == expected_history

        # 3. Verify persistence on page reload
        response = client.get("/")
        assert response.status_code == 200
        assert "hi there" in response.get_data(as_text=True)

        # 4. Clear the conversation
        response = client.post("/clear")
        assert response.status_code == 200
        with client.session_transaction() as sess:
            assert "conversation_id" not in sess

        with app.app_context():
            db = get_db()
            cur = db.execute(
                "SELECT history FROM conversation WHERE id = ?", (conversation_id,)
            )
            row = cur.fetchone()
            assert row is None
