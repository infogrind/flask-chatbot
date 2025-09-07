# Flask Chatbot

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

This project provides a Flask-based chatbot that integrates with OpenAI's ChatGPT API
and the Spotify API to generate curated playlists based on user prompts.

<img width="827" height="886" alt="Screenshot 2025-09-07 at 06 45 17" src="https://github.com/user-attachments/assets/6904aea9-d946-4a3b-ac27-6cd04507d77d" />

## Prerequisites

- Python 3.13+
- `uv` tool ([docs](https://docs.astral.sh/uv/))

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
