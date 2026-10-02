import json
import logging
from collections.abc import Iterator
from pprint import pformat

from openai import OpenAI
from openai.types.responses import (
    EasyInputMessageParam,
    FunctionToolParam,
    ResponseFunctionToolCall,
    ResponseFunctionToolCallParam,
    ResponseInputParam,
    ResponseOutputMessage,
    ResponseOutputText,
)
from openai.types.responses.response_input_param import FunctionCallOutput

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
from app.spotify_client import SpotifyClient

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)  # enable DEBUG only for this module

DEFAULT_MODEL = "gpt-4o-mini"

SYSTEM_MESSAGE: EasyInputMessageParam = {
    "role": "system",
    "content": [{"type": "input_text", "text": SYSTEM_PROMPT}],
}

TOOLS: list[FunctionToolParam] = [
    {
        "type": "function",
        "name": spec["name"],
        "description": spec["description"],
        "parameters": spec["parameters"],
        "strict": True,
    }
    for spec in TOOL_SPECS
]


class OpenAIChatClient:
    """Runs the chat against the OpenAI Responses API."""

    def __init__(self, api_key: str, model: str = DEFAULT_MODEL) -> None:
        if not api_key:
            raise ValueError("No OpenAI API key configured.")
        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.tools = TOOLS

    def perform_function_call(
        self,
        spotify_client: SpotifyClient,
        call: ResponseFunctionToolCall,
    ) -> FunctionCallOutput:
        """Executes a tool call; errors are returned to the model as the output."""
        output, _ = run_tool(spotify_client, call.name, json.loads(call.arguments))
        return {
            "type": "function_call_output",
            "call_id": call.call_id,
            "output": output,
        }

    def process_tool_call(
        self,
        spotify_client: SpotifyClient,
        call: ResponseFunctionToolCall,
        conversation_history: ResponseInputParam,
    ) -> None:
        """Executes a tool call and appends it and its result to the history."""
        function_call: ResponseFunctionToolCallParam = {
            "type": "function_call",
            "name": call.name,
            "call_id": call.call_id,
            "arguments": call.arguments,
        }
        if call.id:
            function_call["id"] = call.id
        function_call_output = self.perform_function_call(spotify_client, call)
        conversation_history.append(function_call)
        conversation_history.append(function_call_output)

    def get_chat_completion(
        self,
        conversation_history: ResponseInputParam,
        spotify_client: SpotifyClient,
    ) -> Iterator[ChatStreamResponse]:
        """Gets a chat completion from the OpenAI API, handling tool calls."""
        try:
            for _ in range(MAX_TOOL_ROUNDS):
                logger.debug("Conversation history: %s", pformat(conversation_history))
                response = self.client.responses.create(
                    model=self.model,
                    input=[SYSTEM_MESSAGE, *conversation_history],
                    tools=self.tools,
                    tool_choice="auto",
                )
                logger.debug("API response:\n%s", pformat(response))

                if not response.output:
                    yield ChatResponse(conversation_history, "No output in response")
                    return

                has_tool_calls = False
                for output in response.output:
                    match output:
                        case ResponseFunctionToolCall():
                            has_tool_calls = True
                            yield ToolCallResponse(output.name, output.arguments)
                            self.process_tool_call(
                                spotify_client, output, conversation_history
                            )
                        case ResponseOutputMessage(content=content):
                            for part in content:
                                text = (
                                    part.text
                                    if isinstance(part, ResponseOutputText)
                                    else part.refusal
                                )
                                conversation_history.append(
                                    {"role": "assistant", "content": text}
                                )
                                yield ChatResponse(conversation_history, text)
                        case _:
                            logger.warning(
                                "Skipping unexpected output of type %s: %s",
                                type(output).__name__,
                                pformat(output),
                            )

                if not has_tool_calls:
                    return

            logger.warning("Stopped after %d tool call rounds", MAX_TOOL_ROUNDS)
            yield ChatResponse(conversation_history, TOO_MANY_ROUNDS_MESSAGE)

        except Exception:
            logger.error("Exception occurred", exc_info=True)
            yield ChatResponse(conversation_history, CONNECTION_ERROR_MESSAGE)
