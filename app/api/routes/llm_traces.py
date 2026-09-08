from fastapi import APIRouter, Query

from app.models.schemas import LlmTraceSummaryResponse
from app.services.llm_synthesis_service import get_llm_trace_summary


router = APIRouter(tags=["llm-traces"])


@router.get("/llm/traces/summary", response_model=LlmTraceSummaryResponse)
def get_llm_trace_summary_route(
    limit: int = Query(default=20, ge=1, le=200),
) -> LlmTraceSummaryResponse:
    return get_llm_trace_summary(limit=limit)
