from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
from fastapi import HTTPException

from app.data_sources.market_data.provider import get_market_ohlcv, get_market_snapshot
from app.models.schemas import ChartFeatureResponse

CHART_FEATURE_SOURCE = "fallback_chart_feature_profile"
REAL_CHART_FEATURE_SOURCE = "yahoo_delayed_chart_feature_engine"


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
    if as_of_timestamp:
        cutoff = pd.to_datetime(as_of_timestamp, utc=True)
        df = df[df["timestamp"] <= cutoff].reset_index(drop=True)
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
        source=REAL_CHART_FEATURE_SOURCE,
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
