from app.models.schemas import SignalResponse
from app.services.chart_feature_service import get_chart_feature_summary

SIGNAL_SOURCE = "chart_feature_signal_service"


def _strength_label(value: str) -> str:
    mapping = {
        "strong": "guclu",
        "moderate": "orta",
        "weak": "zayif",
    }
    return mapping.get(value.lower(), value)


def build_signal_summary_from_chart_feature(feature_summary) -> SignalResponse | None:
    if feature_summary is None:
        return None

    positive_factors: list[str] = []
    negative_factors: list[str] = []

    if feature_summary.signal_bias == "bullish":
        positive_factors.append(
            f"Teknik gorunum {_strength_label(feature_summary.signal_strength)} pozitif bias tasiyor"
        )
    elif feature_summary.signal_bias == "neutral":
        positive_factors.append("Teknik gorunum tamamen bozulmadan denge ariyor")
    else:
        negative_factors.append(
            f"Teknik gorunum {_strength_label(feature_summary.signal_strength)} negatif bias uretmeye basladi"
        )

    if feature_summary.breakout_state in {"confirmed_breakout_up", "breakout_watch_up"}:
        positive_factors.append("Kirilim yapisi yukari yone donus sinyali veriyor")
    elif feature_summary.breakout_state in {"confirmed_breakout_down", "breakout_watch_down"}:
        negative_factors.append("Kirilim yapisi asagi yone baski riski uretiyor")

    if feature_summary.level_status in {"near_support", "compressed_between_levels"} and feature_summary.structure_bias != "bearish":
        positive_factors.append("Fiyat seviyeleri tepki veya sikisma kaynakli yon arayisi sunuyor")
    if feature_summary.level_status == "near_resistance":
        negative_factors.append("Dirence yakin seyir yukari hareketin teyit ihtiyacini artiriyor")

    if feature_summary.rsi14 >= 72:
        negative_factors.append("Momentum guclu olsa da RSI asiri isinma bolgesine yaklasiyor")
    elif feature_summary.rsi14 <= 45:
        negative_factors.append("Momentum zayif; RSI tepki gucunun sinirli kalabilecegini soyluyor")

    if feature_summary.macd_score > 0:
        positive_factors.append("MACD momentum katmani pozitif teyit uretiyor")
    elif feature_summary.macd_score < 0:
        negative_factors.append("MACD momentum katmani negatif uyari uretiyor")

    if feature_summary.ichimoku_score > 0:
        positive_factors.append("Ichimoku bulutu trend kalitesini destekliyor")
    elif feature_summary.ichimoku_score < 0:
        negative_factors.append("Ichimoku bulutu trend kalitesinde zayiflama gosteriyor")

    if feature_summary.trend_channel_score > 0:
        positive_factors.append("Trend kanali fiyat hareketini destekleyen bolgede")
    elif feature_summary.trend_channel_score < 0:
        negative_factors.append("Trend kanali fiyat hareketinde riskli bolgeye isaret ediyor")

    return SignalResponse(
        ticker=feature_summary.ticker,
        direction=feature_summary.signal_bias,
        strength=feature_summary.signal_strength,
        positive_factors=positive_factors[:4],
        negative_factors=negative_factors[:4],
        source=SIGNAL_SOURCE,
    )


# Signal katmani teknik feature'lari tekrar yazmak yerine daha ozet bir yorum katmani uretir.
def get_signal_summary(ticker: str) -> SignalResponse | None:
    feature_summary = get_chart_feature_summary(ticker)
    return build_signal_summary_from_chart_feature(feature_summary)
