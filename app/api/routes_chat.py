"""Chat endpoints"""
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import List, Dict, Optional
import json
import uuid

from app.core.logging import get_logger
from app.rag.chains import rag_chain
from app.rag.guardrails import guardrails

logger = get_logger(__name__)

router = APIRouter()


class Message(BaseModel):
    """Chat message"""
    role: str = Field(..., description="Message role: user, assistant, or system")
    content: str = Field(..., description="Message content")


class ChatRequest(BaseModel):
    """Chat request"""
    messages: List[Message] = Field(..., description="Conversation messages")
    persona: Optional[str] = Field(None, description="Optional persona: teacher, student, etc.")
    stream: bool = Field(True, description="Enable streaming responses")


class Citation(BaseModel):
    """Citation reference"""
    title: str
    reference: str


class ChatResponse(BaseModel):
    """Chat response (non-streaming)"""
    response: str
    citations: List[Citation]
    request_id: str


@router.post("/chat")
async def chat(request: ChatRequest):
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
        
        query = user_messages[-1].content
        
        # Check query safety
        query_check = guardrails.check_query(query)
        
        # Handle emergency
        if "emergency" in query_check.get("issues", []):
            emergency_response = guardrails.handle_emergency()
            return ChatResponse(
                response=emergency_response,
                citations=[],
                request_id=request_id
            )
        
        # Stream response
        if request.stream:
            async def generate():
                try:
                    full_response = ""
                    
                    async for chunk in rag_chain.invoke(query, use_angelitic=True, stream=True):
                        full_response += chunk
                        
                        # Send chunk
                        yield f"data: {json.dumps({'chunk': chunk, 'type': 'content'})}\n\n"
                    
                    # Check response safety
                    response_check = guardrails.check_response(full_response)
                    
                    # Add disclaimers if needed
                    if query_check.get("requires_disclaimer"):
                        disclaimer_types = []
                        if "medical_query" in query_check.get("issues", []):
                            disclaimer_types.append("medical")
                        full_response = guardrails.add_disclaimers(full_response, disclaimer_types)
                    
                    # Extract citations
                    citations = rag_chain.extract_citations(full_response)
                    
                    # Send citations
                    yield f"data: {json.dumps({'citations': [c for c in citations], 'type': 'citations'})}\n\n"
                    
                    # Send done signal
                    yield "data: [DONE]\n\n"
                    
                except Exception as e:
                    logger.error(f"Error in streaming: {e}", extra={"request_id": request_id})
                    yield f"data: {json.dumps({'error': str(e), 'type': 'error'})}\n\n"
            
            return StreamingResponse(
                generate(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "X-Request-ID": request_id
                }
            )
        
        # Non-streaming response
        else:
            full_response = ""
            async for chunk in rag_chain.invoke(query, use_angelitic=True, stream=False):
                full_response += chunk
            
            # Check and add disclaimers
            if query_check.get("requires_disclaimer"):
                disclaimer_types = []
                if "medical_query" in query_check.get("issues", []):
                    disclaimer_types.append("medical")
                full_response = guardrails.add_disclaimers(full_response, disclaimer_types)
            
            # Extract citations
            citations = rag_chain.extract_citations(full_response)
            
            return ChatResponse(
                response=full_response,
                citations=[Citation(**c) for c in citations],
                request_id=request_id
            )
    
    except Exception as e:
        logger.error(f"Error in chat endpoint: {e}", extra={"request_id": request_id})
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )