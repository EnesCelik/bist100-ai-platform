from fastapi import APIRouter, Query

from app.models.schemas import (
    TradingAgentCycleResponse,
    TradingAgentLearningReportResponse,
    TradingAgentLearningWeightsResponse,
    TradingAgentMorningTelegramResponse,
    TradingAgentOpeningPlanRequest,
    TradingAgentReduceResponse,
    TradingAgentRegimeResponse,
    TradingAgentReplayResponse,
    TradingAgentSignalScoreItem,
    TradingAgentStatusResponse,
)
from app.services.trading_agent_decision_service import build_agent_learning_report
from app.services.market_scan_service import scan_opening_candidates
from app.services.trading_agent_learning_weights_service import build_next_session_weight_adjustments
from app.services.trading_agent_replay_service import evaluate_agent_candidate_replay
from app.services.trading_agent_signal_service import detect_regime_from_opening_candidates, score_opening_candidate
from app.services.trading_agent_telegram_service import send_intraday_momentum_telegram, send_morning_opening_telegram
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


@router.get("/agent/trading/learning-weights", response_model=TradingAgentLearningWeightsResponse)
def get_trading_agent_learning_weights(
    trade_date: str | None = Query(default=None),
    strategy_name: str | None = Query(default=None),
) -> TradingAgentLearningWeightsResponse:
    return build_next_session_weight_adjustments(trade_date=trade_date, strategy_name=strategy_name)


@router.get("/agent/trading/signals", response_model=list[TradingAgentSignalScoreItem])
def get_trading_agent_signal_scores(
    limit: int = Query(default=10, ge=1, le=30),
) -> list[TradingAgentSignalScoreItem]:
    scan = scan_opening_candidates(limit=max(limit * 2, limit))
    regime = detect_regime_from_opening_candidates(scan.items)
    learning = build_next_session_weight_adjustments()
    scored = [score_opening_candidate(item, regime=regime, learning_adjustments=learning.adjustments) for item in scan.items]
    return sorted(scored, key=lambda item: item.agent_score, reverse=True)[:limit]


@router.get("/agent/trading/regime", response_model=TradingAgentRegimeResponse)
def get_trading_agent_regime(
    limit: int = Query(default=20, ge=5, le=50),
) -> TradingAgentRegimeResponse:
    scan = scan_opening_candidates(limit=limit)
    return detect_regime_from_opening_candidates(scan.items)


@router.get("/agent/trading/replay", response_model=TradingAgentReplayResponse)
def get_trading_agent_replay(
    limit: int = Query(default=5, ge=1, le=20),
    horizon_bars: int = Query(default=10, ge=1, le=60),
    sample_size: int = Query(default=8, ge=1, le=30),
) -> TradingAgentReplayResponse:
    scan = scan_opening_candidates(limit=max(limit * 2, limit))
    regime = detect_regime_from_opening_candidates(scan.items)
    learning = build_next_session_weight_adjustments()
    scored = [score_opening_candidate(item, regime=regime, learning_adjustments=learning.adjustments) for item in scan.items]
    ranked = sorted(scored, key=lambda item: item.agent_score, reverse=True)[:limit]
    return evaluate_agent_candidate_replay(ranked, horizon_bars=horizon_bars, sample_size=sample_size)


@router.post("/agent/trading/morning-telegram", response_model=TradingAgentMorningTelegramResponse)
def send_trading_agent_morning_telegram(
    force: bool = Query(default=False),
) -> TradingAgentMorningTelegramResponse:
    return send_morning_opening_telegram(force=force)


@router.post("/agent/trading/intraday-telegram", response_model=TradingAgentMorningTelegramResponse)
def send_trading_agent_intraday_telegram(
    slot: str = Query(default="manual"),
    force: bool = Query(default=False),
) -> TradingAgentMorningTelegramResponse:
    return send_intraday_momentum_telegram(slot=slot, force=force)


@router.get("/agent/trading/status", response_model=TradingAgentStatusResponse)
def get_trading_agent_current_status(
    strategy_name: str | None = Query(default=None),
) -> TradingAgentStatusResponse:
    return get_trading_agent_status(strategy_name=strategy_name)
