def describe_signal_bias(value: str | None) -> str:
    mapping = {
        "bullish": "Genel teknik egilim pozitif",
        "bearish": "Genel teknik egilim negatif",
        "neutral": "Genel teknik egilim kararsiz",
    }
    return mapping.get(value or "", "Genel teknik egilim net degil")


def describe_breakout_state(value: str | None) -> str:
    mapping = {
        "confirmed_breakout_up": "Yukari kirilim hacimle teyit almis",
        "breakout_watch_up": "Yukari kirilim denemesi var, hacim teyidi izlenmeli",
        "resistance_test": "Fiyat direnc bolgesini test ediyor",
        "support_test": "Fiyat destek bolgesini test ediyor",
        "range": "Fiyat belirgin destek-direnc bandi icinde",
        "breakout_watch_down": "Asagi kirilim riski izlenmeli",
        "confirmed_breakout_down": "Asagi kirilim hacimle teyit almis",
    }
    return mapping.get(value or "", "Kirilim durumu net degil")


def describe_level_status(value: str | None) -> str:
    mapping = {
        "near_support": "Fiyat destek bolgesine yakin",
        "near_resistance": "Fiyat direnc bolgesine yakin",
        "compressed_between_levels": "Fiyat destek ve direnc arasinda sikismis",
        "mid_range": "Fiyat bandin orta bolgesinde",
    }
    return mapping.get(value or "", "Seviye konumu net degil")


def describe_macd_state(state: str | None, score: int | float | None = None) -> str:
    mapping = {
        "bullish_expanding": "MACD yukari momentumun guclendigini gosteriyor",
        "bullish_fading": "MACD pozitif tarafta ama momentum zayifliyor",
        "early_bullish_cross": "MACD erken pozitif kesisim sinyali veriyor",
        "bearish_expanding": "MACD asagi momentumun guclendigini gosteriyor",
        "bearish_fading": "MACD negatif tarafta ama satis momentumu zayifliyor",
        "early_bearish_cross": "MACD erken negatif kesisim uyarisi veriyor",
        "neutral": "MACD net bir yon teyidi vermiyor",
    }
    text = mapping.get(state or "", "MACD verisi net okunamadi")
    return _with_score(text, score)


def describe_ichimoku_state(state: str | None, score: int | float | None = None) -> str:
    mapping = {
        "above_cloud_bullish": "Ichimoku tarafinda fiyat bulutun ustunde ve trend kalitesi guclu",
        "above_cloud_mixed": "Ichimoku tarafinda fiyat bulutun ustunde ama teyitler karisik",
        "inside_cloud_neutral": "Ichimoku bulutu icinde karar bolgesi devam ediyor",
        "below_cloud_bearish": "Ichimoku tarafinda fiyat bulutun altinda ve trend zayif",
        "below_cloud_mixed": "Ichimoku tarafinda fiyat bulutun altinda, toparlanma icin teyit gerekiyor",
        "cloud_unknown": "Ichimoku icin yeterli veya guvenilir bulut verisi yok",
    }
    text = mapping.get(state or "", "Ichimoku verisi net okunamadi")
    return _with_score(text, score)


def describe_trend_channel_state(state: str | None, score: int | float | None = None) -> str:
    mapping = {
        "rising_mid_channel": "Trend kanali yukari egimli ve fiyat saglikli orta bolgede",
        "rising_channel_pullback": "Yukselen kanalda fiyat geri cekilme bolgesinde, tepki potansiyeli var",
        "rising_upper_channel_extended": "Yukselen kanal ust bandina yakin; yeni alimda kovalamaca riski var",
        "rising_channel_overextended": "Fiyat yukselen kanalin ustune tasmis; hareket guclu ama riskli uzamis",
        "rising_channel_breakdown_watch": "Fiyat yukselen kanalin altina sarkmis; trend yorulmasi izlenmeli",
        "falling_channel": "Trend kanali asagi egimli; tepki denemeleri zayif kalabilir",
        "falling_lower_channel": "Fiyat dusen kanalin alt bolgesinde; baski suruyor",
        "falling_channel_breakdown": "Fiyat dusen kanalin da altina sarkmis; satis riski yuksek",
        "sideways_upper_channel": "Yatay kanal ust bandina yakin; kar satisi riski artiyor",
        "sideways_lower_channel": "Yatay kanal alt bandina yakin; tepki potansiyeli olusabilir",
        "sideways_mid_channel": "Yatay kanal ortasinda; yon teyidi henuz net degil",
    }
    text = mapping.get(state or "", "Trend kanali verisi net okunamadi")
    return _with_score(text, score)


def describe_fibonacci_position(position: str | None, score: int | float | None = None) -> str:
    mapping = {
        "near_swing_high": "Fibonacci acisindan fiyat tepe bolgesine yakin; yeni alimda mesafe riski var",
        "above_382": "Fibonacci tarafinda fiyat 0.382 ustunde kalarak tepki gucunu koruyor",
        "above_382_near_reaction_level": "Fiyat Fibonacci tepki seviyesine yakin ve 0.382 ustunu koruyor",
        "between_382_618": "Fiyat Fibonacci 0.382-0.618 araliginda, karar bolgesi devam ediyor",
        "between_382_618_near_reaction_level": "Fiyat Fibonacci tepki bandina yakin, toparlanma icin izlenebilir",
        "below_618_watch": "Fiyat Fibonacci 0.618 altina yakin; zayiflama riski izlenmeli",
        "below_618_watch_near_reaction_level": "Fiyat Fibonacci 0.618 cevresinde tepki ariyor ama teyit gerekiyor",
        "below_618_watch_near_risk_level": "Fiyat Fibonacci kritik risk seviyesine yakin; asagi kirilim riski var",
        "deep_retracement": "Fibonacci acisindan derin geri cekilme var",
        "deep_retracement_near_risk_level": "Fibonacci derin geri cekilme ve kritik risk bolgesini gosteriyor",
        "fib_unknown": "Fibonacci icin yeterli veya guvenilir seviye verisi yok",
    }
    text = mapping.get(position or "", "Fibonacci verisi net okunamadi")
    return _with_score(text, score)


