from __future__ import annotations

import json
import os
import time
from threading import Lock
from typing import Any, Dict, Optional

import requests

from src.config.llm_settings import LLMSettings


class LLMClientError(Exception):
    """Structured LLM client error with deterministic error_code."""

    def __init__(
        self,
        *,
        error_code: str,
        message: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.details = details or {}


class LLMTimeoutError(LLMClientError):
    pass


class LLMRateLimitError(LLMClientError):
    pass


class LLMResponseFormatError(LLMClientError):
    pass


class LLMInternalError(LLMClientError):
    pass


class LLMClient:
    """LLM API wrapper that guarantees JSON-only outputs.

    The wrapper is intentionally provider-agnostic, but it defaults to an
    OpenAI-compatible Chat Completions endpoint.
    """

    def __init__(
        self,
        settings: LLMSettings,
        *,
        base_url: Optional[str] = None,
        session: Optional[requests.Session] = None,
    ) -> None:
        self._settings = settings
        self._base_url = base_url or os.getenv(
            "LLM_BASE_URL",
            "https://api.openai.com/v1/chat/completions",
        )
        self._session = session or requests.Session()

        # Last assistant `message.content` string from the provider (debug / diagnostics).
        # Set on each successful completion parse path; not part of the public contract.
        self._last_model_content_text: Optional[str] = None

        # Simple deterministic rate limiter (min interval between calls).
        self._rate_lock = Lock()
        self._min_interval_seconds = 1.0 / self._settings.rate_limit_qps
        self._last_request_monotonic = 0.0
        self._backoff_base_seconds = 0.5

    def generate_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        schema_name: str,
        temperature: float = 0.0,
    ) -> Dict[str, Any]:
        """Generate JSON that can be parsed into a strict schema later."""

        if not self._settings.enabled:
            raise LLMInternalError(
                error_code="LLM_DISABLED",
                message="LLM client called while LLM is disabled in settings.",
            )

        # Include schema_name in the prompt as a contract hint for the model.
        user_prompt_with_schema = (
            f"{user_prompt}\n\n"
            f"Respond with a JSON object matching the schema name: {schema_name}."
        )

        payload: Dict[str, Any] = {
            "model": self._settings.model,
            "temperature": float(temperature),
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt_with_schema},
            ],
        }

        return self._request_with_retry(payload)

    def _apply_rate_limit(self) -> None:
        with self._rate_lock:
            now = time.monotonic()
            wait_seconds = (self._last_request_monotonic + self._min_interval_seconds) - now
            if wait_seconds > 0:
                time.sleep(wait_seconds)
            self._last_request_monotonic = time.monotonic()

    def _sleep_backoff(self, attempt: int) -> None:
        # Exponential backoff: base * 2^attempt.
        time.sleep(self._backoff_base_seconds * (2**attempt))

    def _extract_model_text(self, response_json: Dict[str, Any]) -> str:
        # OpenAI-compatible response: choices[0].message.content
        if "choices" in response_json and response_json["choices"]:
            choice0 = response_json["choices"][0]
            message = choice0.get("message") or {}
            content = message.get("content")
            if isinstance(content, str):
                return content

        # Fallbacks for other simple providers.
        if isinstance(response_json.get("content"), str):
            return response_json["content"]
        if isinstance(response_json.get("text"), str):
            return response_json["text"]

        raise LLMResponseFormatError(
            error_code="RESPONSE_MISSING_CONTENT",
            message="LLM response did not contain a JSON string content field.",
            details={"response_json_keys": sorted(response_json.keys())},
        )

    def _parse_content_json_object(self, content: Any) -> Dict[str, Any]:
        if isinstance(content, dict):
            return content
        if not isinstance(content, str):
            raise LLMResponseFormatError(
                error_code="RESPONSE_JSON_NOT_STRING",
                message="LLM content was not a string or dict.",
            )
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as e:
            raise LLMResponseFormatError(
                error_code="RESPONSE_NOT_VALID_JSON",
                message="LLM output was not valid JSON.",
            ) from e

        if not isinstance(parsed, dict):
            raise LLMResponseFormatError(
                error_code="RESPONSE_JSON_NOT_OBJECT",
                message="LLM output JSON must be an object.",
            )
        return parsed

    def _request_with_retry(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self._settings.api_key}",
            "Content-Type": "application/json",
        }

        transient_attempts = self._settings.max_retries
        last_transient_status: Optional[int] = None

        for attempt in range(transient_attempts + 1):
            self._apply_rate_limit()
            try:
                resp = self._session.post(
                    self._base_url,
                    headers=headers,
                    json=payload,
                    timeout=self._settings.timeout_seconds,
                )
            except requests.Timeout as e:
                if attempt >= transient_attempts:
                    raise LLMTimeoutError(
                        error_code="TIMEOUT_MAX_RETRIES_EXCEEDED",
                        message="LLM request timed out.",
                    ) from e
                self._sleep_backoff(attempt)
                continue
            except requests.RequestException as e:
                # Only 429/5xx are specified for retries; other request errors are non-retryable.
                raise LLMInternalError(
                    error_code="REQUEST_EXCEPTION",
                    message="LLM request failed.",
                ) from e

            if resp.status_code == 429 or 500 <= resp.status_code <= 599:
                last_transient_status = resp.status_code
                if attempt >= transient_attempts:
                    if resp.status_code == 429:
                        raise LLMRateLimitError(
                            error_code="MAX_RETRIES_EXCEEDED_RATE_LIMIT",
                            message="LLM rate limit exceeded after retries.",
                            details={"status_code": resp.status_code},
                        )
                    raise LLMInternalError(
                        error_code="MAX_RETRIES_EXCEEDED_SERVER_ERROR",
                        message="LLM server error exceeded retry cap.",
                        details={"status_code": resp.status_code},
                    )

                self._sleep_backoff(attempt)
                continue

            if not (200 <= resp.status_code <= 299):
                raise LLMInternalError(
                    error_code=f"HTTP_{resp.status_code}",
                    message=f"LLM request failed with status {resp.status_code}.",
                    details={"status_code": resp.status_code},
                )

            try:
                response_json = resp.json()
            except Exception as e:
                raise LLMResponseFormatError(
                    error_code="RESPONSE_NOT_JSON",
                    message="LLM HTTP response was not JSON.",
                ) from e

            content_text = self._extract_model_text(response_json)
            self._last_model_content_text = content_text
            return self._parse_content_json_object(content_text)

        # Should be unreachable due to the for-loop exhaustion logic.
        raise LLMInternalError(
            error_code="UNREACHABLE_RETRY_LOOP",
            message="LLM retry loop exited unexpectedly.",
            details={"last_transient_status": last_transient_status},
        )

