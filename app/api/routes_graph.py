"""LangGraph-based chat endpoint"""
from fastapi import APIRouter, Header, HTTPException, Request, status
from pydantic import BaseModel, Field
from typing import List, Optional
import uuid

from app.api.chat_common import (
    GENERATION_ERROR_MESSAGE,
    LimitedConversation,
    Message,  # noqa: F401 - re-exported request model
    finalize_response,
)
from app.core.logging import get_logger
from app.core.usage import enforce_chat_limits
from app.rag.citations import validate_citations
from app.rag.graph import rag_graph
from app.rag.conversation import split_conversation
from app.rag.guardrails import guardrails

logger = get_logger(__name__)

router = APIRouter()


class GraphChatRequest(LimitedConversation):
    """Graph-based chat request"""
    thread_id: Optional[str] = Field(None, max_length=128, description="Thread ID for stateful conversation")


class GraphChatResponse(BaseModel):
    """Graph-based chat response"""
    response: str
    citations: List[dict]
    thread_id: str
    retry_count: int


@router.post("/chat/graph", response_model=GraphChatResponse)
async def chat_with_graph(
    request: GraphChatRequest,
    http_request: Request,
    x_session_id: Optional[str] = Header(None, alias="X-Session-ID"),
):
    """
    Chat endpoint using LangGraph for stateful conversations with corrective loops

    This endpoint uses a more advanced RAG pipeline with:
    - Query rewriting for better retrieval
    - Retrieval quality checks with retry logic
    - Response quality checks with corrective generation
    - Sources attached from the retrieved documents
    """
    thread_id = request.thread_id or str(uuid.uuid4())
    request_id = str(uuid.uuid4())

    try:
        # Get the last user message
        user_messages = [msg for msg in request.messages if msg.role == "user"]
        if not user_messages:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No user message found"
            )

        # Current question + prior user/assistant turns from this request only
        query, history = split_conversation(request.messages)

        # Emergency takes priority: no model call, never rate-limited
        query_check = guardrails.check_query(query)
        if "emergency" in query_check.get("issues", []):
            return GraphChatResponse(
                response=guardrails.handle_emergency(),
                citations=[],
                thread_id=thread_id,
                retry_count=0,
            )

        # Usage limits (429) before any model call
        await enforce_chat_limits(http_request, request_id, x_session_id or request.thread_id)

        # Invoke graph
        result = await rag_graph.invoke(query, thread_id=thread_id, history=history)

        documents = result.get("documents", [])
        return GraphChatResponse(
            response=finalize_response(result.get("response", ""), query_check, request_id),
            citations=validate_citations(result.get("citations", []), documents),
            thread_id=thread_id,
            retry_count=result.get("retry_count", 0)
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in graph chat endpoint: {type(e).__name__}: {e}", extra={"request_id": request_id})
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=GENERATION_ERROR_MESSAGE
        )
