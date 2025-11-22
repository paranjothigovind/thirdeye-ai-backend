"""Retrieval components - FIXED for empty section fields"""
from typing import List, Dict, Any, Optional
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery
from azure.core.credentials import AzureKeyCredential

from app.core.config import settings
from app.core.logging import get_logger
from app.models.embeddings import embeddings_client

logger = get_logger(__name__)


class HybridRetriever:
    """Fixed hybrid retrieval using Azure AI Search"""

    def __init__(self):
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
        """Retrieve documents using hybrid search (vector + BM25)"""
        try:
            k = top_k or self.top_k

            # ---- 1) Vectorize query ----
            query_vector = await embeddings_client.embed_query(query)
            
            if not query_vector or len(query_vector) == 0:
                logger.error("❌ Query vector is empty!")
                return await self._text_only_search(query, filters, k)
            
            # ---- 2) Create vector query ----
            vector_query = VectorizedQuery(
                vector=query_vector,
                k_nearest_neighbors=k,
                fields="content_vector"
            )

            # ---- 3) Build filter string ----
            filter_str = self._build_filter_string(filters)

            
            results = self.search_client.search(
                search_text=query,
                vector_queries=[vector_query],
                filter=filter_str,
                select=["id", "content", "title", "source", "page", "url", "section", "version"],
                top=k,
                query_type="simple",
            )

        

            # ---- 5) Process results ----
            docs = []
            result_count = 0
            
            for item in results:
                result_count += 1
                doc = {
                    "content": item.get("content", ""),
                    "title": item.get("title", ""),
                    "source": item.get("source", ""),
                    "page": item.get("page"),
                    "url": item.get("url"),
                    "section": item.get("section", ""),
                    "version": item.get("version"),
                    "score": item.get("@search.score", 0.0),
                }
                docs.append(doc)
                
                if result_count <= 3:
                    logger.info(
                        f"📄 Result {result_count}: "
                        f"score={doc['score']:.4f}, "
                        f"section='{doc.get('section', 'N/A')}', "
                        f"title='{doc['title'][:50]}...'"
                    )

            # ---- 6) Fallback if needed ----
            if len(docs) == 0:
                logger.warning("⚠️ Hybrid search returned 0 results. Trying pure TEXT search...")
                return await self._text_only_search(query, filters, k)

            return docs

        except Exception as e:
            logger.error(f"❌ Error in retrieve(): {e}", exc_info=True)
            raise

    async def _text_only_search(
        self,
        query: str,
        filters: Optional[Dict[str, Any]],
        k: int
    ) -> List[Dict[str, Any]]:
        """Pure BM25 text search fallback"""
        try:
            
            filter_str = self._build_filter_string(filters)
            
            text_results = self.search_client.search(
                search_text=query,
                filter=filter_str,
                select=["id", "content", "title", "source", "page", "url", "section", "version"],
                top=k,
                query_type="simple",
            )

            docs = []
            for item in text_results:
                docs.append({
                    "content": item.get("content", ""),
                    "title": item.get("title", ""),
                    "source": item.get("source", ""),
                    "page": item.get("page"),
                    "url": item.get("url"),
                    "section": item.get("section", ""),
                    "version": item.get("version"),
                    "score": item.get("@search.score", 0.0),
                })

            
            if len(docs) == 0:
                logger.error("🚨 ZERO results from text search!")
                await self._diagnostic_search()

            return docs

        except Exception as e:
            logger.error(f"❌ Text-only search failed: {e}", exc_info=True)
            return []

    async def _diagnostic_search(self):
        """Run diagnostic queries"""
        try:
            logger.info("🔬 Running diagnostic search...")
            
            test_results = self.search_client.search(
                search_text="*",
                select=["id", "content", "title", "section"],
                top=5
            )
            
            count = 0
            for item in test_results:
                count += 1
                logger.info(
                    f"   ✓ Found document: "
                    f"id={item.get('id')}, "
                    f"section='{item.get('section', '')}', "
                    f"title={item.get('title', 'N/A')[:30]}"
                )
            
            if count == 0:
                logger.error("🚨 CRITICAL: Index is EMPTY!")
            else:
                logger.info(f"✅ Diagnostic found {count} documents")
                
        except Exception as e:
            logger.error(f"❌ Diagnostic failed: {e}")

    def _build_filter_string(self, filters: Optional[Dict[str, Any]]) -> Optional[str]:
        """Build OData filter string from dictionary"""
        if not filters:
            return None
            
        parts = []
        for key, value in filters.items():
            if isinstance(value, bool):
                parts.append(f"{key} eq {str(value).lower()}")
            elif isinstance(value, str):
                # ⚠️ Skip filtering on empty strings
                if not value:
                    logger.warning(f"⚠️ Skipping filter for '{key}' - value is empty string")
                    continue
                escaped = value.replace("'", "''")
                parts.append(f"{key} eq '{escaped}'")
            elif isinstance(value, (int, float)):
                parts.append(f"{key} eq {value}")
            elif isinstance(value, list):
                # Safely quote string values for OData IN clause
                escaped_values = [("'" + v.replace("'", "''") + "'") if isinstance(v, str) else str(v) for v in value]
                parts.append(f"{key} in ({', '.join(escaped_values)})")
            else:
                logger.warning(f"⚠️ Unsupported filter type for {key}: {type(value)}")
                
        filter_str = " and ".join(parts)
        
        if filter_str:
            logger.info(f"🔎 OData filter: {filter_str}")
            
        return filter_str if filter_str else None

    async def retrieve_by_layer(
        self,
        query: str,
        layer: str,
        top_k: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Retrieve documents by layer.
        
        ⚠️ NOTE: Currently disabled section filtering because documents 
        have empty section fields. This will retrieve based on semantic 
        similarity only.
        """
        
        # ❌ OLD CODE - Doesn't work because section field is empty
        # layer_filters = {
        #     "canonical": {"section": "teachings"},
        #     "safety": {"section": "safety"},
        #     "practices": {"section": "practices"},
        #     "qa": {"section": "qa"},
        # }
        # filters = layer_filters.get(layer)
        
        # ✅ NEW CODE - No filtering, pure semantic search
        logger.info(f"🏷️ Layer '{layer}' - Using semantic search (no section filter)")
        logger.info(f"   💡 TIP: To enable layer filtering, re-index documents with section metadata")
        
        return await self.retrieve(
            query=query,
            filters=None,  # No filters since section is empty in docs
            top_k=top_k
        )


# Global retriever instance
hybrid_retriever = HybridRetriever()
