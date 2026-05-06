import json
from urllib import error, parse, request

from app.core.config import settings


def _normalize_symbol(ticker: str) -> str:
    return f"{ticker.upper()}.IS"


def fetch_company_profile(ticker: str) -> dict | None:
    if not settings.eodhd_api_token:
        return None

    symbol = _normalize_symbol(ticker)
    query = parse.urlencode({"api_token": settings.eodhd_api_token, "fmt": "json"})
    url = f"{settings.eodhd_base_url.rstrip('/')}/fundamentals/{symbol}?{query}"
    req = request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with request.urlopen(req, timeout=settings.eodhd_timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (error.URLError, error.HTTPError, TimeoutError, json.JSONDecodeError):
        return None

    if not isinstance(payload, dict):
        return None

    general = payload.get("General") or {}
    raw_name = general.get("Name") or general.get("Code")
    raw_sector = general.get("Sector")
    raw_industry = general.get("Industry")
    if not any([raw_name, raw_sector, raw_industry]):
        return None

    return {
        "ticker": ticker.upper(),
        "raw_name": raw_name,
        "raw_sector": raw_sector,
        "raw_industry": raw_industry,
        "provider": "eodhd_fundamentals",
    }
