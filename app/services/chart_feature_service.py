from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
from fastapi import HTTPException

from app.data_sources.market_data.provider import get_market_ohlcv, get_market_snapshot
from app.models.schemas import ChartFeatureResponse

CHART_FEATURE_SOURCE = "fallback_chart_feature_profile"
REAL_CHART_FEATURE_SOURCE = "ohlcv_chart_feature_engine"


@dataclass(frozen=True)
class ChartFeatureProfile:
    current_price: float
    ema20: float
    ema50: float
    ema200: float
    rsi14: float
    avg_volume: int
    support: float
    resistance: float
    atr_percent: float
    market_structure: str


CHART_FEATURE_PROFILES: dict[str, ChartFeatureProfile] = {
    "GARAN": ChartFeatureProfile(
        current_price=128.40,
        ema20=126.80,
        ema50=123.90,
        ema200=118.70,
        rsi14=61.5,
        avg_volume=13200000,
        support=125.50,
        resistance=129.80,
        atr_percent=1.8,
        market_structure="higher_highs_and_higher_lows",
    ),
    "THYAO": ChartFeatureProfile(
        current_price=322.75,
        ema20=324.10,
        ema50=326.80,
        ema200=301.20,
        rsi14=43.8,
        avg_volume=9400000,
        support=318.00,
        resistance=327.00,
        atr_percent=2.7,
        market_structure="lower_highs_near_support",
    ),
    "ASELS": ChartFeatureProfile(
        current_price=71.90,
        ema20=69.80,
        ema50=66.70,
        ema200=58.20,
        rsi14=67.2,
        avg_volume=21800000,
        support=69.40,
        resistance=72.50,
        atr_percent=2.4,
        market_structure="higher_highs_and_higher_lows",
    ),
    "EREGL": ChartFeatureProfile(
        current_price=48.60,
        ema20=47.90,
        ema50=46.50,
        ema200=44.10,
        rsi14=57.0,
        avg_volume=31000000,
        support=47.20,
        resistance=49.80,
        atr_percent=2.1,
        market_structure="range_turning_up",
    ),
}


@dataclass(frozen=True)
class DerivedLevelMetrics:
    support_gap_percent: float
    resistance_gap_percent: float
    price_position_percent: float
    level_status: str


@dataclass(frozen=True)
class DerivedStructureMetrics:
    structure_bias: str
    structure_score: int


@dataclass(frozen=True)
class DerivedBreakoutMetrics:
    breakout_state: str
    breakout_score: int


@dataclass(frozen=True)
class DerivedSignalMetrics:
    signal_bias: str
    signal_strength: str
    signal_score: int


@dataclass(frozen=True)
class DerivedMacdMetrics:
    macd_line: float
    macd_signal: float
    macd_histogram: float
    macd_state: str
    macd_score: int


@dataclass(frozen=True)
class DerivedIchimokuMetrics:
    tenkan: float
    kijun: float
    cloud_top: float
    cloud_bottom: float
    ichimoku_state: str
    ichimoku_score: int


@dataclass(frozen=True)
class DerivedTrendChannelMetrics:
    channel_upper: float
    channel_mid: float
    channel_lower: float
    slope_percent: float
    position_percent: float
    channel_state: str
    channel_score: int


@dataclass(frozen=True)
class DerivedFibonacciMetrics:
    swing_high: float
    swing_low: float
    nearest_level: float
    fib_position: str
    fib_score: int


@dataclass(frozen=True)
class DerivedTradeLevels:
    trend_reference_level: float
    entry_zone_low: float
    entry_zone_high: float
    breakout_buy_trigger: float
    breakdown_sell_trigger: float
    take_profit_level: float
    stop_loss_level: float
    trade_setup: str
    risk_reward_ratio: float
    level_commentary: str


def _build_trade_level_factors(
    price: float,
    trend: str,
    breakout_metrics: DerivedBreakoutMetrics,
    level_metrics: DerivedLevelMetrics,
    trade_levels: DerivedTradeLevels,
) -> tuple[list[str], list[str]]:
    positive_factors: list[str] = []
    negative_factors: list[str] = []

    if trade_levels.risk_reward_ratio >= 1.8:
        positive_factors.append("Seviye plani kabul edilebilir risk/odul dengesiyle alici lehine kaliyor")
    elif trade_levels.risk_reward_ratio < 1.15:
        negative_factors.append("Mevcut seviye plani risk/odul dengesini zayiflatarak yeni islem kalitesini dusuruyor")

    if trend == "bullish":
        if price <= trade_levels.entry_zone_high * 1.02:
            positive_factors.append("Fiyat tanimli giris bolgesine yakin kalarak kontrollu alim ihtimalini koruyor")
        elif price > trade_levels.entry_zone_high * 1.05 and breakout_metrics.breakout_state == "range":
            negative_factors.append("Fiyat giris bolgesinden uzaklastigi icin yeni alimda kovalamaca riski artiyor")

        if breakout_metrics.breakout_state in {"breakout_watch_up", "confirmed_breakout_up"}:
            positive_factors.append("Kirilim seviyesi yakin oldugu icin yukari teyit halinde hizli ivme gelebilir")

    if trend == "neutral" and trade_levels.trade_setup == "range_trade" and level_metrics.price_position_percent >= 75:
        negative_factors.append("Bant ust bolgesine yakin seyir yeni alim icin risk/odul dengesini sinirliyor")

    if trend == "bearish" and breakout_metrics.breakout_state in {"breakout_watch_down", "confirmed_breakout_down"}:
        positive_factors.append("Asagi kirilim seviyesine yakinlik satis yonlu senaryoyu daha net hale getiriyor")

    return positive_factors[:3], negative_factors[:3]


@dataclass(frozen=True)
class ComputedTechnicalMetrics:
    price: float
    ema20: float
    ema50: float
    ema200: float
    rsi14: float
    current_volume: int
    avg_volume: int
    support: float
    resistance: float
    atr_percent: float
    market_structure: str
    source: str
    macd: DerivedMacdMetrics
    ichimoku: DerivedIchimokuMetrics
    trend_channel: DerivedTrendChannelMetrics
    fibonacci: DerivedFibonacciMetrics



