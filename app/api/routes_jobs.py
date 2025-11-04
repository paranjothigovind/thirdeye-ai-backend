"""Job status endpoints"""
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from typing import Optional, Any, Dict
from celery.result import AsyncResult

from app.core.logging import get_logger
from app.ingestion.workers import celery_app

logger = get_logger(__name__)

router = APIRouter()


class JobStatus(BaseModel):
    """Job status response"""
    job_id: str
    status: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


@router.get("/jobs/{job_id}", response_model=JobStatus)
async def get_job_status(job_id: str):
    """Get job status by ID"""
    try:
        # Get task result
        task_result = AsyncResult(job_id, app=celery_app)
        
        # Map Celery states to our status
        status_map = {
            "PENDING": "queued",
            "STARTED": "processing",
            "SUCCESS": "completed",
            "FAILURE": "failed",
            "RETRY": "retrying",
            "REVOKED": "cancelled"
        }
        
        job_status = status_map.get(task_result.state, task_result.state.lower())
        
        response = JobStatus(
            job_id=job_id,
            status=job_status
        )
        
        # Add result if completed
        if task_result.state == "SUCCESS":
            response.result = task_result.result
        
        # Add error if failed
        elif task_result.state == "FAILURE":
            response.error = str(task_result.info)
        
        return response
    
    except Exception as e:
        logger.error(f"Error getting job status: {e}", extra={"job_id": job_id})
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )