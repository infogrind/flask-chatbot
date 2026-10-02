"""Selection of the LLM provider, read from an XDG config file.

The file lives at `$XDG_CONFIG_HOME/flask-chatbot/config.toml` (by default
`~/.config/flask-chatbot/config.toml`); see `config.example.toml`.
"""

import logging
import os
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, get_args

logger = logging.getLogger(__name__)

Provider = Literal["anthropic", "openai"]
Effort = Literal["low", "medium", "high", "xhigh", "max"]

APP_NAME = "flask-chatbot"
DEFAULT_PROVIDER: Provider = "openai"
DEFAULT_MODELS: dict[Provider, str] = {
    "anthropic": "claude-opus-5-5",
    "openai": "gpt-4o-mini",
}
DEFAULT_EFFORT: Effort = "medium"
API_KEY_ENV_VARS: dict[Provider, str] = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
}


@dataclass(frozen=True)
class LLMSettings:
    provider: Provider
    # `None` lets the Anthropic SDK resolve credentials itself (env, `ant` profile).
    api_key: str | None
    model: str
    # Anthropic only: how much the model thinks, and with it cost and latency.
    effort: Effort = DEFAULT_EFFORT
    # Anthropic only: retry safety-classifier refusals on a fallback model.
    refusal_fallback: bool = True


def config_path(env: Mapping[str, str] = os.environ) -> Path:
    """Returns the config file path according to the XDG Base Directory spec."""
    xdg_config_home = env.get("XDG_CONFIG_HOME", "")
    # The spec requires ignoring relative paths
    if xdg_config_home and Path(xdg_config_home).is_absolute():
        base = Path(xdg_config_home)
    else:
        base = Path(env.get("HOME", Path.home())) / ".config"
    return base / APP_NAME / "config.toml"


def _read_config(path: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as f:
            data = tomllib.load(f)
    except FileNotFoundError:
        logger.info("No config file at %s, using defaults", path)
        return {}
    if path.stat().st_mode & 0o077:
        logger.warning(
            "%s contains API keys but is readable by other users; run `chmod 600 %s`",
            path,
            path,
        )
    return data


def load_llm_settings(
    path: Path | None = None, env: Mapping[str, str] = os.environ
) -> LLMSettings:
    """Loads the LLM settings; API keys fall back to the provider's env var."""
    path = path or config_path(env)
    data = _read_config(path)

    provider = data.get("provider", DEFAULT_PROVIDER)
    if provider not in get_args(Provider):
        raise ValueError(
            f"{path}: unknown provider {provider!r}, "
            f"expected one of {', '.join(get_args(Provider))}"
        )
    section: dict[str, Any] = data.get(provider, {})

    effort = section.get("effort", DEFAULT_EFFORT)
    if effort not in get_args(Effort):
        raise ValueError(
            f"{path}: unknown effort {effort!r}, "
            f"expected one of {', '.join(get_args(Effort))}"
        )

    return LLMSettings(
        provider=provider,
        api_key=section.get("api_key") or env.get(API_KEY_ENV_VARS[provider]),
        model=section.get("model", DEFAULT_MODELS[provider]),
        effort=effort,
        refusal_fallback=section.get("refusal_fallback", True),
    )
