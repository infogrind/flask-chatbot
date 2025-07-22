import os
from typing import Iterator
from unittest.mock import MagicMock, patch

import pytest
from openai.types.responses import (
    Response,
    ResponseFunctionToolCall,
    ResponseOutputMessage,
    ResponseOutputText,
)

from app.chat_client import ChatClient, ChatResponse, ToolCallResponse


@pytest.fixture
def chat_client() -> Iterator[ChatClient]:
    """Fixture to provide a ChatClient instance with a mocked OpenAI client."""
    with patch("openai.OpenAI") as mock_openai_class:
        mock_openai_instance = mock_openai_class.return_value
        # This is the key change: we are mocking the `create` method on the `responses` attribute
        mock_create = MagicMock()
        mock_openai_instance.responses.create = mock_create

        os.environ["OPENAI_API_KEY"] = "test_api_key"
        client = ChatClient()
        client.client.responses.create = mock_create  # And we assign it here
        yield client
        del os.environ["OPENAI_API_KEY"]


def test_chat_client_initialization() -> None:
    """Test that the ChatClient initializes correctly."""
    # Arrange
    os.environ["OPENAI_API_KEY"] = "test_api_key"

    # Act
    client = ChatClient()

    # Assert
    assert client.client is not None
    assert len(client.tools) > 0
    del os.environ["OPENAI_API_KEY"]


def test_chat_client_initialization_no_api_key() -> None:
    """Test that the ChatClient raises an error if the API key is not set."""
    # Arrange
    if "OPENAI_API_KEY" in os.environ:
        del os.environ["OPENAI_API_KEY"]

    # Act & Assert
    with pytest.raises(
        ValueError, match="OPENAI_API_KEY environment variable not set."
    ):
        ChatClient()


def test_get_chat_completion_no_tool_calls(chat_client: ChatClient) -> None:
    """Test a simple chat completion with no tool calls."""
    # Arrange
    mock_response = MagicMock(spec=Response)
    mock_output_message = ResponseOutputMessage(
        id="test_id",
        content=[
            ResponseOutputText(
                text="Hello, how can I help you?", type="output_text", annotations=[]
            )
        ],
        type="message",
        role="assistant",
        status="completed",
    )
    mock_response.output = [mock_output_message]

    chat_client.client.responses.create.return_value = mock_response
    conversation_history = [{"role": "user", "content": "Hello"}]
    mock_spotify_client = MagicMock()

    # Act
    result = next(
        chat_client.get_chat_completion(conversation_history, mock_spotify_client)
    )

    # Assert
    assert isinstance(result, ChatResponse)
    assert result.response == "Hello, how can I help you?"
    assert len(result.conversation_history) == 2  # user + assistant
    chat_client.client.responses.create.assert_called_once()


def test_get_chat_completion_with_tool_call(chat_client: ChatClient) -> None:
    """Test a chat completion that involves a tool call."""
    # Arrange
    # First API call returns a tool call
    mock_response_tool_call = MagicMock(spec=Response)
    mock_function_tool_call = ResponseFunctionToolCall(
        id="test_tool_call_id",
        call_id="call_123",
        name="get_my_playlists",
        arguments="{}",
        type="function_call",
    )
    mock_response_tool_call.output = [mock_function_tool_call]

    # Second API call returns a text response
    mock_response_text = MagicMock(spec=Response)
    mock_output_message = ResponseOutputMessage(
        id="test_id",
        content=[
            ResponseOutputText(
                text="Here are your playlists.", type="output_text", annotations=[]
            )
        ],
        type="message",
        role="assistant",
        status="completed",
    )
    mock_response_text.output = [mock_output_message]

    chat_client.client.responses.create.side_effect = [
        mock_response_tool_call,
        mock_response_text,
    ]
    conversation_history = [{"role": "user", "content": "Show my playlists"}]
    mock_spotify_client = MagicMock()
    mock_spotify_client.get_user_playlists.return_value = [
        {"name": "My Favs", "description": "Favorites", "tracks": 20}
    ]

    # Act
    generator = chat_client.get_chat_completion(
        conversation_history, mock_spotify_client
    )
    tool_call_response = next(generator)
    chat_response = next(generator)

    # Assert
    assert isinstance(tool_call_response, ToolCallResponse)
    assert tool_call_response.function_name == "get_my_playlists"
    assert isinstance(chat_response, ChatResponse)
    assert chat_response.response == "Here are your playlists."
    assert (
        len(chat_response.conversation_history) == 4
    )  # user, assistant (tool), function, assistant (text)
    assert chat_client.client.responses.create.call_count == 2
    mock_spotify_client.get_user_playlists.assert_called_once()


def test_get_chat_completion_api_error(chat_client: ChatClient) -> None:
    """Test how the chat client handles an API error."""
    # Arrange
    chat_client.client.responses.create.side_effect = Exception("API connection failed")
    conversation_history = [{"role": "user", "content": "Hello"}]
    mock_spotify_client = MagicMock()

    # Act
    generator = chat_client.get_chat_completion(
        conversation_history, mock_spotify_client
    )
    with pytest.raises(StopIteration) as excinfo:
        next(generator)

    # Assert
    result = excinfo.value.value
    assert isinstance(result, ChatResponse)
    assert "I'm sorry" in result.response
    assert len(result.conversation_history) == 1  # Original history is preserved
    chat_client.client.responses.create.assert_called_once()


def test_create_playlist_tool_call(chat_client: ChatClient) -> None:
    """Test a chat completion that involves a tool call to create a playlist."""
    # Arrange
    # First API call returns a tool call
    mock_response_tool_call = MagicMock(spec=Response)
    mock_function_tool_call = ResponseFunctionToolCall(
        id="test_tool_call_id",
        call_id="call_123",
        name="create_playlist",
        arguments='{"name": "New Playlist", "description": "A new playlist", "track_uris": ["spotify:track:123"]}',
        type="function_call",
    )
    mock_response_tool_call.output = [mock_function_tool_call]

    # Second API call returns a text response
    mock_response_text = MagicMock(spec=Response)
    mock_output_message = ResponseOutputMessage(
        id="test_id",
        content=[
            ResponseOutputText(
                text="Playlist created.", type="output_text", annotations=[]
            )
        ],
        type="message",
        role="assistant",
        status="completed",
    )
    mock_response_text.output = [mock_output_message]

    chat_client.client.responses.create.side_effect = [
        mock_response_tool_call,
        mock_response_text,
    ]
    conversation_history = [{"role": "user", "content": "Create a playlist for me."}]
    mock_spotify_client = MagicMock()
    mock_spotify_client.create_playlist.return_value = "new_playlist_id"

    # Act
    generator = chat_client.get_chat_completion(
        conversation_history, mock_spotify_client
    )
    tool_call_response = next(generator)
    chat_response = next(generator)

    # Assert
    assert isinstance(tool_call_response, ToolCallResponse)
    assert tool_call_response.function_name == "create_playlist"
    assert isinstance(chat_response, ChatResponse)
    assert chat_response.response == "Playlist created."
    assert (
        len(chat_response.conversation_history) == 4
    )  # user, assistant (tool), function, assistant (text)
    assert chat_client.client.responses.create.call_count == 2
    mock_spotify_client.create_playlist.assert_called_once_with(
        "New Playlist", "A new playlist", ["spotify:track:123"]
    )
