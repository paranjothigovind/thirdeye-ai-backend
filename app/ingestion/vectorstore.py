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

    async def check_document_ingested(self, doc_id: str) -> Dict[str, Any]:
        """Check if a document has been ingested and return metadata"""
        try:
            # Search for the latest version of the document
            results = self.search_client.search(
                search_text="*",
                filter=f"doc_id eq '{doc_id}' and is_latest eq true",
                select=["doc_id", "version", "title", "source", "timestamp"],
                top=1
            )

            for result in results:
                return {
                    "ingested": True,
                    "doc_id": result["doc_id"],
                    "version": result["version"],
                    "title": result.get("title", ""),
                    "source": result.get("source", ""),
                    "timestamp": result.get("timestamp", "")
                }

            # No document found
            return {
                "ingested": False,
                "doc_id": doc_id
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