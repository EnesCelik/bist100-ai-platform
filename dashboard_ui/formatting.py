def format_tr_number(value: float | int | None, decimals: int = 2) -> str:
    if value is None:
        return "-"
    formatted = f"{float(value):,.{decimals}f}"
    return formatted.replace(",", "_").replace(".", ",").replace("_", ".")


def format_tr_int(value: float | int | None) -> str:
    if value is None:
        return "-"
    return f"{int(round(float(value))):,}".replace(",", ".")


def humanize_slug(value: str | None) -> str:
    if not value:
        return "-"
    mapping = {
        "confirmed_breakout_up": "Yukari Kirilim Teyidi",
        "breakout_watch_up": "Yukari Kirilim Izleme",
        "confirmed_breakout_down": "Asagi Kirilim Teyidi",
        "breakout_watch_down": "Asagi Kirilim Izleme",
        "support_test": "Destek Testi",
        "resistance_test": "Direnc Testi",
        "range": "Yatay Bolge",
        "near_support": "Destege Yakin",
        "near_resistance": "Dirence Yakin",
        "mid_range": "Band Ortasi",
        "compressed_between_levels": "Sikisan Alan",
        "bullish": "Pozitif",
        "bearish": "Negatif",
        "neutral": "Dengeli",
        "higher_highs_and_higher_lows": "Yukselen Tepe ve Dipler",
        "lower_highs_near_support": "Dusuk Tepe ve Destek Baskisi",
        "mixed_stack": "Karisik Ortalama Dizilimi",
        "bullish_stack": "Pozitif Ortalama Dizilimi",
        "moderate": "Orta",
        "strong": "Guclu",
        "weak": "Zayif",
        "pullback_buy": "Destekten Alim",
        "trend_follow": "Trend Takibi",
        "breakout_watch": "Kirilim Izleme",
        "range_trade": "Bant Ici Islem",
        "sell_rally": "Tepki Satisi",
        "breakdown_watch": "Asagi Kirilim Izleme",
    }
    if value in mapping:
        return mapping[value]
    return value.replace("_", " ").title()


def build_readable_source(raw: str | None) -> str:
    if not raw:
        return "-"
    mapping = {
        "yahoo_delayed_market_data": "Yahoo Gecikmeli",
        "yahoo_delayed_market_data_cache": "Yahoo Cache",
        "mock_market_data_tool": "Mock Veri",
        "yahoo_delayed_ohlcv": "Yahoo OHLCV",
        "yahoo_delayed_ohlcv_cache": "Yahoo OHLCV Cache",
    }
    return mapping.get(raw, raw.replace("_", " ").title())


def build_runtime_status_label(value: str | None) -> str:
    mapping = {
        None: "-",
        "ok": "Hazir",
        "running": "Calisiyor",
        "error": "Hata",
    }
    return mapping.get(value, value or "-")


def summarize_mapping(values: dict | None, limit: int = 3) -> str:
    if not values:
        return "-"
    items = sorted(values.items(), key=lambda item: (-item[1], item[0]))[:limit]
    return " · ".join([f"{key}: {value}" for key, value in items])


def build_readable_technical_summary(raw: str | None) -> str:
    if not raw:
        return "-"
    parts = [part.strip() for part in raw.split("·")]
    if not parts:
        return raw
    normalized = []
    for part in parts:
        lower = part.lower()
        if lower.startswith("rsi"):
            normalized.append(part.upper().replace(" ", " "))
        else:
            normalized.append(humanize_slug(lower))
    return " · ".join(normalized)
