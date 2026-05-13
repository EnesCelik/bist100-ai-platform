from fastapi import HTTPException

from app.data_sources.market_data.provider import get_market_ohlcv, get_market_snapshot, get_order_book_pressure
from app.models.schemas import (
    GarantiBrowserBootstrapRequest,
    GarantiBrowserBootstrapResponse,
    GarantiSsoCompleteRequest,
    GarantiSsoCompleteResponse,
    GarantiSsoStartResponse,
    MarketDataCleanupResponse,
    MarketDataDebugResponse,
    MarketDataResponse,
    OHLCVResponse,
    OrderBookPressureResponse,
)
from app.services.garanti_sso_service import complete_garanti_sso_login, start_garanti_sso_login
from app.services.market_data_cache_service import cleanup_market_data_cache, get_market_data_debug
from app.data_sources.market_data.matriks_provider import decode_market_data_token_expiry, store_market_data_token


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
