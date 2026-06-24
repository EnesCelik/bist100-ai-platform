from __future__ import annotations

from datetime import datetime

from app.models.schemas import OpeningCandidateItem, TradingAgentRegimeResponse, TradingAgentSignalScoreItem
from app.services.chart_feature_service import get_chart_feature_summary
from app.services.macro_event_service import get_macro_event_summary
from app.services.replay_evaluation_service import get_trade_calibration_cached
from app.services.technical_indicator_text_service import (
    describe_fibonacci_position,
    describe_ichimoku_state,
    describe_macd_state,
    describe_trend_channel_state,
)


def _clamp(value: float, minimum: float = 0.0, maximum: float = 100.0) -> float:
    return max(minimum, min(maximum, value))


def _bias_score(value: str | None) -> float:
    normalized = (value or "").lower()
    if "bullish" in normalized or "breakout" in normalized:
        return 82.0
    if "positive" in normalized or "support" in normalized:
        return 68.0
    if "bearish" in normalized or "breakdown" in normalized:
        return 22.0
    if "weak" in normalized:
        return 35.0
    return 50.0


def _volume_score(ratio: float | None) -> float:
    if ratio is None:
        return 42.0
    if ratio >= 3.0:
        return 95.0
    if ratio >= 2.0:
        return 85.0
    if ratio >= 1.25:
        return 70.0
    if ratio >= 0.8:
        return 55.0
    return 30.0


def _order_flow_score(item: OpeningCandidateItem) -> float:
    pressure = (item.order_book_pressure or "").lower()
    proxy = (item.order_flow_proxy or "").lower()
    imbalance = item.bid_ask_imbalance
    score = 50.0
    if "strong_bid" in pressure or "bid_pressure" in pressure:
        score += 22.0
    elif "ask" in pressure:
        score -= 18.0
    if "healthy" in proxy or "tight" in proxy:
        score += 12.0
    elif "wide" in proxy:
        score -= 16.0
    if imbalance is not None:
        if imbalance >= 1.6:
            score += 12.0
        elif imbalance <= 0.7:
            score -= 12.0
    return _clamp(score)


def _risk_penalty(item: OpeningCandidateItem) -> tuple[float, str, list[str]]:
    penalty = 0.0
    risks: list[str] = []
    gap = (item.gap_risk or "").lower()
    spread = item.spread_percent

    if "high" in gap:
        penalty += 14.0
        risks.append("Gap/chase riski yuksek; acilista fiyat kovalamaya uygun degil.")
    elif "medium" in gap:
        penalty += 6.0

    if spread is not None:
        if spread >= 1.0:
            penalty += 14.0
            risks.append("Spread genis; emir kalitesi ve kayma riski yuksek.")
        elif spread >= 0.45:
            penalty += 6.0

    if item.change_percent is not None and item.change_percent > 7.0:
        penalty += 9.0
        risks.append("Gunluk getiri zaten yuksek; tavan kovalamada geri cekilme riski var.")

    if penalty >= 18.0:
        return penalty, "high", risks
    if penalty >= 8.0:
        return penalty, "medium", risks
    return penalty, "low", risks


def _calibration_component(ticker: str) -> tuple[float, list[str], list[str]]:
    calibration = get_trade_calibration_cached(
        ticker,
        timeframe="1G",
        horizon_bars=10,
        sample_size=8,
        step_bars=5,
        use_cache_only=True,
    )
    if calibration is None:
        return 0.0, [], ["Replay kalibrasyonu cache'te yok; skor canli sinyallere daha fazla dayaniyor."]

    reasons: list[str] = []
    risks: list[str] = []
    score = 0.0
    if calibration.calibration_bias == "supportive":
        score += 8.0
        reasons.append("Replay kalibrasyonu destekleyici.")
    elif calibration.calibration_bias == "fragile":
        score -= 10.0
        risks.append("Replay kalibrasyonu kirilgan.")
    else:
        score -= 2.0

    score += (calibration.take_profit_rate - calibration.stop_loss_rate) * 10.0
    score += max(min(calibration.average_close_return_percent, 4.0), -4.0)
    return score, reasons, risks


