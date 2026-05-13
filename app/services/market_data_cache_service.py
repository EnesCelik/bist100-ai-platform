from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, or_, select

from app.core.config import settings
from app.db.models import MarketSnapshotCurrent, OHLCVBarCache
from app.db.session import SessionLocal, ensure_runtime_schema
from app.models.schemas import MarketDataCleanupResponse, MarketDataDebugResponse, MarketDataResponse, OHLCVBar, OHLCVResponse


def _source_family(source: str | None) -> str | None:
    normalized = (source or "").strip().lower()
    if not normalized:
        return None
    if "matriks" in normalized:
        return "matriks"
    if "yahoo" in normalized:
        return "yahoo"
    if "mock" in normalized:
        return "mock"
    return normalized


def _parse_iso(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(UTC).replace(tzinfo=None)


def _retention_days(timeframe: str) -> int:
    mapping = {
        "1H": settings.ohlcv_retention_days_1h,
        "4H": settings.ohlcv_retention_days_4h,
        "1G": settings.ohlcv_retention_days_1g,
        "1W": settings.ohlcv_retention_days_1w,
    }
    return mapping.get(timeframe.upper(), settings.ohlcv_retention_days_1g)


def save_market_snapshot(snapshot: MarketDataResponse) -> None:
    ensure_runtime_schema()
    with SessionLocal() as session:
        existing = session.get(MarketSnapshotCurrent, snapshot.ticker.upper())
        if existing is None:
            existing = MarketSnapshotCurrent(ticker=snapshot.ticker.upper())
            session.add(existing)
        existing.last_price = snapshot.last_price
        existing.change_percent = snapshot.change_percent
        existing.volume = snapshot.volume
        existing.best_bid = snapshot.best_bid
        existing.best_ask = snapshot.best_ask
        existing.source = snapshot.source
        existing.updated_at = datetime.utcnow()
        session.execute(
            delete(MarketSnapshotCurrent).where(
                MarketSnapshotCurrent.updated_at < datetime.utcnow() - timedelta(days=settings.market_snapshot_retention_days)
            )
        )
        session.commit()


def get_cached_market_snapshot(ticker: str, max_age_minutes: int | None = None) -> MarketDataResponse | None:
    ensure_runtime_schema()
    with SessionLocal() as session:
        row = session.get(MarketSnapshotCurrent, ticker.upper())
        if row is None:
            return None
        if max_age_minutes is not None and row.updated_at is not None:
            cutoff = datetime.utcnow() - timedelta(minutes=max(max_age_minutes, 0))
            if row.updated_at < cutoff:
                return None
        return MarketDataResponse(
            ticker=row.ticker,
            last_price=row.last_price,
            change_percent=row.change_percent,
            volume=row.volume,
            best_bid=row.best_bid,
            best_ask=row.best_ask,
            source=f"{row.source}_cache",
        )


def save_ohlcv_response(response: OHLCVResponse) -> None:
    ensure_runtime_schema()
    normalized_ticker = response.ticker.upper()
    normalized_timeframe = response.timeframe.upper()
    candles_by_timestamp = {
        _parse_iso(candle.timestamp): candle
        for candle in response.candles
    }
    with SessionLocal() as session:
        for ts, candle in candles_by_timestamp.items():
            statement = select(OHLCVBarCache).where(
                OHLCVBarCache.ticker == normalized_ticker,
                OHLCVBarCache.timeframe == normalized_timeframe,
                OHLCVBarCache.timestamp == ts,
            )
            existing = session.execute(statement).scalar_one_or_none()
            if existing is None:
                existing = OHLCVBarCache(
                    ticker=normalized_ticker,
                    timeframe=normalized_timeframe,
                    timestamp=ts,
                )
                session.add(existing)
            existing.open = candle.open
            existing.high = candle.high
            existing.low = candle.low
            existing.close = candle.close
            existing.volume = candle.volume
            existing.source = response.source
            existing.updated_at = datetime.utcnow()

        cutoff = datetime.utcnow() - timedelta(days=_retention_days(normalized_timeframe))
        session.execute(
            delete(OHLCVBarCache).where(
                OHLCVBarCache.ticker == normalized_ticker,
                OHLCVBarCache.timeframe == normalized_timeframe,
                OHLCVBarCache.timestamp < cutoff,
            )
        )
        session.commit()


def get_cached_ohlcv(
    ticker: str,
    timeframe: str = "1G",
    bars: int = 60,
    max_age_minutes: int | None = None,
    preferred_sources: list[str] | None = None,
    allow_fallback_sources: bool = True,
) -> OHLCVResponse | None:
    ensure_runtime_schema()
    normalized_ticker = ticker.upper()
    normalized_timeframe = timeframe.upper()
    with SessionLocal() as session:
        base_statement = (
            select(OHLCVBarCache)
            .where(OHLCVBarCache.ticker == normalized_ticker, OHLCVBarCache.timeframe == normalized_timeframe)
            .order_by(OHLCVBarCache.timestamp.desc())
        )

        rows: list[OHLCVBarCache] = []
        normalized_sources = [item.strip() for item in (preferred_sources or []) if item and item.strip()]
        if normalized_sources:
            source_filters = [OHLCVBarCache.source == source for source in normalized_sources]
            preferred_statement = base_statement.where(or_(*source_filters)).limit(max(bars, 1))
            rows = list(session.execute(preferred_statement).scalars().all())

        if not rows and allow_fallback_sources:
            fallback_statement = base_statement.limit(max(bars, 1))
            rows = list(session.execute(fallback_statement).scalars().all())

    if not rows:
        return None
    latest_row = rows[0]
    if max_age_minutes is not None and latest_row.updated_at is not None:
        cutoff = datetime.utcnow() - timedelta(minutes=max(max_age_minutes, 0))
        if latest_row.updated_at < cutoff:
            return None
    if _is_latest_bar_stale(normalized_timeframe, latest_row.timestamp):
        return None
    ordered = list(reversed(rows))
    candles = [
        OHLCVBar(
            timestamp=row.timestamp.replace(tzinfo=UTC).isoformat(),
            open=row.open,
            high=row.high,
            low=row.low,
            close=row.close,
            volume=row.volume,
        )
        for row in ordered
    ]
    return OHLCVResponse(
        ticker=normalized_ticker,
        timeframe=normalized_timeframe,
        bars=len(candles),
        candles=candles,
        source=f"{ordered[-1].source}_cache",
    )


def _is_latest_bar_stale(timeframe: str, latest_timestamp: datetime | None) -> bool:
    if latest_timestamp is None:
        return True
    latest = latest_timestamp
    if latest.tzinfo is None:
        latest = latest.replace(tzinfo=UTC)
    now = datetime.now(UTC)
    max_age_by_timeframe = {
        "1H": timedelta(days=2),
        "4H": timedelta(days=3),
        "1G": timedelta(days=5),
        "1W": timedelta(days=21),
    }
    max_age = max_age_by_timeframe.get(timeframe.upper())
    return max_age is not None and latest < now - max_age


def get_market_data_debug(ticker: str, timeframe: str = "1G") -> MarketDataDebugResponse:
    ensure_runtime_schema()
    normalized_ticker = ticker.upper()
    normalized_timeframe = timeframe.upper()
    with SessionLocal() as session:
        snapshot_row = session.get(MarketSnapshotCurrent, normalized_ticker)
        statement = (
            select(OHLCVBarCache)
            .where(OHLCVBarCache.ticker == normalized_ticker, OHLCVBarCache.timeframe == normalized_timeframe)
            .order_by(OHLCVBarCache.timestamp.desc())
        )
        rows = list(session.execute(statement).scalars().all())

    latest_bar = rows[0] if rows else None
    ohlcv_sources = sorted({row.source for row in rows if row.source})
    snapshot_source = snapshot_row.source if snapshot_row is not None else None
    snapshot_family = _source_family(snapshot_source)
    ohlcv_source = latest_bar.source if latest_bar is not None else None
    ohlcv_family = _source_family(ohlcv_source)
    return MarketDataDebugResponse(
        ticker=normalized_ticker,
        snapshot_available=snapshot_row is not None,
        snapshot_source=snapshot_source,
        snapshot_updated_at=snapshot_row.updated_at.isoformat() if snapshot_row is not None and snapshot_row.updated_at is not None else None,
        snapshot_source_family=snapshot_family,
        snapshot_is_matriks=snapshot_family == "matriks",
        ohlcv_timeframe=normalized_timeframe,
        ohlcv_cached_bars=len(rows),
        ohlcv_latest_timestamp=latest_bar.timestamp.replace(tzinfo=UTC).isoformat() if latest_bar is not None else None,
        ohlcv_source=ohlcv_source,
        ohlcv_source_family=ohlcv_family,
        ohlcv_is_matriks=ohlcv_family == "matriks",
        ohlcv_cache_sources=ohlcv_sources,
        ohlcv_has_matriks_cache=any(_source_family(source) == "matriks" for source in ohlcv_sources),
        ohlcv_has_yahoo_cache=any(_source_family(source) == "yahoo" for source in ohlcv_sources),
    )


def cleanup_market_data_cache(ticker: str | None = None, timeframe: str | None = None) -> MarketDataCleanupResponse:
    ensure_runtime_schema()
    normalized_ticker = ticker.upper() if ticker else None
    normalized_timeframe = timeframe.upper() if timeframe else None
    snapshot_deleted = 0
    ohlcv_deleted = 0

    with SessionLocal() as session:
        snapshot_stmt = delete(MarketSnapshotCurrent).where(
            MarketSnapshotCurrent.updated_at < datetime.utcnow() - timedelta(days=settings.market_snapshot_retention_days)
        )
        if normalized_ticker is not None:
            snapshot_stmt = snapshot_stmt.where(MarketSnapshotCurrent.ticker == normalized_ticker)
        snapshot_result = session.execute(snapshot_stmt)
        snapshot_deleted = int(snapshot_result.rowcount or 0)

        if normalized_timeframe is not None:
            ohlcv_cutoff = datetime.utcnow() - timedelta(days=_retention_days(normalized_timeframe))
            ohlcv_stmt = delete(OHLCVBarCache).where(OHLCVBarCache.timestamp < ohlcv_cutoff)
            ohlcv_stmt = ohlcv_stmt.where(OHLCVBarCache.timeframe == normalized_timeframe)
            if normalized_ticker is not None:
                ohlcv_stmt = ohlcv_stmt.where(OHLCVBarCache.ticker == normalized_ticker)
            ohlcv_result = session.execute(ohlcv_stmt)
            ohlcv_deleted = int(ohlcv_result.rowcount or 0)
        else:
            for tf in ["1H", "4H", "1G", "1W"]:
                cutoff = datetime.utcnow() - timedelta(days=_retention_days(tf))
                ohlcv_stmt = delete(OHLCVBarCache).where(OHLCVBarCache.timeframe == tf, OHLCVBarCache.timestamp < cutoff)
                if normalized_ticker is not None:
                    ohlcv_stmt = ohlcv_stmt.where(OHLCVBarCache.ticker == normalized_ticker)
                ohlcv_result = session.execute(ohlcv_stmt)
                ohlcv_deleted += int(ohlcv_result.rowcount or 0)

        session.commit()

    return MarketDataCleanupResponse(
        status="cleaned",
        snapshot_deleted=snapshot_deleted,
        ohlcv_deleted=ohlcv_deleted,
        ticker_filter=normalized_ticker,
        timeframe_filter=normalized_timeframe,
    )
