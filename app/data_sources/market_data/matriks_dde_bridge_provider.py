from __future__ import annotations

import json
from urllib import error, parse, request

from app.core.config import settings
from app.models.schemas import MarketDataResponse, OHLCVResponse, OrderBookPressureResponse
from app.services.market_data_cache_service import get_cached_market_snapshot, save_market_snapshot

MATRIKS_DDE_BRIDGE_SOURCE_NAME = "matriks_dde_bridge"


def _normalized_base_url() -> str:
    return settings.matriks_dde_bridge_base_url.strip().rstrip("/")


def _build_url(path: str) -> str:
    base_url = _normalized_base_url()
    normalized_path = path.strip()
    if not normalized_path:
        return ""
    if not normalized_path.startswith("/"):
        normalized_path = f"/{normalized_path}"
    return f"{base_url}{normalized_path}"


def _request_json(url: str) -> dict | list | None:
    if not url:
        return None

    req = request.Request(url, headers={"Accept": "application/json", "User-Agent": "bist100-ai-platform/0.1"})
    try:
        with request.urlopen(req, timeout=settings.matriks_dde_bridge_timeout_seconds) as response:
            payload = response.read().decode("utf-8")
            return json.loads(payload)
    except (error.HTTPError, error.URLError, TimeoutError, json.JSONDecodeError, UnicodeDecodeError, ValueError):
        return None


def _symbol_path(ticker: str) -> str:
    template = settings.matriks_dde_bridge_symbol_path_template.strip() or "/symbol/{ticker}"
    return template.replace("{ticker}", parse.quote((ticker or "").upper().strip()))


def _ohlcv_path(ticker: str, timeframe: str, bars: int) -> str:
    template = settings.matriks_dde_bridge_ohlcv_path_template.strip()
    if not template:
        return ""

    path = template.replace("{ticker}", parse.quote((ticker or "").upper().strip()))
    separator = "&" if "?" in path else "?"
    return f"{path}{separator}{parse.urlencode({'timeframe': timeframe.upper().strip(), 'bars': max(int(bars), 1)})}"


def get_bridge_health() -> dict | None:
    return _request_json(_build_url(settings.matriks_dde_bridge_health_path.strip() or "/health"))


def get_market_snapshot(ticker: str, force_refresh: bool = False) -> MarketDataResponse | None:
    normalized_ticker = (ticker or "").upper().strip()
    if not normalized_ticker:
        return None

    if not force_refresh:
        cached = get_cached_market_snapshot(normalized_ticker)
        if cached is not None and cached.source == MATRIKS_DDE_BRIDGE_SOURCE_NAME:
            return cached

    payload = _request_json(_build_url(_symbol_path(normalized_ticker)))
    if not isinstance(payload, dict):
        cached = get_cached_market_snapshot(normalized_ticker)
        if cached is not None and cached.source == MATRIKS_DDE_BRIDGE_SOURCE_NAME:
            return cached
        return None

    try:
        response = MarketDataResponse(
            ticker=str(payload.get("ticker") or normalized_ticker).upper(),
            last_price=float(payload.get("last_price")),
            change_percent=float(payload.get("change_percent", 0.0)),
            volume=int(float(payload.get("volume", 0) or 0)),
            best_bid=float(payload.get("best_bid", 0.0) or 0.0),
            best_ask=float(payload.get("best_ask", 0.0) or 0.0),
            source=str(payload.get("source") or MATRIKS_DDE_BRIDGE_SOURCE_NAME),
        )
    except (TypeError, ValueError):
        cached = get_cached_market_snapshot(normalized_ticker)
        if cached is not None and cached.source == MATRIKS_DDE_BRIDGE_SOURCE_NAME:
            return cached
        return None

    save_market_snapshot(response)
    return response


def get_market_ohlcv(ticker: str, timeframe: str = "1G", bars: int = 60) -> OHLCVResponse | None:
    payload = _request_json(_build_url(_ohlcv_path(ticker, timeframe, bars)))
    if not payload:
        return None
    return None


def get_order_book_pressure(ticker: str, levels: int = 10) -> OrderBookPressureResponse:
    normalized_ticker = (ticker or "").upper().strip()
    return OrderBookPressureResponse(
        ticker=normalized_ticker,
        available=False,
        bid_total_quantity=0,
        ask_total_quantity=0,
        bid_ask_imbalance=None,
        pressure_bucket="not_available",
        top_bid_price=None,
        top_ask_price=None,
        top_bid_quantity=None,
        top_ask_quantity=None,
        bid_levels=[],
        ask_levels=[],
        source=MATRIKS_DDE_BRIDGE_SOURCE_NAME,
        message="Matriks DDE bridge order-book endpoint is not wired yet.",
    )
