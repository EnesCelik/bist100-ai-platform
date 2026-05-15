from fastapi import APIRouter, Query

from app.models.schemas import (
    TradingAgentCycleResponse,
    TradingAgentLearningReportResponse,
    TradingAgentOpeningPlanRequest,
    TradingAgentReduceResponse,
    TradingAgentStatusResponse,
)
from app.services.trading_agent_decision_service import build_agent_learning_report
from app.services.trading_agent_service import (
    evaluate_open_positions,
    get_agent_daily_report,
    get_trading_agent_status,
    run_finalize_cycle,
    run_monitor_cycle,
    run_opening_plan,
    simulate_reduce_or_exit,
)

router = APIRouter(tags=["trading-agent"])


@router.post("/agent/trading/opening-plan", response_model=TradingAgentCycleResponse)
def create_trading_agent_opening_plan(payload: TradingAgentOpeningPlanRequest) -> TradingAgentCycleResponse:
    return run_opening_plan(payload)


@router.post("/agent/trading/monitor", response_model=TradingAgentCycleResponse)
def monitor_trading_agent(strategy_name: str | None = Query(default=None)) -> TradingAgentCycleResponse:
    return run_monitor_cycle(strategy_name=strategy_name)


@router.post("/agent/trading/position-decisions", response_model=TradingAgentStatusResponse)
def evaluate_trading_agent_positions(
    strategy_name: str | None = Query(default=None),
) -> TradingAgentStatusResponse:
    evaluate_open_positions(strategy_name=strategy_name, persist=True)
    return get_trading_agent_status(strategy_name=strategy_name)


@router.post("/agent/trading/reduce-or-exit", response_model=TradingAgentReduceResponse)
def reduce_or_exit_trading_agent_positions(
    strategy_name: str | None = Query(default=None),
    reduce_percent: float = Query(default=50.0, ge=1.0, le=100.0),
) -> TradingAgentReduceResponse:
    return simulate_reduce_or_exit(strategy_name=strategy_name, reduce_percent=reduce_percent)


@router.post("/agent/trading/finalize", response_model=TradingAgentCycleResponse)
def finalize_trading_agent(strategy_name: str | None = Query(default=None)) -> TradingAgentCycleResponse:
    return run_finalize_cycle(strategy_name=strategy_name)


@router.get("/agent/trading/report", response_model=TradingAgentCycleResponse)
def get_trading_agent_report(
    trade_date: str | None = Query(default=None),
    strategy_name: str | None = Query(default=None),
) -> TradingAgentCycleResponse:
    return get_agent_daily_report(trade_date=trade_date, strategy_name=strategy_name)


@router.get("/agent/trading/learning-report", response_model=TradingAgentLearningReportResponse)
def get_trading_agent_learning_report(
    trade_date: str | None = Query(default=None),
    strategy_name: str | None = Query(default=None),
) -> TradingAgentLearningReportResponse:
    return build_agent_learning_report(trade_date=trade_date, strategy_name=strategy_name)


@router.get("/agent/trading/status", response_model=TradingAgentStatusResponse)
def get_trading_agent_current_status(
    strategy_name: str | None = Query(default=None),
) -> TradingAgentStatusResponse:
    return get_trading_agent_status(strategy_name=strategy_name)
