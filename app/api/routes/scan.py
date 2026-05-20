from fastapi import APIRouter, HTTPException, Query
from sqlalchemy.exc import SQLAlchemyError

from app.models.schemas import (
    LimitUpCandidateResponse,
    LiveMomentumRadarResponse,
    MarketScanResponse,
    OpeningCandidateResponse,
    OpportunityScanResponse,
    ScanSnapshotCreateResponse,
    ScanSnapshotHistoryResponse,
)
from app.services.market_scan_service import (
    get_market_scan_snapshot_history,
    save_market_scan_snapshot,
    scan_limit_up_candidates,
    scan_live_momentum_radar,
    scan_market,
    scan_opening_candidates,
    scan_opportunities,
)


router = APIRouter(tags=["scan"])


@router.get("/scan/market", response_model=MarketScanResponse)
def get_market_scan(
    stance: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
) -> MarketScanResponse:
    # Tarama endpoint'i bos sonuc senaryosunda 404 donmemeli.
    # Dashboard bullish/bearish gibi filtreli taramalarda bos listeyi dogal olarak gosterebilir.
    return scan_market(stance=stance, limit=limit)


@router.get("/scan/limit-up-candidates", response_model=LimitUpCandidateResponse)
def get_limit_up_candidates(
    limit: int = Query(default=15, ge=1, le=100),
) -> LimitUpCandidateResponse:
    return scan_limit_up_candidates(limit=limit)


@router.get("/scan/opening-candidates", response_model=OpeningCandidateResponse)
def get_opening_candidates(
    limit: int = Query(default=15, ge=1, le=100),
) -> OpeningCandidateResponse:
    return scan_opening_candidates(limit=limit)


@router.get("/scan/opportunities", response_model=OpportunityScanResponse)
def get_opportunities(
    limit: int = Query(default=15, ge=1, le=100),
    include_avoid: bool = Query(default=False),
) -> OpportunityScanResponse:
    return scan_opportunities(limit=limit, include_avoid=include_avoid)


@router.get("/scan/live-momentum-radar", response_model=LiveMomentumRadarResponse)
def get_live_momentum_radar(
    limit: int = Query(default=15, ge=1, le=100),
    universe_code: str = Query(default="bist100"),
) -> LiveMomentumRadarResponse:
    return scan_live_momentum_radar(limit=limit, universe_code=universe_code)


@router.post("/scan/market/snapshot", response_model=ScanSnapshotCreateResponse)
def create_market_scan_snapshot(
    stance: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
) -> ScanSnapshotCreateResponse:
    try:
        return save_market_scan_snapshot(stance=stance, limit=limit)
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=500, detail="Market scan snapshot kaydedilemedi") from exc


@router.get("/scan/history", response_model=ScanSnapshotHistoryResponse)
def get_market_scan_history(
    limit: int = Query(default=20, ge=1, le=100),
    stance: str | None = Query(default=None),
    provider: str | None = Query(default=None),
) -> ScanSnapshotHistoryResponse:
    try:
        history = get_market_scan_snapshot_history(limit=limit, stance=stance, provider=provider)
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=500, detail="Market scan history okunamadi") from exc

    if history.total == 0:
        raise HTTPException(status_code=404, detail="Market scan history bulunamadi")
    return history
