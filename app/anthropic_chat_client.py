import json
import logging
from collections.abc import Iterator
from pprint import pformat
from typing import Any

import anthropic
from anthropic import omit
from anthropic.types.beta import (
    BetaContentBlock,
    BetaMessage,
    BetaMessageParam,
    BetaOutputConfigParam,
    BetaToolParam,
    BetaToolResultBlockParam,
)

from app.chat import (
    CONNECTION_ERROR_MESSAGE,
    MAX_TOOL_ROUNDS,
    SYSTEM_PROMPT,
    TOO_MANY_ROUNDS_MESSAGE,
    TOOL_SPECS,
    ChatResponse,
    ChatStreamResponse,
    ToolCallResponse,
    run_tool,
)
from app.llm_settings import DEFAULT_EFFORT, DEFAULT_MODELS, Effort, config_path
from app.spotify_client import SpotifyClient

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)  # enable DEBUG only for this module

# Room for adaptive thinking (which counts toward the limit) plus the reply.
MAX_TOKENS = 16000

# Retries safety-classifier refusals on a fallback model Anthropic picks for the
# refusal category, within the same request.
REFUSAL_FALLBACK_BETA = "server-side-fallback-2026-07-01"

REFUSAL_MESSAGE = "I'm sorry, I can't help with that request."


def api_key_message() -> str:
    return (
        "The Anthropic API key is missing or invalid. "
        f"Set `api_key` in the `[anthropic]` section of {config_path()}."
    )


TRUNCATED_MESSAGE = "(The response was cut off because it got too long.)"

TOOLS: list[BetaToolParam] = [
    {
        "name": spec["name"],
        "description": spec["description"],
        "input_schema": spec["parameters"],
        "strict": True,
    }
    for spec in TOOL_SPECS
]

# Block types from before a fallback boundary that may be passed back.
ECHOABLE_BEFORE_FALLBACK = {"text"}


def echoable_content(blocks: list[BetaContentBlock]) -> list[dict[str, object]]:
    """Converts response blocks to params that can be stored and passed back.

    Blocks are passed back unchanged (thinking blocks must not be modified),
    except that only text survives from before the last `fallback` block: the
    declined model's thinking and tool calls must not be echoed.
    """
    content = [block.to_dict(mode="json") for block in blocks]
    boundary = max(
        (i for i, block in enumerate(content) if block["type"] == "fallback"),
        default=-1,
    )
    return [
        block
        for i, block in enumerate(content)
        if i > boundary or block["type"] in ECHOABLE_BEFORE_FALLBACK
    ]


class AnthropicChatClient:
    """Runs the chat against the Claude Messages API."""

    def __init__(
        self,
        api_key: str | None,
        model: str = DEFAULT_MODELS["anthropic"],
        effort: Effort = DEFAULT_EFFORT,
        refusal_fallback: bool = True,
    ) -> None:
        # Without a key, the SDK uses `ANTHROPIC_API_KEY` or an `ant` CLI profile
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        self.effort: Effort = effort
        self.refusal_fallback = refusal_fallback

    def has_credentials(self) -> bool:
        """Whether the SDK found a key, auth token, or `ant` profile.

        Without any, requests fail with a bare `TypeError` rather than an API error.
        """
        return any(
            (self.client.api_key, self.client.auth_token, self.client.credentials)
        )

    def _create_message(self, messages: list[BetaMessageParam]) -> BetaMessage:
        output_config: BetaOutputConfigParam = {"effort": self.effort}
        return self.client.beta.messages.create(
            model=self.model,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
            output_config=output_config,
            # System prompt and tools never change and the history is only
            # appended to, so each request can reuse the previous one's cache.
            cache_control={"type": "ephemeral"},
            betas=[REFUSAL_FALLBACK_BETA] if self.refusal_fallback else omit,
            fallbacks="default" if self.refusal_fallback else omit,
        )

    def get_chat_completion(
        self,
        conversation_history: list[BetaMessageParam],
        spotify_client: SpotifyClient,
    ) -> Iterator[ChatStreamResponse]:
        """Gets a reply from Claude, executing tool calls until it is done."""
        if not self.has_credentials():
            yield ChatResponse(conversation_history, api_key_message())
            return
        try:
            for _ in range(MAX_TOOL_ROUNDS):
                response = self._create_message(conversation_history)
                logger.debug("API response:\n%s", pformat(response))

                if response.stop_reason == "refusal":
                    # Partial output of a declined response is discarded
                    logger.warning("Request refused: %s", response.stop_details)
                    yield ChatResponse(conversation_history, REFUSAL_MESSAGE)
                    return

                content = echoable_content(response.content)
                truncated = response.stop_reason == "max_tokens"
                if truncated:
                    # A cut-off tool call can't be executed, and passing it back
                    # without a result would be rejected
                    content = [b for b in content if b["type"] != "tool_use"]
                if content:
                    conversation_history.append(
                        {"role": "assistant", "content": content}
                    )

                for block in content:
                    if block["type"] == "text":
                        yield ChatResponse(conversation_history, str(block["text"]))
                if truncated:
                    yield ChatResponse(conversation_history, TRUNCATED_MESSAGE)
                    return

                tool_uses = [b for b in content if b["type"] == "tool_use"]
                if not tool_uses:
                    return

                tool_results: list[BetaToolResultBlockParam] = []
                for tool_use in tool_uses:
                    arguments: dict[str, Any] = tool_use["input"]  # type: ignore[assignment]
                    yield ToolCallResponse(str(tool_use["name"]), json.dumps(arguments))
                    output, is_error = run_tool(
                        spotify_client, str(tool_use["name"]), arguments
                    )
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": str(tool_use["id"]),
                            "content": output,
                            "is_error": is_error,
                        }
                    )
                # All results of one turn go back in a single user message
                conversation_history.append({"role": "user", "content": tool_results})

            logger.warning("Stopped after %d tool call rounds", MAX_TOOL_ROUNDS)
            yield ChatResponse(conversation_history, TOO_MANY_ROUNDS_MESSAGE)

        except anthropic.AuthenticationError:
            logger.exception("Anthropic authentication failed")
            yield ChatResponse(conversation_history, api_key_message())
        except anthropic.RateLimitError:
            logger.exception("Anthropic rate limit")
            yield ChatResponse(
                conversation_history,
                "I'm getting too many requests right now. Please try again shortly.",
            )
        except anthropic.BadRequestError as e:
            # E.g. "Your credit balance is too low" - worth showing verbatim
            logger.exception("Anthropic rejected the request")
            yield ChatResponse(
                conversation_history,
                f"The Anthropic API rejected the request: {e.message}",
            )
        except Exception:
            logger.exception("Exception occurred")
            yield ChatResponse(conversation_history, CONNECTION_ERROR_MESSAGE)
