import os
import subprocess
import sys
from collections.abc import Iterator
from unittest.mock import MagicMock, patch

import pytest
from openai.types.responses import (
    Response,
    ResponseFunctionToolCall,
    ResponseOutputMessage,
    ResponseOutputText,
)

from app.chat_client import (
    MAX_TOOL_ROUNDS,
    ChatClient,
    ChatResponse,
    ToolCallResponse,
)


@pytest.fixture
def chat_client() -> Iterator[ChatClient]:
    """Fixture to provide a ChatClient instance with a mocked OpenAI client."""
    with patch("app.chat_client.OpenAI"):
        client = ChatClient("test_api_key")
        client.client.responses.create = MagicMock()
        yield client


def test_chat_client_initialization() -> None:
    """Test that the ChatClient initializes correctly."""
    # Act
    client = ChatClient("test_api_key")

    # Assert
    assert client.client is not None
    assert len(client.tools) > 0


def test_chat_client_initialization_no_api_key() -> None:
    """Test that the ChatClient raises an error if the API key is not set."""
    # Act & Assert
    with pytest.raises(
        ValueError, match="OPENAI_API_KEY environment variable not set."
    ):
        ChatClient("")


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
    results = list(
        chat_client.get_chat_completion(conversation_history, mock_spotify_client)
    )

    # Assert
    assert len(results) == 1
    result = results[0]
    assert isinstance(result, ChatResponse)
    assert "I'm sorry" in result.response
    assert len(result.conversation_history) == 1  # Original history is preserved
    chat_client.client.responses.create.assert_called_once()


def test_get_chat_completion_empty_output(chat_client: ChatClient) -> None:
    """An empty model output is reported to the user instead of being dropped."""
    # Arrange
    mock_response = MagicMock(spec=Response)
    mock_response.output = []
    chat_client.client.responses.create.return_value = mock_response

    # Act
    results = list(
        chat_client.get_chat_completion(
            [{"role": "user", "content": "Hello"}], MagicMock()
        )
    )

    # Assert
    assert len(results) == 1
    assert isinstance(results[0], ChatResponse)
    assert results[0].response


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
        name="New Playlist",
        description="A new playlist",
        track_uris=["spotify:track:123"],
    )


def test_concurrent_completions_use_their_own_spotify_client(
    chat_client: ChatClient,
) -> None:
    """Interleaved requests must not run tool calls against another user's account."""
    # Arrange
    tool_call_response = MagicMock(spec=Response)
    tool_call_response.output = [
        ResponseFunctionToolCall(
            call_id="call_1",
            name="get_my_playlists",
            arguments="{}",
            type="function_call",
        )
    ]
    text_response = MagicMock(spec=Response)
    text_response.output = [
        ResponseOutputMessage(
            id="msg",
            content=[ResponseOutputText(text="ok", type="output_text", annotations=[])],
            type="message",
            role="assistant",
            status="completed",
        )
    ]
    chat_client.client.responses.create.side_effect = [
        tool_call_response,
        tool_call_response,
        text_response,
        text_response,
    ]
    spotify_a, spotify_b = MagicMock(), MagicMock()
    stream_a = chat_client.get_chat_completion([], spotify_a)
    stream_b = chat_client.get_chat_completion([], spotify_b)

    # Act
    next(stream_a)
    next(stream_b)
    list(stream_a)
    list(stream_b)

    # Assert
    spotify_a.get_user_playlists.assert_called_once()
    spotify_b.get_user_playlists.assert_called_once()


def _tool_call_response(name: str = "get_my_playlists") -> MagicMock:
    response = MagicMock(spec=Response)
    response.output = [
        ResponseFunctionToolCall(
            call_id="call_1", name=name, arguments="{}", type="function_call"
        )
    ]
    return response


def _text_response(text: str) -> MagicMock:
    response = MagicMock(spec=Response)
    response.output = [
        ResponseOutputMessage(
            id="msg",
            content=[ResponseOutputText(text=text, type="output_text", annotations=[])],
            type="message",
            role="assistant",
            status="completed",
        )
    ]
    return response


def test_failing_tool_call_is_reported_to_model(chat_client: ChatClient) -> None:
    """A Spotify error is passed back to the model instead of aborting the stream."""
    # Arrange
    chat_client.client.responses.create.side_effect = [
        _tool_call_response(),
        _text_response("Sorry, Spotify failed."),
    ]
    spotify_client = MagicMock()
    spotify_client.get_user_playlists.side_effect = RuntimeError("token expired")

    # Act
    results = list(chat_client.get_chat_completion([], spotify_client))

    # Assert
    assert results[-1] == ChatResponse(
        results[-1].conversation_history, "Sorry, Spotify failed."
    )
    call_output = results[-1].conversation_history[1]
    assert call_output["type"] == "function_call_output"
    assert "token expired" in call_output["output"]


def test_unknown_tool_is_reported_to_model(chat_client: ChatClient) -> None:
    # Arrange
    chat_client.client.responses.create.side_effect = [
        _tool_call_response("no_such_tool"),
        _text_response("done"),
    ]

    # Act
    results = list(chat_client.get_chat_completion([], MagicMock()))

    # Assert
    call_output = results[-1].conversation_history[1]
    assert "no_such_tool" in call_output["output"]


def test_agent_loop_is_bounded(chat_client: ChatClient) -> None:
    """A model that never stops calling tools must not loop forever."""
    # Arrange
    chat_client.client.responses.create.side_effect = lambda **_: _tool_call_response()

    # Act
    results = list(chat_client.get_chat_completion([], MagicMock()))

    # Assert
    assert chat_client.client.responses.create.call_count == MAX_TOOL_ROUNDS
    assert isinstance(results[-1], ChatResponse)


def test_unknown_output_types_are_not_shown_to_user(chat_client: ChatClient) -> None:
    # Arrange
    response = _text_response("Hi")
    response.output.append(MagicMock())
    chat_client.client.responses.create.return_value = response

    # Act
    results = list(chat_client.get_chat_completion([], MagicMock()))

    # Assert
    assert [r.response for r in results] == ["Hi"]


def test_importing_routes_does_not_require_api_key() -> None:
    """`flask init-db` etc. must work without `OPENAI_API_KEY`."""
    env = {**os.environ, "OPENAI_API_KEY": ""}
    result = subprocess.run(
        [sys.executable, "-c", "import app.routes"],
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
