from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional


DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_MAX_RETRIES = 3
DEFAULT_RATE_LIMIT_QPS = 1.0


class LLMSettingsError(ValueError):
    """Deterministic error for LLM configuration loading."""


def _parse_bool(value: Optional[str]) -> Optional[bool]:
    if value is None:
        return None
    cleaned = value.strip().lower()
    if cleaned in {"1", "true", "t", "yes", "y", "on"}:
        return True
    if cleaned in {"0", "false", "f", "no", "n", "off"}:
        return False
    raise LLMSettingsError(
        "LLM_SETTINGS_ERROR: invalid boolean value for LLM_ENABLED. "
        f"Got {value!r}."
    )


@dataclass(frozen=True)
class LLMSettings:
    api_key: str
    model: str
    timeout_seconds: float
    max_retries: int
    rate_limit_qps: float
    enabled: bool


def load_llm_settings() -> LLMSettings:
    """Load and validate deterministic LLM runtime settings from environment.

    Optional defaults are only applied for timeout/retries/rate-limit.
    """

    api_key = os.getenv("LLM_API_KEY", "").strip()
    model = os.getenv("LLM_MODEL", "").strip()

    # Enabled can be explicitly overridden (LLM_ENABLED) or implicitly inferred
    # from presence of an API key.
    enabled_override = os.getenv("LLM_ENABLED")
    enabled_from_override = _parse_bool(enabled_override)
    enabled = enabled_from_override if enabled_from_override is not None else bool(api_key)

    timeout_raw = os.getenv("LLM_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT_SECONDS))
    max_retries_raw = os.getenv("LLM_MAX_RETRIES", str(DEFAULT_MAX_RETRIES))
    rate_limit_qps_raw = os.getenv(
        "LLM_RATE_LIMIT_QPS", str(DEFAULT_RATE_LIMIT_QPS)
    )

    try:
        timeout_seconds = float(timeout_raw)
    except ValueError as e:
        raise LLMSettingsError(
            "LLM_SETTINGS_ERROR: invalid LLM_TIMEOUT_SECONDS. "
            f"Got {timeout_raw!r}."
        ) from e

    try:
        max_retries = int(max_retries_raw)
    except ValueError as e:
        raise LLMSettingsError(
            "LLM_SETTINGS_ERROR: invalid LLM_MAX_RETRIES. "
            f"Got {max_retries_raw!r}."
        ) from e

    try:
        rate_limit_qps = float(rate_limit_qps_raw)
    except ValueError as e:
        raise LLMSettingsError(
            "LLM_SETTINGS_ERROR: invalid LLM_RATE_LIMIT_QPS. "
            f"Got {rate_limit_qps_raw!r}."
        ) from e

    if timeout_seconds <= 0:
        raise LLMSettingsError(
            "LLM_SETTINGS_ERROR: LLM_TIMEOUT_SECONDS must be > 0."
        )
    if max_retries < 0:
        raise LLMSettingsError(
            "LLM_SETTINGS_ERROR: LLM_MAX_RETRIES must be >= 0."
        )
    if rate_limit_qps <= 0:
        raise LLMSettingsError(
            "LLM_SETTINGS_ERROR: LLM_RATE_LIMIT_QPS must be > 0."
        )

    if enabled and not api_key:
        raise LLMSettingsError(
            "LLM_SETTINGS_ERROR: LLM is enabled but LLM_API_KEY is missing."
        )
    if enabled and not model:
        raise LLMSettingsError(
            "LLM_SETTINGS_ERROR: LLM is enabled but LLM_MODEL is missing."
        )

    return LLMSettings(
        api_key=api_key,
        model=model,
        timeout_seconds=timeout_seconds,
        max_retries=max_retries,
        rate_limit_qps=rate_limit_qps,
        enabled=enabled,
    )

