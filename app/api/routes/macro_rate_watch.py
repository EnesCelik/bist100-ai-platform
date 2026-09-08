from fastapi import APIRouter, Query

from app.services.macro_rate_watch_service import PolicyRateWatchResponse, run_policy_rate_watch
from app.services.real_rate_watch_service import RealRateWatchResponse, run_real_rate_watch


router = APIRouter(tags=["macro-rate-watch"])


@router.post("/macro-events/rate-watch/run", response_model=PolicyRateWatchResponse)
def run_policy_rate_watch_route(
    ingest: bool = Query(default=False),
) -> PolicyRateWatchResponse:
    return run_policy_rate_watch(ingest=ingest)


@router.post("/macro-events/real-rate-watch/run", response_model=RealRateWatchResponse)
def run_real_rate_watch_route(
    ingest: bool = Query(default=False),
) -> RealRateWatchResponse:
    return run_real_rate_watch(ingest=ingest)
