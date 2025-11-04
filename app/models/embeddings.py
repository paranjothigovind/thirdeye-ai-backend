"""Embeddings generation"""
from typing import List
from langchain_openai import AzureOpenAIEmbeddings
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class EmbeddingsClient:
    """Azure OpenAI embeddings client"""

    def __init__(self):
        """Initialize embeddings client"""
        self.embeddings = AzureOpenAIEmbeddings(
            azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
            api_key=settings.AZURE_OPENAI_API_KEY,
            api_version=settings.AZURE_OPENAI_API_VERSION,
            deployment=settings.AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT,
        )
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    async def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple documents"""
        try:
            return await self.embeddings.aembed_documents(texts)
        except Exception as e:
            logger.error(f"Error generating embeddings: {e}")
            raise
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    async def embed_query(self, text: str) -> List[float]:
        """Generate embedding for a single query"""
        try:
            return await self.embeddings.aembed_query(text)
        except Exception as e:
            logger.error(f"Error generating query embedding: {e}")
            raise


# Global embeddings instance
embeddings_client = EmbeddingsClient()