def _round(value: float) -> float:
    return round(value, 2)



def _build_dataframe_from_ohlcv(ticker: str, timeframe: str = "1G", as_of_timestamp: str | None = None) -> pd.DataFrame | None:
    bars = 220 if timeframe.upper() == "1H" else 160
    payload = get_market_ohlcv(ticker, timeframe=timeframe, bars=bars)
    if payload is None or not payload.candles:
        return None
    rows = [bar.model_dump() for bar in payload.candles]
    df = pd.DataFrame(rows)
    if df.empty:
        return None
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.sort_values("timestamp").reset_index(drop=True)
    df.attrs["ohlcv_source"] = payload.source
    if as_of_timestamp:
        cutoff = pd.to_datetime(as_of_timestamp, utc=True)
        df = df[df["timestamp"] <= cutoff].reset_index(drop=True)
        df.attrs["ohlcv_source"] = payload.source
    return df if not df.empty else None



def _compute_rsi(close: pd.Series, period: int = 14) -> float:
    delta = close.diff()
    gains = delta.clip(lower=0)
    losses = -delta.clip(upper=0)
    avg_gain = gains.rolling(period, min_periods=period).mean()
    avg_loss = losses.rolling(period, min_periods=period).mean()
    if avg_gain.empty or avg_loss.empty:
        return 50.0
    rs = avg_gain / avg_loss.replace(0, pd.NA)
    rsi = 100 - (100 / (1 + rs))
    value = rsi.dropna()
    if value.empty:
        if avg_loss.dropna().empty:
            return 50.0
        return 100.0 if float(avg_loss.dropna().iloc[-1]) == 0 else 50.0
    return float(value.iloc[-1])



