import json
from urllib import error, parse, request

from app.core.config import settings


def _normalize_symbol(ticker: str) -> str:
    return f"{ticker.upper()}.IS"


def fetch_company_profile(ticker: str) -> dict | None:
    if not settings.fmp_api_key:
        return None

    query = parse.urlencode({
        "symbol": _normalize_symbol(ticker),
        "apikey": settings.fmp_api_key,
    })
    url = f"{settings.fmp_base_url.rstrip('/')}/profile?{query}"
    req = request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with request.urlopen(req, timeout=settings.fmp_timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (error.URLError, error.HTTPError, TimeoutError, json.JSONDecodeError):
        return None

    if not isinstance(payload, list) or not payload:
        return None

    item = payload[0] or {}
    raw_name = item.get("companyName") or item.get("name")
    raw_sector = item.get("sector")
    raw_industry = item.get("industry")
    if not any([raw_name, raw_sector, raw_industry]):
        return None

    return {
        "ticker": ticker.upper(),
        "raw_name": raw_name,
        "raw_sector": raw_sector,
        "raw_industry": raw_industry,
        "provider": "fmp_profile",
    }
