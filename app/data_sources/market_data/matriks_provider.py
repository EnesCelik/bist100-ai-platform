from __future__ import annotations

import base64
import hashlib
import json
import random
import ssl
import threading
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib import error, parse, request

from app.core.config import settings
from app.models.schemas import MarketDataResponse, OHLCVBar, OHLCVResponse, OrderBookLevel, OrderBookPressureResponse
from app.services.market_data_cache_service import get_cached_market_snapshot, save_market_snapshot
from app.services.market_data_cache_service import get_cached_ohlcv, save_ohlcv_response

MATRIKS_SOURCE_NAME = "matriks_market_data_tool"
MATRIKS_OHLCV_SOURCE_NAME = "matriks_ohlcv"
MATRIKS_DEPTH_SOURCE_NAME = "matriks_depth"
_LOGIN_MSG_TYPE = "A"
_DEFAULT_SNAPSHOT_PATH = "/dumrul/v1/snapshot-market-real"
_DEFAULT_BAR_PATH = "/dumrul/v1/tick/bar.gz"
_DEFAULT_INTEGRATION_URL = "https://etrader.garantibbvayatirim.com.tr/0172_v3_trader/Integration.aspx"
_DEFAULT_SOURCE_ID = "40"
_DEFAULT_EXCHANGE_ID = "4"
_DEFAULT_CLIENT_IP = "127.0.0.1"
_DEFAULT_PLATFORM = "D"
_DEFAULT_LANGUAGE = "tr"
_DEFAULT_VERSION = "20250804.20250915.20240520.20241017"
_TOKEN_REFRESH_SKEW_SECONDS = 120

_runtime_market_data_token: str | None = None
_runtime_token_expires_at: datetime | None = None
_token_lock = threading.Lock()

_TIMEFRAME_FETCH_CONFIG: dict[str, dict[str, int | str]] = {
    "1H": {"period": "5min", "aggregate": 12, "fetch_bars": 12},
    "4H": {"period": "5min", "aggregate": 48, "fetch_bars": 48},
    "1G": {"period": "1day", "aggregate": 1, "fetch_bars": 1},
}



def is_matriks_configured() -> bool:
    return bool(_read_configured_token() or _can_auto_login())



def normalize_matriks_symbol(ticker: str) -> str:
    normalized_ticker = ticker.upper().strip()
    suffix = settings.matriks_symbol_suffix.strip()

    if suffix and not normalized_ticker.endswith(suffix.upper()):
        return f"{normalized_ticker}{suffix}"

    return normalized_ticker



def build_quote_request_context(ticker: str) -> dict[str, Any]:
    return {
        "base_url": settings.matriks_base_url.strip().rstrip("/"),
        "token": _get_valid_market_data_token(),
        "snapshot_path": settings.matriks_snapshot_path.strip() or _DEFAULT_SNAPSHOT_PATH,
        "timeout_seconds": settings.matriks_timeout_seconds,
        "verify_ssl": settings.matriks_verify_ssl,
        "symbol": normalize_matriks_symbol(ticker),
    }


def build_bar_request_context(ticker: str, timeframe: str, bars: int) -> dict[str, Any]:
    normalized_timeframe = timeframe.upper()
    fetch_config = _TIMEFRAME_FETCH_CONFIG.get(normalized_timeframe, {})
    aggregate = int(fetch_config.get("aggregate", 1) or 1)
    fetch_multiplier = int(fetch_config.get("fetch_bars", aggregate) or aggregate)
    return {
        "base_url": settings.matriks_base_url.strip().rstrip("/"),
        "token": _get_valid_market_data_token(),
        "bar_path": settings.matriks_bar_path.strip() or _DEFAULT_BAR_PATH,
        "timeout_seconds": settings.matriks_timeout_seconds,
        "verify_ssl": settings.matriks_verify_ssl,
        "symbol": normalize_matriks_symbol(ticker),
        "timeframe": normalized_timeframe,
        "bars": max(bars, 1),
        "aggregate": aggregate,
        "fetch_count": max(bars, 1) * max(fetch_multiplier, 1),
    }


