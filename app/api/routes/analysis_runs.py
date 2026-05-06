from datetime import date

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy.exc import SQLAlchemyError

from app.models.schemas import AnalysisRunHistoryResponse
from app.services.analysis_run_service import get_analysis_run_history


router = APIRouter(tags=["analysis-runs"])


@router.get("/analysis-runs", response_model=AnalysisRunHistoryResponse)
def get_analysis_runs(
    limit: int = Query(default=20, ge=1, le=100),
    ticker: str | None = Query(default=None),
    route_type: str | None = Query(default=None),
    stance: str | None = Query(default=None),
    action: str | None = Query(default=None),
    min_confidence: float | None = Query(default=None, ge=0, le=1),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
) -> AnalysisRunHistoryResponse:
    try:
        history = get_analysis_run_history(
            limit=limit,
            ticker=ticker,
            route_type=route_type,
            stance=stance,
            action=action,
            min_confidence=min_confidence,
            date_from=date_from,
            date_to=date_to,
        )
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=500, detail="Analysis run history could not be read") from exc

    if history.total == 0:
        raise HTTPException(status_code=404, detail="Analysis run history bulunamadi")

    return history
