"""Vector store operations"""
from typing import List, Dict, Any
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchIndex,
    SimpleField,
    SearchableField,
    SearchField,
    SearchFieldDataType,
    VectorSearch,
    VectorSearchProfile,
    HnswAlgorithmConfiguration,
)
from azure.core.credentials import AzureKeyCredential
from datetime import datetime
import uuid

from app.core.config import settings
from app.core.logging import get_logger
from app.models.embeddings import embeddings_client

logger = get_logger(__name__)


class VectorStore:
    """Azure AI Search vector store"""
    
    def __init__(self):
        """Initialize vector store"""
        credential = AzureKeyCredential(settings.AZURE_SEARCH_KEY)
        
        self.search_client = SearchClient(
            endpoint=settings.AZURE_SEARCH_ENDPOINT,
            index_name=settings.AZURE_SEARCH_INDEX,
            credential=credential
        )
        
        self.index_client = SearchIndexClient(
            endpoint=settings.AZURE_SEARCH_ENDPOINT,
            credential=credential
        )
        
        self._ensure_index()
    
    def _ensure_index(self):
        """Ensure search index exists with correct dimensions"""
        try:
            # Check if index exists
            try:
                existing_index = self.index_client.get_index(settings.AZURE_SEARCH_INDEX)
                logger.info(f"Index {settings.AZURE_SEARCH_INDEX} already exists")

                # Check vector dimensions
                vector_field = next((f for f in existing_index.fields if f.name == "content_vector"), None)
                if vector_field and hasattr(vector_field, 'vector_search_dimensions'):
                    current_dims = vector_field.vector_search_dimensions
                    if current_dims != settings.EMBEDDING_DIMENSIONS:
                        logger.warning(f"Index has {current_dims} dimensions, but config specifies {settings.EMBEDDING_DIMENSIONS}. Recreating index.")
                        self.index_client.delete_index(settings.AZURE_SEARCH_INDEX)
                        logger.info(f"Deleted old index: {settings.AZURE_SEARCH_INDEX}")
                    else:
                        return
                else:
                    logger.warning("Could not determine vector dimensions of existing index. Recreating.")
                    self.index_client.delete_index(settings.AZURE_SEARCH_INDEX)
                    logger.info(f"Deleted old index: {settings.AZURE_SEARCH_INDEX}")

            except Exception as e:
                logger.info(f"Index {settings.AZURE_SEARCH_INDEX} does not exist or error checking: {e}")
            
            # Create index
            fields = [
                SimpleField(name="id", type=SearchFieldDataType.String, key=True),
                SimpleField(name="doc_id", type=SearchFieldDataType.String, filterable=True, sortable=True),
                SimpleField(name="version", type=SearchFieldDataType.Int32, filterable=True, sortable=True),
                SimpleField(name="is_latest", type=SearchFieldDataType.Boolean, filterable=True),
                SearchableField(name="title", type=SearchFieldDataType.String),
                SearchableField(name="content", type=SearchFieldDataType.String),
                SimpleField(name="source", type=SearchFieldDataType.String, filterable=True),
                SimpleField(name="page", type=SearchFieldDataType.Int32, filterable=True),
                SearchableField(name="section", type=SearchFieldDataType.String, filterable=True),
                SearchableField(name="url", type=SearchFieldDataType.String),
                SimpleField(name="timestamp", type=SearchFieldDataType.DateTimeOffset, sortable=True),
                SearchField(
                    name="content_vector",
                    type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                    searchable=True,
                    vector_search_dimensions=settings.EMBEDDING_DIMENSIONS,
                    vector_search_profile_name="default-profile"
                ),
            ]
            
            # Vector search configuration
            vector_search = VectorSearch(
                profiles=[
                    VectorSearchProfile(
                        name="default-profile",
                        algorithm_configuration_name="default-algorithm"
                    )
                ],
                algorithms=[
                    HnswAlgorithmConfiguration(name="default-algorithm")
                ]
            )
            
            index = SearchIndex(
                name=settings.AZURE_SEARCH_INDEX,
                fields=fields,
                vector_search=vector_search
            )
            
            self.index_client.create_index(index)
            logger.info(f"Created index: {settings.AZURE_SEARCH_INDEX}")
            
        except Exception as e:
            logger.error(f"Error ensuring index: {e}")
            raise
    
    async def upsert_documents(
        self,
        documents: List[Dict[str, Any]],
        doc_id: str,
        version: int = 1
    ) -> Dict[str, Any]:
        """Upsert documents with versioning"""
        try:
            # Mark previous versions as not latest
            if version > 1:
                await self._mark_old_versions(doc_id)
            
            # Generate embeddings
            texts = [doc["content"] for doc in documents]
            embeddings = await embeddings_client.embed_documents(texts)
            
            # Prepare documents for upload
            search_documents = []
            for doc, embedding in zip(documents, embeddings):
                search_doc = {
                    "id": str(uuid.uuid4()),
                    "doc_id": doc_id,
                    "version": version,
                    "is_latest": True,
                    "title": doc.get("title", ""),
                    "content": doc["content"],
                    "source": doc.get("source", ""),
                    "page": doc.get("page"),
                    "section": doc.get("section", ""),
                    "url": doc.get("url", ""),
                    "timestamp": datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%fZ'),
                    "content_vector": embedding,
                }
                search_documents.append(search_doc)
            
            # Upload to search index
            result = self.search_client.upload_documents(documents=search_documents)
            
            success_count = sum(1 for r in result if r.succeeded)
            logger.info(f"Upserted {success_count}/{len(documents)} documents for doc_id: {doc_id}")
            
            return {
                "doc_id": doc_id,
                "version": version,
                "total_chunks": len(documents),
                "success_count": success_count
            }
            
        except Exception as e:
            logger.error(f"Error upserting documents: {e}")
            raise
    
    async def _mark_old_versions(self, doc_id: str):
        """Mark old versions as not latest"""
        try:
            # Search for existing documents
            results = self.search_client.search(
                search_text="*",
                filter=f"doc_id eq '{doc_id}' and is_latest eq true",
                select=["id"]
            )

            # Update documents
            updates = []
            for result in results:
                updates.append({
                    "id": result["id"],
                    "is_latest": False
                })

            if updates:
                self.search_client.merge_documents(documents=updates)
                logger.info(f"Marked {len(updates)} old versions as not latest for doc_id: {doc_id}")

        except Exception as e:
            logger.error(f"Error marking old versions: {e}")

    async def list_all_doc_ids(self) -> Dict[str, Any]:
        """Return all unique doc_ids and run dummy query tests"""
        try:

            # ====================================================
            # 1️⃣ LIST ALL DOC IDS
            # ====================================================
            results = self.search_client.search(
                search_text="*",
                select=["doc_id"],
                top=10000
            )

            doc_ids = set()
            total_scanned = 0

            for item in results:
                total_scanned += 1
                doc_id = item.get("doc_id")
                if doc_id:
                    doc_ids.add(doc_id)

            doc_ids_list = sorted(doc_ids)

            # ====================================================
            # 2️⃣ DUMMY QUERY TEXT SEARCH
            # ====================================================
            dummy_query = "who is paranjothi"

            text_results_raw = list(self.search_client.search(
                search_text=dummy_query,
                select=["id", "doc_id", "content", "title"],
                top=5
            ))

            text_results = []
            for r in text_results_raw:
                text_results.append({
                    "id": r.get("id"),
                    "doc_id": r.get("doc_id"),
                    "title": r.get("title"),
                    "content": r.get("content"),
                    "score": r.get("@search.score")
                })

            logger.info(f"📄 Dummy TEXT search returned {len(text_results)} docs")

            # ====================================================
            # 3️⃣ DUMMY VECTOR SEARCH
            # ====================================================
            vector_results = []
            try:
                dummy_vector = await embeddings_client.embed_query(dummy_query)

                from azure.search.documents.models import VectorizedQuery
                vector_query = VectorizedQuery(
                    vector=dummy_vector,
                    k_nearest_neighbors=5,
                    fields="content_vector",
                )


                vector_raw = list(self.search_client.search(
                    search_text="",
                    vector_queries=[vector_query],
                    select=["id", "doc_id", "content", "title"],
                    top=5
                ))

                for item in vector_raw:
                    vector_results.append({
                        "id": item.get("id"),
                        "doc_id": item.get("doc_id"),
                        "title": item.get("title"),
                        "content": item.get("content"),
                        "score": item.get("@search.score")
                    })


            except Exception as ve:
                logger.error(f"❌ Dummy VECTOR search failed: {ve}")

            # ====================================================
            # 4️⃣ RETURN EVERYTHING
            # ====================================================
            return {
                "count": len(doc_ids_list),
                "doc_ids": doc_ids_list,
                "dummy_query": dummy_query,
                "text_results": text_results,
                "vector_results": vector_results
            }

        except Exception as e:
            logger.error(f"❌ Error listing doc_ids: {e}")
            return {
                "error": str(e),
                "count": 0,
                "doc_ids": [],
                "dummy_query": "who is paranjothi",
                "text_results": [],
                "vector_results": []
            }



    async def check_document_ingested(self, doc_id: str) -> Dict[str, Any]:
        """Check ingestion status and print document counts"""
        try:
            # ---------------------------
            # 1. Count ALL documents
            # ---------------------------
            count_all = self.search_client.get_document_count()

            # ---------------------------
            # 2. Count docs for this doc_id
            # ---------------------------
            results_iter = self.search_client.search(
                search_text="*",
                filter=f"doc_id eq '{doc_id}'",
                select=["id", "doc_id", "version", "title", "source", "timestamp"]
            )

            docs_for_id = list(results_iter)
            count_for_id = len(docs_for_id)

            # ---------------------------
            # 3. Return metadata of latest version
            # ---------------------------
            latest_iter = self.search_client.search(
                search_text="*",
                filter=f"doc_id eq '{doc_id}' and is_latest eq true",
                select=["id", "doc_id", "version", "title", "source", "timestamp"],
                top=1
            )

            latest_list = list(latest_iter)

            if not latest_list:
                return {
                    "ingested": False,
                    "doc_id": doc_id,
                    "total_docs_in_index": count_all,
                    "total_docs_for_id": count_for_id,
                }

            latest = latest_list[0]

            return {
                "ingested": True,
                "doc_id": latest["doc_id"],
                "version": latest["version"],
                "title": latest.get("title", ""),
                "source": latest.get("source", ""),
                "timestamp": latest.get("timestamp", ""),
                "total_docs_in_index": count_all,
                "total_docs_for_id": count_for_id,
            }

        except Exception as e:
            logger.error(f"Error checking document ingestion: {e}")
            return {
                "ingested": False,
                "doc_id": doc_id,
                "error": str(e)
            }

    async def clear_all(self) -> Dict[str, Any]:
        """Delete all documents and recreate the index"""
        try:
            # Delete the existing index
            try:
                self.index_client.delete_index(settings.AZURE_SEARCH_INDEX)
                logger.info(f"Deleted index: {settings.AZURE_SEARCH_INDEX}")
            except Exception as e:
                logger.warning(f"Index {settings.AZURE_SEARCH_INDEX} may not exist: {e}")

            # Recreate the index
            self._ensure_index()
            logger.info(f"Recreated index: {settings.AZURE_SEARCH_INDEX}")

            return {
                "status": "success",
                "message": "All vector data cleared and index recreated"
            }

        except Exception as e:
            logger.error(f"Error clearing vector store: {e}")
            return {
                "status": "error",
                "error": str(e)
            }


# Global vector store instance
vector_store = VectorStore()