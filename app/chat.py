"""Provider-neutral parts of the chat: prompt, tools, and stream responses."""

import json
import logging
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Any, Protocol, TypeAlias, TypedDict

from app.spotify_client import SpotifyClient

logger = logging.getLogger(__name__)

# Upper bound on model calls per user message, so a model that keeps requesting
# tool calls cannot loop forever.
MAX_TOOL_ROUNDS = 10

TOO_MANY_ROUNDS_MESSAGE = (
    "I'm sorry, I had to stop because this took too many steps. "
    "Please try again with a more specific request."
)
CONNECTION_ERROR_MESSAGE = (
    "I'm sorry, I'm having trouble connecting to the chat service."
)

SYSTEM_PROMPT = """\
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
"""


class ToolSpec(TypedDict):
    name: str
    description: str
    # JSON schema of the arguments
    parameters: dict[str, Any]


TOOL_SPECS: list[ToolSpec] = [
    {
        "name": "get_my_playlists",
        "description": "Returns a list of the user's Spotify playlists",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False,
        },
    },
    {
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
    },
    {
        "name": "get_liked_songs",
        "description": "Returns a list of the user's liked songs from Spotify.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False,
        },
    },
    {
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
    },
    {
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
    },
]


# Yielded by `get_chat_completion` for text that should be shown in the UI.
@dataclass
class ChatResponse:
    # The conversation history, in the provider's own message format.
    conversation_history: list[Any]

    # The response to display in the UI. Can be an error.
    response: str


# Yielded by `get_chat_completion` before a tool call is executed.
@dataclass
class ToolCallResponse:
    function_name: str
    arguments: str


ChatStreamResponse: TypeAlias = ChatResponse | ToolCallResponse


class ChatClient(Protocol):
    def get_chat_completion(
        self, conversation_history: list[Any], spotify_client: SpotifyClient
    ) -> Iterator[ChatStreamResponse]:
        """Runs the agent loop for the last user message in the history.

        Appends to `conversation_history` in place and yields what to show in the UI.
        """
        ...


def run_tool(
    spotify_client: SpotifyClient, name: str, arguments: dict[str, Any]
) -> tuple[str, bool]:
    """Executes a tool call.

    Returns the JSON-encoded output and whether it is an error. Errors are returned
    rather than raised, so they can be reported to the model.
    """
    functions: dict[str, Callable[..., object]] = {
        "get_my_playlists": spotify_client.get_user_playlists,
        "get_liked_songs": spotify_client.get_liked_songs,
        "get_playlist_contents": spotify_client.get_playlist_contents,
        "create_playlist": spotify_client.create_playlist,
        "search_songs": spotify_client.search_songs,
    }
    function = functions.get(name)
    if function is None:
        return json.dumps({"error": f"Undefined function: '{name}'"}), True
    try:
        return json.dumps(function(**arguments), default=str), False
    except Exception as e:
        logger.exception("Tool call %s failed", name)
        return json.dumps({"error": f"{type(e).__name__}: {e}"}), True


def visible_messages(conversation_history: list[Any]) -> list[dict[str, str]]:
    """Extracts the user and assistant text to show in the UI from a history.

    Works for both providers' formats: content is either a string or a list of
    blocks, of which only `text` blocks are shown. Tool calls, tool results, and
    thinking blocks are skipped.
    """
    messages = []
    for item in conversation_history:
        role = item.get("role")
        if role not in ("user", "assistant"):
            continue
        content = item.get("content")
        if isinstance(content, list):
            content = "\n\n".join(
                block["text"] for block in content if block.get("type") == "text"
            )
        if content:
            messages.append({"role": role, "content": content})
    return messages
