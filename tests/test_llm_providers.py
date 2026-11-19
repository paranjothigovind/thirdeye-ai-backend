"""Unit tests for the LLM provider abstraction, the Claude provider and the factory.

The Anthropic SDK runs for real against an in-process ``httpx2.MockTransport``:
no network access, no API key and no API credits are used.
"""
import json

import anthropic
import httpx2
import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.models import provider_factory
from app.models.anthropic_claude import REFUSAL_FALLBACK_BETA, AnthropicProvider
from app.models.azure_openai import AzureOpenAIClient
from app.models.base import (
    LLMAuthenticationError,
    LLMProvider,
    LLMProviderError,
    LLMRateLimitError,
    LLMRefusalError,
    LLMServiceUnavailableError,
    LLMTimeoutError,
    split_system_messages,
)

TEST_KEY = "sk-ant-test-not-a-real-key"
MODEL = "claude-opus-5-5"

# Required non-LLM settings, so Settings() can be built without a .env file.
BASE_SETTINGS = dict(
    AZURE_OPENAI_ENDPOINT="https://example.openai.azure.com/",
    AZURE_OPENAI_ENDPOINT_CHAT="https://example.openai.azure.com/",
    AZURE_OPENAI_CHAT_API_KEY="azure-test-key",
    AZURE_OPENAI_API_KEY="azure-test-key",
    AZURE_OPENAI_CHAT_DEPLOYMENT="gpt-test",
    AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT="embed-test",
    AZURE_SEARCH_ENDPOINT="https://example.search.windows.net",
    AZURE_SEARCH_KEY="search-test-key",
    AZURE_BLOB_CONNECTION_STRING="UseDevelopmentStorage=true",
)

MESSAGES = [
    {"role": "system", "content": "You are a meditation assistant."},
    {"role": "user", "content": "What is witnessing?"},
]


# --------------------------------------------------------------------------- helpers

def make_settings(**overrides) -> Settings:
    return Settings(_env_file=None, **{**BASE_SETTINGS, **overrides})


def message_json(text="Witnessing is observing without effort.", stop_reason="end_turn"):
    content = [{"type": "thinking", "thinking": "", "signature": "sig"}]
    if text:
        content.append({"type": "text", "text": text})
    return {
        "id": "msg_test",
        "type": "message",
        "role": "assistant",
        "model": MODEL,
        "content": content,
        "stop_reason": stop_reason,
        "stop_sequence": None,
        "usage": {"input_tokens": 10, "output_tokens": 5},
    }


def sse_body(deltas, stop_reason="end_turn") -> bytes:
    """Anthropic Messages SSE stream: a thinking block, then text deltas."""
    events = [
        ("message_start", {"type": "message_start", "message": {
            "id": "msg_test", "type": "message", "role": "assistant", "model": MODEL,
            "content": [], "stop_reason": None, "stop_sequence": None,
            "usage": {"input_tokens": 10, "output_tokens": 1}}}),
        ("content_block_start", {"type": "content_block_start", "index": 0,
                                 "content_block": {"type": "thinking", "thinking": "", "signature": ""}}),
        ("content_block_delta", {"type": "content_block_delta", "index": 0,
                                 "delta": {"type": "signature_delta", "signature": "sig"}}),
        ("content_block_stop", {"type": "content_block_stop", "index": 0}),
        ("content_block_start", {"type": "content_block_start", "index": 1,
                                 "content_block": {"type": "text", "text": ""}}),
    ]
    for delta in deltas:
        events.append(("content_block_delta", {"type": "content_block_delta", "index": 1,
                                               "delta": {"type": "text_delta", "text": delta}}))
    events += [
        ("content_block_stop", {"type": "content_block_stop", "index": 1}),
        ("message_delta", {"type": "message_delta",
                           "delta": {"stop_reason": stop_reason, "stop_sequence": None},
                           "usage": {"output_tokens": 5}}),
        ("message_stop", {"type": "message_stop"}),
    ]
    return "".join(f"event: {name}\ndata: {json.dumps(data)}\n\n" for name, data in events).encode()