def build_depth_request_context(ticker: str, levels: int = 10) -> dict[str, Any]:
    return {
        "base_url": settings.matriks_base_url.strip().rstrip("/"),
        "token": _get_valid_market_data_token(),
        "depth_path": settings.matriks_depth_path.strip(),
        "timeout_seconds": settings.matriks_timeout_seconds,
        "verify_ssl": settings.matriks_verify_ssl,
        "symbol": normalize_matriks_symbol(ticker),
        "levels": max(levels, 1),
    }



def _read_configured_token() -> str:
    return settings.matriks_market_data_token.strip()



def _read_runtime_token() -> str:
    return (_runtime_market_data_token or "").strip()



def _can_auto_login() -> bool:
    return bool(settings.matriks_username.strip() and settings.matriks_password.strip())



def _utcnow() -> datetime:
    return datetime.now(UTC)



def _normalize_expiry(expiry: datetime | None) -> datetime | None:
    if expiry is None:
        return None
    return expiry.astimezone(UTC)



def _decode_jwt_expiry(token: str) -> datetime | None:
    try:
        parts = token.split(".")
        if len(parts) < 2:
            return None
        payload = parts[1]
        payload += "=" * (-len(payload) % 4)
        decoded = base64.urlsafe_b64decode(payload.encode("ascii")).decode("utf-8")
        exp_value = json.loads(decoded).get("exp")
        if exp_value in (None, ""):
            return None
        return datetime.fromtimestamp(int(exp_value), tz=UTC)
    except (ValueError, TypeError, json.JSONDecodeError, UnicodeDecodeError):
        return None



def _is_token_usable(token: str, expires_at: datetime | None) -> bool:
    if not token.strip():
        return False
    normalized_expiry = _normalize_expiry(expires_at)
    if normalized_expiry is None:
        return True
    return normalized_expiry > _utcnow() + timedelta(seconds=_TOKEN_REFRESH_SKEW_SECONDS)



def _set_runtime_token(token: str) -> str:
    global _runtime_market_data_token, _runtime_token_expires_at

    normalized_token = token.strip()
    _runtime_market_data_token = normalized_token or None
    _runtime_token_expires_at = _decode_jwt_expiry(normalized_token)
    return normalized_token


def store_market_data_token(token: str) -> str:
    return _set_runtime_token(token)


def decode_market_data_token_expiry(token: str) -> datetime | None:
    return _decode_jwt_expiry(token.strip())



def _get_valid_market_data_token() -> str:
    runtime_token = _read_runtime_token()
    if _is_token_usable(runtime_token, _runtime_token_expires_at):
        return runtime_token

    configured_token = _read_configured_token()
    configured_expiry = _decode_jwt_expiry(configured_token)
    if _is_token_usable(configured_token, configured_expiry):
        return _set_runtime_token(configured_token)

    if not _can_auto_login():
        return runtime_token or configured_token

    with _token_lock:
        runtime_token = _read_runtime_token()
        if _is_token_usable(runtime_token, _runtime_token_expires_at):
            return runtime_token
        return _login_and_store_market_data_token()



def _build_snapshot_url(context: dict[str, Any]) -> str:
    snapshot_path = context["snapshot_path"] or _DEFAULT_SNAPSHOT_PATH
    if not snapshot_path.startswith("/"):
        snapshot_path = f"/{snapshot_path}"
    query = parse.urlencode({"symbols": context["symbol"]})
    return f"{context['base_url']}{snapshot_path}?{query}"


def _period_for_timeframe(timeframe: str) -> str:
    normalized = timeframe.upper()
    fetch_config = _TIMEFRAME_FETCH_CONFIG.get(normalized, {})
    mapping = {
        "1H": settings.matriks_bar_period_1h.strip() or str(fetch_config.get("period", "")),
        "4H": settings.matriks_bar_period_4h.strip() or str(fetch_config.get("period", "")),
        "1G": settings.matriks_bar_period_1g.strip() or str(fetch_config.get("period", "1day")),
        "1W": settings.matriks_bar_period_1w.strip(),
    }
    return mapping.get(normalized, "")


