import pytest

from src.config.llm_settings import (
    DEFAULT_MAX_RETRIES,
    DEFAULT_RATE_LIMIT_QPS,
    DEFAULT_TIMEOUT_SECONDS,
    LLMSettingsError,
    load_llm_settings,
)


def test_loads_defaults_when_optional_vars_absent(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "TEST_API_KEY")
    monkeypatch.setenv("LLM_MODEL", "test-model")

    monkeypatch.delenv("LLM_TIMEOUT_SECONDS", raising=False)
    monkeypatch.delenv("LLM_MAX_RETRIES", raising=False)
    monkeypatch.delenv("LLM_RATE_LIMIT_QPS", raising=False)
    monkeypatch.delenv("LLM_ENABLED", raising=False)

    settings = load_llm_settings()

    assert settings.enabled is True
    assert settings.timeout_seconds == DEFAULT_TIMEOUT_SECONDS
    assert settings.max_retries == DEFAULT_MAX_RETRIES
    assert settings.rate_limit_qps == DEFAULT_RATE_LIMIT_QPS


def test_fails_without_api_key_when_enabled(monkeypatch):
    monkeypatch.setenv("LLM_ENABLED", "true")
    monkeypatch.setenv("LLM_MODEL", "test-model")
    monkeypatch.delenv("LLM_API_KEY", raising=False)

    with pytest.raises(LLMSettingsError, match="LLM_API_KEY is missing"):
        load_llm_settings()


@pytest.mark.parametrize(
    "env_key, env_value, match",
    [
        ("LLM_TIMEOUT_SECONDS", "0", "LLM_TIMEOUT_SECONDS must be > 0"),
        ("LLM_TIMEOUT_SECONDS", "-1", "LLM_TIMEOUT_SECONDS must be > 0"),
        ("LLM_MAX_RETRIES", "-1", "LLM_MAX_RETRIES must be >= 0"),
        ("LLM_RATE_LIMIT_QPS", "0", "LLM_RATE_LIMIT_QPS must be > 0"),
    ],
)
def test_validates_numeric_bounds(monkeypatch, env_key, env_value, match):
    monkeypatch.setenv("LLM_API_KEY", "TEST_API_KEY")
    monkeypatch.setenv("LLM_MODEL", "test-model")
    monkeypatch.delenv("LLM_ENABLED", raising=False)

    monkeypatch.setenv(env_key, env_value)

    with pytest.raises(LLMSettingsError, match=match):
        load_llm_settings()

