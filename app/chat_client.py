import os
from openai import OpenAI


class ChatClient:
    """A wrapper for the OpenAI API client."""

    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set.")
        self.client = OpenAI(api_key=api_key)

    def get_chat_completion(self, messages):
        """Gets a chat completion from the OpenAI API."""
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
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"An error occurred: {e}")
            return "I'm sorry, I'm having trouble connecting to the chat service."
