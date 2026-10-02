# AGENTS.md

This file provides guidance to AI coding agents (Claude Code, Gemini CLI, etc.)
when working with code in this repository. `CLAUDE.md` and `GEMINI.md` are
symlinks to this file.

## Project Overview

A Flask-based chatbot that uses an LLM (Anthropic Claude or OpenAI) and the
Spotify API to create curated playlists. The user chats (e.g. "Create a
playlist with 20 songs representing early 20th century American jazz"); the
model proposes songs and, on confirmation, creates the playlist in the user's
Spotify account.

Python 3.13+, dependencies managed with [`uv`](https://docs.astral.sh/uv/).

## Commands

```bash
# Run the Flask development server
uv run flask run

# Initialize/reset the SQLite database (instance/flask-chatbot.sqlite)
uv run flask init-db

# Run all tests
uv run pytest

# Run a single test file or test
uv run pytest tests/test_anthropic_chat_client.py
uv run pytest tests/test_app.py::test_name

# Lint, auto-fix, and format (run before committing)
uv run ruff check --fix && uv run ruff format

# Dependencies
uv add package-name          # runtime
uv add --dev package-name    # dev
uv lock --upgrade            # upgrade all
```

## Architecture

The app uses the Flask application-factory pattern: `create_app()` in
`app/__init__.py` loads `Config` (from `config.py`, which reads `.env`), loads
the LLM settings into `app.config["LLM"]`, registers the `routes` blueprint,
and initializes the database.

The LLM provider (`anthropic` or `openai`), its API key, and model are read by
`app/llm_settings.py` from an XDG config file,
`$XDG_CONFIG_HOME/flask-chatbot/config.toml` (default
`~/.config/flask-chatbot/config.toml`; see `config.example.toml`). Keys fall
back to `ANTHROPIC_API_KEY` / `OPENAI_API_KEY`. Tests set `XDG_CONFIG_HOME` to
a temporary directory (autouse fixture in `tests/conftest.py`).

Request flow for a chat message:

1. `GET /chat` in `app/routes.py` appends the user query to the conversation
   history and returns a Server-Sent-Events stream (`text/event-stream`).
   The frontend (`app/templates/index.html`) consumes these events.
1. `get_chat_completion()` of the configured `ChatClient` runs an agentic
   loop: it yields `ChatResponse` (text for the UI) and `ToolCallResponse`
   (tool-call notifications) dataclasses, executes tool calls via
   `run_tool()`, which dispatches to `SpotifyClient`, appends to the history,
   and loops (at most `MAX_TOOL_ROUNDS` times) until the model produces a final
   text response. Provider-neutral parts (system prompt, `TOOL_SPECS`,
   `run_tool`, response dataclasses, the `ChatClient` protocol) live in
   `app/chat.py`. Implementations:
   - `AnthropicChatClient` (`app/anthropic_chat_client.py`): Claude
     **Messages API** via `client.beta.messages.create` (beta for server-side
     refusal fallbacks). Thinking blocks must be stored and passed back
     unchanged, and the history must stay append-only (no edits to earlier
     messages, the system prompt, or the tool list).
   - `OpenAIChatClient` (`app/openai_chat_client.py`): **OpenAI Responses
     API** (`client.responses.create`, not Chat Completions).
1. `SpotifyClient` (`app/spotify_client.py`) wraps `spotipy` and handles
   pagination; it returns plain dicts/lists that are stringified into tool
   outputs.

State handling:

- Conversation histories (in the provider's own message format) are
  JSON-serialized into a SQLite `conversation` table (`app/database.py`,
  `app/schema.sql`), keyed by a UUID stored in the Flask session. The session
  also records the provider; switching providers starts a new conversation.
  `visible_messages()` extracts the displayable text from either format.
- Spotify OAuth tokens are cached per session in `.spotify_cache/<uuid>`
  files; the OAuth flow lives in the `/spotify/login` and `/spotify/callback`
  routes.

## Guidelines

- All tests go in `tests/`; `pytest` is used exclusively (fixtures in
  `tests/conftest.py` provide `app` and `client`).
- Always use Python type annotations. If that is not possible for some
  reason, state this explicitly and ask for permission to omit them.
- When asked to make a plan, never change any files yet — research, then
  state the plan, explicitly mentioning which files you would edit.

## Development Process

Always use this order, both for features and bug fixes:

1. If the code and application structure within which to implement a change
   already exist, add a test first, and verify that it fails.
1. Implement the fix.
1. Format the code.
1. Verify that the test passes.
1. Create a local commit but NEVER push anything yourself.

## Git and Commit Conventions

- The main branch is `main`.
- Use backticks for code in commit messages.
- First line of a commit message ≤ 72 characters; all other lines ≤ 100.
- For multiline commit messages, write the message to `commit_message.txt`,
  then commit with `git commit -F commit_message.txt`.
- Never stage AGENTS.md together with code changes. AGENTS.md must always be
  in separate commits that are only about agent instructions.

## AGENTS.md Memory Updates

Whenever the user prefixes a prompt with the hash sign `#`, they want the
instruction memorized in this file — update AGENTS.md accordingly.

## References

- Flask API reference: <https://flask.palletsprojects.com/en/stable/api/>
- Claude tool use (Messages API):
  <https://platform.claude.com/docs/en/agents-and-tools/tool-use/overview>
- OpenAI function calling (Responses API):
  <https://platform.openai.com/docs/guides/function-calling>
