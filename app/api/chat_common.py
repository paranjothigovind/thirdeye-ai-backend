"""Shared request models, response finalization and SSE helpers for chat routes."""
import asyncio
import json
from contextlib import aclosing, suppress
from typing import Any, AsyncIterator, Awaitable, Callable, Dict, Iterator, List, Optional

from pydantic import BaseModel, Field, model_validator

from app.core.config import settings
from app.core.logging import get_logger
from app.rag.citations import strip_source_tags
from app.rag.guardrails import guardrails

logger = get_logger(__name__)

# Client-facing text for generation failures; details are logged server-side only.
GENERATION_ERROR_MESSAGE = "Sorry, a response could not be generated right now. Please try again."


class Message(BaseModel):
    """Chat message"""
    role: str = Field(..., max_length=32, description="Message role: user, assistant, or system")
    content: str = Field(
        ..., max_length=settings.CHAT_MAX_MESSAGE_CHARS, description="Message content"
    )


class LimitedConversation(BaseModel):
    """Base for chat requests: caps message count and total characters."""
    messages: List[Message] = Field(
        ..., max_length=settings.CHAT_MAX_MESSAGES, description="Conversation messages"
    )

    @model_validator(mode="after")
    def check_total_size(self):
        total = sum(len(message.content) for message in self.messages)
        if total > settings.CHAT_MAX_TOTAL_CHARS:
            raise ValueError(
                f"Conversation is too long ({total} characters; maximum {settings.CHAT_MAX_TOTAL_CHARS})"
            )
        return self


def sse_event(payload: Any) -> str:
    return f"data: {json.dumps(payload)}\n\n"


SSE_DONE = "data: [DONE]\n\n"
SSE_KEEPALIVE = ": keep-alive\n\n"


def chunk_text(text: str, size: int = 200) -> Iterator[str]:
    for start in range(0, len(text), size):
        yield text[start:start + size]


def finalize_response(raw_response: str, query_check: Dict[str, Any], request_id: str) -> str:
    """Validate a complete response, strip internal tags and apply disclaimers."""
    response_check = guardrails.check_response(raw_response)
    if response_check["issues"]:
        logger.info(
            f"Response guardrail findings: {response_check['issues']}",
            extra={"request_id": request_id},
        )

    disclaimer_types = []
    if (
        "medical_query" in query_check.get("issues", [])
        or "contains_medical_advice" in response_check["issues"]
    ):
        disclaimer_types.append("medical")
    return guardrails.add_disclaimers(strip_source_tags(raw_response), disclaimer_types)


def approved_chunks(chunks: List[str], raw_response: str, final_response: str) -> Iterator[str]:
    """Split the approved response into SSE chunks.

    Keeps the provider's chunk boundaries when validation only appended text
    (e.g. a disclaimer); otherwise re-chunks the final text.
    """
    if final_response.startswith(raw_response):
        yield from chunks
        suffix = final_response[len(raw_response):]
        if suffix:
            yield suffix
        return
    yield from chunk_text(final_response)


async def emergency_event_stream(message: str) -> AsyncIterator[str]:
    """Emergency response in the standard SSE contract (no model content)."""
    for chunk in chunk_text(message):
        yield sse_event({"chunk": chunk, "type": "content"})
    yield sse_event({"citations": [], "type": "citations"})
    yield SSE_DONE


async def collect_chunks(agen: AsyncIterator[str]) -> List[str]:
    """Consume a generator completely (nothing is sent to the client yet)."""
    chunks: List[str] = []
    async with aclosing(agen) as stream:
        async for chunk in stream:
            if chunk:
                chunks.append(chunk)
    return chunks


async def with_keepalive(
    work: Callable[[], Awaitable[Any]],
    keepalive_seconds: Optional[float] = None,
) -> AsyncIterator[Any]:
    """Run ``work`` while yielding SSE keep-alive comments; finally yield its result.

    Keep-alive lines are SSE comments (``: keep-alive``), which clients ignore,
    so the response stays alive through proxies without sending any content.
    The work task is cancelled if the client disconnects. Exceptions from
    ``work`` propagate to the caller.
    """
    interval = settings.SSE_KEEPALIVE_SECONDS if keepalive_seconds is None else keepalive_seconds
    task = asyncio.create_task(work())
    try:
        while True:
            done, _ = await asyncio.wait({task}, timeout=interval if interval > 0 else None)
            if done:
                break
            yield SSE_KEEPALIVE
        yield task.result()
    finally:
        if not task.done():
            task.cancel()
            with suppress(asyncio.CancelledError, Exception):
                await task
