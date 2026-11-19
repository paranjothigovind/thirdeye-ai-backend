"""Anthropic Claude generation provider (official ``anthropic`` SDK, async client).

Retries and timeouts are handled by the SDK: connection errors, 408, 409, 429
and 5xx are retried with exponential backoff (honouring ``retry-after``) up to
``max_retries`` times. A stream is retried only if it fails before the first
event; a failure mid-stream is surfaced, never replayed.

Sampling parameters (``temperature``/``top_p``/``top_k``) are not sent: current
Claude models and API version 2026-10-21 (sent by SDK 2.x) reject them.

Refusal fallback (server-side ``fallbacks``, beta): a decline before any output
is transparently served by the fallback model. A decline after partial output
is treated as a refusal here: the stream raises ``LLMRefusalError`` so callers
discard everything already produced.
"""
import time
from typing import Any, AsyncIterator, Dict, List, Optional, Tuple

import anthropic

from app.core.llm_telemetry import LLMCallRecord, record_llm_call
from app.core.logging import get_logger
from app.models.base import (
    ChatMessage,
    LLMAuthenticationError,
    LLMProvider,
    LLMProviderError,
    LLMRateLimitError,
    LLMRefusalError,
    LLMServiceUnavailableError,
    LLMTimeoutError,
    split_system_messages,
)

logger = get_logger(__name__)

REFUSAL_FALLBACK_BETA = "server-side-fallback-2026-07-01"

_ALL_EFFORT = frozenset({"low", "medium", "high", "xhigh", "max"})
_EFFORT_NO_XHIGH = frozenset({"low", "medium", "high", "max"})

# Claude model compatibility for the request parameters this provider sends.
#   effort: accepted output_config.effort values (empty = parameter not supported)
#   refusal_fallback: server-side `fallbacks` is documented for this model
# Models not listed are sent as configured, with a startup warning.
CLAUDE_MODEL_CAPABILITIES: Dict[str, Dict[str, Any]] = {
    "claude-fable-5-2": {"effort": _ALL_EFFORT, "refusal_fallback": True},
    "claude-mythos-5-2": {"effort": _ALL_EFFORT, "refusal_fallback": True},
    "claude-fable-5-1": {"effort": _ALL_EFFORT, "refusal_fallback": True},
    "claude-mythos-5-1": {"effort": _ALL_EFFORT, "refusal_fallback": True},
    "claude-fable-5": {"effort": _ALL_EFFORT, "refusal_fallback": True},
    "claude-opus-5-5": {"effort": _ALL_EFFORT, "refusal_fallback": True},
    "claude-opus-5": {"effort": _ALL_EFFORT, "refusal_fallback": True},
    "claude-sonnet-5-5": {"effort": _ALL_EFFORT, "refusal_fallback": True},
    "claude-sonnet-5": {"effort": _ALL_EFFORT, "refusal_fallback": False},
    "claude-haiku-5-5": {"effort": _ALL_EFFORT, "refusal_fallback": False},
    "claude-opus-4-8": {"effort": _ALL_EFFORT, "refusal_fallback": False},
    "claude-opus-4-7": {"effort": _ALL_EFFORT, "refusal_fallback": False},
    "claude-opus-4-6": {"effort": _EFFORT_NO_XHIGH, "refusal_fallback": False},
    "claude-sonnet-4-6": {"effort": _EFFORT_NO_XHIGH, "refusal_fallback": False},
    "claude-haiku-4-5": {"effort": frozenset(), "refusal_fallback": False},
}


def resolve_model_features(
    model: str, effort: Optional[str], refusal_fallback: bool
) -> Tuple[Optional[str], bool, List[str]]:
    """Return the (effort, refusal_fallback) actually sent, plus warnings.

    Unsupported settings for a known model are disabled (sending them would make
    every request fail); unknown models keep the configured values.
    """
    warnings: List[str] = []
    capabilities = CLAUDE_MODEL_CAPABILITIES.get(model)
    if capabilities is None:
        warnings.append(
            f"ANTHROPIC_MODEL={model!r} is not in the compatibility matrix; "
            "effort and refusal-fallback settings are sent unverified"
        )
        return effort, refusal_fallback, warnings

    if effort and effort not in capabilities["effort"]:
        warnings.append(
            f"ANTHROPIC_EFFORT={effort!r} is not supported by {model}; the effort parameter is not sent"
        )
        effort = None
    if refusal_fallback and not capabilities["refusal_fallback"]:
        warnings.append(
            f"Server-side refusal fallback is not documented for {model}; it is disabled "
            "(refusals return the safe error response)"
        )
        refusal_fallback = False
    return effort, refusal_fallback, warnings


