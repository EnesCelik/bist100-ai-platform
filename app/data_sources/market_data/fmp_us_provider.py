"""ABD borsalarinda (NASDAQ/NYSE) islem goren hisseler icin FMP (Financial
Modeling Prep) uzerinden canli/gecikmeli fiyat verisi.

Neden ayri bir dosya: `app/data_sources/company_profile/fmp_provider.py` zaten
var ama o sadece BIST sirketleri icin sirket profili (isim/sektor) cekiyor ve
sembole sabit ".IS" sonu ekliyor. Burada ihtiyac farkli - ABD sembolleri
(orn. "AAPL") hic suffix almadan, ve profil degil CANLI FIYAT (quote)
istiyoruz. Ayni FMP API anahtarini (`settings.fmp_api_key`) kullaniyor ama
tamamen farkli bir endpoint'e (/quote) gidiyor.

Bu, kullanicinin Garanti hesabiyla/token'iyla hicbir ilgisi olmayan, bizim
platformun kendi (ayrica abone oldugumuz) FMP anahtarini kullanan bagimsiz
bir veri kaynagi."""
from __future__ import annotations

import json
from urllib import error, parse, request

from app.core.config import settings


def fetch_us_quote(ticker: str) -> dict | None:
    if not settings.fmp_api_key:
        return None

    symbol = ticker.upper().strip()
    query = parse.urlencode({"symbol": symbol, "apikey": settings.fmp_api_key})
    url = f"{settings.fmp_base_url.rstrip('/')}/quote?{query}"
    req = request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with request.urlopen(req, timeout=settings.fmp_timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (error.URLError, error.HTTPError, TimeoutError, json.JSONDecodeError):
        return None

    if not isinstance(payload, list) or not payload:
        return None

    item = payload[0] or {}
    if item.get("price") is None:
        return None

    return {
        "ticker": symbol,
        "company_name": item.get("name"),
        "exchange": item.get("exchange"),
        "last_price": item.get("price"),
        "change_percent": item.get("changePercentage"),
        "change": item.get("change"),
        "volume": item.get("volume"),
        "day_low": item.get("dayLow"),
        "day_high": item.get("dayHigh"),
        "year_low": item.get("yearLow"),
        "year_high": item.get("yearHigh"),
        "previous_close": item.get("previousClose"),
        "open": item.get("open"),
        "market_cap": item.get("marketCap"),
    }