def _build_bar_url(context: dict[str, Any]) -> str:
    bar_path = context["bar_path"] or _DEFAULT_BAR_PATH
    if not bar_path.startswith("/"):
        bar_path = f"/{bar_path}"

    period = _period_for_timeframe(context["timeframe"])
    if not period:
        return ""

    query = parse.urlencode({
        "symbol": context["symbol"],
        "period": period,
        "count": context["fetch_count"],
        "timestamp": int(_utcnow().timestamp() * 1000),
        "mid": int(_utcnow().timestamp() * 1000),
        "ngsw-bypass": "true",
    })
    return f"{context['base_url']}{bar_path}?{query}"


def _build_depth_url(context: dict[str, Any]) -> str:
    depth_path = context["depth_path"]
    if not depth_path:
        return ""
    if not depth_path.startswith("/"):
        depth_path = f"/{depth_path}"

    query = parse.urlencode({
        "symbol": context["symbol"],
        "count": context["levels"],
        "timestamp": int(_utcnow().timestamp() * 1000),
    })
    return f"{context['base_url']}{depth_path}?{query}"



def _get_ssl_context(verify_ssl: bool) -> ssl.SSLContext | None:
    if verify_ssl:
        return None
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    return ssl_context



def _extract_snapshot_row(payload: Any) -> dict[str, Any] | None:
    if isinstance(payload, list):
        return payload[0] if payload else None
    if isinstance(payload, dict):
        for key in ("data", "items", "result"):
            value = payload.get(key)
            if isinstance(value, list) and value:
                first_item = value[0]
                if isinstance(first_item, dict):
                    return first_item
        if "symbol" in payload or "last" in payload:
            return payload
    return None



def _open_request(req: request.Request, timeout_seconds: float, verify_ssl: bool) -> Any:
    ssl_context = _get_ssl_context(verify_ssl)
    if ssl_context is None:
        return request.urlopen(req, timeout=timeout_seconds)
    return request.urlopen(req, timeout=timeout_seconds, context=ssl_context)



def _fetch_quote_payload(ticker: str) -> dict[str, Any] | None:
    context = build_quote_request_context(ticker)
    if not context["token"].strip():
        return None

    request_url = _build_snapshot_url(context)
    req = request.Request(
        request_url,
        headers={
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
            "Content-Type": "application/json; charset=utf-8",
            "Authorization": f"jwt {context['token']}",
            "Origin": "https://trader.garantibbva.com.tr",
            "Referer": "https://trader.garantibbva.com.tr/",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "cross-site",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36",
        },
    )

    try:
        with _open_request(req, timeout_seconds=context["timeout_seconds"], verify_ssl=context["verify_ssl"]) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (error.URLError, error.HTTPError, TimeoutError, json.JSONDecodeError):
        return None

    return _extract_snapshot_row(payload)


def _fetch_bar_payload(ticker: str, timeframe: str, bars: int) -> list[dict[str, Any]] | None:
    context = build_bar_request_context(ticker, timeframe=timeframe, bars=bars)
    if not context["token"].strip():
        return None

    request_url = _build_bar_url(context)
    if not request_url:
        return None

    req = request.Request(
        request_url,
        headers={
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
            "Content-Type": "application/json; charset=utf-8",
            "Authorization": f"jwt {context['token']}",
            "Origin": "https://trader.garantibbva.com.tr",
            "Referer": "https://trader.garantibbva.com.tr/",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "cross-site",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36",
        },
    )

    try:
        with _open_request(req, timeout_seconds=context["timeout_seconds"], verify_ssl=context["verify_ssl"]) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (error.URLError, error.HTTPError, TimeoutError, json.JSONDecodeError):
        return None

    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    return None


def _fetch_depth_payload(ticker: str, levels: int = 10) -> Any | None:
    context = build_depth_request_context(ticker, levels=levels)
    if not context["token"].strip():
        return None

    request_url = _build_depth_url(context)
    if not request_url:
        return None

    req = request.Request(
        request_url,
        headers={
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json; charset=utf-8",
            "Authorization": f"jwt {context['token']}",
        },
    )

    try:
        with _open_request(req, timeout_seconds=context["timeout_seconds"], verify_ssl=context["verify_ssl"]) as response:
            return json.loads(response.read().decode("utf-8"))
    except (error.URLError, error.HTTPError, TimeoutError, json.JSONDecodeError):
        return None



