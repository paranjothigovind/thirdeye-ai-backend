"""Azure OpenAI generation provider (LangChain ``AzureChatOpenAI``).

Retries for transient failures (connection errors, 408/409/429/5xx) are done
by the openai SDK inside ``AzureChatOpenAI`` (``max_retries``, default 2).
"""
import time
from typing import Any, AsyncIterator, Dict, List, Optional

import openai
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_openai import AzureChatOpenAI

from app.core.config import settings
from app.core.llm_telemetry import LLMCallRecord, record_llm_call
from app.core.logging import get_logger
from app.models.base import (
    ChatMessage,
    estimate_tokens,
    LLMAuthenticationError,
    LLMProvider,
    LLMProviderError,
    LLMRateLimitError,
    LLMServiceUnavailableError,
    LLMTimeoutError,
)

logger = get_logger(__name__)


def map_openai_error(error: openai.APIError) -> LLMProviderError:
    """Translate an openai SDK exception into the provider-neutral hierarchy."""
    status = getattr(error, "status_code", None)
    detail = f"Azure OpenAI {type(error).__name__}"
    if status is not None:
        detail += f" (HTTP {status})"
    kwargs = {"provider": "azure_openai", "status_code": status}
    if isinstance(error, (openai.AuthenticationError, openai.PermissionDeniedError)):
        return LLMAuthenticationError(detail, **kwargs)
    if isinstance(error, openai.RateLimitError):
        return LLMRateLimitError(detail, **kwargs)
    if isinstance(error, openai.APITimeoutError):
        return LLMTimeoutError(detail, **kwargs)
    if isinstance(error, openai.APIConnectionError):
        return LLMServiceUnavailableError(detail, **kwargs)
    if isinstance(error, openai.APIStatusError) and error.status_code >= 500:
        return LLMServiceUnavailableError(detail, **kwargs)
    return LLMProviderError(detail, **kwargs)


class AzureOpenAIClient(LLMProvider):
    """Azure OpenAI client wrapper implementing ``LLMProvider``"""

    name = "azure_openai"

    def __init__(self):
        """Initialize Azure OpenAI client"""
        self.model = settings.AZURE_OPENAI_CHAT_DEPLOYMENT
        self.chat_model = AzureChatOpenAI(
            azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
            api_key=settings.AZURE_OPENAI_CHAT_API_KEY,
            api_version=settings.AZURE_OPENAI_API_VERSION,
            deployment_name=settings.AZURE_OPENAI_CHAT_DEPLOYMENT,
            streaming=True,
        )

    def _model_with(self, temperature: Optional[float], max_tokens: Optional[int]):
        params: Dict[str, Any] = {}
        if temperature is not None:
            params["temperature"] = temperature
        if max_tokens is not None:
            # gpt-5 / o-series deployments reject `max_tokens`; `max_completion_tokens`
            # is accepted by current chat models and API versions
            params["max_completion_tokens"] = max_tokens
        return self.chat_model.bind(**params) if params else self.chat_model

    def _record(self, operation: str) -> LLMCallRecord:
        return LLMCallRecord(provider=self.name, model_requested=self.model, operation=operation)

    @staticmethod
    def _apply_usage(record: LLMCallRecord, message: Any, messages: List[ChatMessage], text: str) -> None:
        """Use provider-reported usage when present, otherwise an estimate."""
        usage = getattr(message, "usage_metadata", None) if message is not None else None
        metadata = getattr(message, "response_metadata", None) or {}
        record.model_served = metadata.get("model_name") or None
        record.stop_reason = metadata.get("finish_reason") or None
        if usage:
            record.input_tokens = usage.get("input_tokens")
            record.output_tokens = usage.get("output_tokens")
            # On Azure/OpenAI, cached tokens are a SUBSET of input_tokens (unlike Anthropic,
            # where they are reported separately), so they must not be added to the total.
            cache_read = (usage.get("input_token_details") or {}).get("cache_read")
            if cache_read:
                record.extra["cached_input_tokens"] = cache_read
        else:
            record.tokens_estimated = True
            record.input_tokens = estimate_tokens("".join(m.get("content", "") for m in messages))
            record.output_tokens = estimate_tokens(text)

    async def generate(
        self,
        messages: List[ChatMessage],
        *,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """Generate a complete response"""
        lc_messages = self._convert_messages(messages)
        record = self._record("generate")
        started = time.perf_counter()
        try:
            try:
                response = await self._model_with(temperature, max_tokens).ainvoke(lc_messages)
            except openai.APIError as error:
                logger.error(f"Error generating response: {type(error).__name__}")
                raise map_openai_error(error) from error
            self._apply_usage(record, response, messages, response.content or "")
            return response.content
        except LLMProviderError as error:
            record.status, record.error_type = "error", type(error).__name__
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
        """Stream response deltas"""
        lc_messages = self._convert_messages(messages)
        record = self._record("stream")
        started = time.perf_counter()
        aggregate = None
        parts: List[str] = []
        completed = False
        try:
            try:
                async for chunk in self._model_with(temperature, max_tokens).astream(lc_messages):
                    aggregate = chunk if aggregate is None else aggregate + chunk
                    if getattr(chunk, "content", None):
                        parts.append(chunk.content)
                        yield chunk.content
            except openai.APIError as error:
                logger.error(f"Error streaming response: {type(error).__name__}")
                raise map_openai_error(error) from error
            self._apply_usage(record, aggregate, messages, "".join(parts))
            completed = True
        except LLMProviderError as error:
            record.status, record.error_type = "error", type(error).__name__
            raise
        finally:
            record.latency_ms = int((time.perf_counter() - started) * 1000)
            if not completed and record.status == "ok":
                record.status = "cancelled"
            await record_llm_call(record)

    async def generate_response_with_context(
        self,
        query: str,
        context: str,
        system_prompt: str,
        stream: bool = True
    ) -> AsyncIterator[str]:
        """Generate response with retrieved context"""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {query}"}
        ]

        async for chunk in self.generate_response(messages, stream):
            yield chunk

    def _convert_messages(self, messages: List[Dict[str, str]]) -> List[BaseMessage]:
        """Convert dict messages to LangChain messages"""
        lc_messages = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            if role == "system":
                lc_messages.append(SystemMessage(content=content))
            elif role == "assistant":
                lc_messages.append(AIMessage(content=content))
            else:
                lc_messages.append(HumanMessage(content=content))

        return lc_messages


# Global client instance
azure_openai_client = AzureOpenAIClient()
