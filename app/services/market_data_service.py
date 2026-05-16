from fastapi import HTTPException

from app.core.config import settings
from app.data_sources.market_data.provider import (
    get_active_market_data_provider,
    get_market_ohlcv,
    get_market_snapshot,
    get_order_book_pressure,
)
from app.models.schemas import (
    GarantiBrowserBootstrapRequest,
    GarantiBrowserBootstrapResponse,
    GarantiSsoCompleteRequest,
    GarantiSsoCompleteResponse,
    GarantiSsoStartResponse,
    MarketDataCleanupResponse,
    MarketDataDebugResponse,
    MarketDataProviderHealthResponse,
    MarketDataResponse,
    OHLCVResponse,
    OrderBookPressureResponse,
)
from app.services.garanti_sso_service import complete_garanti_sso_login, start_garanti_sso_login
from app.services.market_data_cache_service import cleanup_market_data_cache, get_market_data_debug
from app.data_sources.market_data.matriks_provider import (
    decode_market_data_token_expiry,
    get_market_data_token_status,
    store_market_data_token,
)


def _source_is_matriks(source: str | None) -> bool:
    return bool(source and source.lower().startswith("matriks"))


def fetch_market_data(ticker: str, force_refresh: bool = True) -> MarketDataResponse:
    market_snapshot = get_market_snapshot(ticker, force_refresh=force_refresh)
    if market_snapshot is None:
        raise HTTPException(
            status_code=404,
            detail=f"Market data for ticker '{ticker.upper()}' was not found.",
        )
    return market_snapshot


def fetch_market_ohlcv(ticker: str, timeframe: str = "1G", bars: int = 60) -> OHLCVResponse:
    market_ohlcv = get_market_ohlcv(ticker, timeframe=timeframe, bars=bars)
    if market_ohlcv is None:
        raise HTTPException(
            status_code=404,
            detail=f"OHLCV data for ticker '{ticker.upper()}' was not found from the currently configured free providers.",
        )
    return market_ohlcv


def fetch_order_book_pressure(ticker: str, levels: int = 10) -> OrderBookPressureResponse:
    return get_order_book_pressure(ticker, levels=levels)


def fetch_market_data_debug_for_ticker(ticker: str, timeframe: str = "1G") -> MarketDataDebugResponse:
    return get_market_data_debug(ticker, timeframe=timeframe)


def fetch_market_data_provider_health(ticker: str = "GARAN", timeframe: str = "1G") -> MarketDataProviderHealthResponse:
    normalized_ticker = ticker.upper().strip() or "GARAN"
    normalized_timeframe = timeframe.upper().strip() or "1G"
    provider = get_active_market_data_provider()
    token_status = get_market_data_token_status()
    notes: list[str] = []

    snapshot = get_market_snapshot(normalized_ticker, force_refresh=True)
    ohlcv = get_market_ohlcv(normalized_ticker, timeframe=normalized_timeframe, bars=3)
    depth = get_order_book_pressure(normalized_ticker, levels=5)

    snapshot_source = snapshot.source if snapshot is not None else None
    ohlcv_source = ohlcv.source if ohlcv is not None else None
    depth_source = depth.source if depth is not None else None
    snapshot_is_matriks = _source_is_matriks(snapshot_source)
    ohlcv_is_matriks = _source_is_matriks(ohlcv_source)

    if settings.production_data_strict and provider != "matriks":
        notes.append("production_data_strict is enabled but active provider is not matriks")
    if snapshot is None:
        notes.append("snapshot probe returned no data")
    elif settings.production_data_strict and not snapshot_is_matriks:
        notes.append("snapshot source is not Matriks while strict mode is enabled")
    if ohlcv is None:
        notes.append("ohlcv probe returned no data")
    elif settings.production_data_strict and not ohlcv_is_matriks:
        notes.append("ohlcv source is not Matriks while strict mode is enabled")
    if not depth.available:
        notes.append(depth.message or "depth/order-book data is not available")
    if not token_status["active_token_loaded"] and provider == "matriks":
        notes.append("Matriks token is not loaded")
    elif not token_status["active_token_usable"] and provider == "matriks":
        notes.append("Matriks token is loaded but local expiry check marks it unusable")

    status = "ok"
    if provider == "matriks" and settings.production_data_strict and (snapshot is None or not snapshot_is_matriks):
        status = "degraded"
    if provider == "matriks" and ohlcv is None:
        status = "degraded"

    return MarketDataProviderHealthResponse(
        status=status,
        provider=provider,
        production_data_strict=settings.production_data_strict,
        ticker=normalized_ticker,
        timeframe=normalized_timeframe,
        token_loaded=bool(token_status["active_token_loaded"]),
        token_usable=bool(token_status["active_token_usable"]),
        token_expires_at=token_status["active_token_expires_at"],
        runtime_token_loaded=bool(token_status["runtime_token_loaded"]),
        configured_token_loaded=bool(token_status["configured_token_loaded"]),
        auto_login_configured=bool(token_status["auto_login_configured"]),
        snapshot_available=snapshot is not None,
        snapshot_source=snapshot_source,
        snapshot_is_matriks=snapshot_is_matriks,
        ohlcv_available=ohlcv is not None,
        ohlcv_source=ohlcv_source,
        ohlcv_is_matriks=ohlcv_is_matriks,
        ohlcv_bars=len(ohlcv.candles) if ohlcv is not None else 0,
        depth_available=depth.available,
        depth_source=depth_source,
        depth_message=depth.message,
        notes=notes,
    )


def run_market_data_cache_cleanup(ticker: str | None = None, timeframe: str | None = None) -> MarketDataCleanupResponse:
    return cleanup_market_data_cache(ticker=ticker, timeframe=timeframe)


def start_market_data_garanti_sso() -> GarantiSsoStartResponse:
    try:
        return start_garanti_sso_login()
    except Exception as exc:  # pragma: no cover - network/SSO edge cases
        raise HTTPException(status_code=502, detail=f"Garanti SSO bootstrap failed: {exc}") from exc


def complete_market_data_garanti_sso(payload: GarantiSsoCompleteRequest) -> GarantiSsoCompleteResponse:
    try:
        return complete_garanti_sso_login(
            client_state=payload.client_state,
            wait_seconds=payload.wait_seconds,
            poll_interval_seconds=payload.poll_interval_seconds,
        )
    except Exception as exc:  # pragma: no cover - network/SSO edge cases
        raise HTTPException(status_code=502, detail=f"Garanti SSO completion failed: {exc}") from exc


def bootstrap_market_data_from_browser(payload: GarantiBrowserBootstrapRequest) -> GarantiBrowserBootstrapResponse:
    token = store_market_data_token(payload.market_data_token)
    if not token:
        raise HTTPException(status_code=400, detail="Provided MarketDataToken is empty.")

    expiry = decode_market_data_token_expiry(token)
    return GarantiBrowserBootstrapResponse(
        status="token_loaded",
        token_loaded=True,
        expires_at=expiry.isoformat() if expiry is not None else None,
        message="Garanti browser session token was loaded into the runtime provider.",
    )