def build_indicator_summary(details: dict[str, str | float | int]) -> str:
    if not details:
        return "Teknik detay okunamadi."
    return " ".join(
        [
            describe_macd_state(str(details.get("macd_state") or ""), details.get("macd_score")),
            describe_ichimoku_state(str(details.get("ichimoku_state") or ""), details.get("ichimoku_score")),
            describe_trend_channel_state(
                str(details.get("trend_channel_state") or ""),
                details.get("trend_channel_score"),
            ),
            describe_fibonacci_position(
                str(details.get("fibonacci_position") or ""),
                details.get("fibonacci_score"),
            ),
        ]
    )


def humanize_label(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if not text:
        return ""
    mapping = {
        "buyable_momentum": "alinabilir momentum",
        "missed_no_fill": "kacirilmis veya emir gerceklesmesi zor aday",
        "watch_no_chase": "izle, fiyat kovalanmamali",
        "watch_spread_risk": "izle, spread riski var",
        "watch_only": "sadece izle",
        "watch_preopen": "acilis oncesi izle",
        "watch_only_no_order_flow": "emir akisi olmadigi icin sadece izle",
        "secondary_watch": "ikincil izleme adayi",
        "avoid_reversal_risk": "geri donus riski nedeniyle kacin",
        "hold_cash": "nakitte kal",
        "selective_add_watch": "secici ek alim icin izle",
        "opened_paper_basket": "sanal sepet acildi",
        "opening_plan": "acilis plani",
        "position_decision": "pozisyon karari",
        "monitor": "izleme",
        "reduce_or_exit": "azalt veya cik",
        "simulated_partial_reduce": "sanal kismi satis",
        "simulated_reduce": "sanal azaltma",
        "watch_reduced_position": "azaltilmis pozisyonu izle",
        "watch_for_reversal": "toparlanma ihtimali icin izle",
        "hold_with_protected_profit": "kar korumali tasima",
        "evaluated_open_positions": "acik pozisyonlar degerlendirildi",
        "monitored_open_trades": "acik islemler izlendi",
        "finalized_open_trades": "acik islemler gun sonu kapatildi",
        "generated_daily_report": "gunluk rapor olusturuldu",
        "strong_candidate": "guclu aday",
        "candidate": "aday",
        "watch_candidate": "izleme adayi",
        "weak_candidate": "zayif aday",
        "open_small": "kucuk pozisyon ac",
        "open": "pozisyon ac",
        "buy": "al",
        "sell": "sat",
        "hold_cash": "nakitte kal",
        "hold": "tasi",
        "skip": "pas gec",
        "watch": "izle",
        "exit": "cik",
        "reduce": "azalt",
        "bullish": "pozitif",
        "bearish": "negatif",
        "neutral": "notr",
        "risk_on": "risk almaya uygun",
        "risk_off": "riskten kacinma modu",
        "high": "yuksek",
        "medium": "orta",
        "low": "dusuk",
        "fresh_matriks": "guncel Matriks verisi",
        "matriks_ohlcv": "Matriks fiyat grafigi verisi",
        "matriks_market_data_tool": "Matriks canli piyasa verisi",
        "intraday_upside_scanner": "gun ici yukari potansiyel taramasi",
        "pre_open_limit_up_scanner": "acilis oncesi tavan izleme taramasi",
        "pre_market_watchlist_scan": "acilis oncesi izleme listesi taramasi",
        "market_scan_service": "genel piyasa taramasi",
        "chart_feature_signal_service": "grafik sinyal motoru",
        "all_open_strategies": "tum acik stratejiler",
        "agent_opening_basket": "agent acilis sepeti",
        "manual_morning_basket": "manuel sabah sepeti",
        "intraday_gain_candidate": "gun ici yukselis adayi",
        "limit_up_watch": "tavan izleme adayi",
        "limit_up_locked": "tavan kilidine yakin aday",
        "positive_momentum": "pozitif momentum",
        "strong_intraday_momentum": "guclu gun ici momentum",
        "high_momentum_gap_watch": "yuksek momentumlu bosluk izleme",
        "closing_strength_breakout_watch": "kapanis gucu kirilim izleme",
        "technical_continuation_watch": "teknik devam izleme",
        "low_conviction_watch": "dusuk guvenli izleme",
        "trend_follow": "trend takip",
        "pullback_buy": "geri cekilme alim kurgusu",
        "breakout_buy": "kirilim alim kurgusu",
        "range_trade": "bant ici islem kurgusu",
        "avoid_or_invalidated": "kacin veya gecersiz sinyal",
        "no_fill": "emir gerceklesmesi zor",
        "healthy_spread": "saglikli spread",
        "wide_spread": "genis spread",
        "strong_bid_pressure": "guclu alis baskisi",
        "strong_ask_pressure": "guclu satis baskisi",
        "none": "yok",
    }
    if text in mapping:
        return mapping[text]
    if "_" not in text:
        return text
    return text.replace("_", " ")


def _with_score(text: str, score: int | float | None) -> str:
    if score is None:
        return f"{text}."
    return f"{text} (katki: {score})."
