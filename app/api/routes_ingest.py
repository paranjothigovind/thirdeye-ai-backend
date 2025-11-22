"""Ingestion endpoints"""
from fastapi import APIRouter, UploadFile, File, HTTPException, status, Form
from pydantic import BaseModel, Field, HttpUrl
from typing import List, Optional, Dict, Any
import uuid

from app.core.config import settings
from app.core.logging import get_logger
from app.ingestion.storage import blob_storage
from app.ingestion.vectorstore import vector_store
from app.ingestion.workers import process_pdf_task, process_urls_task

logger = get_logger(__name__)

router = APIRouter()


class URLIngestRequest(BaseModel):
    """URL ingestion request"""
    urls: List[HttpUrl] = Field(..., description="List of URLs to scrape and ingest")


class IngestResponse(BaseModel):
    """Ingestion response"""
    job_id: str
    status: str
    message: str

class DocIdListResponse(BaseModel):
    count: int
    doc_ids: List[str] = []
    dummy_query: Optional[str] = None
    text_results: Optional[List[Dict[str, Any]]] = None
    vector_results: Optional[List[Dict[str, Any]]] = None
    error: Optional[str] = None



class DocumentStatusResponse(BaseModel):
    """Document ingestion status response"""
    ingested: bool
    doc_id: str
    version: Optional[int] = None
    title: Optional[str] = None
    source: Optional[str] = None
    timestamp: Optional[str] = None
    error: Optional[str] = None


@router.post("/ingest", response_model=IngestResponse)
async def ingest(
    file: Optional[UploadFile] = File(None),
    urls: Optional[str] = Form(None)
):
    """
    Ingest content from either PDF file or URLs
    
    - **file**: PDF file upload (multipart/form-data)
    - **urls**: JSON string of URLs to scrape
    """
    job_id = str(uuid.uuid4())
    
    try:
        # PDF ingestion
        if file:
            # Validate file type
            if not file.filename.lower().endswith('.pdf'):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Only PDF files are supported"
                )
            
            # Check file size
            file_content = await file.read()
            if len(file_content) > settings.MAX_UPLOAD_SIZE_BYTES:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"File size exceeds {settings.MAX_UPLOAD_SIZE_MB}MB limit"
                )
            
            # Upload to blob storage
            from io import BytesIO
            file_obj = BytesIO(file_content)
            blob_name = blob_storage.upload_file(
                file_obj,
                file.filename,
                metadata={"job_id": job_id}
            )
            
            # Queue processing task
            task = process_pdf_task.apply_async(
                args=[blob_name, file.filename, {"job_id": job_id}],
                task_id=job_id
            )
            
            logger.info(f"Queued PDF ingestion job: {job_id}", extra={"job_id": job_id})
            
            return IngestResponse(
                job_id=job_id,
                status="queued",
                message=f"PDF ingestion job queued for {file.filename}"
            )
        
        # URL ingestion
        elif urls:
            import json
            try:
                url_list = json.loads(urls)
                if not isinstance(url_list, list):
                    raise ValueError("URLs must be a list")
            except json.JSONDecodeError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid JSON format for URLs"
                )
            
            if not url_list:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="URL list cannot be empty"
                )
            
            # Queue processing task
            task = process_urls_task.apply_async(
                args=[url_list],
                task_id=job_id
            )
            
            logger.info(f"Queued URL ingestion job: {job_id}", extra={"job_id": job_id})
            
            return IngestResponse(
                job_id=job_id,
                status="queued",
                message=f"URL ingestion job queued for {len(url_list)} URLs"
            )
        
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Either file or urls must be provided"
            )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in ingest endpoint: {e}", extra={"job_id": job_id})
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/documents", response_model=DocIdListResponse)
async def list_documents():
    """List all unique ingested document IDs"""
    try:
        result = await vector_store.list_all_doc_ids()
        return DocIdListResponse(**result)

    except Exception as e:
        logger.error(f"Error listing document IDs: {e}")
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


@router.post("/ingest/urls", response_model=IngestResponse)
async def ingest_urls(request: URLIngestRequest):
    """Ingest content from URLs (JSON endpoint)"""
    job_id = str(uuid.uuid4())
    
    try:
        url_list = [str(url) for url in request.urls]
        
        # Queue processing task
        task = process_urls_task.apply_async(
            args=[url_list],
            task_id=job_id
        )
        
        logger.info(f"Queued URL ingestion job: {job_id}", extra={"job_id": job_id})
        
        return IngestResponse(
            job_id=job_id,
            status="queued",
            message=f"URL ingestion job queued for {len(url_list)} URLs"
        )
    
    except Exception as e:
        logger.error(f"Error in ingest_urls endpoint: {e}", extra={"job_id": job_id})
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/documents/{doc_id}/status", response_model=DocumentStatusResponse)
async def get_document_status(doc_id: str):
    """Check if a document has been ingested"""
    try:
        result = await vector_store.check_document_ingested(doc_id)
        return DocumentStatusResponse(**result)

    except Exception as e:
        logger.error(f"Error checking document status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


class ClearResponse(BaseModel):
    """Clear response"""
    status: str
    message: str
    vector_result: Optional[Dict[str, Any]] = None
    storage_result: Optional[Dict[str, Any]] = None


@router.post("/clear", response_model=ClearResponse)
async def clear_all_data():
    """Clear all vector data and ingested PDFs"""
    try:
        # Clear vector store
        vector_result = await vector_store.clear_all()

        # Clear blob storage
        storage_result = blob_storage.clear_all()

        # Check if both succeeded
        if vector_result["status"] == "success" and storage_result["status"] == "success":
            status_msg = "success"
            message = "All vector data and PDFs cleared successfully"
        else:
            status_msg = "partial_success"
            message = "Some operations may have failed"

        return ClearResponse(
            status=status_msg,
            message=message,
            vector_result=vector_result,
            storage_result=storage_result
        )

    except Exception as e:
        logger.error(f"Error clearing data: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
