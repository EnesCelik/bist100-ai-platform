import json
from urllib import error, parse, request

API_DEFAULT = "http://127.0.0.1:8000/api/v1"


def api_get(base_url: str, path: str, params: dict | None = None) -> dict:
    query = f"?{parse.urlencode(params)}" if params else ""
    url = f"{base_url}{path}{query}"
    try:
        with request.urlopen(url) as response:
            return json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8")
        raise RuntimeError(f"GET {path} failed: {detail}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"API baglantisi kurulamadi: {exc.reason}") from exc


def api_post(base_url: str, path: str, payload: dict) -> dict:
    url = f"{base_url}{path}"
    data = json.dumps(payload).encode("utf-8")
    req = request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with request.urlopen(req) as response:
            return json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8")
        raise RuntimeError(f"POST {path} failed: {detail}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"API baglantisi kurulamadi: {exc.reason}") from exc


def load_scan(base_url: str, stance: str | None = None, limit: int = 100) -> dict:
    params = {"limit": limit}
    if stance:
        params["stance"] = stance
    return api_get(base_url, "/scan/market", params)


def load_ticker_bundle(base_url: str, ticker: str, timeframe: str = "1G") -> dict:
    bundle: dict[str, dict | str] = {}
    for name, path in [
        ("company", f"/companies/{ticker}"),
        ("chart", f"/chart-features/{ticker}"),
        ("news", f"/news/history/{ticker}"),
        ("macro", f"/macro-events/history/{ticker}"),
        ("runs", f"/analysis-runs?ticker={ticker}&limit=5"),
    ]:
        try:
            if name == "runs":
                bundle[name] = api_get(base_url, "/analysis-runs", {"ticker": ticker, "limit": 5})
            elif name == "chart":
                bundle[name] = api_get(base_url, path, {"timeframe": timeframe})
            else:
                bundle[name] = api_get(base_url, path)
        except RuntimeError as exc:
            bundle[name] = str(exc)
    return bundle


def load_scan_history(base_url: str, limit: int = 5) -> dict | str:
    try:
        return api_get(base_url, "/scan/history", {"limit": limit})
    except RuntimeError as exc:
        return str(exc)


def load_runtime_health(base_url: str) -> dict | str:
    try:
        return api_get(base_url, "/health/runtime")
    except RuntimeError as exc:
        return str(exc)


def load_ohlcv_series(base_url: str, ticker: str, timeframe: str, bars: int) -> dict | str:
    try:
        return api_get(base_url, f"/market-data/{ticker}/ohlcv", {"timeframe": timeframe, "bars": bars})
    except RuntimeError as exc:
        return str(exc)


def load_market_debug(base_url: str, ticker: str, timeframe: str = "1G") -> dict | str:
    try:
        return api_get(base_url, f"/market-data/{ticker}/debug", {"timeframe": timeframe})
    except RuntimeError as exc:
        return str(exc)


def load_all_time_paper_trade_report(base_url: str) -> dict | str:
    try:
        return api_get(base_url, "/simulation/report/all-time")
    except RuntimeError as exc:
        return str(exc)


def load_llm_trace_summary(base_url: str, limit: int = 10) -> dict | str:
    try:
        return api_get(base_url, "/llm/traces/summary", {"limit": limit})
    except RuntimeError as exc:
        return str(exc)


def load_trading_safety_status(base_url: str) -> dict | str:
    try:
        return api_get(base_url, "/simulation/safety/status")
    except RuntimeError as exc:
        return str(exc)


def halt_trading_safety(base_url: str, reason: str) -> dict | str:
    try:
        return api_post(base_url, f"/simulation/safety/halt?reason={parse.quote(reason)}", {})
    except RuntimeError as exc:
        return str(exc)


def resume_trading_safety(base_url: str) -> dict | str:
    try:
        return api_post(base_url, "/simulation/safety/resume", {})
    except RuntimeError as exc:
        return str(exc)