def _generate_clord_id(unique_suffix: str = _DEFAULT_EXCHANGE_ID) -> str:
    day_diff = max((_utcnow().date() - datetime(2021, 10, 9, tzinfo=UTC).date()).days, 0)
    prefix = f"{day_diff:09d}"
    suffix = f"{int(unique_suffix):06d}" if unique_suffix.isdigit() else unique_suffix[-6:].rjust(6, "0")
    random_tail = f"{random.randint(0, 9999):04d}"
    return f"{prefix}{suffix}{random_tail}"



def _build_hardware_id(username: str, customer_no: str) -> str | None:
    normalized_customer_no = customer_no.strip()
    normalized_username = username.strip()
    seed = normalized_customer_no if normalized_customer_no not in {"", "0", "null", "undefined"} else normalized_username
    if not seed:
        return None
    return base64.b64encode(hashlib.sha256(seed.encode("utf-8")).digest()).decode("ascii")



def _build_login_payload_for_credentials(
    *,
    username: str,
    password: str,
    customer_no: str = "0",
    account_id: str = "0",
    session_key: str = "",
    action: str = "",
    otp: str = "",
) -> str:
    normalized_customer_no = customer_no.strip() or "0"
    normalized_account_id = account_id.strip() or "0"
    exchange_id = settings.matriks_exchange_id.strip() or _DEFAULT_EXCHANGE_ID
    payload: dict[str, str] = {
        "MsgType": _LOGIN_MSG_TYPE,
        "SourceID": settings.matriks_source_id.strip() or _DEFAULT_SOURCE_ID,
        "Version": settings.matriks_version.strip() or _DEFAULT_VERSION,
        "ClientIP": settings.matriks_client_ip.strip() or _DEFAULT_CLIENT_IP,
        "P": settings.matriks_platform.strip() or _DEFAULT_PLATFORM,
        "Language": settings.matriks_language.strip() or _DEFAULT_LANGUAGE,
        "ngsw-bypass": "true",
        "sso": "false",
        "Username": username.strip(),
        "Password": password.strip(),
        "AccountID": normalized_account_id,
        "CustomerNo": normalized_customer_no,
        "ClOrdID": _generate_clord_id(exchange_id),
        "ExchangeID": exchange_id,
        "ETX": "1",
    }

    hardware_id = _build_hardware_id(username=username, customer_no=normalized_customer_no)
    if hardware_id:
        payload["HardwareID"] = hardware_id

    if session_key.strip():
        payload["SessionKey"] = session_key.strip()
    if action.strip():
        payload["Action"] = action.strip()
    if otp.strip():
        payload["Otp"] = otp.strip()

    return parse.urlencode(payload)


def _build_login_payload() -> str:
    return _build_login_payload_for_credentials(
        username=settings.matriks_username.strip(),
        password=settings.matriks_password.strip(),
        customer_no=settings.matriks_customer_no.strip(),
        account_id=settings.matriks_account_id.strip(),
        session_key=settings.matriks_session_key.strip(),
        action=settings.matriks_login_action.strip(),
        otp=settings.matriks_login_otp.strip(),
    )



def _parse_login_response(raw_body: str) -> dict[str, Any] | None:
    try:
        parsed = json.loads(raw_body)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None



def _login_and_store_market_data_token() -> str:
    return login_with_bridge_credentials(
        username=settings.matriks_username.strip(),
        password=settings.matriks_password.strip(),
        customer_no=settings.matriks_customer_no.strip(),
        account_id=settings.matriks_account_id.strip(),
        session_key=settings.matriks_session_key.strip(),
        action=settings.matriks_login_action.strip(),
        otp=settings.matriks_login_otp.strip(),
    )


