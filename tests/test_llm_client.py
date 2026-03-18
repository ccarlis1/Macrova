from unittest.mock import Mock, patch

import pytest

from src.config.llm_settings import LLMSettings
from src.llm.client import (
    LLMClient,
    LLMInternalError,
    LLMRateLimitError,
    LLMResponseFormatError,
)


class DummyResponse:
    def __init__(self, status_code: int, json_payload=None, json_raises: bool = False):
        self.status_code = status_code
        self._json_payload = json_payload if json_payload is not None else {}
        self._json_raises = json_raises

    def json(self):
        if self._json_raises:
            raise ValueError("not json")
        return self._json_payload


def test_generate_json_parses_valid_json():
    settings = LLMSettings(
        api_key="TEST_API_KEY",
        model="test-model",
        timeout_seconds=5.0,
        max_retries=2,
        rate_limit_qps=1000.0,
        enabled=True,
    )
    session = Mock()
    session.post.return_value = DummyResponse(
        200,
        {
            "choices": [{"message": {"content": '{"a": 1}'}}],
        },
    )

    client = LLMClient(settings, base_url="http://example.com", session=session)
    result = client.generate_json(
        system_prompt="system",
        user_prompt="user",
        schema_name="RecipeDraft",
    )
    assert result == {"a": 1}
    assert session.post.call_count == 1


def test_generate_json_retries_on_429_then_succeeds():
    settings = LLMSettings(
        api_key="TEST_API_KEY",
        model="test-model",
        timeout_seconds=5.0,
        max_retries=2,
        rate_limit_qps=1000.0,
        enabled=True,
    )

    session = Mock()
    session.post.side_effect = [
        DummyResponse(429),
        DummyResponse(200, {"choices": [{"message": {"content": '{"ok": true}'}}]}),
    ]

    client = LLMClient(settings, base_url="http://example.com", session=session)
    with patch("src.llm.client.time.sleep") as sleep_mock:
        result = client.generate_json(
            system_prompt="system",
            user_prompt="user",
            schema_name="RecipeDraft",
        )

    assert result == {"ok": True}
    assert session.post.call_count == 2
    assert sleep_mock.call_count >= 1


def test_generate_json_fails_after_max_retries_on_5xx():
    settings = LLMSettings(
        api_key="TEST_API_KEY",
        model="test-model",
        timeout_seconds=5.0,
        max_retries=1,
        rate_limit_qps=1000.0,
        enabled=True,
    )

    session = Mock()
    session.post.return_value = DummyResponse(500, {"any": "thing"})

    client = LLMClient(settings, base_url="http://example.com", session=session)
    with patch("src.llm.client.time.sleep"):
        with pytest.raises(LLMInternalError) as exc:
            client.generate_json(
                system_prompt="system",
                user_prompt="user",
                schema_name="RecipeDraft",
            )

    assert exc.value.error_code == "MAX_RETRIES_EXCEEDED_SERVER_ERROR"
    assert session.post.call_count == 2


def test_generate_json_rejects_non_json_output():
    settings = LLMSettings(
        api_key="TEST_API_KEY",
        model="test-model",
        timeout_seconds=5.0,
        max_retries=2,
        rate_limit_qps=1000.0,
        enabled=True,
    )

    session = Mock()
    session.post.return_value = DummyResponse(
        200,
        {"choices": [{"message": {"content": "not json"}}]},
    )

    client = LLMClient(settings, base_url="http://example.com", session=session)
    with pytest.raises(LLMResponseFormatError) as exc:
        client.generate_json(
            system_prompt="system",
            user_prompt="user",
            schema_name="RecipeDraft",
        )

    assert exc.value.error_code == "RESPONSE_NOT_VALID_JSON"
    assert session.post.call_count == 1


def test_rate_limit_error_after_retries():
    settings = LLMSettings(
        api_key="TEST_API_KEY",
        model="test-model",
        timeout_seconds=5.0,
        max_retries=1,
        rate_limit_qps=1000.0,
        enabled=True,
    )

    session = Mock()
    session.post.return_value = DummyResponse(429)

    client = LLMClient(settings, base_url="http://example.com", session=session)
    with patch("src.llm.client.time.sleep"):
        with pytest.raises(LLMRateLimitError) as exc:
            client.generate_json(
                system_prompt="system",
                user_prompt="user",
                schema_name="RecipeDraft",
            )

    assert exc.value.error_code == "MAX_RETRIES_EXCEEDED_RATE_LIMIT"
    assert session.post.call_count == 2

