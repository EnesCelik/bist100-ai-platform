from app.core.config import settings
from app.models.schemas import MarketDataResponse, OHLCVResponse, OrderBookPressureResponse

from app.data_sources.market_data.matriks_provider import get_order_book_pressure as get_matriks_order_book_pressure
from app.data_sources.market_data.matriks_provider import get_market_ohlcv as get_matriks_market_ohlcv
from app.data_sources.market_data.matriks_provider import get_market_snapshot as get_matriks_market_snapshot
from app.data_sources.market_data.mock_provider import get_order_book_pressure as get_mock_order_book_pressure
from app.data_sources.market_data.mock_provider import get_market_snapshot as get_mock_market_snapshot
from app.data_sources.market_data.yahoo_provider import get_market_ohlcv as get_yahoo_market_ohlcv
from app.data_sources.market_data.yahoo_provider import get_market_snapshot as get_yahoo_market_snapshot

SUPPORTED_MARKET_DATA_PROVIDERS = {"mock", "matriks", "yahoo_delayed"}


def _normalize_provider_name() -> str:
    provider = settings.market_data_provider.lower().strip()
    if provider not in SUPPORTED_MARKET_DATA_PROVIDERS:
        return "mock"
    return provider


def get_market_snapshot(ticker: str, force_refresh: bool = False) -> MarketDataResponse | None:
    provider = _normalize_provider_name()

    if provider == "matriks":
        matriks_snapshot = get_matriks_market_snapshot(ticker, force_refresh=force_refresh)
        if matriks_snapshot is not None:
            return matriks_snapshot

    yahoo_snapshot = get_yahoo_market_snapshot(ticker, force_refresh=force_refresh)
    if yahoo_snapshot is not None:
        return yahoo_snapshot

    if provider == "mock":
        return get_mock_market_snapshot(ticker)
    return None


def get_market_ohlcv(ticker: str, timeframe: str = "1G", bars: int = 60) -> OHLCVResponse | None:
    provider = _normalize_provider_name()

    if provider == "matriks":
        matriks_payload = get_matriks_market_ohlcv(ticker, timeframe=timeframe, bars=bars)
        if matriks_payload is not None:
            return matriks_payload

    yahoo_payload = get_yahoo_market_ohlcv(ticker, timeframe=timeframe, bars=bars)
    if yahoo_payload is not None:
        return yahoo_payload

    return None


def get_order_book_pressure(ticker: str, levels: int = 10) -> OrderBookPressureResponse:
    provider = _normalize_provider_name()

    if provider == "matriks":
        return get_matriks_order_book_pressure(ticker, levels=levels)

    return get_mock_order_book_pressure(ticker, levels=levels)


def get_active_market_data_provider() -> str:
    return _normalize_provider_name()
