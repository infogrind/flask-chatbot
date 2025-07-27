# Flask Chatbot

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

This project provides a Flask-based chatbot that integrates with OpenAI's ChatGPT API
and the Spotify API to generate curated playlists based on user prompts.

## Prerequisites

```bash
Python 3.13+
`uv` tool ([docs](https://docs.astral.sh/uv/))
```

## Installation

```bash
# Install dependencies and create a virtual environment
uv lock --install
```

## Configuration

Copy `.env.example` to `.env` and set your environment variables:

```bash
cp .env.example .env
# Then edit .env to add your API keys
```

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
