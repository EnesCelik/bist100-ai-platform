import json
from datetime import UTC, datetime
from urllib import error, parse, request

from app.core.config import settings
from app.models.schemas import MarketDataResponse, OHLCVBar, OHLCVResponse
from app.services.market_data_cache_service import (
    get_cached_market_snapshot,
    get_cached_ohlcv,
    save_market_snapshot,
    save_ohlcv_response,
)


TIMEFRAME_CONFIG = {
    "1H": {"interval": "1h", "range": "1mo", "aggregate": 1, "max_age_minutes": lambda: settings.ohlcv_cache_max_age_minutes_1h},
    "4H": {"interval": "1h", "range": "3mo", "aggregate": 4, "max_age_minutes": lambda: settings.ohlcv_cache_max_age_minutes_4h},
    "1G": {"interval": "1d", "range": "1y", "aggregate": 1, "max_age_minutes": lambda: settings.ohlcv_cache_max_age_minutes_1g},
    "1W": {"interval": "1wk", "range": "5y", "aggregate": 1, "max_age_minutes": lambda: settings.ohlcv_cache_max_age_minutes_1w},
}


def _normalize_symbol(ticker: str) -> str:
    return f"{ticker.upper()}.IS"


def _fetch_chart_payload(symbol: str, interval: str, data_range: str) -> dict | None:
    query = parse.urlencode({
        "interval": interval,
        "range": data_range,
        "includePrePost": "false",
        "events": "div,splits",
    })
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?{query}"
    req = request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with request.urlopen(req, timeout=settings.yahoo_timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))
    except (error.URLError, error.HTTPError, TimeoutError, json.JSONDecodeError):
        return None


def _parse_quote_rows(payload: dict) -> tuple[list[dict], dict | None]:
    chart = payload.get("chart", {})
    results = chart.get("result") or []
    if not results:
        return [], None
    result = results[0]
    timestamps = result.get("timestamp") or []
    quotes = ((result.get("indicators") or {}).get("quote") or [{}])[0]
    opens = quotes.get("open") or []
    highs = quotes.get("high") or []
    lows = quotes.get("low") or []
    closes = quotes.get("close") or []
    volumes = quotes.get("volume") or []
    rows: list[dict] = []
    for idx, ts in enumerate(timestamps):
        open_v = opens[idx] if idx < len(opens) else None
        high_v = highs[idx] if idx < len(highs) else None
        low_v = lows[idx] if idx < len(lows) else None
        close_v = closes[idx] if idx < len(closes) else None
        volume_v = volumes[idx] if idx < len(volumes) else None
        if None in (open_v, high_v, low_v, close_v, volume_v):
            continue
        rows.append({
            "timestamp": datetime.fromtimestamp(ts, tz=UTC).isoformat(),
            "open": float(open_v),
            "high": float(high_v),
            "low": float(low_v),
            "close": float(close_v),
            "volume": int(volume_v),
        })
    return rows, result.get("meta")


def _aggregate_rows(rows: list[dict], aggregate: int) -> list[dict]:
    if aggregate <= 1:
        return rows
    grouped: list[dict] = []
    for start in range(0, len(rows), aggregate):
        chunk = rows[start:start + aggregate]
        if len(chunk) < aggregate:
            continue
        grouped.append({
            "timestamp": chunk[-1]["timestamp"],
            "open": chunk[0]["open"],
            "high": max(item["high"] for item in chunk),
            "low": min(item["low"] for item in chunk),
            "close": chunk[-1]["close"],
            "volume": sum(item["volume"] for item in chunk),
        })
    return grouped


def get_market_snapshot(ticker: str, force_refresh: bool = False) -> MarketDataResponse | None:
    if not force_refresh:
        fresh_cached_snapshot = get_cached_market_snapshot(ticker, max_age_minutes=settings.market_snapshot_max_age_minutes)
        if fresh_cached_snapshot is not None:
            return fresh_cached_snapshot

    symbol = _normalize_symbol(ticker)
    payload = _fetch_chart_payload(symbol, interval="1d", data_range="5d")
    if payload is None:
        return get_cached_market_snapshot(ticker)
    rows, meta = _parse_quote_rows(payload)
    if not rows:
        return get_cached_market_snapshot(ticker)
    last_row = rows[-1]
    prev_close = None
    if meta is not None:
        prev_close = meta.get("chartPreviousClose") or meta.get("previousClose")
    if prev_close in (None, 0):
        prev_close = rows[-2]["close"] if len(rows) > 1 else last_row["close"]
    change_percent = ((last_row["close"] - float(prev_close)) / float(prev_close)) * 100 if prev_close else 0.0
    snapshot = MarketDataResponse(
        ticker=ticker.upper(),
        last_price=round(last_row["close"], 2),
        change_percent=round(change_percent, 2),
        volume=int(last_row["volume"]),
        best_bid=round(last_row["close"], 2),
        best_ask=round(last_row["close"], 2),
        source="yahoo_delayed_market_data",
    )
    save_market_snapshot(snapshot)
    return snapshot


def get_market_ohlcv(ticker: str, timeframe: str = "1G", bars: int = 60) -> OHLCVResponse | None:
    normalized_timeframe = timeframe.upper()
    config = TIMEFRAME_CONFIG.get(normalized_timeframe, TIMEFRAME_CONFIG["1G"])
    fresh_cached_ohlcv = get_cached_ohlcv(
        ticker,
        timeframe=normalized_timeframe,
        bars=bars,
        max_age_minutes=config["max_age_minutes"](),
    )
    if fresh_cached_ohlcv is not None:
        return fresh_cached_ohlcv

    symbol = _normalize_symbol(ticker)
    payload = _fetch_chart_payload(symbol, interval=config["interval"], data_range=config["range"])
    if payload is None:
        return get_cached_ohlcv(ticker, timeframe=normalized_timeframe, bars=bars)
    rows, _ = _parse_quote_rows(payload)
    if not rows:
        return get_cached_ohlcv(ticker, timeframe=normalized_timeframe, bars=bars)
    rows = _aggregate_rows(rows, config["aggregate"])
    if not rows:
        return None
    trimmed = rows[-bars:] if bars > 0 else rows
    candles = [OHLCVBar(**row) for row in trimmed]
    response = OHLCVResponse(
        ticker=ticker.upper(),
        timeframe=normalized_timeframe,
        bars=bars,
        candles=candles,
        source="yahoo_delayed_ohlcv",
    )
    save_ohlcv_response(response)
    return response