def login_with_bridge_credentials(
    *,
    username: str,
    password: str,
    customer_no: str = "",
    account_id: str = "",
    session_key: str = "",
    action: str = "",
    otp: str = "",
) -> str:
    integration_url = settings.matriks_integration_url.strip() or _DEFAULT_INTEGRATION_URL
    request_body = _build_login_payload_for_credentials(
        username=username,
        password=password,
        customer_no=customer_no,
        account_id=account_id,
        session_key=session_key,
        action=action,
        otp=otp,
    ).encode("utf-8")
    req = request.Request(
        integration_url,
        data=request_body,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    try:
        with _open_request(req, timeout_seconds=settings.matriks_timeout_seconds, verify_ssl=settings.matriks_verify_ssl) as response:
            parsed_response = _parse_login_response(response.read().decode("utf-8"))
    except (error.URLError, error.HTTPError, TimeoutError, UnicodeDecodeError):
        return ""

    if not parsed_response:
        return ""

    result = parsed_response.get("Result") or {}
    if result.get("State") is not True:
        return ""

    market_data_token = str(parsed_response.get("MarketDataToken") or "").strip()
    if not market_data_token:
        return ""

    return _set_runtime_token(market_data_token)



def _pick_first(payload: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in payload and payload[key] is not None:
            return payload[key]
    return default



def _to_float(value: Any, default: float = 0.0) -> float:
    if value in (None, ""):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default



def _to_int(value: Any, default: int = 0) -> int:
    if value in (None, ""):
        return default
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default



def _compute_change_percent(payload: dict[str, Any], last_price: float) -> float:
    explicit_change = _pick_first(payload, "change_percent", "daily_change_percent")
    if explicit_change not in (None, ""):
        return _to_float(explicit_change)

    reference_close = _to_float(_pick_first(payload, "dayClose", "basePrice", "prevClose"), default=0.0)
    if reference_close <= 0:
        return 0.0

    return ((last_price - reference_close) / reference_close) * 100



def _map_quote_payload(ticker: str, payload: dict[str, Any]) -> MarketDataResponse | None:
    if not payload:
        return None

    last_price = _to_float(_pick_first(payload, "last_price", "last", "price", "close"), default=0.0)
    if last_price <= 0:
        return None

    bid = _to_float(_pick_first(payload, "best_bid", "bid", "bid_price"), default=last_price)
    ask = _to_float(_pick_first(payload, "best_ask", "ask", "ask_price"), default=last_price)
    volume = _to_int(_pick_first(payload, "quantity", "volume", "lot", "total_volume"), default=0)

    return MarketDataResponse(
        ticker=ticker.upper(),
        last_price=round(last_price, 4),
        change_percent=round(_compute_change_percent(payload, last_price), 2),
        volume=volume,
        best_bid=round(bid, 4),
        best_ask=round(ask, 4),
        source=MATRIKS_SOURCE_NAME,
    )


def _map_bar_timestamp(payload: dict[str, Any]) -> str | None:
    time_value = payload.get("time")
    if time_value in (None, ""):
        return None
    try:
        timestamp = datetime.fromtimestamp(float(time_value) / 1000.0, tz=UTC)
    except (TypeError, ValueError, OSError):
        return None
    return timestamp.isoformat()


def _map_bar_payload(ticker: str, timeframe: str, bars: int, payload: list[dict[str, Any]]) -> OHLCVResponse | None:
    candles: list[OHLCVBar] = []
    for item in payload:
        timestamp = _map_bar_timestamp(item)
        if timestamp is None:
            continue
        open_value = _to_float(item.get("open"), default=0.0)
        high_value = _to_float(item.get("high"), default=0.0)
        low_value = _to_float(item.get("low"), default=0.0)
        close_value = _to_float(item.get("close"), default=0.0)
        volume_value = _to_int(item.get("totalQuantity"), default=_to_int(item.get("volume"), default=0))
        if min(open_value, high_value, low_value, close_value) <= 0:
            continue
        candles.append(
            OHLCVBar(
                timestamp=timestamp,
                open=round(open_value, 4),
                high=round(high_value, 4),
                low=round(low_value, 4),
                close=round(close_value, 4),
                volume=volume_value,
            )
        )

    if not candles:
        return None

    trimmed = candles[-bars:] if bars > 0 else candles
    return OHLCVResponse(
        ticker=ticker.upper(),
        timeframe=timeframe.upper(),
        bars=len(trimmed),
        candles=trimmed,
        source=MATRIKS_OHLCV_SOURCE_NAME,
    )


def _extract_depth_sides(payload: Any) -> tuple[list[Any], list[Any]]:
    if isinstance(payload, dict):
        for key in ("data", "items", "result"):
            value = payload.get(key)
            if isinstance(value, dict):
                payload = value
                break
        bid_candidates = (
            payload.get("bids"),
            payload.get("bid"),
            payload.get("buy"),
            payload.get("buyOrders"),
            payload.get("bidLevels"),
        )
        ask_candidates = (
            payload.get("asks"),
            payload.get("ask"),
            payload.get("sell"),
            payload.get("sellOrders"),
            payload.get("askLevels"),
        )
        bids = next((value for value in bid_candidates if isinstance(value, list)), [])
        asks = next((value for value in ask_candidates if isinstance(value, list)), [])
        return bids, asks

    if isinstance(payload, list):
        bids: list[Any] = []
        asks: list[Any] = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            side = str(_pick_first(item, "side", "S", "type", default="")).lower()
            if side in {"bid", "buy", "b", "alis", "alış"}:
                bids.append(item)
            elif side in {"ask", "sell", "s", "satis", "satış"}:
                asks.append(item)
        return bids, asks

    return [], []


def _map_depth_level(item: Any) -> OrderBookLevel | None:
    if isinstance(item, dict):
        price = _to_float(_pick_first(item, "price", "p", "bid", "ask", "levelPrice"), default=0.0)
        quantity = _to_int(_pick_first(item, "quantity", "q", "qty", "lot", "amount", "levelQuantity"), default=0)
    elif isinstance(item, (list, tuple)) and len(item) >= 2:
        price = _to_float(item[0], default=0.0)
        quantity = _to_int(item[1], default=0)
    else:
        return None

    if price <= 0 or quantity <= 0:
        return None
    return OrderBookLevel(price=round(price, 4), quantity=quantity)


def _pressure_bucket(imbalance: float | None) -> str:
    if imbalance is None:
        return "unavailable"
    if imbalance >= 2.0:
        return "strong_bid_pressure"
    if imbalance >= 1.25:
        return "bid_pressure"
    if imbalance > 0.8:
        return "balanced"
    if imbalance > 0.5:
        return "ask_pressure"
    return "strong_ask_pressure"


def _unavailable_depth_response(ticker: str, message: str) -> OrderBookPressureResponse:
    return OrderBookPressureResponse(
        ticker=ticker.upper(),
        available=False,
        bid_total_quantity=0,
        ask_total_quantity=0,
        bid_ask_imbalance=None,
        pressure_bucket="unavailable",
        top_bid_price=None,
        top_ask_price=None,
        top_bid_quantity=None,
        top_ask_quantity=None,
        bid_levels=[],
        ask_levels=[],
        source=MATRIKS_DEPTH_SOURCE_NAME,
        message=message,
    )


def _map_depth_payload(ticker: str, levels: int, payload: Any) -> OrderBookPressureResponse:
    raw_bids, raw_asks = _extract_depth_sides(payload)
    bid_levels = [level for item in raw_bids for level in [_map_depth_level(item)] if level is not None][:levels]
    ask_levels = [level for item in raw_asks for level in [_map_depth_level(item)] if level is not None][:levels]

    if not bid_levels and not ask_levels:
        return _unavailable_depth_response(ticker, "Depth payload could not be parsed into bid/ask levels.")

    bid_total = sum(item.quantity for item in bid_levels)
    ask_total = sum(item.quantity for item in ask_levels)
    imbalance = round(bid_total / ask_total, 3) if ask_total > 0 else None

    return OrderBookPressureResponse(
        ticker=ticker.upper(),
        available=True,
        bid_total_quantity=bid_total,
        ask_total_quantity=ask_total,
        bid_ask_imbalance=imbalance,
        pressure_bucket=_pressure_bucket(imbalance),
        top_bid_price=bid_levels[0].price if bid_levels else None,
        top_ask_price=ask_levels[0].price if ask_levels else None,
        top_bid_quantity=bid_levels[0].quantity if bid_levels else None,
        top_ask_quantity=ask_levels[0].quantity if ask_levels else None,
        bid_levels=bid_levels,
        ask_levels=ask_levels,
        source=MATRIKS_DEPTH_SOURCE_NAME,
        message=None,
    )


def _aggregate_candles(candles: list[OHLCVBar], aggregate: int) -> list[OHLCVBar]:
    if aggregate <= 1:
        return candles

    grouped: list[OHLCVBar] = []
    for start in range(0, len(candles), aggregate):
        chunk = candles[start:start + aggregate]
        if len(chunk) < aggregate:
            continue
        grouped.append(
            OHLCVBar(
                timestamp=chunk[-1].timestamp,
                open=chunk[0].open,
                high=max(item.high for item in chunk),
                low=min(item.low for item in chunk),
                close=chunk[-1].close,
                volume=sum(item.volume for item in chunk),
            )
        )
    return grouped



def get_market_snapshot(ticker: str, force_refresh: bool = False) -> MarketDataResponse | None:
    if not is_matriks_configured():
        return None

    if not force_refresh:
        fresh_cached_snapshot = get_cached_market_snapshot(ticker, max_age_minutes=settings.market_snapshot_max_age_minutes)
        if fresh_cached_snapshot is not None:
            return fresh_cached_snapshot

    payload = _fetch_quote_payload(ticker)
    if payload is None:
        if force_refresh:
            return None
        return get_cached_market_snapshot(ticker)

    snapshot = _map_quote_payload(ticker, payload)
    if snapshot is None:
        if force_refresh:
            return None
        return get_cached_market_snapshot(ticker)

    save_market_snapshot(snapshot)
    return snapshot


def get_market_ohlcv(ticker: str, timeframe: str = "1G", bars: int = 60) -> OHLCVResponse | None:
    if not is_matriks_configured():
        return None

    normalized_timeframe = timeframe.upper()
    period = _period_for_timeframe(normalized_timeframe)
    if not period:
        return get_cached_ohlcv(
            ticker,
            timeframe=normalized_timeframe,
            bars=bars,
            preferred_sources=[MATRIKS_OHLCV_SOURCE_NAME],
            allow_fallback_sources=False,
        )

    cached = get_cached_ohlcv(
        ticker,
        timeframe=normalized_timeframe,
        bars=bars,
        preferred_sources=[MATRIKS_OHLCV_SOURCE_NAME],
        allow_fallback_sources=False,
    )
    if cached is not None:
        return cached

    payload = _fetch_bar_payload(ticker, timeframe=normalized_timeframe, bars=bars)
    if payload is None:
        return get_cached_ohlcv(
            ticker,
            timeframe=normalized_timeframe,
            bars=bars,
            preferred_sources=[MATRIKS_OHLCV_SOURCE_NAME],
            allow_fallback_sources=False,
        )

    response = _map_bar_payload(ticker, timeframe=normalized_timeframe, bars=max(bars, 1) * int(build_bar_request_context(ticker, normalized_timeframe, bars)["aggregate"]), payload=payload)
    if response is None:
        return get_cached_ohlcv(
            ticker,
            timeframe=normalized_timeframe,
            bars=bars,
            preferred_sources=[MATRIKS_OHLCV_SOURCE_NAME],
            allow_fallback_sources=False,
        )

    aggregate = int(build_bar_request_context(ticker, normalized_timeframe, bars)["aggregate"])
    response = OHLCVResponse(
        ticker=response.ticker,
        timeframe=response.timeframe,
        bars=bars,
        candles=_aggregate_candles(response.candles, aggregate)[-bars:] if aggregate > 1 else response.candles[-bars:],
        source=response.source,
    )
    if not response.candles:
        return get_cached_ohlcv(
            ticker,
            timeframe=normalized_timeframe,
            bars=bars,
            preferred_sources=[MATRIKS_OHLCV_SOURCE_NAME],
            allow_fallback_sources=False,
        )

    save_ohlcv_response(response)
    return response


def get_order_book_pressure(ticker: str, levels: int = 10) -> OrderBookPressureResponse:
    if not is_matriks_configured():
        return _unavailable_depth_response(ticker, "Matriks provider is not configured.")
    if not settings.matriks_depth_path.strip():
        return _unavailable_depth_response(ticker, "Matriks depth path is not configured yet.")

    payload = _fetch_depth_payload(ticker, levels=levels)
    if payload is None:
        return _unavailable_depth_response(ticker, "Matriks depth request failed or returned no payload.")

    return _map_depth_payload(ticker, levels=max(levels, 1), payload=payload)
