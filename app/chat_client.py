import json
import logging
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pprint import pformat
from typing import TypeAlias

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

from app.spotify_client import SpotifyClient

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)  # enable DEBUG only for this module

MODEL = "gpt-4o-mini"

# Upper bound on model calls per user message, so a model that keeps requesting
# tool calls cannot loop forever.
MAX_TOOL_ROUNDS = 10

SYSTEM_PROMPT: EasyInputMessageParam = {
    "role": "system",
    "content": [
        {
            "type": "input_text",
            "text": """\
You are a musical history expert and you help
analyzing the user's spotify Playlists and creating new playlists.
In particular, you can curate new playlists based on a period or a
genre that the user is interested in, and you can furnish the
corresponding explanations. For example, you could create a playlist
of the most important transition shifts of The Beatles and furnish a text,
while the user can listen to the playlist you've created.

You have the following tools available:
1) Retrieve the user's playlists from Spotify.
2) Retrieve the user's liked songs list from Spotify.
3) Retrieve all the songs from a given playlist.
4) Search Spotify for a song by title and artist to get its Spotify ID.
5) Create a new playlist in the user's Spotify account.

Rely on your existing knowledge about music to answer the user's questions. Do not use the
user's playlists to answer general musical questions, or questions about a certain era or
artist.

When creating a playlist, you must first call `search_songs` to get each song's Spotify ID.

IMPORTANT: Only make a function call to get Spotify information after the user
explicitly confirms that you can do it.
""",
        }
    ],
}

TOOLS: list[FunctionToolParam] = [
    {
        "type": "function",
        "name": "get_my_playlists",
        "description": "Returns a list of the user's Spotify playlists",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "get_playlist_contents",
        "description": "Returns a list of songs in a playlist",
        "parameters": {
            "type": "object",
            "properties": {
                "playlist_id": {
                    "type": "string",
                    "description": (
                        "The ID of the playlist. "
                        "This ID must have been previously retrieved by a call "
                        "to get_my_playlists."
                    ),
                },
            },
            "required": ["playlist_id"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "get_liked_songs",
        "description": "Returns a list of the user's liked songs from Spotify.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "create_playlist",
        "description": "Creates a new playlist on Spotify.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "The name of the playlist.",
                },
                "description": {
                    "type": "string",
                    "description": "The description of the playlist.",
                },
                "track_uris": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "A list of Spotify track URIs to add to the playlist.",
                },
            },
            "required": ["name", "description", "track_uris"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "search_songs",
        "description": "Searches for songs on Spotify by title and artist.",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "The title of the song.",
                },
                "artist": {
                    "type": "string",
                    "description": "The artist of the song.",
                },
                "limit": {
                    "type": "integer",
                    "description": "The maximum number of songs to return.",
                },
            },
            "required": ["title", "artist", "limit"],
            "additionalProperties": False,
        },
        "strict": True,
    },
]


# Yielded by `get_chat_completion` for text that should be shown in the UI.
@dataclass
class ChatResponse:
    # The conversation history.
    conversation_history: ResponseInputParam

    # The response to display in the UI. Can be an error.
    response: str


# Yielded by `get_chat_completion` before a tool call is executed.
@dataclass
class ToolCallResponse:
    function_name: str
    arguments: str


ChatStreamResponse: TypeAlias = ChatResponse | ToolCallResponse


class ChatClient:
    """A wrapper for the OpenAI API client."""

    def __init__(self, api_key: str) -> None:
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set.")
        self.client = OpenAI(api_key=api_key)
        self.tools = TOOLS

    def perform_function_call(
        self,
        spotify_client: SpotifyClient,
        call: ResponseFunctionToolCall,
    ) -> FunctionCallOutput:
        """Executes a tool call; errors are returned to the model as the output."""
        functions: dict[str, Callable[..., object]] = {
            "get_my_playlists": spotify_client.get_user_playlists,
            "get_liked_songs": spotify_client.get_liked_songs,
            "get_playlist_contents": spotify_client.get_playlist_contents,
            "create_playlist": spotify_client.create_playlist,
            "search_songs": spotify_client.search_songs,
        }
        function = functions.get(call.name)
        if function is None:
            output: object = {"error": f"Undefined function: '{call.name}'"}
        else:
            try:
                output = function(**json.loads(call.arguments))
            except Exception as e:
                logger.exception("Tool call %s failed", call.name)
                output = {"error": f"{type(e).__name__}: {e}"}
        return {
            "type": "function_call_output",
            "call_id": call.call_id,
            "output": json.dumps(output, default=str),
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
                    model=MODEL,
                    input=[SYSTEM_PROMPT, *conversation_history],
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
            yield ChatResponse(
                conversation_history,
                "I'm sorry, I had to stop because this took too many steps. "
                "Please try again with a more specific request.",
            )

        except Exception:
            logger.error("Exception occurred", exc_info=True)
            yield ChatResponse(
                conversation_history,
                "I'm sorry, I'm having trouble connecting to the chat service.",
            )
