import json
import os
from openai import OpenAI


class ChatClient:
    """A wrapper for the OpenAI API client."""

    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set.")
        self.client = OpenAI(api_key=api_key)
        self.tools = [
            {
                "type": "function",
                "function": {
                    "name": "get_my_playlists",
                    "description": "Get a list of the current user's playlists.",
                    "parameters": {"type": "object", "properties": {}},
                },
            }
        ]

    def get_chat_completion(self, messages, available_tools=None):
        """Gets a chat completion from the OpenAI API, handling tool calls."""
        api_messages = []
        for message in messages:
            if message["role"] == "bot":
                api_messages.append(
                    {"role": "assistant", "content": message["content"]}
                )
            else:
                api_messages.append(message)
        try:
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=api_messages,
                tools=self.tools,
                tool_choice="auto",
            )
            response_message = response.choices[0].message

            tool_calls = response_message.tool_calls
            if tool_calls:
                results = {"tool_calls": []}
                for tool_call in tool_calls:
                    function_name = tool_call.function.name
                    if function_name in available_tools:
                        function_to_call = available_tools[function_name]
                        function_args = json.loads(tool_call.function.arguments)
                        function_response = function_to_call(**function_args)
                        results["tool_calls"].append(
                            {
                                "id": tool_call.id,
                                "name": function_name,
                                "result": function_response,
                            }
                        )
                return results

            return response_message.content
        except Exception as e:
            print(f"An error occurred: {e}")
            return "I'm sorry, I'm having trouble connecting to the chat service."
