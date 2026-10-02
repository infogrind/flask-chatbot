# Flask Chatbot

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

This project provides a Flask-based chatbot that uses an LLM (Anthropic's Claude or
OpenAI's GPT models) and the Spotify API to generate curated playlists based on user
prompts.

<img width="827" height="886" alt="Screenshot 2025-09-07 at 06 45 17" src="https://github.com/user-attachments/assets/6904aea9-d946-4a3b-ac27-6cd04507d77d" />

## Prerequisites

- Python 3.13+
- `uv` tool ([docs](https://docs.astral.sh/uv/))

## Installation

```bash
# Install dependencies and create a virtual environment
uv sync
```

## Configuration

Copy `.env.example` to `.env` and set your environment variables:

```bash
cp .env.example .env
# Then edit .env to add your Spotify credentials and a SECRET_KEY
```

### LLM provider

The LLM provider and its API key are configured in a TOML file following the
[XDG Base Directory specification](https://specifications.freedesktop.org/basedir-spec/latest/),
at `$XDG_CONFIG_HOME/flask-chatbot/config.toml` (by default
`~/.config/flask-chatbot/config.toml`):

```bash
mkdir -p ~/.config/flask-chatbot
cp config.example.toml ~/.config/flask-chatbot/config.toml
chmod 600 ~/.config/flask-chatbot/config.toml
# Then edit it to choose the provider and add its API key
```

```toml
provider = "anthropic"  # or "openai"

[anthropic]
api_key = "sk-ant-..."
model = "claude-opus-5-5"  # optional, this is the default
effort = "medium"          # optional: low, medium, high, xhigh, max
```

See `config.example.toml` for all options. Without a config file the app uses OpenAI,
and API keys missing from the file fall back to the `ANTHROPIC_API_KEY` and
`OPENAI_API_KEY` environment variables.

## Running the application

```bash
uv run flask run
# Or with specific host/port:
uv run flask run --host=0.0.0.0 --port=5000
```

## Testing

```bash
uv run pytest
```

## Code Quality

```bash
uv run ruff check --fix && uv run ruff format
```
