import json
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
    response: str
    conversation_history: ResponseInputParam


class ChatClient:
    """A wrapper for the OpenAI API client."""

    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set.")
        self.client = OpenAI(api_key=api_key)
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
            }
        ]

    def get_chat_completion(
        self, query: str, conversation_history: ResponseInputParam
    ) -> ChatResponse:
        """Gets a chat completion from the OpenAI API, handling tool calls."""
        try:
            conversation_history.append(
                {
                    "content": query,
                    "role": "user",
                    "type": "message",
                }
            )

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
                    "Error: no output in response.", conversation_history
                )
            elif len(response.output) == 0:
                return ChatResponse("Error: zero outputs.", conversation_history)
            elif len(response.output) > 1:
                return ChatResponse(
                    f"Error: {len(response.output)} outputs, expected 1.",
                    conversation_history,
                )

            output: ResponseOutputItem = response.output[0]

            match output:
                case ResponseOutputMessage(id=id, content=content, type=typ):
                    if len(content) != 1:
                        return ChatResponse(
                            f"Unexpected output content length {len(content)}.",
                            conversation_history,
                        )
                    c = content[0]
                    match c:
                        case ResponseOutputText(text=text):
                            conversation_history.append(
                                {"role": "assistant", "content": text}
                            )
                            return ChatResponse(text, conversation_history)
                        case ResponseOutputRefusal(refusal=refusal):
                            return ChatResponse(
                                f"Refusal: {refusal}", conversation_history
                            )
                case ResponseFunctionToolCall(
                    call_id=call_id, name=name, type=typ, id=id
                ):
                    return ChatResponse(
                        f"Model wants to call function {name}. type = {typ}, id = {id}, call_id = {call_id}.",
                        conversation_history,
                    )
                case _:
                    return ChatResponse(
                        f"Unknown output type: {type(output).__name__}",
                        conversation_history,
                    )

        except Exception as e:
            print(f"An error occurred: {e.with_traceback(None)}")
            return ChatResponse(
                "I'm sorry, I'm having trouble connecting to the chat service.",
                conversation_history,
            )
