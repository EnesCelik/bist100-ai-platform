from app.models.schemas import MarketDataResponse


# Simdilik gercek bir broker ya da API baglantisi yok.
# Bu nedenle tool davranisini gostermek icin sahte ama tutarli bir veri kaynagi kullaniyoruz.
MOCK_MARKET_DATA = {
    "GARAN": {
        "ticker": "GARAN",
        "last_price": 128.40,
        "change_percent": 1.85,
        "volume": 15420000,
        "best_bid": 128.35,
        "best_ask": 128.45,
        "source": "mock_market_data_tool",
    },
    "THYAO": {
        "ticker": "THYAO",
        "last_price": 322.75,
        "change_percent": -0.62,
        "volume": 8450000,
        "best_bid": 322.50,
        "best_ask": 323.00,
        "source": "mock_market_data_tool",
    },
    "ASELS": {
        "ticker": "ASELS",
        "last_price": 71.90,
        "change_percent": 2.14,
        "volume": 26350000,
        "best_bid": 71.85,
        "best_ask": 71.95,
        "source": "mock_market_data_tool",
    },
}


def get_market_snapshot(ticker: str) -> MarketDataResponse | None:
    # Ticker degerini standart hale getiriyoruz ki kucuk/buyuk harf sorunu olmasin.
    normalized_ticker = ticker.upper()

    # Ilgili ticker icin mock veriyi bul.
    market_snapshot = MOCK_MARKET_DATA.get(normalized_ticker)
    if market_snapshot is None:
        return None

    # Ham sozlugu schema nesnesine cevirerek kontrollu veri dondur.
    return MarketDataResponse(**market_snapshot)
