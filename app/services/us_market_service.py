"""ABD borsalari icin ince bir servis katmani - `fmp_us_provider`'in ham
sozlugunu `USStockQuoteResponse` semasina ceviriyor. Bu sayede BIST
servislerindeki "available=False + mesaj" deseni ABD hisseleri icin de
tutarli kaliyor."""
from __future__ import annotations

from app.core.config import settings
from app.data_sources.market_data.fmp_us_provider import fetch_us_quote
from app.models.schemas import USStockQuoteResponse

US_QUOTE_SOURCE_NAME = "fmp_quote"


def get_us_stock_quote(ticker: str) -> USStockQuoteResponse:
    data = fetch_us_quote(ticker)
    if data is None:
        return USStockQuoteResponse(
            ticker=ticker.upper(),
            available=False,
            source=US_QUOTE_SOURCE_NAME,
            message="FMP'den bu sembol icin fiyat alinamadi (gecersiz sembol, API anahtari yapilandirilmamis veya gecici bir hata olabilir).",
        )

    return USStockQuoteResponse(
        ticker=data["ticker"],
        available=True,
        company_name=data.get("company_name"),
        exchange=data.get("exchange"),
        last_price=data.get("last_price"),
        change_percent=data.get("change_percent"),
        change=data.get("change"),
        volume=data.get("volume"),
        day_low=data.get("day_low"),
        day_high=data.get("day_high"),
        year_low=data.get("year_low"),
        year_high=data.get("year_high"),
        previous_close=data.get("previous_close"),
        open=data.get("open"),
        market_cap=data.get("market_cap"),
        source=US_QUOTE_SOURCE_NAME,
        message=None,
    )


def get_us_watchlist_quotes() -> list[USStockQuoteResponse]:
    return [get_us_stock_quote(ticker) for ticker in settings.us_watchlist_tickers]
