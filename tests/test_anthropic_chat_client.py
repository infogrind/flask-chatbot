import json
from typing import Any
from unittest.mock import MagicMock

import anthropic
import pytest
from anthropic import omit
from anthropic.types.beta import BetaMessage

from app.anthropic_chat_client import (
    REFUSAL_FALLBACK_BETA,
    AnthropicChatClient,
)
from app.chat import MAX_TOOL_ROUNDS, SYSTEM_PROMPT, ChatResponse, ToolCallResponse

THINKING = {"type": "thinking", "thinking": "", "signature": "sig-1"}


def _message(content: list[dict[str, Any]], stop_reason: str) -> BetaMessage:
    return BetaMessage.model_validate(
        {
            "id": "msg_1",
            "type": "message",
            "role": "assistant",
            "model": "claude-opus-5-5",
            "content": content,
            "stop_reason": stop_reason,
            "stop_sequence": None,
            "usage": {"input_tokens": 10, "output_tokens": 5},
        }
    )


def _text(text: str) -> BetaMessage:
    return _message([THINKING, {"type": "text", "text": text}], "end_turn")


def _tool_use(name: str = "get_my_playlists", **arguments: Any) -> BetaMessage:
    return _message(
        [
            THINKING,
            {"type": "tool_use", "id": "toolu_1", "name": name, "input": arguments},
        ],
        "tool_use",
    )


@pytest.fixture
def chat_client() -> AnthropicChatClient:
    client = AnthropicChatClient(api_key="test-key", model="claude-opus-5-5")
    client.client = MagicMock()
    return client


def _create(client: AnthropicChatClient) -> MagicMock:
    return client.client.beta.messages.create


def _history_snapshots(client: AnthropicChatClient) -> list[list[Any]]:
    """Messages sent on each request (copied, since the list is mutated later)."""
    return [
        json.loads(json.dumps(call.kwargs["messages"]))
        for call in _create(client).call_args_list
    ]


def test_text_response(chat_client: AnthropicChatClient) -> None:
    # Arrange
    _create(chat_client).return_value = _text("Hello!")
    history: list[Any] = [{"role": "user", "content": "Hi"}]

    # Act
    results = list(chat_client.get_chat_completion(history, MagicMock()))

    # Assert
    assert [r.response for r in results] == ["Hello!"]
    # Thinking blocks are stored unchanged so they can be passed back later
    assert history[-1] == {
        "role": "assistant",
        "content": [THINKING, {"type": "text", "text": "Hello!"}],
    }


def test_request_parameters(chat_client: AnthropicChatClient) -> None:
    # Arrange
    _create(chat_client).return_value = _text("Hello!")

    # Act
    list(
        chat_client.get_chat_completion(
            [{"role": "user", "content": "Hi"}], MagicMock()
        )
    )

    # Assert
    kwargs = _create(chat_client).call_args.kwargs
    assert kwargs["model"] == "claude-opus-5-5"
    assert kwargs["system"] == SYSTEM_PROMPT
    assert kwargs["output_config"] == {"effort": "medium"}
    assert kwargs["cache_control"] == {"type": "ephemeral"}
    assert kwargs["fallbacks"] == "default"
    assert kwargs["betas"] == [REFUSAL_FALLBACK_BETA]
    assert "thinking" not in kwargs
    assert "tool_choice" not in kwargs
    tool = next(t for t in kwargs["tools"] if t["name"] == "search_songs")
    assert tool["strict"] is True
    assert tool["input_schema"]["required"] == ["title", "artist", "limit"]


def test_refusal_fallback_can_be_disabled() -> None:
    client = AnthropicChatClient(
        api_key="k", model="claude-opus-5-5", refusal_fallback=False
    )
    client.client = MagicMock()
    _create(client).return_value = _text("Hello!")

    list(client.get_chat_completion([{"role": "user", "content": "Hi"}], MagicMock()))

    # `omit` leaves the parameter out of the request
    kwargs = _create(client).call_args.kwargs
    assert kwargs["fallbacks"] is omit
    assert kwargs["betas"] is omit


def test_tool_call_round_trip(chat_client: AnthropicChatClient) -> None:
    # Arrange
    _create(chat_client).side_effect = [
        _tool_use("search_songs", title="So What", artist="Miles Davis", limit=3),
        _text("Found it."),
    ]
    spotify_client = MagicMock()
    spotify_client.search_songs.return_value = [{"track_id": "abc"}]
    history: list[Any] = [{"role": "user", "content": "Find So What"}]

    # Act
    results = list(chat_client.get_chat_completion(history, spotify_client))

    # Assert
    assert results == [
        ToolCallResponse(
            "search_songs",
            json.dumps({"title": "So What", "artist": "Miles Davis", "limit": 3}),
        ),
        ChatResponse(history, "Found it."),
    ]
    spotify_client.search_songs.assert_called_once_with(
        title="So What", artist="Miles Davis", limit=3
    )
    second_request = _history_snapshots(chat_client)[1]
    assert second_request[1]["content"][0] == THINKING
    assert second_request[2] == {
        "role": "user",
        "content": [
            {
                "type": "tool_result",
                "tool_use_id": "toolu_1",
                "content": json.dumps([{"track_id": "abc"}]),
                "is_error": False,
            }
        ],
    }


