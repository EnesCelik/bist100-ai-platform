from fastapi import APIRouter, Query

from app.models.schemas import PaperDecisionLogCreateResponse, PaperDecisionLogHistoryResponse, PaperDecisionOutcomeHistoryResponse, PaperDecisionOutcomeResponse, PaperDecisionPerformanceSummaryResponse, PaperDecisionResolvedPerformanceSummaryResponse
from app.services.paper_decision_log_service import evaluate_paper_decision_outcome, get_paper_decision_history, get_paper_decision_outcomes, get_paper_decision_performance_summary, get_paper_decision_resolved_performance_summary, save_paper_decision_for_ticker, save_paper_decision_from_scan


router = APIRouter(tags=["paper-decision-log"])


@router.post("/evaluation/paper-log/scan", response_model=PaperDecisionLogCreateResponse)
def create_paper_decision_from_scan(
    limit: int = Query(default=10, ge=1, le=50),
    stance: str | None = Query(default=None),
    stances: str | None = Query(default=None, description="Comma-separated stance list such as bullish,neutral"),
) -> PaperDecisionLogCreateResponse:
    parsed_stances = [value.strip() for value in (stances or '').split(',') if value.strip()] or None
    return save_paper_decision_from_scan(limit=limit, stance=stance, stances=parsed_stances)


@router.post("/evaluation/paper-log/{ticker}", response_model=PaperDecisionLogCreateResponse)
def create_paper_decision_for_ticker(
    ticker: str,
    question: str | None = Query(default=None),
) -> PaperDecisionLogCreateResponse:
    return save_paper_decision_for_ticker(ticker=ticker, question=question)


@router.get("/evaluation/paper-log", response_model=PaperDecisionLogHistoryResponse)
def list_paper_decision_history(
    limit: int = Query(default=20, ge=1, le=100),
    ticker: str | None = Query(default=None),
    source_mode: str | None = Query(default=None),
    batch_id: str | None = Query(default=None),
) -> PaperDecisionLogHistoryResponse:
    return get_paper_decision_history(limit=limit, ticker=ticker, source_mode=source_mode, batch_id=batch_id)


@router.get("/evaluation/paper-log/summary", response_model=PaperDecisionPerformanceSummaryResponse)
def get_paper_decision_summary(
    limit: int = Query(default=50, ge=1, le=200),
    ticker: str | None = Query(default=None),
    source_mode: str | None = Query(default=None),
    batch_id: str | None = Query(default=None),
    timeframe: str = Query(default="1G"),
    horizon_bars: int = Query(default=10, ge=1, le=60),
) -> PaperDecisionPerformanceSummaryResponse:
    return get_paper_decision_performance_summary(limit=limit, ticker=ticker, source_mode=source_mode, batch_id=batch_id, timeframe=timeframe, horizon_bars=horizon_bars)


@router.get("/evaluation/paper-log/resolved-summary", response_model=PaperDecisionResolvedPerformanceSummaryResponse)
def get_paper_decision_resolved_summary(
    limit: int = Query(default=50, ge=1, le=200),
    ticker: str | None = Query(default=None),
    source_mode: str | None = Query(default=None),
    batch_id: str | None = Query(default=None),
    timeframe: str = Query(default="1G"),
    horizon_bars: int = Query(default=10, ge=1, le=60),
) -> PaperDecisionResolvedPerformanceSummaryResponse:
    return get_paper_decision_resolved_performance_summary(limit=limit, ticker=ticker, source_mode=source_mode, batch_id=batch_id, timeframe=timeframe, horizon_bars=horizon_bars)


@router.get("/evaluation/paper-log/outcomes", response_model=PaperDecisionOutcomeHistoryResponse)
def list_paper_decision_outcomes(
    limit: int = Query(default=20, ge=1, le=100),
    ticker: str | None = Query(default=None),
    source_mode: str | None = Query(default=None),
    batch_id: str | None = Query(default=None),
    timeframe: str = Query(default="1G"),
    horizon_bars: int = Query(default=10, ge=1, le=60),
) -> PaperDecisionOutcomeHistoryResponse:
    return get_paper_decision_outcomes(limit=limit, ticker=ticker, source_mode=source_mode, batch_id=batch_id, timeframe=timeframe, horizon_bars=horizon_bars)


@router.get("/evaluation/paper-log/{log_id}/outcome", response_model=PaperDecisionOutcomeResponse)
def get_paper_decision_outcome(
    log_id: int,
    timeframe: str = Query(default="1G"),
    horizon_bars: int = Query(default=10, ge=1, le=60),
) -> PaperDecisionOutcomeResponse:
    return evaluate_paper_decision_outcome(log_id=log_id, timeframe=timeframe, horizon_bars=horizon_bars)
