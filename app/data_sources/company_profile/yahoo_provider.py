import json
from urllib import error, parse, request

from app.core.config import settings


def _normalize_symbol(ticker: str) -> str:
    return f"{ticker.upper()}.IS"


def fetch_company_profile(ticker: str) -> dict | None:
    symbol = _normalize_symbol(ticker)
    query = parse.urlencode({"modules": "price,quoteType,assetProfile"})
    url = f"https://query1.finance.yahoo.com/v10/finance/quoteSummary/{symbol}?{query}"
    req = request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with request.urlopen(req, timeout=settings.yahoo_timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (error.URLError, error.HTTPError, TimeoutError, json.JSONDecodeError):
        return None

    quote_summary = payload.get("quoteSummary", {})
    results = quote_summary.get("result") or []
    if not results:
        return None

    result = results[0]
    price = result.get("price") or {}
    quote_type = result.get("quoteType") or {}
    asset_profile = result.get("assetProfile") or {}

    raw_name = price.get("longName") or quote_type.get("longName") or price.get("shortName") or quote_type.get("shortName")
    raw_sector = asset_profile.get("sector") or quote_type.get("sector")
    raw_industry = asset_profile.get("industry") or quote_type.get("industry")

    if not any([raw_name, raw_sector, raw_industry]):
        return None

    return {
        "ticker": ticker.upper(),
        "raw_name": raw_name,
        "raw_sector": raw_sector,
        "raw_industry": raw_industry,
        "provider": "yahoo_quote_summary",
    }
