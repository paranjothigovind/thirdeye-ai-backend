"""Chat endpoints"""
from fastapi import APIRouter, Header, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional
import asyncio
import uuid

from app.api.chat_common import (
    GENERATION_ERROR_MESSAGE,
    SSE_DONE,
    SSE_KEEPALIVE,
    LimitedConversation,
    Message,  # noqa: F401 - re-exported request model
    approved_chunks,
    collect_chunks,
    emergency_event_stream,
    finalize_response,
    sse_event,
    with_keepalive,
)
from app.core.logging import get_logger
from app.core.usage import current_usage, enforce_chat_limits
from app.rag.chains import rag_chain
from app.rag.citations import build_citations
from app.rag.conversation import split_conversation
from app.rag.guardrails import guardrails
from app.rag.course_class_agent import course_class_agent
from app.rag.post_class_support_agent import post_class_support_agent

logger = get_logger(__name__)

router = APIRouter()

SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}


class ChatRequest(LimitedConversation):
    """Chat request"""
    persona: Optional[str] = Field(None, max_length=64, description="Optional persona: teacher, student, etc.")
    stream: bool = Field(True, description="Enable streaming responses")


class Citation(BaseModel):
    """Source reference (a document retrieved and supplied to the model)"""
    title: str
    reference: str


class ChatResponse(BaseModel):
    """Chat response (non-streaming)"""
    response: str
    citations: List[Citation]
    request_id: str


def _select_agent(persona: Optional[str]) -> Any:
    agent = rag_chain  # Default to standard RAG chain
    if persona:
        persona_lower = persona.lower()
        if "course" in persona_lower or "class" in persona_lower:
            agent = course_class_agent
        elif "post" in persona_lower or "support" in persona_lower:
            agent = post_class_support_agent
    return agent


async def _generate_approved(
    agent: Any,
    query: str,
    history: List[Dict[str, str]],
    query_check: Dict[str, Any],
    request_id: str,
    stream: bool,
):
    """Run the agent to completion, validate, and build Sources (nothing sent yet)."""
    sources: List[Dict[str, Any]] = []
    chunks = await collect_chunks(agent.invoke(query, stream=stream, history=history, sources=sources))
    raw_response = "".join(chunks)
    final_response = finalize_response(raw_response, query_check, request_id)
    return chunks, raw_response, final_response, build_citations(sources)


@router.post("/chat")
async def chat(
    request: ChatRequest,
    http_request: Request,
    x_session_id: Optional[str] = Header(None, alias="X-Session-ID"),
):
    """Chat endpoint with streaming support"""
    request_id = str(uuid.uuid4())

    try:
        # Get the last user message
        user_messages = [msg for msg in request.messages if msg.role == "user"]
        if not user_messages:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No user message found"
            )

        # Current question + prior turns from this request only (client system
        # messages are dropped so they cannot override the application prompt)
        query, history = split_conversation(request.messages)

        # Check query safety
        query_check = guardrails.check_query(query)

        # Emergency takes priority: no model call, never rate-limited
        if "emergency" in query_check.get("issues", []):
            emergency_response = guardrails.handle_emergency()
            if request.stream:
                return StreamingResponse(
                    emergency_event_stream(emergency_response),
                    media_type="text/event-stream",
                    headers={**SSE_HEADERS, "X-Request-ID": request_id},
                )
            return ChatResponse(
                response=emergency_response,
                citations=[],
                request_id=request_id
            )

        # Usage limits (429) before any model call
        usage_ctx = await enforce_chat_limits(http_request, request_id, x_session_id)

        agent = _select_agent(request.persona)

        # Stream response
        if request.stream:
            async def generate():
                # The provider stream is consumed in full and validated before any
                # content is sent, so unvalidated or later-refused text never
                # reaches the client. Keep-alive comments hold the connection open
                # meanwhile; the approved text is then emitted using the same SSE
                # event contract as before.
                current_usage.set(usage_ctx)
                result = None
                try:
                    async for item in with_keepalive(
                        lambda: _generate_approved(agent, query, history, query_check, request_id, True)
                    ):
                        if item is SSE_KEEPALIVE:
                            yield item
                        else:
                            result = item
                except asyncio.CancelledError:
                    logger.info("Client disconnected during generation", extra={"request_id": request_id})
                    raise
                except Exception as e:
                    logger.error(
                        f"Error in streaming: {type(e).__name__}: {e}",
                        extra={"request_id": request_id},
                    )
                    yield sse_event({"error": GENERATION_ERROR_MESSAGE, "type": "error", "request_id": request_id})
                    return

                chunks, raw_response, full_response, citations = result
                for chunk in approved_chunks(chunks, raw_response, full_response):
                    yield sse_event({"chunk": chunk, "type": "content"})

                yield sse_event({"citations": citations, "type": "citations"})
                yield SSE_DONE

            return StreamingResponse(
                generate(),
                media_type="text/event-stream",
                headers={**SSE_HEADERS, "X-Request-ID": request_id},
            )

        # Non-streaming response
        else:
            _, _, full_response, citations = await _generate_approved(
                agent, query, history, query_check, request_id, False
            )

            return ChatResponse(
                response=full_response,
                citations=[Citation(**c) for c in citations],
                request_id=request_id
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in chat endpoint: {type(e).__name__}: {e}", extra={"request_id": request_id})
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"{GENERATION_ERROR_MESSAGE} (request_id: {request_id})"
        )