def _compute_atr_percent(df: pd.DataFrame, period: int = 14) -> float:
    prev_close = df["close"].shift(1)
    tr = pd.concat(
        [
            df["high"] - df["low"],
            (df["high"] - prev_close).abs(),
            (df["low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    atr = tr.rolling(period, min_periods=period).mean().dropna()
    if atr.empty:
        return 2.0
    close_value = max(float(df["close"].iloc[-1]), 1.0)
    return float((atr.iloc[-1] / close_value) * 100)


def _default_advanced_metrics(
    price: float,
    support: float,
    resistance: float,
    trend: str | None = None,
) -> tuple[DerivedMacdMetrics, DerivedIchimokuMetrics, DerivedTrendChannelMetrics, DerivedFibonacciMetrics]:
    neutral_macd = DerivedMacdMetrics(0.0, 0.0, 0.0, "neutral", 0)
    neutral_ichimoku = DerivedIchimokuMetrics(
        tenkan=_round(price),
        kijun=_round(price),
        cloud_top=_round(max(price, resistance)),
        cloud_bottom=_round(min(price, support)),
        ichimoku_state="cloud_unknown",
        ichimoku_score=0,
    )
    price_range = max(resistance - support, 0.0001)
    position = ((price - support) / price_range) * 100
    neutral_channel = DerivedTrendChannelMetrics(
        channel_upper=_round(resistance),
        channel_mid=_round((support + resistance) / 2),
        channel_lower=_round(support),
        slope_percent=0.0,
        position_percent=_round(max(0.0, min(position, 100.0))),
        channel_state=f"{trend or 'neutral'}_channel_unknown",
        channel_score=0,
    )
    neutral_fib = DerivedFibonacciMetrics(
        swing_high=_round(resistance),
        swing_low=_round(support),
        nearest_level=_round(price),
        fib_position="fib_unknown",
        fib_score=0,
    )
    return neutral_macd, neutral_ichimoku, neutral_channel, neutral_fib


def _compute_macd_metrics(close: pd.Series) -> DerivedMacdMetrics:
    if len(close) < 35:
        return _default_advanced_metrics(float(close.iloc[-1]), float(close.min()), float(close.max()))[0]
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd_line_series = ema12 - ema26
    signal_series = macd_line_series.ewm(span=9, adjust=False).mean()
    histogram_series = macd_line_series - signal_series
    macd_line = float(macd_line_series.iloc[-1])
    signal = float(signal_series.iloc[-1])
    histogram = float(histogram_series.iloc[-1])
    previous_histogram = float(histogram_series.iloc[-2]) if len(histogram_series) >= 2 else histogram
    expanding = histogram > previous_histogram

    if macd_line > signal and histogram > 0:
        state = "bullish_expanding" if expanding else "bullish_fading"
        score = 2 if expanding else 1
    elif macd_line < signal and histogram < 0:
        state = "bearish_expanding" if histogram < previous_histogram else "bearish_fading"
        score = -2 if histogram < previous_histogram else -1
    elif macd_line > signal:
        state = "early_bullish_cross"
        score = 1
    elif macd_line < signal:
        state = "early_bearish_cross"
        score = -1
    else:
        state = "neutral"
        score = 0

    return DerivedMacdMetrics(_round(macd_line), _round(signal), _round(histogram), state, score)


def _compute_ichimoku_metrics(df: pd.DataFrame) -> DerivedIchimokuMetrics:
    if len(df) < 52:
        price = float(df["close"].iloc[-1])
        return _default_advanced_metrics(price, float(df["low"].min()), float(df["high"].max()))[1]

    high = df["high"]
    low = df["low"]
    close = df["close"]
    tenkan = (high.rolling(9).max() + low.rolling(9).min()) / 2
    kijun = (high.rolling(26).max() + low.rolling(26).min()) / 2
    senkou_a = (tenkan + kijun) / 2
    senkou_b = (high.rolling(52).max() + low.rolling(52).min()) / 2
    tenkan_value = float(tenkan.iloc[-1])
    kijun_value = float(kijun.iloc[-1])
    span_a = float(senkou_a.iloc[-1])
    span_b = float(senkou_b.iloc[-1])
    price = float(close.iloc[-1])
    cloud_top = max(span_a, span_b)
    cloud_bottom = min(span_a, span_b)

    if price > cloud_top and tenkan_value > kijun_value and span_a >= span_b:
        state, score = "above_cloud_bullish", 2
    elif price > cloud_top:
        state, score = "above_cloud_mixed", 1
    elif price < cloud_bottom and tenkan_value < kijun_value and span_a <= span_b:
        state, score = "below_cloud_bearish", -2
    elif price < cloud_bottom:
        state, score = "below_cloud_mixed", -1
    else:
        state, score = "inside_cloud_neutral", 0

    return DerivedIchimokuMetrics(
        tenkan=_round(tenkan_value),
        kijun=_round(kijun_value),
        cloud_top=_round(cloud_top),
        cloud_bottom=_round(cloud_bottom),
        ichimoku_state=state,
        ichimoku_score=score,
    )


def _linear_regression_line(values: list[float]) -> tuple[float, float]:
    n = len(values)
    if n <= 1:
        return 0.0, values[-1] if values else 0.0
    x_mean = (n - 1) / 2
    y_mean = sum(values) / n
    numerator = sum((index - x_mean) * (value - y_mean) for index, value in enumerate(values))
    denominator = sum((index - x_mean) ** 2 for index in range(n)) or 1.0
    slope = numerator / denominator
    intercept = y_mean - slope * x_mean
    return slope, intercept


def _compute_trend_channel_metrics(df: pd.DataFrame, window: int = 60) -> DerivedTrendChannelMetrics:
    recent = df.tail(min(window, len(df)))
    close_values = [float(value) for value in recent["close"].tolist()]
    price = float(recent["close"].iloc[-1])
    if len(close_values) < 20:
        return _default_advanced_metrics(price, float(recent["low"].min()), float(recent["high"].max()))[2]

    slope, intercept = _linear_regression_line(close_values)
    fitted = [intercept + slope * index for index in range(len(close_values))]
    residuals = [abs(value - fitted[index]) for index, value in enumerate(close_values)]
    channel_width = max(sum(residuals) / len(residuals) * 1.8, price * 0.01)
    mid = fitted[-1]
    upper = mid + channel_width
    lower = mid - channel_width
    span = max(upper - lower, 0.0001)
    raw_position = ((price - lower) / span) * 100
    position = max(0.0, min(raw_position, 100.0))
    slope_percent = ((fitted[-1] - fitted[0]) / max(abs(fitted[0]), 1.0)) * 100

    if slope_percent >= 2.0 and raw_position < -8:
        state, score = "rising_channel_breakdown_watch", -1
    elif slope_percent >= 2.0 and raw_position > 110:
        state, score = "rising_channel_overextended", -1
    elif slope_percent >= 2.0 and 25 <= position <= 78:
        state, score = "rising_mid_channel", 2
    elif slope_percent >= 2.0 and position > 86:
        state, score = "rising_upper_channel_extended", 0
    elif slope_percent >= 2.0:
        state, score = "rising_channel_pullback", 1
    elif slope_percent <= -2.0 and raw_position < -8:
        state, score = "falling_channel_breakdown", -2
    elif slope_percent <= -2.0 and position < 35:
        state, score = "falling_lower_channel", -2
    elif slope_percent <= -2.0:
        state, score = "falling_channel", -1
    elif position > 85:
        state, score = "sideways_upper_channel", -1
    elif position < 20:
        state, score = "sideways_lower_channel", 1
    else:
        state, score = "sideways_mid_channel", 0

    return DerivedTrendChannelMetrics(
        channel_upper=_round(upper),
        channel_mid=_round(mid),
        channel_lower=_round(lower),
        slope_percent=_round(slope_percent),
        position_percent=_round(position),
        channel_state=state,
        channel_score=score,
    )


def _compute_fibonacci_metrics(df: pd.DataFrame, window: int = 80) -> DerivedFibonacciMetrics:
    recent = df.tail(min(window, len(df)))
    price = float(recent["close"].iloc[-1])
    swing_high = float(recent["high"].max())
    swing_low = float(recent["low"].min())
    swing_range = swing_high - swing_low
    if swing_range <= 0:
        return _default_advanced_metrics(price, swing_low, swing_high)[3]

    levels = {
        "fib_236": swing_high - swing_range * 0.236,
        "fib_382": swing_high - swing_range * 0.382,
        "fib_500": swing_high - swing_range * 0.500,
        "fib_618": swing_high - swing_range * 0.618,
        "fib_786": swing_high - swing_range * 0.786,
    }
    nearest_name, nearest_value = min(levels.items(), key=lambda item: abs(price - item[1]))
    tolerance = max(price * 0.008, swing_range * 0.025)

    if price >= levels["fib_236"]:
        position, score = "near_swing_high", 0
    elif price >= levels["fib_382"]:
        position, score = "above_382", 1
    elif price >= levels["fib_618"]:
        position, score = "between_382_618", 0
    elif price >= levels["fib_786"]:
        position, score = "below_618_watch", -1
    else:
        position, score = "deep_retracement", -2

    if abs(price - nearest_value) <= tolerance:
        if nearest_name in {"fib_382", "fib_500", "fib_618"} and position != "deep_retracement":
            score += 1
            position = f"{position}_near_reaction_level"
        elif nearest_name == "fib_786":
            score -= 1
            position = f"{position}_near_risk_level"

    return DerivedFibonacciMetrics(
        swing_high=_round(swing_high),
        swing_low=_round(swing_low),
        nearest_level=_round(float(nearest_value)),
        fib_position=position,
        fib_score=max(-2, min(score, 2)),
    )


def _compute_advanced_metrics(df: pd.DataFrame) -> tuple[DerivedMacdMetrics, DerivedIchimokuMetrics, DerivedTrendChannelMetrics, DerivedFibonacciMetrics]:
    return (
        _compute_macd_metrics(df["close"]),
        _compute_ichimoku_metrics(df),
        _compute_trend_channel_metrics(df),
        _compute_fibonacci_metrics(df),
    )



def _derive_market_structure_from_series(df: pd.DataFrame) -> str:
    if len(df) < 20:
        return "range_turning_up"

    recent = df.tail(10)
    prior = df.iloc[-20:-10]
    if prior.empty:
        return "range_turning_up"

    recent_high = float(recent["high"].max())
    prior_high = float(prior["high"].max())
    recent_low = float(recent["low"].min())
    prior_low = float(prior["low"].min())
    last_close = float(df["close"].iloc[-1])
    ema20 = float(df["close"].ewm(span=20, adjust=False).mean().iloc[-1])

    if recent_high > prior_high and recent_low > prior_low:
        return "higher_highs_and_higher_lows"
    if recent_high < prior_high and recent_low < prior_low:
        return "lower_highs_and_lower_lows"
    if recent_high < prior_high and last_close <= ema20:
        return "lower_highs_near_support"
    if recent_high >= prior_high and last_close >= ema20:
        return "range_turning_up"
    return "range_turning_down"



def _compute_metrics_from_ohlcv(ticker: str, timeframe: str = "1G", as_of_timestamp: str | None = None) -> ComputedTechnicalMetrics | None:
    df = _build_dataframe_from_ohlcv(ticker, timeframe=timeframe, as_of_timestamp=as_of_timestamp)
    if df is None or len(df) < 30:
        return None

    close = df["close"]
    ema20 = float(close.ewm(span=20, adjust=False).mean().iloc[-1])
    ema50 = float(close.ewm(span=50, adjust=False).mean().iloc[-1])
    ema200 = float(close.ewm(span=200, adjust=False).mean().iloc[-1])
    rsi14 = _compute_rsi(close, period=14)
    current_price = float(close.iloc[-1])
    current_volume = int(df["volume"].iloc[-1])
    avg_volume = int(df["volume"].tail(20).mean())

    level_window = df.tail(20)
    support = float(level_window["low"].min())
    resistance = float(level_window["high"].max())
    atr_percent = _compute_atr_percent(df, period=14)
    market_structure = _derive_market_structure_from_series(df)

    # Son kapanis seviyeyi bozuyorsa destek/direnc mantigini daha anlamli tut.
    support = min(support, current_price)
    resistance = max(resistance, current_price)

    ohlcv_source = str(df.attrs.get("ohlcv_source") or "").lower()
    source = "matriks_ohlcv_chart_feature_engine" if "matriks" in ohlcv_source else REAL_CHART_FEATURE_SOURCE
    macd_metrics, ichimoku_metrics, trend_channel_metrics, fibonacci_metrics = _compute_advanced_metrics(df)

    return ComputedTechnicalMetrics(
        price=current_price,
        ema20=ema20,
        ema50=ema50,
        ema200=ema200,
        rsi14=rsi14,
        current_volume=current_volume,
        avg_volume=max(avg_volume, 1),
        support=support,
        resistance=resistance,
        atr_percent=atr_percent,
        market_structure=market_structure,
        source=source,
        macd=macd_metrics,
        ichimoku=ichimoku_metrics,
        trend_channel=trend_channel_metrics,
        fibonacci=fibonacci_metrics,
    )



def _resolve_runtime_metrics(ticker: str, profile: ChartFeatureProfile, timeframe: str = "1G") -> ComputedTechnicalMetrics:
    real_metrics = _compute_metrics_from_ohlcv(ticker, timeframe=timeframe)
    if real_metrics is not None:
        return real_metrics

    market_snapshot = get_market_snapshot(ticker)
    if market_snapshot is None:
        price = profile.current_price
        current_volume = profile.avg_volume
    else:
        price = market_snapshot.last_price
        current_volume = market_snapshot.volume
    fallback_macd, fallback_ichimoku, fallback_channel, fallback_fibonacci = _default_advanced_metrics(
        price=price,
        support=profile.support,
        resistance=profile.resistance,
        trend=profile.market_structure,
    )

    return ComputedTechnicalMetrics(
        price=price,
        ema20=profile.ema20,
        ema50=profile.ema50,
        ema200=profile.ema200,
        rsi14=profile.rsi14,
        current_volume=current_volume,
        avg_volume=profile.avg_volume,
        support=profile.support,
        resistance=profile.resistance,
        atr_percent=profile.atr_percent,
        market_structure=profile.market_structure,
        source=CHART_FEATURE_SOURCE,
        macd=fallback_macd,
        ichimoku=fallback_ichimoku,
        trend_channel=fallback_channel,
        fibonacci=fallback_fibonacci,
    )



def _derive_trend(price: float, ema20: float, ema50: float, ema200: float) -> str:
    if price > ema20 > ema50 > ema200:
        return "bullish"
    if price < ema20 < ema50 < ema200:
        return "bearish"
    return "neutral"



def _derive_ema_alignment(ema20: float, ema50: float, ema200: float) -> str:
    if ema20 > ema50 > ema200:
        return "bullish_stack"
    if ema20 < ema50 < ema200:
        return "bearish_stack"
    return "mixed_stack"



def _derive_volatility_regime(atr_percent: float) -> str:
    if atr_percent >= 4.0:
        return "high"
    if atr_percent >= 2.0:
        return "normal"
    return "low"



def _derive_level_metrics(price: float, support: float, resistance: float) -> DerivedLevelMetrics:
    support_gap_percent = max(((price - support) / max(price, 1)) * 100, 0.0)
    resistance_gap_percent = max(((resistance - price) / max(price, 1)) * 100, 0.0)
    price_range = max(resistance - support, 0.0001)
    price_position_percent = ((price - support) / price_range) * 100
    price_position_percent = max(0.0, min(price_position_percent, 100.0))

    if support_gap_percent <= 0.8 and resistance_gap_percent <= 0.8:
        level_status = "compressed_between_levels"
    elif support_gap_percent <= 1.1:
        level_status = "near_support"
    elif resistance_gap_percent <= 1.1:
        level_status = "near_resistance"
    else:
        level_status = "mid_range"

    return DerivedLevelMetrics(
        support_gap_percent=_round(support_gap_percent),
        resistance_gap_percent=_round(resistance_gap_percent),
        price_position_percent=_round(price_position_percent),
        level_status=level_status,
    )



def _derive_structure_metrics(market_structure: str) -> DerivedStructureMetrics:
    bullish_structures = {"higher_highs_and_higher_lows", "range_turning_up"}
    bearish_structures = {"lower_highs_near_support", "lower_highs_and_lower_lows", "range_turning_down"}

    if market_structure in bullish_structures:
        return DerivedStructureMetrics(structure_bias="bullish", structure_score=2)
    if market_structure in bearish_structures:
        return DerivedStructureMetrics(structure_bias="bearish", structure_score=-2)
    return DerivedStructureMetrics(structure_bias="neutral", structure_score=0)



def _derive_breakout_metrics(
    price: float,
    resistance: float,
    support: float,
    volume_ratio: float,
    level_metrics: DerivedLevelMetrics,
) -> DerivedBreakoutMetrics:
    breakout_buffer = 0.3
    confirm_volume = 1.10

    if price >= resistance * (1 + breakout_buffer / 100):
        if volume_ratio >= confirm_volume:
            return DerivedBreakoutMetrics(breakout_state="confirmed_breakout_up", breakout_score=2)
        return DerivedBreakoutMetrics(breakout_state="breakout_watch_up", breakout_score=1)

    if price <= support * (1 - breakout_buffer / 100):
        if volume_ratio >= confirm_volume:
            return DerivedBreakoutMetrics(breakout_state="confirmed_breakout_down", breakout_score=-2)
        return DerivedBreakoutMetrics(breakout_state="breakout_watch_down", breakout_score=-1)

    if level_metrics.resistance_gap_percent <= 0.8:
        return DerivedBreakoutMetrics(breakout_state="resistance_test", breakout_score=0)
    if level_metrics.support_gap_percent <= 0.8:
        return DerivedBreakoutMetrics(breakout_state="support_test", breakout_score=0)
    return DerivedBreakoutMetrics(breakout_state="range", breakout_score=0)



def _build_positive_factors(
    price: float,
    trend: str,
    ema_alignment: str,
    rsi14: float,
    volume_ratio: float,
    breakout_metrics: DerivedBreakoutMetrics,
    structure_metrics: DerivedStructureMetrics,
    level_metrics: DerivedLevelMetrics,
    trade_levels: DerivedTradeLevels,
) -> list[str]:
    factors: list[str] = []

    if trend == "bullish":
        factors.append("Fiyat EMA20, EMA50 ve EMA200 uzerinde kalarak pozitif trend yapisini koruyor")
    elif trend == "neutral":
        factors.append("Fiyat uzun vadeli ortalamalara gore ana trendi tamamen bozmadan denge ariyor")

    if ema_alignment == "bullish_stack":
        factors.append("Kisa ve orta vadeli ortalamalar yukari siralanarak trend devamini destekliyor")

    if 55 <= rsi14 <= 70:
        factors.append("RSI asiri sisme bolgesine girmeden momentum destegini koruyor")

    if volume_ratio >= 1.15:
        factors.append("Ortalama uzeri hacim hareketin teyit alma olasiligini artiriyor")

    if breakout_metrics.breakout_state == "confirmed_breakout_up":
        factors.append("Direnc ustu fiyatlama hacim teyidiyle kirilim devam senaryosunu guclendiriyor")
    elif breakout_metrics.breakout_state == "breakout_watch_up":
        factors.append("Direnc uzeri deneme var; hacim teyidi gelirse kirilim kuvvetlenebilir")

    if structure_metrics.structure_bias == "bullish":
        factors.append("Market structure daha yuksek dip ve tepe uretme egiliminde")

    if level_metrics.level_status == "near_support" and structure_metrics.structure_bias != "bearish":
        factors.append("Fiyat destek bolgesine yakin kalarak tepki alimi zemini olusturuyor")

    return factors[:5]



def _build_negative_factors(
    price: float,
    trend: str,
    ema_alignment: str,
    rsi14: float,
    volume_ratio: float,
    breakout_metrics: DerivedBreakoutMetrics,
    structure_metrics: DerivedStructureMetrics,
    level_metrics: DerivedLevelMetrics,
    trade_levels: DerivedTradeLevels,
) -> list[str]:
    factors: list[str] = []

    if trend == "bearish":
        factors.append("Fiyat kisa ve orta vadeli ortalamalarin altinda kalarak asagi baskiyi artiriyor")
    elif trend == "neutral":
        factors.append("Yatay ve kararsiz trend yapisi yon konusunda teyit ihtiyacini artiriyor")

    if ema_alignment == "bearish_stack":
        factors.append("EMA dizilimi yukari denemelerde satis baskisinin surme riskine isaret ediyor")

    if rsi14 < 45:
        factors.append("RSI zayif momentum bolgesinde kalarak tepki gucunu sinirliyor")
    elif rsi14 > 72:
        factors.append("RSI asiri alim bolgesine yaklasarak kar satisi riskini artiriyor")

    if volume_ratio < 0.9:
        factors.append("Zayif hacim hareketin teyitsiz kalma ihtimalini artiriyor")

    if breakout_metrics.breakout_state == "confirmed_breakout_down":
        factors.append("Destek alti fiyatlama hacim teyidiyle daha derin satis dalgasi riskini artiriyor")
    elif breakout_metrics.breakout_state == "breakout_watch_down":
        factors.append("Destek alti zayiflama var; hacim artarsa satis baskisi sertlesebilir")

    if structure_metrics.structure_bias == "bearish":
        factors.append("Dusuk tepe yapisi destek bolgesinde kirilim riskini canli tutuyor")

    if level_metrics.level_status == "near_resistance":
        factors.append("Yakindaki direnc bolgesi yukari hareketi kisa vadede zorlayabilir")
    if level_metrics.level_status == "near_support":
        factors.append("Destek bolgesine yakin seyir asagi kirilim halinde oynakligi artirabilir")
    if level_metrics.level_status == "compressed_between_levels":
        factors.append("Sikisan fiyat yapisi bir sonraki harekette volatiliteyi artirabilir")

    return factors[:5]


def _build_advanced_factors(
    macd: DerivedMacdMetrics,
    ichimoku: DerivedIchimokuMetrics,
    trend_channel: DerivedTrendChannelMetrics,
    fibonacci: DerivedFibonacciMetrics,
) -> tuple[list[str], list[str]]:
    positive_factors: list[str] = []
    negative_factors: list[str] = []

    if macd.macd_state in {"bullish_expanding", "early_bullish_cross"}:
        positive_factors.append("MACD yukari momentumun guclendigini veya erken pozitif kesişimi destekliyor")
    elif macd.macd_state == "bullish_fading":
        negative_factors.append("MACD pozitif olsa da histogram zayiflayarak momentum kaybi riski uretiyor")
    elif macd.macd_state in {"bearish_expanding", "early_bearish_cross"}:
        negative_factors.append("MACD asagi momentum veya negatif kesişim riski gosteriyor")

    if ichimoku.ichimoku_state == "above_cloud_bullish":
        positive_factors.append("Ichimoku bulutu fiyati destekliyor; fiyat bulut ustunde ve Tenkan-Kijun pozitif")
    elif ichimoku.ichimoku_state == "above_cloud_mixed":
        positive_factors.append("Fiyat Ichimoku bulutu ustunde kalarak ana trendde pozitif alan koruyor")
    elif ichimoku.ichimoku_state == "inside_cloud_neutral":
        negative_factors.append("Fiyat Ichimoku bulutu icinde; yon teyidi zayif ve karar bolgesi devam ediyor")
    elif ichimoku.ichimoku_state.startswith("below_cloud"):
        negative_factors.append("Fiyat Ichimoku bulutu altinda; trend kalitesi zayif")

    if trend_channel.channel_state in {"rising_mid_channel", "rising_channel_pullback"}:
        positive_factors.append("Trend kanali yukari egimli ve fiyat kanalda saglikli bolgede kaliyor")
    elif trend_channel.channel_state in {"rising_upper_channel_extended", "rising_channel_overextended"}:
        negative_factors.append("Yukselen kanal ust bandina yakinlik yeni alimda kovalamaca riskini artiriyor")
    elif trend_channel.channel_state == "rising_channel_breakdown_watch":
        negative_factors.append("Yukselen kanal altina sarkma trendin yorulduguna dair erken uyari uretiyor")
    elif trend_channel.channel_state in {"falling_channel", "falling_lower_channel"}:
        negative_factors.append("Trend kanali asagi egimli; tepki denemeleri satisla karsilasabilir")
    elif trend_channel.channel_state == "sideways_lower_channel":
        positive_factors.append("Yatay kanal alt bandina yakinlik tepki potansiyeli olusturuyor")
    elif trend_channel.channel_state == "sideways_upper_channel":
        negative_factors.append("Yatay kanal ust bandina yakinlik kar realizasyonu riskini artiriyor")

    if fibonacci.fib_score > 0:
        positive_factors.append("Fibonacci konumu geri cekilme sonrasi tepki seviyelerini destekliyor")
    elif fibonacci.fib_score < 0:
        negative_factors.append("Fibonacci konumu derin geri cekilme veya kritik seviye kirilim riski uretiyor")

    return positive_factors[:4], negative_factors[:4]



def _derive_trade_levels(
    price: float,
    trend: str,
    ema20: float,
    ema50: float,
    support: float,
    resistance: float,
    atr_percent: float,
    level_metrics: DerivedLevelMetrics,
    breakout_metrics: DerivedBreakoutMetrics,
    structure_metrics: DerivedStructureMetrics,
) -> DerivedTradeLevels:
    atr_value = max((price * atr_percent) / 100, max(price * 0.005, 0.01))

    breakout_buy_trigger = resistance + (atr_value * 0.2)
    breakdown_sell_trigger = support - (atr_value * 0.2)

    if trend == "bullish":
        trend_reference_level = max(support, min(price, ema20))
        entry_zone_low = max(support, ema20 - (atr_value * 0.35))
        entry_zone_high = min(price, max(support, ema20 + (atr_value * 0.15)))
        take_profit_level = max(resistance, price + (atr_value * 1.2))
        bullish_invalidation_base = support if level_metrics.level_status == "near_support" else max(support, ema50)
        stop_loss_level = bullish_invalidation_base - (atr_value * 0.35)
        if level_metrics.level_status == "near_resistance":
            trade_setup = "breakout_watch"
            level_commentary = (
                f"{_round(breakout_buy_trigger)} ustu kapanis yukari hareketi teyit edebilir; "
                f"{_round(stop_loss_level)} alti ise gorunumu zayiflatir"
            )
        elif level_metrics.level_status == "near_support":
            trade_setup = "pullback_buy"
            level_commentary = (
                f"{_round(entry_zone_low)}-{_round(entry_zone_high)} bandi tepki alimi icin izlenebilir; "
                f"{_round(stop_loss_level)} alti riskli bolge"
            )
        else:
            trade_setup = "trend_follow"
            level_commentary = (
                f"Trend referansi { _round(trend_reference_level) }; { _round(breakout_buy_trigger) } ustu devam, "
                f"{ _round(stop_loss_level) } alti zayiflama sinyali"
            )
    elif trend == "bearish":
        trend_reference_level = min(resistance, max(price, ema20))
        entry_zone_low = max(price, resistance - (atr_value * 0.35))
        entry_zone_high = resistance
        take_profit_level = min(support, price - (atr_value * 1.2))
        stop_loss_level = max(resistance, ema50) + (atr_value * 0.35)
        if breakout_metrics.breakout_state in {"confirmed_breakout_down", "breakout_watch_down"}:
            trade_setup = "breakdown_watch"
            level_commentary = (
                f"{_round(breakdown_sell_trigger)} alti kalicilik satis baskisini artirabilir; "
                f"{_round(stop_loss_level)} uzeri ise negatif gorunumu bozabilir"
            )
        else:
            trade_setup = "sell_rally"
            level_commentary = (
                f"{_round(entry_zone_low)}-{_round(entry_zone_high)} bandi tepki satisi alani olabilir; "
                f"{_round(stop_loss_level)} uzeri riskli"
            )
    else:
        trend_reference_level = ema50
        entry_zone_low = max(support, ema50 - (atr_value * 0.4))
        entry_zone_high = min(resistance, ema50 + (atr_value * 0.4))
        take_profit_level = resistance
        stop_loss_level = support - (atr_value * 0.35)
        trade_setup = "range_trade"
        if structure_metrics.structure_bias == "bullish":
            level_commentary = (
                f"{_round(entry_zone_low)}-{_round(entry_zone_high)} dengesi korunursa bant ici tepki surer; "
                f"{_round(breakout_buy_trigger)} ustu yeni ivme alanidir"
            )
        else:
            level_commentary = (
                f"Bant ici karar bolgesi { _round(entry_zone_low) }-{ _round(entry_zone_high) }; "
                f"{ _round(breakdown_sell_trigger) } alti satis baskisini artirabilir"
            )

    entry_mid = (entry_zone_low + entry_zone_high) / 2
    minimum_risk_distance = max(atr_value * 0.75, price * 0.012)
    if trend == "bullish":
        risk_distance = max(entry_mid - stop_loss_level, minimum_risk_distance)
        reward_distance = max(take_profit_level - entry_mid, atr_value * 0.35)
    elif trend == "bearish":
        risk_distance = max(stop_loss_level - entry_mid, minimum_risk_distance)
        reward_distance = max(entry_mid - take_profit_level, atr_value * 0.35)
    else:
        risk_distance = max(abs(entry_mid - stop_loss_level), minimum_risk_distance)
        reward_distance = max(abs(take_profit_level - entry_mid), atr_value * 0.35)
    risk_reward_ratio = reward_distance / risk_distance

    return DerivedTradeLevels(
        trend_reference_level=_round(trend_reference_level),
        entry_zone_low=_round(min(entry_zone_low, entry_zone_high)),
        entry_zone_high=_round(max(entry_zone_low, entry_zone_high)),
        breakout_buy_trigger=_round(breakout_buy_trigger),
        breakdown_sell_trigger=_round(breakdown_sell_trigger),
        take_profit_level=_round(take_profit_level),
        stop_loss_level=_round(stop_loss_level),
        trade_setup=trade_setup,
        risk_reward_ratio=_round(risk_reward_ratio),
        level_commentary=level_commentary,
    )


def _derive_signal_metrics(
    price: float,
    trend: str,
    ema_alignment: str,
    rsi14: float,
    volume_ratio: float,
    breakout_metrics: DerivedBreakoutMetrics,
    structure_metrics: DerivedStructureMetrics,
    level_metrics: DerivedLevelMetrics,
    trade_levels: DerivedTradeLevels,
    atr_percent: float,
    macd: DerivedMacdMetrics,
    ichimoku: DerivedIchimokuMetrics,
    trend_channel: DerivedTrendChannelMetrics,
    fibonacci: DerivedFibonacciMetrics,
) -> DerivedSignalMetrics:
    score = 0

    if trend == "bullish":
        score += 2
    elif trend == "bearish":
        score -= 2

    if ema_alignment == "bullish_stack":
        score += 1
    elif ema_alignment == "bearish_stack":
        score -= 1

    if 55 <= rsi14 <= 68:
        score += 1
    elif rsi14 < 45:
        score -= 1
    elif rsi14 > 72:
        score -= 1

    if volume_ratio >= 1.15:
        score += 1
    elif volume_ratio < 0.9:
        score -= 1

    score += breakout_metrics.breakout_score
    score += structure_metrics.structure_score
    score += macd.macd_score
    score += ichimoku.ichimoku_score
    score += trend_channel.channel_score
    score += fibonacci.fib_score

    if level_metrics.level_status == "near_support" and structure_metrics.structure_bias == "bullish":
        score += 1
    if level_metrics.level_status == "near_resistance" and trend != "bullish":
        score -= 1

    if trade_levels.risk_reward_ratio >= 2.0:
        score += 1
    elif trade_levels.risk_reward_ratio < 1.1:
        score -= 1

    if trend == "bullish" and price <= trade_levels.entry_zone_high * 1.02:
        score += 1
    elif trend == "bullish" and price > trade_levels.entry_zone_high * 1.05 and breakout_metrics.breakout_state == "range":
        score -= 1

    if trend == "neutral" and trade_levels.trade_setup == "range_trade" and level_metrics.price_position_percent >= 75:
        score -= 1

    score = max(-10, min(score, 10))

    if score >= 3:
        signal_bias = "bullish"
    elif score <= -3:
        signal_bias = "bearish"
    else:
        signal_bias = "neutral"

    intensity = abs(score)
    if breakout_metrics.breakout_state in {"confirmed_breakout_up", "confirmed_breakout_down"}:
        intensity += 1
    if atr_percent >= 2.5:
        intensity += 1

    if signal_bias == "neutral":
        signal_strength = "mixed"
    elif intensity >= 5:
        signal_strength = "strong"
    else:
        signal_strength = "moderate"

    return DerivedSignalMetrics(
        signal_bias=signal_bias,
        signal_strength=signal_strength,
        signal_score=score,
    )



def get_chart_feature_summary(ticker: str, timeframe: str = "1G", as_of_timestamp: str | None = None) -> ChartFeatureResponse | None:
    normalized_ticker = ticker.upper().strip()
    normalized_timeframe = timeframe.upper().strip() or "1G"
    profile = CHART_FEATURE_PROFILES.get(normalized_ticker)

    real_metrics = _compute_metrics_from_ohlcv(normalized_ticker, timeframe=normalized_timeframe, as_of_timestamp=as_of_timestamp)
    if real_metrics is not None:
        metrics = real_metrics
    else:
        if profile is None:
            return None
        metrics = _resolve_runtime_metrics(normalized_ticker, profile, timeframe=normalized_timeframe)
    volume_ratio = metrics.current_volume / max(metrics.avg_volume, 1)
    trend = _derive_trend(metrics.price, metrics.ema20, metrics.ema50, metrics.ema200)
    ema_alignment = _derive_ema_alignment(metrics.ema20, metrics.ema50, metrics.ema200)
    level_metrics = _derive_level_metrics(metrics.price, metrics.support, metrics.resistance)
    structure_metrics = _derive_structure_metrics(metrics.market_structure)
    breakout_metrics = _derive_breakout_metrics(
        price=metrics.price,
        resistance=metrics.resistance,
        support=metrics.support,
        volume_ratio=volume_ratio,
        level_metrics=level_metrics,
    )
    volatility_regime = _derive_volatility_regime(metrics.atr_percent)
    trade_levels = _derive_trade_levels(
        price=metrics.price,
        trend=trend,
        ema20=metrics.ema20,
        ema50=metrics.ema50,
        support=metrics.support,
        resistance=metrics.resistance,
        atr_percent=metrics.atr_percent,
        level_metrics=level_metrics,
        breakout_metrics=breakout_metrics,
        structure_metrics=structure_metrics,
    )
    positive_factors = _build_positive_factors(
        price=metrics.price,
        trend=trend,
        ema_alignment=ema_alignment,
        rsi14=metrics.rsi14,
        volume_ratio=volume_ratio,
        breakout_metrics=breakout_metrics,
        structure_metrics=structure_metrics,
        level_metrics=level_metrics,
        trade_levels=trade_levels,
    )
    negative_factors = _build_negative_factors(
        price=metrics.price,
        trend=trend,
        ema_alignment=ema_alignment,
        rsi14=metrics.rsi14,
        volume_ratio=volume_ratio,
        breakout_metrics=breakout_metrics,
        structure_metrics=structure_metrics,
        level_metrics=level_metrics,
        trade_levels=trade_levels,
    )
    advanced_positive_factors, advanced_negative_factors = _build_advanced_factors(
        metrics.macd,
        metrics.ichimoku,
        metrics.trend_channel,
        metrics.fibonacci,
    )
    positive_factors = (positive_factors + advanced_positive_factors)[:7]
    negative_factors = (negative_factors + advanced_negative_factors)[:7]
    trade_level_positive_factors, trade_level_negative_factors = _build_trade_level_factors(
        price=metrics.price,
        trend=trend,
        breakout_metrics=breakout_metrics,
        level_metrics=level_metrics,
        trade_levels=trade_levels,
    )
    signal_metrics = _derive_signal_metrics(
        price=metrics.price,
        trend=trend,
        ema_alignment=ema_alignment,
        rsi14=metrics.rsi14,
        volume_ratio=volume_ratio,
        breakout_metrics=breakout_metrics,
        structure_metrics=structure_metrics,
        level_metrics=level_metrics,
        trade_levels=trade_levels,
        atr_percent=metrics.atr_percent,
        macd=metrics.macd,
        ichimoku=metrics.ichimoku,
        trend_channel=metrics.trend_channel,
        fibonacci=metrics.fibonacci,
    )

    return ChartFeatureResponse(
        ticker=normalized_ticker,
        current_price=_round(metrics.price),
        trend=trend,
        ema20=_round(metrics.ema20),
        ema50=_round(metrics.ema50),
        ema200=_round(metrics.ema200),
        ema_alignment=ema_alignment,
        rsi14=_round(metrics.rsi14),
        macd_line=metrics.macd.macd_line,
        macd_signal=metrics.macd.macd_signal,
        macd_histogram=metrics.macd.macd_histogram,
        macd_state=metrics.macd.macd_state,
        macd_score=metrics.macd.macd_score,
        ichimoku_tenkan=metrics.ichimoku.tenkan,
        ichimoku_kijun=metrics.ichimoku.kijun,
        ichimoku_cloud_top=metrics.ichimoku.cloud_top,
        ichimoku_cloud_bottom=metrics.ichimoku.cloud_bottom,
        ichimoku_state=metrics.ichimoku.ichimoku_state,
        ichimoku_score=metrics.ichimoku.ichimoku_score,
        trend_channel_upper=metrics.trend_channel.channel_upper,
        trend_channel_mid=metrics.trend_channel.channel_mid,
        trend_channel_lower=metrics.trend_channel.channel_lower,
        trend_channel_slope_percent=metrics.trend_channel.slope_percent,
        trend_channel_position_percent=metrics.trend_channel.position_percent,
        trend_channel_state=metrics.trend_channel.channel_state,
        trend_channel_score=metrics.trend_channel.channel_score,
        fibonacci_swing_high=metrics.fibonacci.swing_high,
        fibonacci_swing_low=metrics.fibonacci.swing_low,
        fibonacci_nearest_level=metrics.fibonacci.nearest_level,
        fibonacci_position=metrics.fibonacci.fib_position,
        fibonacci_score=metrics.fibonacci.fib_score,
        current_volume=metrics.current_volume,
        avg_volume=metrics.avg_volume,
        volume_ratio=_round(volume_ratio),
        breakout_state=breakout_metrics.breakout_state,
        breakout_score=breakout_metrics.breakout_score,
        nearest_support=_round(metrics.support),
        nearest_resistance=_round(metrics.resistance),
        support_gap_percent=level_metrics.support_gap_percent,
        resistance_gap_percent=level_metrics.resistance_gap_percent,
        price_position_percent=level_metrics.price_position_percent,
        level_status=level_metrics.level_status,
        trend_reference_level=trade_levels.trend_reference_level,
        entry_zone_low=trade_levels.entry_zone_low,
        entry_zone_high=trade_levels.entry_zone_high,
        breakout_buy_trigger=trade_levels.breakout_buy_trigger,
        breakdown_sell_trigger=trade_levels.breakdown_sell_trigger,
        take_profit_level=trade_levels.take_profit_level,
        stop_loss_level=trade_levels.stop_loss_level,
        trade_setup=trade_levels.trade_setup,
        risk_reward_ratio=trade_levels.risk_reward_ratio,
        level_commentary=trade_levels.level_commentary,
        trade_level_positive_factors=trade_level_positive_factors,
        trade_level_negative_factors=trade_level_negative_factors,
        atr_percent=_round(metrics.atr_percent),
        volatility_regime=volatility_regime,
        market_structure=metrics.market_structure,
        structure_bias=structure_metrics.structure_bias,
        signal_bias=signal_metrics.signal_bias,
        signal_strength=signal_metrics.signal_strength,
        signal_score=signal_metrics.signal_score,
        positive_factors=positive_factors,
        negative_factors=negative_factors,
        source=metrics.source,
    )



def fetch_chart_feature_summary(ticker: str, timeframe: str = "1G", as_of_timestamp: str | None = None) -> ChartFeatureResponse:
    summary = get_chart_feature_summary(ticker, timeframe=timeframe, as_of_timestamp=as_of_timestamp)
    if summary is None:
        raise HTTPException(status_code=404, detail=f"Chart features for ticker '{ticker.upper()}' were not found.")
    return summary
