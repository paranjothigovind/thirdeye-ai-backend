"""LangGraph-based chat endpoint"""
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from typing import List, Optional
import uuid

from app.core.logging import get_logger
from app.rag.graph import rag_graph

logger = get_logger(__name__)

router = APIRouter()


class Message(BaseModel):
    """Chat message"""
    role: str = Field(..., description="Message role: user, assistant, or system")
    content: str = Field(..., description="Message content")


class GraphChatRequest(BaseModel):
    """Graph-based chat request"""
    messages: List[Message] = Field(..., description="Conversation messages")
    thread_id: Optional[str] = Field(None, description="Thread ID for stateful conversation")


class GraphChatResponse(BaseModel):
    """Graph-based chat response"""
    response: str
    citations: List[dict]
    thread_id: str
    retry_count: int


@router.post("/chat/graph", response_model=GraphChatResponse)
async def chat_with_graph(request: GraphChatRequest):
    """
    Chat endpoint using LangGraph for stateful conversations with corrective loops
    
    This endpoint uses a more advanced RAG pipeline with:
    - Query rewriting for better retrieval
    - Retrieval quality checks with retry logic
    - Response quality checks with corrective generation
    - Automatic citation extraction
    """
    thread_id = request.thread_id or str(uuid.uuid4())
    
    try:
        # Get the last user message
        user_messages = [msg for msg in request.messages if msg.role == "user"]
        if not user_messages:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No user message found"
            )
        
        query = user_messages[-1].content
        
        # Invoke graph
        result = await rag_graph.invoke(query, thread_id=thread_id)
        
        return GraphChatResponse(
            response=result.get("response", ""),
            citations=result.get("citations", []),
            thread_id=thread_id,
            retry_count=result.get("retry_count", 0)
        )
    
    except Exception as e:
        logger.error(f"Error in graph chat endpoint: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )