from fastapi import APIRouter, Query

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
from app.services.market_data_service import (
    bootstrap_market_data_from_browser,
    complete_market_data_garanti_sso,
    fetch_market_data,
    fetch_market_data_debug_for_ticker,
    fetch_market_data_provider_health,
    fetch_market_ohlcv,
    fetch_order_book_pressure,
    run_market_data_cache_cleanup,
    start_market_data_garanti_sso,
)


router = APIRouter(tags=["market-data"])


@router.get("/market-data/provider-health", response_model=MarketDataProviderHealthResponse)
def get_market_data_provider_health(
    ticker: str = Query(default="GARAN"),
    timeframe: str = Query(default="1G"),
) -> MarketDataProviderHealthResponse:
    return fetch_market_data_provider_health(ticker=ticker, timeframe=timeframe)


@router.get("/market-data/{ticker}", response_model=MarketDataResponse)
def get_market_data(ticker: str) -> MarketDataResponse:
    return fetch_market_data(ticker)


@router.post("/market-data/auth/garanti/sso/start", response_model=GarantiSsoStartResponse)
def start_garanti_sso_auth() -> GarantiSsoStartResponse:
    return start_market_data_garanti_sso()


@router.post("/market-data/auth/garanti/sso/complete", response_model=GarantiSsoCompleteResponse)
def complete_garanti_sso_auth(payload: GarantiSsoCompleteRequest) -> GarantiSsoCompleteResponse:
    return complete_market_data_garanti_sso(payload)


@router.post("/market-data/auth/garanti/browser-bootstrap", response_model=GarantiBrowserBootstrapResponse)
def bootstrap_garanti_browser_auth(payload: GarantiBrowserBootstrapRequest) -> GarantiBrowserBootstrapResponse:
    return bootstrap_market_data_from_browser(payload)




@router.get("/market-data/{ticker}/debug", response_model=MarketDataDebugResponse)
def get_market_data_debug(
    ticker: str,
    timeframe: str = Query(default="1G"),
) -> MarketDataDebugResponse:
    return fetch_market_data_debug_for_ticker(ticker, timeframe=timeframe)

@router.get("/market-data/{ticker}/ohlcv", response_model=OHLCVResponse)
def get_market_ohlcv(
    ticker: str,
    timeframe: str = Query(default="1G"),
    bars: int = Query(default=60, ge=10, le=300),
) -> OHLCVResponse:
    return fetch_market_ohlcv(ticker, timeframe=timeframe, bars=bars)


@router.get("/market-data/{ticker}/order-book-pressure", response_model=OrderBookPressureResponse)
def get_order_book_pressure_endpoint(
    ticker: str,
    levels: int = Query(default=10, ge=1, le=25),
) -> OrderBookPressureResponse:
    return fetch_order_book_pressure(ticker, levels=levels)


@router.post("/market-data/cleanup/cache", response_model=MarketDataCleanupResponse)
def cleanup_market_data_cache_endpoint(
    ticker: str | None = Query(default=None),
    timeframe: str | None = Query(default=None),
) -> MarketDataCleanupResponse:
    return run_market_data_cache_cleanup(ticker=ticker, timeframe=timeframe)
