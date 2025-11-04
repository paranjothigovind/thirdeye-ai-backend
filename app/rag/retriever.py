"""Retrieval components"""
from typing import List, Dict, Any, Optional
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery
from azure.core.credentials import AzureKeyCredential

from app.core.config import settings
from app.core.logging import get_logger
from app.models.embeddings import embeddings_client

logger = get_logger(__name__)


class HybridRetriever:
    """Hybrid retrieval using Azure AI Search"""
    
    def __init__(self):
        """Initialize retriever"""
        self.search_client = SearchClient(
            endpoint=settings.AZURE_SEARCH_ENDPOINT,
            index_name=settings.AZURE_SEARCH_INDEX,
            credential=AzureKeyCredential(settings.AZURE_SEARCH_KEY)
        )
        self.top_k = settings.TOP_K_RESULTS
    
    async def retrieve(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        top_k: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Retrieve relevant documents using hybrid search"""
        try:
            # Generate query embedding
            query_vector = await embeddings_client.embed_query(query)
            
            # Create vector query
            vector_query = VectorizedQuery(
                vector=query_vector,
                k_nearest_neighbors=top_k or self.top_k,
                fields="content_vector"
            )
            
            # Build filter string with correct OData syntax
            filter_str = None
            if filters:
                filter_parts = []
                for key, value in filters.items():
                    if isinstance(value, bool):
                        filter_parts.append(f"{key} eq {str(value).lower()}")
                    elif isinstance(value, str):
                        # Properly escape single quotes in string values
                        escaped_value = value.replace("'", "''")
                        filter_parts.append(f"{key} eq '{escaped_value}'")
                    elif isinstance(value, (int, float)):
                        filter_parts.append(f"{key} eq {value}")
                    else:
                        # For other types, convert to string
                        escaped_value = str(value).replace("'", "''")
                        filter_parts.append(f"{key} eq '{escaped_value}'")
                
                filter_str = " and ".join(filter_parts)
            
            # Add default filter for latest versions
            if filter_str:
                filter_str = f"(is_latest eq true) and ({filter_str})"
            else:
                filter_str = "is_latest eq true"
            
            # Perform hybrid search
            results = self.search_client.search(
                search_text=query,
                vector_queries=[vector_query],
                filter=filter_str,
                select=["id", "content", "title", "source", "page", "url", "section", "version"],
                # Changed from "doc_id" to "id" - adjust based on your actual key field name
                top=top_k or self.top_k
            )
            
            # Format results
            documents = []
            for result in results:
                doc = {
                    "content": result.get("content", ""),
                    "title": result.get("title", ""),
                    "source": result.get("source", ""),
                    "page": result.get("page"),
                    "url": result.get("url"),
                    "section": result.get("section"),
                    "score": result.get("@search.score", 0.0),
                }
                documents.append(doc)
            
            logger.info(f"Retrieved {len(documents)} documents for query: {query[:50]}...")
            return documents
            
        except Exception as e:
            logger.error(f"Error retrieving documents: {e}")
            raise
    async def retrieve_by_layer(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        top_k: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Retrieve relevant documents using hybrid search"""
        try:
            # Generate query embedding
            query_vector = await embeddings_client.embed_query(query)
            
            # Create vector query
            vector_query = VectorizedQuery(
                vector=query_vector,
                k_nearest_neighbors=top_k or self.top_k,
                fields="content_vector"
            )
            
            # Build filter string
            filter_str = None
            if filters:
                filter_parts = []
                for key, value in filters.items():
                    if isinstance(value, bool):
                        filter_parts.append(f"{key} eq {str(value).lower()}")
                    elif isinstance(value, str):
                        filter_parts.append(f"{key} eq '{value}'")
                else:
                        filter_parts.append(f"{key} eq {value}")
                filter_str = " and ".join(filter_parts)
            
            # Default filter for latest versions
            if filter_str:
                filter_str = f"is_latest eq true and ({filter_str})"
            else:
                filter_str = "is_latest eq true"
            
            # Perform hybrid search
            results = self.search_client.search(
                search_text=query,
                vector_queries=[vector_query],
                filter=filter_str,
                select=["id", "content", "title", "source", "page", "url", "section", "version"],
                top=top_k or self.top_k
            )
            
            # Format results
            documents = []
            for result in results:
                doc = {
                    "content": result.get("content", ""),
                    "title": result.get("title", ""),
                    "source": result.get("source", ""),
                    "page": result.get("page"),
                    "url": result.get("url"),
                    "section": result.get("section"),
                    "score": result.get("@search.score", 0.0),
                }
                documents.append(doc)
            
            logger.info(f"Retrieved {len(documents)} documents for query: {query[:50]}...")
            return documents
            
        except Exception as e:
            logger.error(f"Error retrieving documents: {e}")
            raise
    
    async def retrieve_by_layer(
        self,
        query: str,
        layer: str,
        top_k: int = 3
    ) -> List[Dict[str, Any]]:
        """Retrieve documents for a specific Angelitic RAG layer"""
        layer_filters = {
            "canonical": {"section": "teachings"},
            "safety": {"section": "safety"},
            "practices": {"section": "practices"},
            "qa": {"section": "qa"},
        }
        
        filters = layer_filters.get(layer, {})
        return await self.retrieve(query, filters=filters, top_k=top_k)


# Global retriever instance
hybrid_retriever = HybridRetriever()