def _technical_indicator_details(ticker: str) -> tuple[dict[str, str | float | int], list[str], list[str]]:
    chart = get_chart_feature_summary(ticker, timeframe="1G")
    if chart is None:
        return {}, [], ["Grafik indikatorleri okunamadi; teknik karar eski opening score ile sinirli."]

    details: dict[str, str | float | int] = {
        "method": "MACD(12,26,9), Ichimoku(9,26,52 non-lookahead), 60-bar regression channel, 80-bar Fibonacci swing",
        "signal_bias": chart.signal_bias,
        "signal_score": chart.signal_score,
        "macd_state": chart.macd_state,
        "macd_score": chart.macd_score,
        "ichimoku_state": chart.ichimoku_state,
        "ichimoku_score": chart.ichimoku_score,
        "trend_channel_state": chart.trend_channel_state,
        "trend_channel_score": chart.trend_channel_score,
        "trend_channel_position_percent": chart.trend_channel_position_percent,
        "fibonacci_position": chart.fibonacci_position,
        "fibonacci_score": chart.fibonacci_score,
    }

    reasons: list[str] = []
    risks: list[str] = []
    if chart.macd_score > 0:
        reasons.append(describe_macd_state(chart.macd_state, chart.macd_score))
    elif chart.macd_score < 0:
        risks.append(describe_macd_state(chart.macd_state, chart.macd_score))

    if chart.ichimoku_score > 0:
        reasons.append(describe_ichimoku_state(chart.ichimoku_state, chart.ichimoku_score))
    elif chart.ichimoku_score < 0:
        risks.append(describe_ichimoku_state(chart.ichimoku_state, chart.ichimoku_score))

    if chart.trend_channel_score > 0:
        reasons.append(describe_trend_channel_state(chart.trend_channel_state, chart.trend_channel_score))
    elif chart.trend_channel_score < 0:
        risks.append(describe_trend_channel_state(chart.trend_channel_state, chart.trend_channel_score))

    if chart.fibonacci_score > 0:
        reasons.append(describe_fibonacci_position(chart.fibonacci_position, chart.fibonacci_score))
    elif chart.fibonacci_score < 0:
        risks.append(describe_fibonacci_position(chart.fibonacci_position, chart.fibonacci_score))

    return details, reasons, risks


def _macro_event_score(ticker: str) -> tuple[float, list[str], list[str]]:
    macro_event = get_macro_event_summary(ticker)
    if macro_event is None:
        return 0.0, [], []

    net_impact = len(macro_event.positive_impacts) - len(macro_event.negative_impacts)
    if net_impact == 0:
        return 0.0, [], []

    score = _clamp(net_impact * 2.2, -8.0, 8.0)
    title = macro_event.latest_macro_event
    if net_impact > 0:
        reasons = [f"Makro haber destegi: {title}"]
        reasons.extend(macro_event.positive_impacts[:2])
        return score, reasons, []

    risks = [f"Makro haber riski: {title}"]
    risks.extend(macro_event.negative_impacts[:2])
    return score, [], risks


