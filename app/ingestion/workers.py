"""Celery workers for background jobs"""
from celery import Celery
from typing import Dict, Any
import asyncio

from app.core.config import settings
from app.core.logging import get_logger
from app.ingestion.pdf_pipeline import pdf_pipeline
from app.ingestion.web_pipeline import web_pipeline

logger = get_logger(__name__)

# Create Celery app
celery_app = Celery(
    "third_eye_workers",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)


@celery_app.task(name="process_pdf_task")
def process_pdf_task(blob_name: str, filename: str, metadata: Dict[str, Any] = None) -> Dict[str, Any]:
    """Background task for PDF processing"""
    try:
        logger.info(f"Starting PDF processing task: {filename}")
        
        # Download from blob
        from app.ingestion.storage import blob_storage
        file_bytes = blob_storage.download_file(blob_name)
        
        # Process PDF
        from io import BytesIO
        file_obj = BytesIO(file_bytes)
        
        # Run async function in sync context
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(
            pdf_pipeline.process_pdf(file_obj, filename, metadata)
        )
        loop.close()
        
        logger.info(f"Completed PDF processing task: {filename}")
        return result
        
    except Exception as e:
        logger.error(f"Error in PDF processing task: {e}")
        return {
            "status": "error",
            "filename": filename,
            "error": str(e)
        }


@celery_app.task(name="process_urls_task")
def process_urls_task(urls: list) -> Dict[str, Any]:
    """Background task for web scraping"""
    try:
        logger.info(f"Starting web scraping task for {len(urls)} URLs")
        
        # Run async function in sync context
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        results = loop.run_until_complete(
            web_pipeline.process_urls(urls)
        )
        loop.close()
        
        # Aggregate results
        success_count = sum(1 for r in results if r["status"] == "success")
        
        logger.info(f"Completed web scraping task: {success_count}/{len(urls)} successful")
        
        return {
            "status": "completed",
            "total_urls": len(urls),
            "success_count": success_count,
            "results": results
        }
        
    except Exception as e:
        logger.error(f"Error in web scraping task: {e}")
        return {
            "status": "error",
            "error": str(e)
        }