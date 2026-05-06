from fastapi import APIRouter, Query

from app.models.schemas import ReplayCalibrationResponse, ReplayEvaluationResponse, ReplayScorecardResponse
from app.services.replay_evaluation_service import evaluate_trade_calibration, evaluate_trade_replay, evaluate_trade_scorecard


router = APIRouter(tags=["replay-evaluation"])


@router.get("/evaluation/replay/{ticker}", response_model=ReplayEvaluationResponse)
def get_trade_replay(
    ticker: str,
    timeframe: str = Query(default="1G"),
    horizon_bars: int = Query(default=10, ge=1, le=60),
    as_of: str | None = Query(default=None),
) -> ReplayEvaluationResponse:
    return evaluate_trade_replay(
        ticker=ticker,
        timeframe=timeframe,
        horizon_bars=horizon_bars,
        as_of_timestamp=as_of,
    )


@router.get("/evaluation/calibration/{ticker}", response_model=ReplayCalibrationResponse)
def get_trade_calibration(
    ticker: str,
    timeframe: str = Query(default="1G"),
    horizon_bars: int = Query(default=10, ge=1, le=60),
    sample_size: int = Query(default=12, ge=3, le=40),
    step_bars: int = Query(default=5, ge=1, le=20),
) -> ReplayCalibrationResponse:
    return evaluate_trade_calibration(
        ticker=ticker,
        timeframe=timeframe,
        horizon_bars=horizon_bars,
        sample_size=sample_size,
        step_bars=step_bars,
    )


@router.get("/evaluation/scorecard", response_model=ReplayScorecardResponse)
def get_trade_scorecard(
    universe_code: str = Query(default="bist100"),
    timeframe: str = Query(default="1G"),
    horizon_bars: int = Query(default=10, ge=1, le=60),
    sample_size: int = Query(default=8, ge=3, le=40),
    step_bars: int = Query(default=5, ge=1, le=20),
    limit: int = Query(default=20, ge=1, le=100),
    cache_only: bool = Query(default=False),
    tickers: str | None = Query(default=None, description="Virgulle ayrilmis ticker listesi"),
) -> ReplayScorecardResponse:
    return evaluate_trade_scorecard(
        universe_code=universe_code,
        timeframe=timeframe,
        horizon_bars=horizon_bars,
        sample_size=sample_size,
        step_bars=step_bars,
        limit=limit,
        cache_only=cache_only,
        tickers=[part.strip() for part in tickers.split(",")] if tickers else None,
    )

