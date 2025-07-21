import json
import logging
import os
from dataclasses import dataclass
from pprint import pformat
from typing import List

from openai import OpenAI
from openai.types.responses import (
    EasyInputMessageParam,
    FunctionToolParam,
    Response,
    ResponseFunctionToolCall,
    ResponseFunctionToolCallParam,
    ResponseInputParam,
    ResponseOutputItem,
    ResponseOutputMessage,
    ResponseOutputRefusal,
    ResponseOutputText,
)
from openai.types.responses.response_input_param import FunctionCallOutput

from app.spotify_client import SpotifyClient

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)  # enable DEBUG only for this module


# passed to each call of `get_chat_completion`.
@dataclass
class ChatResponse:
    # The conversation history.
    conversation_history: ResponseInputParam

    # The response to display in the UI. Can be an error.
    response: str


class ChatClient:
    """A wrapper for the OpenAI API client."""

    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set.")
        self.client = OpenAI(api_key=api_key)
        self.tools = []
        self.tools: List[FunctionToolParam] = [
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
        ]

    def handle_non_tool_outputs(
        self,
        outputs: List[ResponseOutputItem],
        conversation_history: ResponseInputParam,
    ):
        responses: List[str] = []
        for output in outputs:
            match output:
                case ResponseOutputMessage(id=_, content=content, type=_):
                    for c in content:
                        match c:
                            case ResponseOutputText(text=text):
                                conversation_history.append(
                                    {"role": "assistant", "content": text}
                                )
                                responses.append(text)
                            case ResponseOutputRefusal(refusal=refusal):
                                conversation_history.append(
                                    {"role": "assistant", "content": refusal}
                                )
                                responses.append(f"Refusal message: {refusal}")
                case _:
                    responses.append(f"Unknown output type: {type(output).__name__}")
        return ChatResponse(conversation_history, "\n".join(responses))

    def perform_function_call(
        self,
        name: str,
        call_id: str,
        arguments: str,
    ) -> FunctionCallOutput:
        if name == "get_my_playlists":
            output = self.spotify_client.get_user_playlists()
        elif name == "get_liked_songs":
            output = self.spotify_client.get_liked_songs()
        elif name == "get_playlist_contents":
            args = json.loads(arguments)
            playlist_id = args["playlist_id"]
            output = self.spotify_client.get_playlist_contents(playlist_id)
        elif name == "create_playlist":
            args = json.loads(arguments)
            name = args["name"]
            description = args["description"]
            track_uris = args["track_uris"]
            logger.info(f"Creating playlist '{name}' with {len(track_uris)} tracks.")
            output = self.spotify_client.create_playlist(name, description, track_uris)
        else:
            output = {"error": f"Undefined function: '{name}'"}
        return {
            "type": "function_call_output",
            "call_id": call_id,
            "output": str(output),
        }

    def process_tool_calls(
        self,
        outputs: List[ResponseOutputItem],
        conversation_history: ResponseInputParam,
    ):
        for output in outputs:
            match output:
                case ResponseFunctionToolCall(
                    call_id=call_id, name=name, arguments=arguments, id=id
                ):
                    function_call: ResponseFunctionToolCallParam = {
                        "type": "function_call",
                        "name": name,
                        "call_id": call_id,
                        "arguments": arguments,
                    }
                    if id:
                        function_call["id"] = id
                    function_call_result: FunctionCallOutput = (
                        self.perform_function_call(name, call_id, arguments)
                    )
                    # Only save function call if result was successfully obtained,
                    # otherwise we'll have a corrupted conversation context.
                    conversation_history.append(function_call)
                    conversation_history.append(function_call_result)
                case _:
                    logger.info(
                        f"Skipping unexpected output of type {type(output).__name__}: {pformat(output)}"
                    )

        return conversation_history

    def get_chat_completion(
        self, conversation_history: ResponseInputParam, spotify_client
    ) -> ChatResponse:
        """Gets a chat completion from the OpenAI API, handling tool calls."""

        self.spotify_client: SpotifyClient = spotify_client

        system_prompt: EasyInputMessageParam = {
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

Rely on your existing knowledge about music to answer the user's questions. Do not use the
user's playlists to answer general musical questions, or questions about a certain era or
artist.

IMPORTANT: Only make a function call to get Spotify information after the user
explicitly confirms that you can do it.
""",
                }
            ],
        }

        try:
            logger.info(f"Tools: {pformat(self.tools)}")

            while True:
                logger.info(f"Conversation history: {pformat(conversation_history)}")
                logger.info("Calling API")
                response: Response = self.client.responses.create(
                    model="gpt-4o-mini",
                    input=[system_prompt] + conversation_history,
                    tools=self.tools,
                    tool_choice="auto",
                )

                logger.debug(f"API response:\n{pformat(response)}")

                if not response.output:
                    return ChatResponse(conversation_history, "No output in response")

                if not any(
                    isinstance(o, ResponseFunctionToolCall) for o in response.output
                ):
                    return self.handle_non_tool_outputs(
                        response.output, conversation_history
                    )

                conversation_history = self.process_tool_calls(
                    response.output, conversation_history
                )
                # Loop

        except Exception:
            logger.error("Exception occurred", exc_info=True)
            return ChatResponse(
                conversation_history,
                "I'm sorry, I'm having trouble connecting to the chat service.",
            )