def map_anthropic_error(error: anthropic.APIError) -> LLMProviderError:
    """Translate an SDK exception into the provider-neutral hierarchy.

    The provider's error text is not included (it is not needed for operations
    and must never risk carrying request content into logs).
    """
    status = getattr(error, "status_code", None)
    request_id = getattr(error, "request_id", None)
    body = getattr(error, "body", None)
    error_type = None
    if isinstance(body, dict) and isinstance(body.get("error"), dict):
        error_type = body["error"].get("type")

    detail = f"Anthropic {type(error).__name__}"
    if status is not None:
        detail += f" (HTTP {status})"
    if error_type:
        detail += f" type={error_type}"
    if request_id:
        detail += f" request_id={request_id}"

    kwargs = {"provider": "anthropic", "status_code": status}
    if isinstance(error, (anthropic.AuthenticationError, anthropic.PermissionDeniedError)):
        return LLMAuthenticationError(detail, **kwargs)
    if isinstance(error, anthropic.RateLimitError):
        return LLMRateLimitError(detail, **kwargs)
    if isinstance(error, anthropic.APITimeoutError):
        return LLMTimeoutError(detail, **kwargs)
    if isinstance(error, anthropic.APIConnectionError):
        return LLMServiceUnavailableError(detail, **kwargs)
    if isinstance(error, anthropic.APIStatusError) and error.status_code >= 500:
        return LLMServiceUnavailableError(detail, **kwargs)
    return LLMProviderError(detail, **kwargs)


def _apply_usage(record: LLMCallRecord, message: Any) -> None:
    """Copy usage, served model and fallback information from a final message."""
    record.model_served = getattr(message, "model", None)
    record.stop_reason = getattr(message, "stop_reason", None)
    usage = getattr(message, "usage", None)
    if usage is not None:
        record.input_tokens = getattr(usage, "input_tokens", None)
        record.output_tokens = getattr(usage, "output_tokens", None)
        record.cache_creation_input_tokens = getattr(usage, "cache_creation_input_tokens", None)
        record.cache_read_input_tokens = getattr(usage, "cache_read_input_tokens", None)
        for iteration in getattr(usage, "iterations", None) or []:
            if getattr(iteration, "type", None) == "fallback_message":
                record.fallback_used = True
                record.fallback_model = getattr(iteration, "model", None) or record.fallback_model
    for block in getattr(message, "content", None) or []:
        if getattr(block, "type", None) == "fallback":
            record.fallback_used = True
            target = getattr(block, "to", None)
            record.fallback_model = getattr(target, "model", None) or record.fallback_model
    if record.fallback_used and not record.fallback_model:
        record.fallback_model = record.model_served


