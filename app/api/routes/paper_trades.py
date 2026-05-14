from fastapi import APIRouter, Query

from app.models.schemas import (
    ManualBasketCreateRequest,
    PaperTradeDailyReportResponse,
    PaperTradeFinalizeResponse,
    PaperTradeHistoryResponse,
    PaperTradeMonitorResponse,
    PaperTradeOpenResponse,
)
from app.services.paper_trade_simulation_service import (
    create_manual_basket,
    finalize_open_trades,
    get_daily_paper_trade_report,
    get_paper_trades,
    monitor_open_trades,
    open_top_opportunity_trades,
)

router = APIRouter(tags=["paper-trades"])


@router.post("/simulation/opportunities/open-top", response_model=PaperTradeOpenResponse)
def open_top_paper_trades(
    limit: int = Query(default=5, ge=1, le=20),
    min_score: float = Query(default=70.0, ge=0.0, le=100.0),
    max_open_trades: int | None = Query(default=None, ge=1, le=50),
) -> PaperTradeOpenResponse:
    return open_top_opportunity_trades(limit=limit, min_score=min_score, max_open_trades=max_open_trades)


@router.post("/simulation/manual-basket", response_model=PaperTradeOpenResponse)
def create_manual_paper_basket(payload: ManualBasketCreateRequest) -> PaperTradeOpenResponse:
    return create_manual_basket(payload)


@router.post("/simulation/tick", response_model=PaperTradeMonitorResponse)
def tick_paper_trades() -> PaperTradeMonitorResponse:
    return monitor_open_trades()


@router.post("/simulation/finalize-day", response_model=PaperTradeFinalizeResponse)
def finalize_paper_trade_day() -> PaperTradeFinalizeResponse:
    return finalize_open_trades()


@router.get("/simulation/trades", response_model=PaperTradeHistoryResponse)
def list_paper_trades(
    limit: int = Query(default=50, ge=1, le=200),
    status: str | None = Query(default=None),
    strategy_name: str | None = Query(default=None),
) -> PaperTradeHistoryResponse:
    return get_paper_trades(limit=limit, status=status, strategy_name=strategy_name)


@router.get("/simulation/report/daily", response_model=PaperTradeDailyReportResponse)
def get_daily_report(
    trade_date: str | None = Query(default=None),
    strategy_name: str | None = Query(default=None),
) -> PaperTradeDailyReportResponse:
    return get_daily_paper_trade_report(trade_date=trade_date, strategy_name=strategy_name)