def detect_regime_from_opening_candidates(items: list[OpeningCandidateItem]) -> TradingAgentRegimeResponse:
    inspected = items[:20]
    changes = [float(item.change_percent) for item in inspected if item.change_percent is not None]
    volumes = [float(item.daily_volume_ratio) for item in inspected if item.daily_volume_ratio is not None]
    avg_change = round(sum(changes) / len(changes), 2) if changes else None
    avg_volume = round(sum(volumes) / len(volumes), 2) if volumes else None
    positive_count = sum(1 for item in inspected if item.change_percent is not None and item.change_percent > 0)
    strong_score_count = sum(1 for item in inspected if item.opening_score >= 70)

    regime = "neutral"
    multiplier = 1.0
    rationale = "Piyasa modu dengeli; standart sermaye dagilimi kullanilir."
    if inspected and positive_count >= max(5, len(inspected) // 2) and (avg_volume or 0) >= 1.2 and strong_score_count >= 3:
        regime = "risk_on"
        multiplier = 1.08
        rationale = "Pozitif aday sayisi ve hacim genisligi destekleyici; secici risk alinabilir."
    elif inspected and (positive_count <= max(2, len(inspected) // 4) or (avg_change is not None and avg_change < -0.5)):
        regime = "risk_off"
        multiplier = 0.72
        rationale = "Pozitif genislik zayif; nakit tamponu ve kucuk pozisyon oncelikli."

    return TradingAgentRegimeResponse(
        generated_at=datetime.utcnow().isoformat(),
        regime=regime,
        risk_multiplier=multiplier,
        average_change_percent=avg_change,
        average_volume_ratio=avg_volume,
        positive_candidate_count=positive_count,
        inspected_count=len(inspected),
        rationale=rationale,
    )


def score_opening_candidate(
    item: OpeningCandidateItem,
    regime: TradingAgentRegimeResponse | None = None,
    learning_adjustments: dict[str, float] | None = None,
) -> TradingAgentSignalScoreItem:
    base = _clamp(float(item.opening_score))
    volume = _volume_score(item.daily_volume_ratio)
    close_strength = _clamp(float(item.closing_strength_proxy if item.closing_strength_proxy is not None else 50.0))
    technical = (_bias_score(item.technical_bias) * 0.55) + (_bias_score(item.intraday_bias_1h) * 0.25) + (_bias_score(item.intraday_bias_4h) * 0.20)
    order_flow = _order_flow_score(item)
    calibration, calibration_reasons, calibration_risks = _calibration_component(item.ticker)
    technical_details, technical_reasons, technical_risks = _technical_indicator_details(item.ticker)
    macro_score, macro_reasons, macro_risks = _macro_event_score(item.ticker)
    risk_penalty, risk_label, risk_notes = _risk_penalty(item)
    regime_bonus = 3.0 if regime and regime.regime == "risk_on" else -6.0 if regime and regime.regime == "risk_off" else 0.0
    adjustments = learning_adjustments or {}
    learning_score_adjustment = float(adjustments.get("volume_weight_delta", 0.0)) - float(adjustments.get("risk_penalty_delta", 0.0))

    agent_score = (
        (base * 0.34)
        + (volume * 0.18)
        + (close_strength * 0.15)
        + (technical * 0.17)
        + (order_flow * 0.10)
        + 8.0
        + calibration
        + macro_score
        + regime_bonus
        + learning_score_adjustment
        - risk_penalty
    )
    agent_score = round(_clamp(agent_score), 2)

    if agent_score >= 78 and risk_label != "high":
        label = "strong_candidate"
        action = "open"
    elif agent_score >= 68:
        label = "candidate"
        action = "open_small" if risk_label == "high" else "open"
    elif agent_score >= 58:
        label = "watch_candidate"
        action = "watch"
    else:
        label = "weak_candidate"
        action = "skip"

    reasons = [
        *item.reasons[:3],
        *technical_reasons,
        *macro_reasons,
        *calibration_reasons,
    ]
    risks = [
        *item.risks[:3],
        *technical_risks,
        *macro_risks,
        *risk_notes,
        *calibration_risks,
    ]
    return TradingAgentSignalScoreItem(
        ticker=item.ticker,
        base_opening_score=round(base, 2),
        agent_score=agent_score,
        signal_label=label,
        risk_label=risk_label,
        suggested_action=action,
        breakdown={
            "base": round(base * 0.34, 2),
            "volume": round(volume * 0.18, 2),
            "close_strength": round(close_strength * 0.15, 2),
            "technical": round(technical * 0.17, 2),
            "order_flow": round(order_flow * 0.10, 2),
            "calibration": round(calibration, 2),
            "macro": round(macro_score, 2),
            "regime": round(regime_bonus, 2),
            "learning": round(learning_score_adjustment, 2),
            "risk_penalty": round(-risk_penalty, 2),
        },
        technical_breakdown=technical_details,
        reasons=list(dict.fromkeys(reasons))[:5],
        risks=list(dict.fromkeys(risks))[:5],
    )


def rank_opening_candidates_for_agent(
    items: list[OpeningCandidateItem],
    limit: int,
    min_agent_score: float,
    learning_adjustments: dict[str, float] | None = None,
) -> tuple[list[TradingAgentSignalScoreItem], TradingAgentRegimeResponse]:
    regime = detect_regime_from_opening_candidates(items)
    scored = [score_opening_candidate(item, regime=regime, learning_adjustments=learning_adjustments) for item in items]
    scored.sort(key=lambda item: (item.agent_score, -len(item.risks)), reverse=True)
    selected = [
        item
        for item in scored
        if item.agent_score >= min_agent_score and item.suggested_action in {"open", "open_small"}
    ][: max(limit, 1)]
    return selected, regime


def allocate_capital_by_score(
    selected: list[TradingAgentSignalScoreItem],
    total_capital: float,
    cash_buffer: float,
    regime: TradingAgentRegimeResponse,
) -> dict[str, float]:
    investable = max((total_capital - cash_buffer) * regime.risk_multiplier, 0.0)
    if not selected or investable <= 0:
        return {}

    weights = {item.ticker: max(item.agent_score - 50.0, 5.0) for item in selected}
    total_weight = sum(weights.values()) or 1.0
    raw = {ticker: investable * weight / total_weight for ticker, weight in weights.items()}
    max_single = total_capital * (0.28 if regime.regime == "risk_on" else 0.22 if regime.regime == "neutral" else 0.16)
    capped = {ticker: min(amount, max_single) for ticker, amount in raw.items()}
    return {ticker: round(amount, 2) for ticker, amount in capped.items()}
