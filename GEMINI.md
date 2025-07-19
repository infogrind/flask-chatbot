# Flask-based Chatbot using the ChatGPT and Spotify APIs to create curated playlists

This directory contains the implementation of a program that should ultimately offer a Flask-based chatbot in which the user can say things like "Create a playlist with 20 songs representing early 20 century american Jazz". The system will then propose a set of songs. When the user accepts, the system will automatically create a playlist in their spotify account.

The tool should use Python 3.13, Flask as web framework, the ChatGPT API and the Spotify API.

## Guidelines and Tools

- All tests go in the `tests` subdirectory. The `pytest` framework is used
exclusively.
- The project relies on the [`uv` tool](https://docs.astral.sh/uv/) to manage
dependencies.
- Always use Python type annotations. If that is not possible for some reason,
state this explicitly and ask for permission to omit them.

## Tool Commands

### Running the Application

```bash
# Run the Flask development server
uv run flask run

# Or run with specific host/port
uv run flask run --host=0.0.0.0 --port=5000
```

### Code Quality

```bash
# Run linter
uv run ruff check

# Auto-fix issues
uv run ruff check --fix

# Format code
uv run ruff format

# Check and format in one command
uv run ruff check --fix && uv run ruff format
```

### Testing

```bash
# Run tests
uv run pytest

# Run tests with coverage
uv run pytest --cov=app
```

### Adding Dependencies

```bash
# Add runtime dependency
uv add package-name

# Add development dependency
uv add --dev package-name

# Upgrade dependencies
uv lock --upgrade
```

## Separate Planning from Implementation

When asked to make a plan, never make any changes to any files yet, just
research and then state your plan. Mention explicitly which files you would
edit.

## General Development Process

Always use this order, both when adding a feature and when fixing a bug.

1. If the code and application structure within which to implement a change
   already exist, add a test first, and verify that it fails.
1. Implement the fix.
1. Format the code.
1. Verify that the test passes.
1. Create a local commit but NEVER push anything yourself.

## Commit Message Guidelines

- Use backticks for code in commit messages

## References

- See <https://flask.palletsprojects.com/en/stable/api/> for the Flask reference.

## Git Repo

- The main branch for this project is called `main`.
- When creating commits with multiline messages, write the message to a file
`commit_message.txt`, then commit with `git commit -F commit_message.txt`.
- When staging code changes, and GEMINI.md also has changes, never stage
GEMINI.md. GEMINI.md must always be in separate commits that are only about
Gemini instructions.
- The first line of a commit message should not be longer than 72 characters,
and all the other lines should have a maximum of 100 characters.

# GEMINI.md Memory Updates

Whenever I prefix a prompt with the hash sign `#`, it means I want you to memorize the instruction in GEMINI.md. In that case, please update GEMINI.md accordingly.

# ChatGPT API Function calling

Enable models to fetch data and take actions.

**Function calling** provides a powerful and flexible way for OpenAI models to interface with your code or external services. This guide will explain how to connect the models to your own custom code to fetch data or take action.

Get weather

Function calling example with get\_weather function

```python
from openai import OpenAI

client = OpenAI()

tools = [{
    "type": "function",
    "name": "get_weather",
    "description": "Get current temperature for a given location.",
    "parameters": {
        "type": "object",
        "properties": {
            "location": {
                "type": "string",
                "description": "City and country e.g. Bogotá, Colombia"
            }
        },
        "required": [
            "location"
        ],
        "additionalProperties": False
    }
}]

response = client.responses.create(
    model="gpt-4.1",
    input=[{"role": "user", "content": "What is the weather like in Paris today?"}],
    tools=tools
)

print(response.output)
```

```javascript
import { OpenAI } from "openai";

const openai = new OpenAI();

const tools = [{
    "type": "function",
    "name": "get_weather",
    "description": "Get current temperature for a given location.",
    "parameters": {
        "type": "object",
        "properties": {
            "location": {
                "type": "string",
                "description": "City and country e.g. Bogotá, Colombia"
            }
        },
        "required": [
            "location"
        ],
        "additionalProperties": false
    }
}];

const response = await openai.responses.create({
    model: "gpt-4.1",
    input: [{ role: "user", content: "What is the weather like in Paris today?" }],
    tools,
});

console.log(response.output);
```

```bash
curl https://api.openai.com/v1/responses \
-H "Content-Type: application/json" \
-H "Authorization: Bearer $OPENAI_API_KEY" \
-d '{
    "model": "gpt-4.1",
    "input": "What is the weather like in Paris today?",
    "tools": [
        {
            "type": "function",
            "name": "get_weather",
            "description": "Get current temperature for a given location.",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "City and country e.g. Bogotá, Colombia"
                    }
                },
                "required": [
                    "location"
                ],
                "additionalProperties": false
            }
        }
    ]
}'
```

Output

```json
[{
    "type": "function_call",
    "id": "fc_12345xyz",
    "call_id": "call_12345xyz",
    "name": "get_weather",
    "arguments": "{\"location\":\"Paris, France\"}"
}]
```
