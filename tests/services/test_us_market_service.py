"""ABD hisse fiyat servisinin saf eslesme mantigina testler.

`fetch_us_quote` ag cagrisi yaptigi icin burada monkeypatch ile izole
ediliyor - test edilen sey FMP'den gelen ham sozlugun dogru sekilde
`USStockQuoteResponse`'a esleniyor olmasi ve veri yokken/API anahtari
eksikken `available=False` ile sessizce (hata firlatmadan) donulmesi."""
from __future__ import annotations

from app.services import us_market_service as service


def test_quote_maps_all_fields_when_data_available(monkeypatch):
    monkeypatch.setattr(
        service,
        "fetch_us_quote",
        lambda ticker: {
            "ticker": "AAPL",
            "company_name": "Apple Inc.",
            "exchange": "NASDAQ",
            "last_price": 333.02,
            "change_percent": 1.09897,
            "change": 3.62,
            "volume": 49875295,
            "day_low": 330.1401,
            "day_high": 339.5,
            "year_low": 243.42,
            "year_high": 345.34,
            "previous_close": 329.4,
            "open": 330.8,
            "market_cap": 4891183295120,
        },
    )

    result = service.get_us_stock_quote("aapl")

    assert result.available is True
    assert result.ticker == "AAPL"
    assert result.company_name == "Apple Inc."
    assert result.last_price == 333.02
    assert result.source == "fmp_quote"
    assert result.message is None


def test_quote_unavailable_when_provider_returns_none(monkeypatch):
    # API anahtari eksik, sembol gecersiz veya FMP gecici hata verdiginde
    # provider None doner - servis bunu hata firlatmadan, acik bir
    # "available=False + mesaj" ile karsilamali.
    monkeypatch.setattr(service, "fetch_us_quote", lambda ticker: None)

    result = service.get_us_stock_quote("NOTATICKER")

    assert result.available is False
    assert result.last_price is None
    assert result.message is not None


def test_quote_uppercases_ticker_even_when_unavailable(monkeypatch):
    # Kucuk harfle girilen sembol, veri bulunamasa bile yanitta buyuk
    # harfle gorunmeli - tutarlilik icin (BIST servislerindeki ayni desen).
    monkeypatch.setattr(service, "fetch_us_quote", lambda ticker: None)

    result = service.get_us_stock_quote("msft")

    assert result.ticker == "MSFT"
