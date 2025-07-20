import json
import logging
import os
from dataclasses import dataclass
from pprint import pprint
from types import TracebackType
from typing import List

from openai import OpenAI
from openai.types.responses import (
    FunctionToolParam,
    Response,
    ResponseFunctionToolCall,
    ResponseInputParam,
    ResponseOutputItem,
    ResponseOutputMessage,
    ResponseOutputMessageParam,
    ResponseOutputRefusal,
    ResponseOutputText,
)


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
        # self.tools: List[FunctionToolParam] = [
        #     {
        #         "type": "function",
        #         "name": "get_my_playlists",
        #         "description": "Returns a list of the user's Spotify playlists",
        #         "parameters": {
        #             "type": "object",
        #             "properties": {},
        #             "required": [],
        #             "additionalProperties": False,
        #         },
        #         "strict": True,
        #     }
        # ]

    def get_chat_completion(
        self, conversation_history: ResponseInputParam
    ) -> ChatResponse:
        """Gets a chat completion from the OpenAI API, handling tool calls."""
        try:
            pprint(conversation_history)
            pprint(self.tools)

            response: Response = self.client.responses.create(
                model="gpt-3.5-turbo",
                input=conversation_history,
                tools=self.tools,
                tool_choice="auto",
            )

            if not hasattr(response, "output"):
                return ChatResponse(
                    conversation_history, "Error: no output in response."
                )
            elif len(response.output) == 0:
                return ChatResponse(conversation_history, "Error: zero outputs.")
            elif len(response.output) > 1:
                return ChatResponse(
                    conversation_history,
                    f"Error: {len(response.output)} outputs, expected 1.",
                )

            output: ResponseOutputItem = response.output[0]

            match output:
                case ResponseOutputMessage(id=id, content=content, type=typ):
                    if len(content) != 1:
                        return ChatResponse(
                            conversation_history,
                            f"Unexpected output content length {len(content)}.",
                        )
                    c = content[0]
                    match c:
                        case ResponseOutputText(text=text):
                            conversation_history.append(
                                {"role": "assistant", "content": text}
                            )
                            return ChatResponse(conversation_history, text)
                        case ResponseOutputRefusal(refusal=refusal):
                            conversation_history.append(
                                {"role": "assistant", "content": refusal}
                            )
                            return ChatResponse(conversation_history, refusal)
                case ResponseFunctionToolCall(
                    call_id=call_id, name=name, type=typ, id=id
                ):
                    return ChatResponse(
                        conversation_history,
                        f"Model wants to call function {name}. type = {typ}, id = {id}, call_id = {call_id}.",
                    )
                case _:
                    return ChatResponse(
                        conversation_history,
                        f"Unknown output type: {type(output).__name__}",
                    )

        except Exception:
            logging.error("Exception occurred", exc_info=True)
            return ChatResponse(
                conversation_history,
                "I'm sorry, I'm having trouble connecting to the chat service.",
            )