def sse_response(deltas, stop_reason="end_turn") -> httpx2.Response:
    return httpx2.Response(200, headers={"content-type": "text/event-stream"},
                           content=sse_body(deltas, stop_reason))


def error_response(status, error_type, message="error", **headers) -> httpx2.Response:
    return httpx2.Response(status, headers=headers,
                           json={"type": "error", "error": {"type": error_type, "message": message}})


class MockAnthropic:
    """Records requests and replies with a scripted sequence of responses."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.requests = []

    def __call__(self, request):
        self.requests.append(request)
        response = self.responses.pop(0) if len(self.responses) > 1 else self.responses[0]
        if isinstance(response, Exception):
            raise response
        # Fresh copy each time: a consumed response object cannot be served twice.
        return httpx2.Response(response.status_code, headers=response.headers, content=response.content)

    @property
    def last_body(self):
        return json.loads(self.requests[-1].content)


def make_provider(mock: MockAnthropic, **overrides) -> AnthropicProvider:
    kwargs = dict(api_key=TEST_KEY, model=MODEL, max_tokens=1024, timeout=5.0,
                  max_retries=2, effort="medium", refusal_fallback=True)
    kwargs.update(overrides)
    http_client = anthropic.DefaultAsyncHttpxClient(transport=httpx2.MockTransport(mock))
    return AnthropicProvider(http_client=http_client, **kwargs)


async def collect(agen):
    return [chunk async for chunk in agen]


# ----------------------------------------------------------------- initialization

async def test_anthropic_provider_initialization():
    provider = make_provider(MockAnthropic(httpx2.Response(200, json=message_json())))
    assert isinstance(provider, LLMProvider)
    assert provider.name == "anthropic"
    assert provider.model == MODEL
    assert provider.max_tokens == 1024
    await provider.aclose()


def test_anthropic_provider_requires_api_key():
    with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
        AnthropicProvider(api_key="  ", model=MODEL, max_tokens=10, timeout=1, max_retries=0)


def test_settings_reject_anthropic_without_key():
    with pytest.raises(ValidationError, match="ANTHROPIC_API_KEY is not set"):
        make_settings(LLM_PROVIDER="anthropic", ANTHROPIC_API_KEY="")


def test_settings_azure_does_not_require_anthropic_key():
    config = make_settings(LLM_PROVIDER="azure_openai")
    assert config.LLM_PROVIDER == "azure_openai"
    assert config.ANTHROPIC_API_KEY is None


def test_settings_reject_unknown_provider():
    with pytest.raises(ValidationError):
        make_settings(LLM_PROVIDER="gemini")


def test_settings_normalize_provider_and_hide_key():
    config = make_settings(LLM_PROVIDER=" Anthropic ", ANTHROPIC_API_KEY=TEST_KEY)
    assert config.LLM_PROVIDER == "anthropic"
    assert TEST_KEY not in repr(config)
    assert TEST_KEY not in str(config.model_dump())


@pytest.mark.parametrize("overrides", [
    {"ANTHROPIC_MAX_TOKENS": 0},
    {"ANTHROPIC_MAX_RETRIES": -1},
    {"LLM_PROVIDER": "anthropic", "ANTHROPIC_API_KEY": "   "},
])
def test_settings_errors_never_echo_secrets(overrides):
    secret_overrides = {"ANTHROPIC_API_KEY": TEST_KEY, "AZURE_SEARCH_KEY": "search-secret-value"}
    with pytest.raises(ValidationError) as excinfo:
        make_settings(**{**secret_overrides, **overrides})
    message = str(excinfo.value)
    assert TEST_KEY not in message
    assert "search-secret-value" not in message


def test_settings_reject_invalid_effort():
    with pytest.raises(ValidationError, match="ANTHROPIC_EFFORT"):
        make_settings(ANTHROPIC_EFFORT="extreme")


# -------------------------------------------------------------------- generation

async def test_non_streaming_response():
    mock = MockAnthropic(httpx2.Response(200, json=message_json("Observe without effort.")))
    provider = make_provider(mock)

    text = await provider.generate(MESSAGES)

    assert text == "Observe without effort."  # thinking block excluded
    body = mock.last_body
    assert body["model"] == MODEL
    assert body["system"] == "You are a meditation assistant."
    assert body["messages"] == [{"role": "user", "content": "What is witnessing?"}]
    assert body["output_config"] == {"effort": "medium"}
    assert body["fallbacks"] == "default"
    assert "temperature" not in body
    assert "stream" not in body
    assert REFUSAL_FALLBACK_BETA in mock.requests[-1].headers["anthropic-beta"]
    await provider.aclose()


async def test_temperature_is_not_sent_to_claude():
    mock = MockAnthropic(httpx2.Response(200, json=message_json()))
    provider = make_provider(mock, refusal_fallback=False, effort=None)

    await provider.generate(MESSAGES, temperature=0.2, max_tokens=50)

    body = mock.last_body
    assert "temperature" not in body
    assert body["max_tokens"] == 50
    assert "output_config" not in body and "fallbacks" not in body
    assert "anthropic-beta" not in mock.requests[-1].headers
    await provider.aclose()


async def test_streaming_response_yields_real_deltas():
    mock = MockAnthropic(sse_response(["Observe ", "the breath ", "naturally."]))
    provider = make_provider(mock)

    chunks = await collect(provider.stream(MESSAGES))

    assert chunks == ["Observe ", "the breath ", "naturally."]
    assert mock.last_body["stream"] is True
    await provider.aclose()


async def test_generate_response_compatibility_entry_point():
    mock = MockAnthropic(httpx2.Response(200, json=message_json("Full answer.")))
    provider = make_provider(mock)
    assert await collect(provider.generate_response(MESSAGES, stream=False)) == ["Full answer."]

    mock.responses = [sse_response(["a", "b"])]
    assert await collect(provider.generate_response(MESSAGES, stream=True)) == ["a", "b"]
    await provider.aclose()


async def test_streaming_refusal_raises_after_partial_text():
    mock = MockAnthropic(sse_response(["Partial "], stop_reason="refusal"))
    provider = make_provider(mock)

    received = []
    with pytest.raises(LLMRefusalError):
        async for chunk in provider.stream(MESSAGES):
            received.append(chunk)
    assert received == ["Partial "]  # caller is responsible for discarding this
    await provider.aclose()


async def test_non_streaming_refusal_raises():
    mock = MockAnthropic(httpx2.Response(200, json=message_json(None, stop_reason="refusal")))
    provider = make_provider(mock)
    with pytest.raises(LLMRefusalError):
        await provider.generate(MESSAGES)
    await provider.aclose()


async def test_max_tokens_without_text_raises():
    mock = MockAnthropic(httpx2.Response(200, json=message_json(None, stop_reason="max_tokens")))
    provider = make_provider(mock)
    with pytest.raises(LLMProviderError, match="max_tokens"):
        await provider.generate(MESSAGES)
    await provider.aclose()


# ------------------------------------------------------------------------ errors

async def test_authentication_failure_is_not_retried():
    mock = MockAnthropic(error_response(401, "authentication_error", "invalid x-api-key"))
    provider = make_provider(mock)

    with pytest.raises(LLMAuthenticationError) as excinfo:
        await provider.generate(MESSAGES)

    assert len(mock.requests) == 1
    assert excinfo.value.status_code == 401
    assert excinfo.value.retryable is False
    assert TEST_KEY not in str(excinfo.value)
    await provider.aclose()


async def test_rate_limit_retried_then_raised():
    mock = MockAnthropic(error_response(429, "rate_limit_error", "slow down", **{"retry-after-ms": "1"}))
    provider = make_provider(mock, max_retries=2)

    with pytest.raises(LLMRateLimitError) as excinfo:
        await provider.generate(MESSAGES)

    assert len(mock.requests) == 3  # initial attempt + 2 SDK retries
    assert excinfo.value.retryable is True
    await provider.aclose()


async def test_timeout_maps_to_timeout_error():
    mock = MockAnthropic(httpx2.ReadTimeout("timed out"))
    provider = make_provider(mock, max_retries=0)

    with pytest.raises(LLMTimeoutError):
        await provider.generate(MESSAGES)
    await provider.aclose()


async def test_transient_server_error_is_retried_then_succeeds():
    mock = MockAnthropic(
        error_response(500, "api_error", "internal", **{"retry-after-ms": "1"}),
        httpx2.Response(200, json=message_json("Recovered.")),
    )
    provider = make_provider(mock, max_retries=2)

    assert await provider.generate(MESSAGES) == "Recovered."
    assert len(mock.requests) == 2
    await provider.aclose()


async def test_stream_retries_overloaded_before_first_event():
    mock = MockAnthropic(
        error_response(529, "overloaded_error", "Overloaded", **{"retry-after-ms": "1"}),
        sse_response(["ok"]),
    )
    provider = make_provider(mock, max_retries=1)

    assert await collect(provider.stream(MESSAGES)) == ["ok"]
    assert len(mock.requests) == 2
    await provider.aclose()


async def test_persistent_server_error_maps_to_unavailable():
    mock = MockAnthropic(error_response(503, "api_error", "unavailable", **{"retry-after-ms": "1"}))
    provider = make_provider(mock, max_retries=1)
    with pytest.raises(LLMServiceUnavailableError):
        await provider.generate(MESSAGES)
    assert len(mock.requests) == 2
    await provider.aclose()


# ------------------------------------------------------------------- normalization

def test_split_system_messages():
    system, conversation = split_system_messages([
        {"role": "system", "content": "A"},
        {"role": "system", "content": "B"},
        {"role": "user", "content": "q1"},
        {"role": "assistant", "content": "a1"},
        {"role": "user", "content": "q2"},
    ])
    assert system == "A\n\nB"
    assert [m["role"] for m in conversation] == ["user", "assistant", "user"]


@pytest.mark.parametrize("messages", [
    [{"role": "system", "content": "only system"}],
    [{"role": "user", "content": "q"}, {"role": "assistant", "content": "a"}],
    [{"role": "tool", "content": "x"}, {"role": "user", "content": "q"}],
])
def test_split_system_messages_rejects_invalid(messages):
    with pytest.raises(ValueError):
        split_system_messages(messages)


# ------------------------------------------------------------------------ factory

async def test_factory_selects_anthropic():
    config = make_settings(LLM_PROVIDER="anthropic", ANTHROPIC_API_KEY=TEST_KEY,
                           ANTHROPIC_MODEL="claude-sonnet-5-5", ANTHROPIC_EFFORT="low")
    provider = provider_factory.create_llm_provider(config)
    assert isinstance(provider, AnthropicProvider)
    assert provider.model == "claude-sonnet-5-5"
    assert provider.effort == "low"
    await provider.aclose()


def test_factory_selects_azure_openai():
    provider = provider_factory.create_llm_provider(make_settings(LLM_PROVIDER="azure_openai"))
    assert isinstance(provider, AzureOpenAIClient)
    assert isinstance(provider, LLMProvider)
    assert provider.name == "azure_openai"


async def test_factory_reuses_and_closes_shared_provider(monkeypatch):
    config = make_settings(LLM_PROVIDER="anthropic", ANTHROPIC_API_KEY=TEST_KEY)
    monkeypatch.setattr(provider_factory, "app_settings", config)
    monkeypatch.setattr(provider_factory, "_provider", None)

    first = provider_factory.get_llm_provider()
    assert provider_factory.get_llm_provider() is first

    await provider_factory.close_llm_provider()
    assert provider_factory._provider is None
    await provider_factory.close_llm_provider()  # idempotent
