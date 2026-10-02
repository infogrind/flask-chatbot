from pathlib import Path

import pytest

from app.llm_settings import LLMSettings, config_path, load_llm_settings


def test_config_path_uses_xdg_config_home(tmp_path: Path) -> None:
    env = {"XDG_CONFIG_HOME": str(tmp_path), "HOME": "/home/user"}

    assert config_path(env) == tmp_path / "flask-chatbot" / "config.toml"


def test_config_path_defaults_to_dot_config() -> None:
    env = {"HOME": "/home/user"}

    assert config_path(env) == Path("/home/user/.config/flask-chatbot/config.toml")


def test_config_path_ignores_relative_xdg_config_home() -> None:
    """The XDG spec says relative paths in `XDG_CONFIG_HOME` must be ignored."""
    env = {"XDG_CONFIG_HOME": "relative/dir", "HOME": "/home/user"}

    assert config_path(env) == Path("/home/user/.config/flask-chatbot/config.toml")


def _write(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "config.toml"
    path.write_text(content)
    path.chmod(0o600)
    return path


def test_load_anthropic_settings(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        """
provider = "anthropic"

[anthropic]
api_key = "sk-ant-test"
model = "claude-sonnet-5-5"
effort = "low"
refusal_fallback = false
""",
    )

    settings = load_llm_settings(path, env={})

    assert settings == LLMSettings(
        provider="anthropic",
        api_key="sk-ant-test",
        model="claude-sonnet-5-5",
        effort="low",
        refusal_fallback=False,
    )


def test_anthropic_defaults(tmp_path: Path) -> None:
    path = _write(tmp_path, 'provider = "anthropic"\n')

    settings = load_llm_settings(path, env={})

    assert settings.model == "claude-opus-5-5"
    assert settings.effort == "medium"
    assert settings.refusal_fallback
    assert settings.api_key is None


def test_load_openai_settings(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        """
provider = "openai"

[openai]
api_key = "sk-test"
""",
    )

    settings = load_llm_settings(path, env={})

    assert settings.provider == "openai"
    assert settings.api_key == "sk-test"
    assert settings.model == "gpt-4o-mini"


def test_missing_file_falls_back_to_openai_and_env(tmp_path: Path) -> None:
    """Existing `.env`-based setups keep working without a config file."""
    settings = load_llm_settings(
        tmp_path / "missing.toml", env={"OPENAI_API_KEY": "sk-env"}
    )

    assert settings.provider == "openai"
    assert settings.api_key == "sk-env"


@pytest.mark.parametrize(
    ("provider", "env_var"),
    [("anthropic", "ANTHROPIC_API_KEY"), ("openai", "OPENAI_API_KEY")],
)
def test_api_key_falls_back_to_env(tmp_path: Path, provider: str, env_var: str) -> None:
    path = _write(tmp_path, f'provider = "{provider}"\n')

    settings = load_llm_settings(path, env={env_var: "from-env"})

    assert settings.api_key == "from-env"


def test_config_file_key_takes_precedence_over_env(tmp_path: Path) -> None:
    path = _write(
        tmp_path, 'provider = "anthropic"\n[anthropic]\napi_key = "from-file"\n'
    )

    settings = load_llm_settings(path, env={"ANTHROPIC_API_KEY": "from-env"})

    assert settings.api_key == "from-file"


def test_unknown_provider_is_rejected(tmp_path: Path) -> None:
    path = _write(tmp_path, 'provider = "gemini"\n')

    with pytest.raises(ValueError, match="gemini"):
        load_llm_settings(path, env={})


def test_invalid_effort_is_rejected(tmp_path: Path) -> None:
    path = _write(tmp_path, 'provider = "anthropic"\n[anthropic]\neffort = "extreme"\n')

    with pytest.raises(ValueError, match="extreme"):
        load_llm_settings(path, env={})


def test_world_readable_config_logs_warning(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    path = _write(tmp_path, 'provider = "openai"\n')
    path.chmod(0o644)

    load_llm_settings(path, env={})

    assert "chmod 600" in caplog.text
