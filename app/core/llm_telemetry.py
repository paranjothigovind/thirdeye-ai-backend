"""Structured per-call LLM telemetry.

Each provider call emits one ``llm_call`` log record with token usage, models,
fallback use, latency, stop reason and the provider request ID. Records carry
no prompt or response text and no credentials. Token totals also feed the usage
limits in ``app.core.usage``.
"""
from dataclasses import asdict, dataclass, field
from typing import Optional

from app.core.logging import get_logger
from app.core.usage import add_token_usage, current_usage

logger = get_logger(__name__)


@dataclass
class LLMCallRecord:
    provider: str
    model_requested: str
    operation: str  # "generate" | "stream"
    status: str = "ok"  # ok | error | refused | discarded
    model_served: Optional[str] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    cache_creation_input_tokens: Optional[int] = None
    cache_read_input_tokens: Optional[int] = None
    tokens_estimated: bool = False
    fallback_used: bool = False
    fallback_model: Optional[str] = None
    stop_reason: Optional[str] = None
    latency_ms: Optional[int] = None
    provider_request_id: Optional[str] = None
    error_type: Optional[str] = None
    extra: dict = field(default_factory=dict)

    @property
    def total_tokens(self) -> int:
        return sum(
            value or 0
            for value in (
                self.input_tokens,
                self.output_tokens,
                self.cache_creation_input_tokens,
                self.cache_read_input_tokens,
            )
        )


async def record_llm_call(record: LLMCallRecord) -> None:
    """Log the call and count its tokens. Never raises."""
    ctx = current_usage.get()
    fields = {k: v for k, v in asdict(record).items() if v is not None and k != "extra"}
    fields.update(record.extra)
    fields["total_tokens"] = record.total_tokens
    if ctx is not None:
        fields["session"] = ctx.session_key
    try:
        logger.info(
            f"LLM call {record.status}: {record.provider}/{record.model_served or record.model_requested}",
            extra={"request_id": ctx.request_id if ctx else None, "event": "llm_call", "llm": fields},
        )
        await add_token_usage(record.total_tokens)
    except Exception as error:  # noqa: BLE001 - telemetry must not break generation
        logger.warning(f"Failed to record LLM usage: {type(error).__name__}")
