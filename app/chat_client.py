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
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter("%(asctime)s %(levelname)s [%(name)s]: %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)


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
                            "type": "integer",
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

    def handle_function_call(
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
            if playlist_id == 1:
                output = [
                    {
                        "song_id": 1,
                        "song_name": "Paradise City",
                        "artist": "Guns N'Roses",
                    },
                    {"song_id": 2, "song_name": "Dream On", "artist": "Aerosmith"},
                ]
            else:
                output = [
                    {
                        "song_id": 3,
                        "song_name": "Beat It",
                        "artist": "Michael Jackson",
                    },
                    {
                        "song_id": 4,
                        "song_name": "The Duke",
                        "artist": "Stevie Wonder",
                    },
                    {
                        "song_id": 5,
                        "song_name": "Let It Be",
                        "artist": "The Beatles",
                    },
                ]
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
                    conversation_history.append(function_call)
                    conversation_history.append(
                        self.handle_function_call(name, call_id, arguments)
                    )
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
                    "text": "You are a musical history expert and you help analyzing the user's spotify Playlists and creating new playlists.",
                }
            ],
        }

        try:
            logger.info(f"Tools: {pformat(self.tools)}")

            while True:
                logger.info(f"Conversation history: {pformat(conversation_history)}")
                logger.info("Calling API")
                response: Response = self.client.responses.create(
                    model="gpt-3.5-turbo",
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