class AnthropicProvider(LLMProvider):
    """Claude provider implementing ``LLMProvider``."""

    name = "anthropic"

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        max_tokens: int,
        timeout: float,
        max_retries: int,
        effort: Optional[str] = None,
        refusal_fallback: bool = True,
        http_client: Any = None,
    ):
        if not api_key or not api_key.strip():
            raise ValueError("ANTHROPIC_API_KEY is required for the Anthropic provider")
        self.model = model
        self.max_tokens = max_tokens
        self.effort, self.refusal_fallback, warnings = resolve_model_features(
            model, effort or None, refusal_fallback
        )
        for warning in warnings:
            logger.warning(warning)
        client_kwargs: Dict[str, Any] = {
            "api_key": api_key,
            "timeout": timeout,
            "max_retries": max_retries,
        }
        if http_client is not None:
            client_kwargs["http_client"] = http_client
        self._client = anthropic.AsyncAnthropic(**client_kwargs)
        logger.info(
            f"Anthropic provider initialized (model={model}, timeout={timeout}s, "
            f"max_retries={max_retries}, effort={self.effort}, refusal_fallback={self.refusal_fallback})"
        )

    @property
    def _messages(self):
        # Server-side refusal fallbacks are a beta parameter, so they need the beta namespace.
        return self._client.beta.messages if self.refusal_fallback else self._client.messages

    def _request_kwargs(
        self,
        messages: List[ChatMessage],
        temperature: Optional[float],
        max_tokens: Optional[int],
    ) -> Dict[str, Any]:
        system, conversation = split_system_messages(messages)
        if temperature is not None:
            logger.debug("Ignoring temperature for Anthropic: sampling parameters are not accepted")
        kwargs: Dict[str, Any] = {
            "model": self.model,
            "max_tokens": max_tokens or self.max_tokens,
            "messages": conversation,
        }
        if system:
            kwargs["system"] = system
        if self.effort:
            kwargs["output_config"] = {"effort": self.effort}
        if self.refusal_fallback:
            kwargs["betas"] = [REFUSAL_FALLBACK_BETA]
            kwargs["fallbacks"] = "default"
        return kwargs

    def _new_record(self, operation: str) -> LLMCallRecord:
        return LLMCallRecord(provider=self.name, model_requested=self.model, operation=operation)

    def _check_stop_reason(self, message: Any, text: str) -> None:
        stop_reason = getattr(message, "stop_reason", None)
        if stop_reason == "refusal":
            details = getattr(message, "stop_details", None)
            category = getattr(details, "category", None) if details else None
            raise LLMRefusalError(
                f"Claude declined the request (category={category})", provider=self.name
            )
        if stop_reason == "max_tokens":
            if not text.strip():
                raise LLMProviderError(
                    "Claude reached max_tokens before producing any answer text; "
                    "increase ANTHROPIC_MAX_TOKENS",
                    provider=self.name,
                )
            logger.warning(f"Claude response truncated at max_tokens (model={self.model})")

    @staticmethod
    def _finish_error(record: LLMCallRecord, error: Exception) -> None:
        record.error_type = type(error).__name__
        record.status = "refused" if isinstance(error, LLMRefusalError) else "error"

    async def generate(
        self,
        messages: List[ChatMessage],
        *,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        kwargs = self._request_kwargs(messages, temperature, max_tokens)
        record = self._new_record("generate")
        started = time.perf_counter()
        try:
            try:
                response = await self._messages.create(**kwargs)
            except anthropic.APIError as error:
                raise map_anthropic_error(error) from error

            record.provider_request_id = getattr(response, "_request_id", None)
            _apply_usage(record, response)
            # Non-streaming fallback responses already omit any declined partial output.
            text = "".join(block.text for block in response.content if block.type == "text")
            self._check_stop_reason(response, text)
            return text
        except LLMProviderError as error:
            self._finish_error(record, error)
            raise
        finally:
            record.latency_ms = int((time.perf_counter() - started) * 1000)
            await record_llm_call(record)

    async def stream(
        self,
        messages: List[ChatMessage],
        *,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> AsyncIterator[str]:
        kwargs = self._request_kwargs(messages, temperature, max_tokens)
        record = self._new_record("stream")
        started = time.perf_counter()
        parts: List[str] = []
        completed = False
        try:
            try:
                # The context manager closes the HTTP response on completion, error,
                # or cancellation (e.g. client disconnect).
                async with self._messages.stream(**kwargs) as stream:
                    record.provider_request_id = getattr(stream, "request_id", None)
                    async for event in stream:
                        event_type = getattr(event, "type", None)
                        if event_type == "content_block_start":
                            block = getattr(event, "content_block", None)
                            if getattr(block, "type", None) == "fallback":
                                record.fallback_used = True
                                record.fallback_model = getattr(getattr(block, "to", None), "model", None)
                                if parts:
                                    # The declined model already produced text; the
                                    # fallback would continue it. Discard everything.
                                    record.status = "discarded"
                                    raise LLMRefusalError(
                                        "Claude declined mid-response; partial output discarded "
                                        "instead of continuing on the fallback model",
                                        provider=self.name,
                                    )
                        elif event_type == "text":
                            parts.append(event.text)
                            yield event.text
                    final_message = await stream.get_final_message()
            except anthropic.APIError as error:
                raise map_anthropic_error(error) from error

            fallback_seen, fallback_model = record.fallback_used, record.fallback_model
            _apply_usage(record, final_message)
            record.fallback_used = record.fallback_used or fallback_seen
            record.fallback_model = fallback_model or record.fallback_model
            # A refusal can arrive after partial text; raising here tells the caller
            # to discard what it has buffered.
            self._check_stop_reason(final_message, "".join(parts))
            completed = True
        except LLMProviderError as error:
            if record.status != "discarded":
                self._finish_error(record, error)
            else:
                record.error_type = type(error).__name__
            raise
        finally:
            record.latency_ms = int((time.perf_counter() - started) * 1000)
            if not completed and record.status == "ok":
                record.status = "cancelled"
            await record_llm_call(record)

    async def aclose(self) -> None:
        await self._client.close()
