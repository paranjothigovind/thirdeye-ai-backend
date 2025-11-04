"""Azure Blob Storage integration"""
from typing import BinaryIO, Optional, Dict, Any
from azure.storage.blob import BlobServiceClient, BlobClient
from datetime import datetime
import uuid

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class BlobStorage:
    """Azure Blob Storage client"""
    
    def __init__(self):
        """Initialize blob storage client"""
        self.blob_service_client = BlobServiceClient.from_connection_string(
            settings.AZURE_BLOB_CONNECTION_STRING
        )
        self.container_name = settings.AZURE_BLOB_CONTAINER
        self._ensure_container()
    
    def _ensure_container(self):
        """Ensure container exists"""
        try:
            container_client = self.blob_service_client.get_container_client(
                self.container_name
            )
            if not container_client.exists():
                container_client.create_container()
                logger.info(f"Created container: {self.container_name}")
        except Exception as e:
            logger.error(f"Error ensuring container: {e}")
    
    def upload_file(
        self,
        file: BinaryIO,
        filename: str,
        metadata: Optional[dict] = None
    ) -> str:
        """Upload file to blob storage"""
        try:
            # Generate unique blob name
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            blob_name = f"{timestamp}_{uuid.uuid4().hex[:8]}_{filename}"
            
            # Get blob client
            blob_client = self.blob_service_client.get_blob_client(
                container=self.container_name,
                blob=blob_name
            )
            
            # Upload with metadata
            blob_client.upload_blob(
                file,
                metadata=metadata or {},
                overwrite=True
            )
            
            logger.info(f"Uploaded file to blob: {blob_name}")
            return blob_name
            
        except Exception as e:
            logger.error(f"Error uploading file: {e}")
            raise
    
    def download_file(self, blob_name: str) -> bytes:
        """Download file from blob storage"""
        try:
            blob_client = self.blob_service_client.get_blob_client(
                container=self.container_name,
                blob=blob_name
            )
            
            return blob_client.download_blob().readall()
            
        except Exception as e:
            logger.error(f"Error downloading file: {e}")
            raise
    
    def get_blob_url(self, blob_name: str) -> str:
        """Get blob URL"""
        blob_client = self.blob_service_client.get_blob_client(
            container=self.container_name,
            blob=blob_name
        )
        return blob_client.url

    def clear_all(self) -> Dict[str, Any]:
        """Delete all blobs in the container"""
        try:
            container_client = self.blob_service_client.get_container_client(self.container_name)
            blobs = container_client.list_blobs()
            deleted_count = 0
            for blob in blobs:
                container_client.delete_blob(blob.name)
                deleted_count += 1
            logger.info(f"Deleted {deleted_count} blobs from container: {self.container_name}")
            return {
                "status": "success",
                "message": f"Deleted {deleted_count} blobs"
            }
        except Exception as e:
            logger.error(f"Error clearing blob storage: {e}")
            return {
                "status": "error",
                "error": str(e)
            }


# Global storage instance
blob_storage = BlobStorage()