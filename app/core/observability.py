"""Observability and tracing utilities"""
import time
from typing import Optional, Dict, Any
from contextlib import contextmanager
from functools import wraps

from app.core.logging import get_logger
from app.core.config import settings

logger = get_logger(__name__)


class Metrics:
    """Simple metrics collector"""
    
    def __init__(self):
        self.metrics: Dict[str, list] = {}
    
    def record(self, metric_name: str, value: float, tags: Optional[Dict[str, str]] = None):
        """Record a metric value"""
        if metric_name not in self.metrics:
            self.metrics[metric_name] = []
        
        self.metrics[metric_name].append({
            "value": value,
            "timestamp": time.time(),
            "tags": tags or {}
        })
    
    def get_stats(self, metric_name: str) -> Dict[str, Any]:
        """Get statistics for a metric"""
        if metric_name not in self.metrics or not self.metrics[metric_name]:
            return {}
        
        values = [m["value"] for m in self.metrics[metric_name]]
        return {
            "count": len(values),
            "mean": sum(values) / len(values),
            "min": min(values),
            "max": max(values),
        }


# Global metrics instance
metrics = Metrics()


@contextmanager
def trace_operation(operation_name: str, metadata: Optional[Dict[str, Any]] = None):
    """Context manager for tracing operations"""
    start_time = time.time()
    logger.info(f"Starting operation: {operation_name}", extra=metadata or {})
    
    try:
        yield
        duration = time.time() - start_time
        metrics.record(f"{operation_name}_duration", duration)
        logger.info(
            f"Completed operation: {operation_name}",
            extra={"duration": duration, **(metadata or {})}
        )
    except Exception as e:
        duration = time.time() - start_time
        metrics.record(f"{operation_name}_error", 1)
        logger.error(
            f"Failed operation: {operation_name}",
            extra={"duration": duration, "error": str(e), **(metadata or {})}
        )
        raise


def trace_function(func):
    """Decorator for tracing function calls"""
    @wraps(func)
    async def async_wrapper(*args, **kwargs):
        with trace_operation(func.__name__):
            return await func(*args, **kwargs)
    
    @wraps(func)
    def sync_wrapper(*args, **kwargs):
        with trace_operation(func.__name__):
            return func(*args, **kwargs)
    
    if hasattr(func, "__await__"):
        return async_wrapper
    return sync_wrapper