from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException

from app.models.schemas import TradingAgentReplayItem, TradingAgentReplayResponse, TradingAgentSignalScoreItem
from app.services.replay_evaluation_service import get_trade_calibration_cached


def _assessment(calibration) -> str:
    if calibration is None:
        return "no_replay_data"
    edge = calibration.take_profit_rate - calibration.stop_loss_rate
    if calibration.calibration_bias == "supportive" and edge >= 0.25:
        return "historically_supportive"
    if calibration.calibration_bias == "fragile" or edge < 0:
        return "historically_fragile"
    return "mixed_replay"


def evaluate_agent_candidate_replay(
    signal_scores: list[TradingAgentSignalScoreItem],
    horizon_bars: int = 10,
    sample_size: int = 8,
) -> TradingAgentReplayResponse:
    items: list[TradingAgentReplayItem] = []
    for signal in signal_scores:
        try:
            calibration = get_trade_calibration_cached(
                signal.ticker,
                timeframe="1G",
                horizon_bars=horizon_bars,
                sample_size=sample_size,
                step_bars=5,
                use_cache_only=False,
            )
        except HTTPException:
            calibration = None
        items.append(
            TradingAgentReplayItem(
                ticker=signal.ticker,
                agent_score=signal.agent_score,
                calibration_bias=calibration.calibration_bias if calibration else None,
                take_profit_rate=calibration.take_profit_rate if calibration else None,
                stop_loss_rate=calibration.stop_loss_rate if calibration else None,
                positive_close_rate=calibration.positive_close_rate if calibration else None,
                average_close_return_percent=calibration.average_close_return_percent if calibration else None,
                average_max_upside_percent=calibration.average_max_upside_percent if calibration else None,
                assessment=_assessment(calibration),
            )
        )

    supportive = sum(1 for item in items if item.assessment == "historically_supportive")
    fragile = sum(1 for item in items if item.assessment == "historically_fragile")
    summary = f"{len(items)} aday replay ile kontrol edildi; supportive={supportive}, fragile={fragile}."
    return TradingAgentReplayResponse(
        generated_at=datetime.utcnow().isoformat(),
        limit=len(signal_scores),
        horizon_bars=horizon_bars,
        sample_size=sample_size,
        total=len(items),
        items=items,
        summary=summary,
    )
