from fastapi import APIRouter, HTTPException, Query
from sqlalchemy.exc import SQLAlchemyError

from app.models.schemas import LimitUpCandidateResponse, MarketScanResponse, ScanSnapshotCreateResponse, ScanSnapshotHistoryResponse
from app.services.market_scan_service import (
    get_market_scan_snapshot_history,
    save_market_scan_snapshot,
    scan_limit_up_candidates,
    scan_market,
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
