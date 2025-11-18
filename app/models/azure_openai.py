"""Azure OpenAI integration"""
from typing import List, Dict, Any, AsyncIterator
from langchain_openai import AzureChatOpenAI
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class AzureOpenAIClient:
    """Azure OpenAI client wrapper"""

    def __init__(self):
        """Initialize Azure OpenAI client"""
        self.chat_model = AzureChatOpenAI(
            azure_endpoint=settings.AZURE_OPENAI_ENDPOINT_CHAT,
            api_key=settings.AZURE_OPENAI_CHAT_API_KEY,
            api_version=settings.AZURE_OPENAI_API_VERSION,
            deployment_name=settings.AZURE_OPENAI_CHAT_DEPLOYMENT,
            temperature=0.7,
            streaming=True,
        )
    print("UMBU", settings)
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    async def generate_response(
        self,
        messages: List[Dict[str, str]],
        stream: bool = True
    ) -> AsyncIterator[str]:
        """Generate chat response with streaming"""
        try:
            # Convert to LangChain messages
            lc_messages = self._convert_messages(messages)
            
            if stream:
                async for chunk in self.chat_model.astream(lc_messages):
                    if hasattr(chunk, "content"):
                        yield chunk.content
            else:
                response = await self.chat_model.ainvoke(lc_messages)
                yield response.content
                
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            raise
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
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