def test_failing_tool_is_reported_as_error(chat_client: AnthropicChatClient) -> None:
    # Arrange
    _create(chat_client).side_effect = [_tool_use(), _text("Spotify failed.")]
    spotify_client = MagicMock()
    spotify_client.get_user_playlists.side_effect = RuntimeError("token expired")
    history: list[Any] = [{"role": "user", "content": "My playlists?"}]

    # Act
    list(chat_client.get_chat_completion(history, spotify_client))

    # Assert
    tool_result = history[2]["content"][0]
    assert tool_result["is_error"] is True
    assert "token expired" in tool_result["content"]


def test_refusal_is_reported_and_not_stored(chat_client: AnthropicChatClient) -> None:
    # Arrange
    _create(chat_client).return_value = _message([], "refusal")
    history: list[Any] = [{"role": "user", "content": "..."}]

    # Act
    results = list(chat_client.get_chat_completion(history, MagicMock()))

    # Assert
    assert len(results) == 1
    assert "can't help" in results[0].response
    assert history == [{"role": "user", "content": "..."}]


def test_blocks_before_fallback_boundary_are_not_echoed(
    chat_client: AnthropicChatClient,
) -> None:
    """After a fallback, the declined model's thinking must not be passed back."""
    # Arrange
    fallback = {
        "type": "fallback",
        "from": {"model": "claude-opus-5-5"},
        "to": {"model": "claude-opus-5"},
        "trigger": {"type": "refusal", "category": "cyber"},
    }
    _create(chat_client).return_value = _message(
        [
            {"type": "thinking", "thinking": "", "signature": "declined"},
            fallback,
            THINKING,
            {"type": "text", "text": "Answer from the fallback model."},
        ],
        "end_turn",
    )
    history: list[Any] = [{"role": "user", "content": "Hi"}]

    # Act
    list(chat_client.get_chat_completion(history, MagicMock()))

    # Assert
    assert history[-1]["content"] == [
        THINKING,
        {"type": "text", "text": "Answer from the fallback model."},
    ]


def test_truncated_tool_call_is_not_executed(chat_client: AnthropicChatClient) -> None:
    # Arrange
    response = _tool_use()
    response.stop_reason = "max_tokens"
    _create(chat_client).return_value = response
    spotify_client = MagicMock()
    history: list[Any] = [{"role": "user", "content": "My playlists?"}]

    # Act
    results = list(chat_client.get_chat_completion(history, spotify_client))

    # Assert
    spotify_client.get_user_playlists.assert_not_called()
    assert "cut off" in results[-1].response
    assert all(
        block["type"] != "tool_use"
        for message in history
        if isinstance(message["content"], list)
        for block in message["content"]
    )


def test_agent_loop_is_bounded(chat_client: AnthropicChatClient) -> None:
    _create(chat_client).side_effect = lambda **_: _tool_use()

    results = list(
        chat_client.get_chat_completion(
            [{"role": "user", "content": "loop"}], MagicMock()
        )
    )

    assert _create(chat_client).call_count == MAX_TOOL_ROUNDS
    assert isinstance(results[-1], ChatResponse)


def test_authentication_error_points_to_config(
    chat_client: AnthropicChatClient,
) -> None:
    _create(chat_client).side_effect = anthropic.AuthenticationError(
        "invalid x-api-key", response=MagicMock(status_code=401), body=None
    )

    results = list(
        chat_client.get_chat_completion(
            [{"role": "user", "content": "Hi"}], MagicMock()
        )
    )

    assert "API key" in results[0].response
    assert "config.toml" in results[0].response


def test_bad_request_message_is_shown(chat_client: AnthropicChatClient) -> None:
    """E.g. an exhausted credit balance is reported as a 400 with a clear message."""
    _create(chat_client).side_effect = anthropic.BadRequestError(
        "Your credit balance is too low",
        response=MagicMock(status_code=400),
        body=None,
    )

    results = list(
        chat_client.get_chat_completion(
            [{"role": "user", "content": "Hi"}], MagicMock()
        )
    )

    assert "credit balance is too low" in results[0].response


def test_missing_credentials_point_to_config(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without any key the SDK raises a bare `TypeError`; explain the fix instead."""
    for var in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_PROFILE"):
        monkeypatch.delenv(var, raising=False)
    client = AnthropicChatClient(api_key=None)

    results = list(
        client.get_chat_completion([{"role": "user", "content": "Hi"}], MagicMock())
    )

    assert len(results) == 1
    assert "API key" in results[0].response
    assert "config.toml" in results[0].response
