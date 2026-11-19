"""Common contract for LLM generation providers.

The RAG layer talks only to ``LLMProvider``; it never imports a vendor SDK.
Messages use the plain ``{"role": ..., "content": ...}`` dict format with
roles ``system``, ``user`` and ``assistant``.
"""
from abc import ABC, abstractmethod
from contextlib import aclosing
from typing import AsyncIterator, Dict, List, Optional, Tuple

ChatMessage = Dict[str, str]

VALID_ROLES = ("system", "user", "assistant")


class LLMProviderError(Exception):
    """Base class for generation failures, normalized across providers.

    Messages are written for server logs. They never contain credentials, and API
    routes must not forward them to clients verbatim.
    """

    retryable: bool = False

    def __init__(self, message: str, *, provider: str = "", status_code: Optional[int] = None):
        super().__init__(message)
        self.provider = provider
        self.status_code = status_code


class LLMAuthenticationError(LLMProviderError):
    """Credentials rejected or lacking permission (not retryable)."""


class LLMRateLimitError(LLMProviderError):
    """Provider rate limit still exceeded after the SDK's retries."""

    retryable = True


class LLMTimeoutError(LLMProviderError):
    """Request timed out after the SDK's retries."""

    retryable = True


class LLMServiceUnavailableError(LLMProviderError):
    """Connection failure or provider 5xx/overloaded after the SDK's retries."""

    retryable = True


class LLMRefusalError(LLMProviderError):
    """The model declined to answer (any partial output must be discarded)."""


def estimate_tokens(text: str) -> int:
    """Rough token estimate (about 4 characters per token) for budget accounting
    when a provider does not report usage."""
    return max(1, len(text) // 4) if text else 0


def split_system_messages(messages: List[ChatMessage]) -> Tuple[Optional[str], List[ChatMessage]]:
    """Separate system instructions from the user/assistant conversation.

    Multiple system messages are joined in order. Raises ``ValueError`` for an
    unknown role, an empty conversation, or one that does not end with a user turn.
    """
    system_parts: List[str] = []
    conversation: List[ChatMessage] = []
    for message in messages:
        role = message.get("role")
        content = message.get("content") or ""
        if role not in VALID_ROLES:
            raise ValueError(f"Unsupported message role: {role!r}")
        if role == "system":
            if content.strip():
                system_parts.append(content)
        else:
            conversation.append({"role": role, "content": content})

    if not conversation:
        raise ValueError("At least one user message is required")
    if conversation[-1]["role"] != "user":
        raise ValueError("The final message must have role 'user'")

    system = "\n\n".join(system_parts) if system_parts else None
    return system, conversation


class LLMProvider(ABC):
    """Interface implemented by every generation provider."""

    name: str = "base"
    model: str = ""

    @abstractmethod
    async def generate(
        self,
        messages: List[ChatMessage],
        *,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """Return the complete response text."""

    @abstractmethod
    def stream(
        self,
        messages: List[ChatMessage],
        *,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> AsyncIterator[str]:
        """Yield response text deltas as the provider produces them."""

    async def generate_response(
        self,
        messages: List[ChatMessage],
        stream: bool = True,
    ) -> AsyncIterator[str]:
        """Backward-compatible entry point used by the RAG chains and graph.

        ``stream=True`` yields provider deltas; ``stream=False`` yields the full
        response as a single chunk.
        """
        if stream:
            async with aclosing(self.stream(messages)) as chunks:
                async for chunk in chunks:
                    yield chunk
        else:
            yield await self.generate(messages)

    async def aclose(self) -> None:
        """Release network resources. Safe to call more than once."""
        return None
