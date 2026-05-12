from datetime import datetime

from sqlalchemy import select

from app.data_sources.company_data.provider import list_company_records
from app.data_sources.market_data.provider import get_active_market_data_provider, get_market_snapshot
from app.db.models import ScanSnapshot
from app.db.session import SessionLocal, ensure_runtime_schema
from app.models.schemas import (
    AnalysisEvidence,
    LimitUpCandidateItem,
    LimitUpCandidateResponse,
    MarketScanItem,
    MarketScanResponse,
    ScanSnapshotCreateResponse,
    ScanSnapshotHistoryItem,
    ScanSnapshotHistoryResponse,
)
from app.services.ask_service import _build_analysis_answer, _calculate_analysis_confidence
from app.services.chart_feature_service import get_chart_feature_summary
from app.services.event_service import get_event_summary
from app.services.fundamental_service import get_fundamental_summary
from app.services.institutional_flow_service import get_institutional_flow_summary
from app.services.macro_event_service import get_macro_event_summary
from app.services.news_impact_service import fetch_optional_news_impact
from app.services.recommendation_policy import derive_recommendation
from app.services.runtime_scheduler_service import get_runtime_health
from app.services.replay_evaluation_service import build_trade_calibration_signals, get_trade_calibration_cached
from app.services.signal_service import build_signal_summary_from_chart_feature


def _top_factors(evidence_items: list[AnalysisEvidence], impact: str, limit: int = 3) -> list[str]:
    factors: list[str] = []
    for item in evidence_items:
        if item.impact == impact and item.detail not in factors:
            factors.append(item.detail)
        if len(factors) >= limit:
            break
    return factors



def _build_technical_summary(chart_summary) -> str | None:
    if chart_summary is None:
        return None

    return (
        f"{chart_summary.signal_bias} · {chart_summary.breakout_state} · "
        f"{chart_summary.level_status} · RSI {chart_summary.rsi14}"
    )



def _build_news_impact_summary(evidence_items: list[AnalysisEvidence]) -> str | None:
    news_items = [item for item in evidence_items if item.category == "news_impact"]
    if not news_items:
        return None

    positive = sum(1 for item in news_items if item.impact == "positive")
    negative = sum(1 for item in news_items if item.impact == "negative")
    if positive > negative:
        return "pozitif haber akisi"
    if negative > positive:
        return "negatif haber akisi"
    return "karisik haber akisi"



def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _probability_bucket(score: float) -> str:
    if score >= 72:
        return "high"
    if score >= 58:
        return "medium"
    return "watch"


def _spread_percent(best_bid: float, best_ask: float) -> float | None:
    if best_bid <= 0 or best_ask <= 0:
        return None
    midpoint = (best_bid + best_ask) / 2
    if midpoint <= 0:
        return None
    return round(((best_ask - best_bid) / midpoint) * 100, 3)


def _order_flow_proxy(best_bid: float, best_ask: float) -> str:
    spread = _spread_percent(best_bid, best_ask)
    if spread is None:
        return "depth_missing"
    if spread <= 0.12:
        return "healthy_spread"
    if spread <= 0.35:
        return "wide_but_tradeable"
    return "wide_spread"


def _summarize_market_data_sources(items: list[MarketScanItem]) -> dict[str, int]:
    summary: dict[str, int] = {}
    for item in items:
        source = item.market_data_source or "unknown"
        summary[source] = summary.get(source, 0) + 1
    return summary



def _summarize_used_sources(items: list[MarketScanItem]) -> dict[str, int]:
    summary: dict[str, int] = {}
    for item in items:
        for source in item.used_sources:
            summary[source] = summary.get(source, 0) + 1
    return summary



def _runtime_health_snapshot() -> dict:
    runtime = get_runtime_health()
    return {
        "scheduler_enabled": runtime.scheduler_enabled,
        "cleanup_enabled": runtime.cleanup_enabled,
        "prefetch_enabled": runtime.prefetch_enabled,
        "last_cleanup_status": runtime.last_cleanup_status,
        "last_cleanup_completed_at": runtime.last_cleanup_completed_at,
        "last_prefetch_status": runtime.last_prefetch_status,
        "last_prefetch_completed_at": runtime.last_prefetch_completed_at,
    }



def _trade_calibration_rank_component(trade_calibration) -> float:
    if trade_calibration is None:
        return 0.0

    component = 0.0
    if trade_calibration.calibration_bias == "supportive":
        component += 1.0
        if trade_calibration.take_profit_rate >= 0.6 and trade_calibration.stop_loss_rate <= 0.2:
            component += 0.45
        elif trade_calibration.positive_close_rate >= 0.75:
            component += 0.25
    elif trade_calibration.calibration_bias == "fragile":
        component -= 1.35
        if trade_calibration.stop_loss_rate >= trade_calibration.take_profit_rate:
            component -= 0.4
        if trade_calibration.average_close_return_percent < 0:
            component -= 0.35
        if trade_calibration.positive_close_rate <= 0.45:
            component -= 0.25
    else:
        if trade_calibration.average_close_return_percent <= 0:
            component -= 0.45
        elif trade_calibration.positive_close_rate >= 0.7:
            component += 0.2
        if trade_calibration.stop_loss_rate > trade_calibration.take_profit_rate:
            component -= 0.2
    return round(component, 3)



def _change_runway_component(change_percent: float | None) -> tuple[float, list[str], list[str]]:
    reasons: list[str] = []
    risks: list[str] = []
    if change_percent is None:
        return 0.0, reasons, ["Gunluk degisim okunamadi"]

    if change_percent >= 9.3:
        return -100.0, reasons, ["Hisse zaten tavan bolgesine cok yakin"]
    if 3.0 <= change_percent <= 7.2:
        reasons.append("Gun ici yuzde artisi tavan kosusu icin ideal ivme bandinda")
        return 21.0, reasons, risks
    if 1.0 <= change_percent < 3.0:
        reasons.append("Pozitif ama henuz doymamis gun ici ivme var")
        return 14.0, reasons, risks
    if 7.2 < change_percent < 9.3:
        reasons.append("Tavana yakin momentum var")
        risks.append("Yuksek yuzde nedeniyle kovalamaca riski artiyor")
        return 11.0, reasons, risks
    if -1.0 <= change_percent < 1.0:
        reasons.append("Gunun geri kalani icin hala hareket alani var")
        return 5.0, reasons, risks
    risks.append("Gun ici performans tavan kosusu icin henuz zayif")
    return -4.0, reasons, risks


def _volume_pressure_component(market_snapshot, daily_chart, intraday_1h) -> tuple[float, float | None, float | None, list[str], list[str]]:
    reasons: list[str] = []
    risks: list[str] = []
    daily_ratio = None
    intraday_ratio = None
    score = 0.0

    if market_snapshot is not None and daily_chart is not None and daily_chart.avg_volume > 0:
        daily_ratio = round(market_snapshot.volume / max(daily_chart.avg_volume, 1), 2)
        if daily_ratio >= 2.0:
            score += 20.0
            reasons.append("Gunluk hacim ortalamanin cok uzerinde")
        elif daily_ratio >= 1.35:
            score += 13.0
            reasons.append("Gunluk hacim ortalamanin belirgin uzerinde")
        elif daily_ratio >= 1.0:
            score += 7.0
            reasons.append("Gunluk hacim ortalama ustunde")
        elif daily_ratio < 0.75:
            score -= 8.0
            risks.append("Gunluk hacim teyidi zayif")

    if intraday_1h is not None:
        intraday_ratio = round(float(intraday_1h.volume_ratio), 2)
        if intraday_ratio >= 1.6:
            score += 15.0
            reasons.append("1H hacim ivmesi guclu")
        elif intraday_ratio >= 1.15:
            score += 8.0
            reasons.append("1H hacim ortalamanin uzerinde")
        elif intraday_ratio < 0.75:
            score -= 6.0
            risks.append("1H hacim ivmesi zayif")

    return score, daily_ratio, intraday_ratio, reasons, risks


def _technical_pressure_component(daily_chart, intraday_1h, intraday_4h) -> tuple[float, list[str], list[str]]:
    reasons: list[str] = []
    risks: list[str] = []
    score = 0.0

    for label, chart, weight in (("gunluk", daily_chart, 1.0), ("1H", intraday_1h, 0.9), ("4H", intraday_4h, 0.75)):
        if chart is None:
            continue
        if chart.signal_bias == "bullish":
            score += 6.0 * weight
            reasons.append(f"{label} teknik bias pozitif")
        elif chart.signal_bias == "bearish":
            score -= 7.0 * weight
            risks.append(f"{label} teknik bias negatif")

        if chart.structure_bias == "bullish":
            score += 4.0 * weight
        elif chart.structure_bias == "bearish":
            score -= 4.0 * weight

        if chart.breakout_state == "confirmed_breakout_up":
            score += 11.0 * weight
            reasons.append(f"{label} kirilim teyidi var")
        elif chart.breakout_state == "breakout_watch_up":
            score += 6.5 * weight
            reasons.append(f"{label} yukari kirilim izleme bolgesinde")
        elif chart.breakout_state in {"breakout_watch_down", "confirmed_breakout_down"}:
            score -= 8.0 * weight
            risks.append(f"{label} asagi kirilim riski var")

    if daily_chart is not None:
        if 52 <= daily_chart.rsi14 <= 69:
            score += 6.0
            reasons.append("RSI momentum bandinda, asiri isinmis degil")
        elif daily_chart.rsi14 >= 78:
            score -= 7.0
            risks.append("Gunluk RSI asiri isinmis")
        elif daily_chart.rsi14 < 42:
            score -= 5.0
            risks.append("Gunluk momentum zayif")

    return score, reasons, risks


def _liquidity_component(market_snapshot) -> tuple[float, float | None, str, list[str], list[str]]:
    reasons: list[str] = []
    risks: list[str] = []
    if market_snapshot is None:
        return -8.0, None, "snapshot_missing", reasons, ["Anlik fiyat verisi alinamadi"]

    spread = _spread_percent(market_snapshot.best_bid, market_snapshot.best_ask)
    proxy = _order_flow_proxy(market_snapshot.best_bid, market_snapshot.best_ask)
    if proxy == "healthy_spread":
        return 6.0, spread, proxy, ["Bid/ask spread saglikli"], risks
    if proxy == "wide_but_tradeable":
        return 1.0, spread, proxy, reasons, ["Spread genislemeye baslamis"]
    if proxy == "wide_spread":
        return -6.0, spread, proxy, reasons, ["Spread genis; emir kalitesi zayiflayabilir"]
    return -2.0, spread, proxy, reasons, ["Derinlik verisi yok, emir akisi proxy ile sinirli"]


def _build_limit_up_candidate(company) -> tuple[LimitUpCandidateItem | None, bool]:
    market_snapshot = get_market_snapshot(company.ticker)
    if market_snapshot is None:
        return None, False

    if market_snapshot.change_percent >= 9.3:
        return None, True

    daily_chart = get_chart_feature_summary(company.ticker, timeframe="1G")
    intraday_1h = get_chart_feature_summary(company.ticker, timeframe="1H")
    intraday_4h = get_chart_feature_summary(company.ticker, timeframe="4H")

    change_score, change_reasons, change_risks = _change_runway_component(market_snapshot.change_percent)
    volume_score, daily_volume_ratio, intraday_volume_ratio, volume_reasons, volume_risks = _volume_pressure_component(market_snapshot, daily_chart, intraday_1h)
    technical_score, technical_reasons, technical_risks = _technical_pressure_component(daily_chart, intraday_1h, intraday_4h)
    liquidity_score, spread, order_proxy, liquidity_reasons, liquidity_risks = _liquidity_component(market_snapshot)

    score = _clamp(28.0 + change_score + volume_score + technical_score + liquidity_score, 0.0, 100.0)
    if score < 42:
        return None, False

    reasons = list(dict.fromkeys(change_reasons + volume_reasons + technical_reasons + liquidity_reasons))[:5]
    risks = list(dict.fromkeys(change_risks + volume_risks + technical_risks + liquidity_risks))[:5]

    return LimitUpCandidateItem(
        ticker=company.ticker,
        company_name=company.name,
        sector=company.sector,
        limit_up_score=round(score, 2),
        probability_bucket=_probability_bucket(score),
        last_price=market_snapshot.last_price,
        change_percent=market_snapshot.change_percent,
        distance_to_limit_percent=round(max(0.0, 10.0 - market_snapshot.change_percent), 2),
        volume=market_snapshot.volume,
        daily_volume_ratio=daily_volume_ratio,
        intraday_volume_ratio_1h=intraday_volume_ratio,
        technical_bias=daily_chart.signal_bias if daily_chart is not None else None,
        intraday_bias_1h=intraday_1h.signal_bias if intraday_1h is not None else None,
        breakout_state_1h=intraday_1h.breakout_state if intraday_1h is not None else None,
        spread_percent=spread,
        order_flow_proxy=order_proxy,
        entry_trigger=intraday_1h.breakout_buy_trigger if intraday_1h is not None else None,
        invalidation_level=intraday_1h.breakdown_sell_trigger if intraday_1h is not None else None,
        reasons=reasons,
        risks=risks,
    ), False


def _intraday_breakout_component(chart_summary) -> float:
    if chart_summary is None:
        return 0.0
    return {
        "confirmed_breakout_up": 0.65,
        "breakout_watch_up": 0.3,
        "support_test": 0.08,
        "range": 0.0,
        "resistance_test": -0.08,
        "breakout_watch_down": -0.3,
        "confirmed_breakout_down": -0.65,
    }.get(chart_summary.breakout_state, 0.0)



def _intraday_change_component(change_percent: float | None) -> float:
    if change_percent is None:
        return 0.0
    if change_percent >= 4.5:
        return 0.95
    if change_percent >= 2.5:
        return 0.65
    if change_percent >= 1.0:
        return 0.35
    if change_percent >= 0.0:
        return 0.1
    if change_percent <= -4.0:
        return -1.1
    if change_percent <= -2.0:
        return -0.65
    if change_percent <= -0.75:
        return -0.3
    return -0.1



def _compute_rank_score(item: MarketScanItem, chart_summary, trade_calibration=None, ranking_mode: str = "default") -> float:
    base = float(item.weighted_score)
    calibration_component = _trade_calibration_rank_component(trade_calibration)
    if chart_summary is None:
        return round(base + (item.confidence * 0.25) + calibration_component, 3)

    technical_component = float(chart_summary.signal_score) * 0.35

    volume_ratio = float(chart_summary.volume_ratio)
    if volume_ratio >= 1.25:
        volume_component = 0.9
    elif volume_ratio >= 1.0:
        volume_component = 0.4
    elif volume_ratio < 0.7:
        volume_component = -0.8
    elif volume_ratio < 0.9:
        volume_component = -0.4
    else:
        volume_component = 0.0

    breakout_component_map = {
        "confirmed_breakout_up": 1.2,
        "breakout_watch_up": 0.55,
        "support_test": 0.2,
        "range": 0.0,
        "resistance_test": -0.15,
        "breakout_watch_down": -0.55,
        "confirmed_breakout_down": -1.2,
    }
    breakout_component = breakout_component_map.get(chart_summary.breakout_state, 0.0)

    structure_component = {
        "bullish": 0.45,
        "neutral": 0.0,
        "bearish": -0.45,
    }.get(chart_summary.structure_bias, 0.0)

    rsi_component = 0.0
    if chart_summary.rsi14 >= 78:
        rsi_component = -0.55
    elif chart_summary.rsi14 >= 72:
        rsi_component = -0.2
    elif 55 <= chart_summary.rsi14 <= 68:
        rsi_component = 0.25
    elif chart_summary.rsi14 < 42:
        rsi_component = -0.35

    confidence_component = float(item.confidence) * 0.25
    rank_score = base + technical_component + volume_component + breakout_component + structure_component + rsi_component + confidence_component + calibration_component

    if ranking_mode != "today":
        return round(rank_score, 3)

    intraday_1h = get_chart_feature_summary(item.ticker, timeframe="1H")
    intraday_4h = get_chart_feature_summary(item.ticker, timeframe="4H")

    intraday_component = 0.0
    if intraday_1h is not None:
        intraday_component += float(intraday_1h.signal_score) * 0.18
        intraday_component += _intraday_breakout_component(intraday_1h)
    if intraday_4h is not None:
        intraday_component += float(intraday_4h.signal_score) * 0.14
        intraday_component += _intraday_breakout_component(intraday_4h) * 0.85

    change_component = _intraday_change_component(item.change_percent)

    if item.volume is not None and chart_summary.avg_volume > 0:
        daily_volume_ratio = item.volume / max(chart_summary.avg_volume, 1)
        if daily_volume_ratio >= 1.35:
            intraday_component += 0.35
        elif daily_volume_ratio <= 0.55:
            intraday_component -= 0.35

    if item.action == "buy" and (item.change_percent or 0) > 0:
        intraday_component += 0.1
    if item.action == "reduce" and (item.change_percent or 0) < 0:
        intraday_component -= 0.15

    rank_score += change_component + intraday_component
    return round(rank_score, 3)



def _append_evidence(
    evidence_items: list[AnalysisEvidence],
    used_sources: list[str],
    category: str,
    positive_factors: list[str],
    negative_factors: list[str],
    source: str,
) -> None:
    if source not in used_sources:
        used_sources.append(source)

    evidence_items.extend(
        AnalysisEvidence(category=category, impact="positive", detail=factor, source=source)
        for factor in positive_factors
    )
    evidence_items.extend(
        AnalysisEvidence(category=category, impact="negative", detail=factor, source=source)
        for factor in negative_factors
    )



def _build_scan_analysis(company):
    ticker = company.ticker
    chart_summary = get_chart_feature_summary(ticker)
    signal_summary = build_signal_summary_from_chart_feature(chart_summary)
    fundamental_summary = get_fundamental_summary(ticker)
    institutional_flow_summary = get_institutional_flow_summary(ticker)
    event_summary = get_event_summary(ticker)
    macro_event_summary = get_macro_event_summary(ticker)
    news_impact_summary = fetch_optional_news_impact(ticker, limit=3, days=3)
    trade_calibration = get_trade_calibration_cached(ticker, timeframe="1G", horizon_bars=10, sample_size=8, step_bars=5, use_cache_only=True)

    if (
        chart_summary is None
        and signal_summary is None
        and fundamental_summary is None
        and institutional_flow_summary is None
        and event_summary is None
        and macro_event_summary is None
        and news_impact_summary is None
        and trade_calibration is None
    ):
        return None

    used_sources: list[str] = []
    evidence_items: list[AnalysisEvidence] = []

    if chart_summary is not None:
        _append_evidence(
            evidence_items,
            used_sources,
            "technical_feature",
            chart_summary.positive_factors,
            chart_summary.negative_factors,
            chart_summary.source,
        )
        _append_evidence(
            evidence_items,
            used_sources,
            "trade_level",
            chart_summary.trade_level_positive_factors,
            chart_summary.trade_level_negative_factors,
            chart_summary.source,
        )

    if signal_summary is not None:
        _append_evidence(
            evidence_items,
            used_sources,
            "signal",
            signal_summary.positive_factors,
            signal_summary.negative_factors,
            signal_summary.source,
        )

    if fundamental_summary is not None:
        _append_evidence(
            evidence_items,
            used_sources,
            "fundamental",
            fundamental_summary.positive_factors,
            fundamental_summary.risk_factors,
            fundamental_summary.source,
        )

    if institutional_flow_summary is not None:
        _append_evidence(
            evidence_items,
            used_sources,
            "institutional_flow",
            institutional_flow_summary.positive_factors,
            institutional_flow_summary.negative_factors,
            institutional_flow_summary.source,
        )

    if event_summary is not None:
        _append_evidence(
            evidence_items,
            used_sources,
            "event",
            event_summary.supportive_events,
            event_summary.pressure_events,
            event_summary.source,
        )

    if macro_event_summary is not None:
        _append_evidence(
            evidence_items,
            used_sources,
            "macro_event",
            macro_event_summary.positive_impacts,
            macro_event_summary.negative_impacts,
            macro_event_summary.source,
        )

    if trade_calibration is not None:
        positive_factors, negative_factors = build_trade_calibration_signals(trade_calibration)
        if positive_factors or negative_factors:
            _append_evidence(
                evidence_items,
                used_sources,
                "trade_calibration",
                positive_factors,
                negative_factors,
                "replay_trade_calibration_service",
            )

    if news_impact_summary is not None:
        provider = news_impact_summary.provider
        average_sentiment = news_impact_summary.average_sentiment
        positive_factors: list[str] = []
        negative_factors: list[str] = []
        if average_sentiment is not None:
            if average_sentiment >= 0.08:
                positive_factors.append("Guncel haber akisi hisse tarafinda pozitif tona donuyor")
            elif average_sentiment <= -0.08:
                negative_factors.append("Guncel haber akisi hisse tarafinda negatif baski uretiyor")
        if positive_factors or negative_factors:
            _append_evidence(
                evidence_items,
                used_sources,
                "news_impact",
                positive_factors,
                negative_factors,
                provider,
            )

    if not evidence_items:
        return None

    recommendation = derive_recommendation(evidence_items)
    answer = _build_analysis_answer(ticker, evidence_items)
    confidence = _calculate_analysis_confidence(evidence_items, recommendation)

    return {
        "chart_summary": chart_summary,
        "trade_calibration": trade_calibration,
        "used_sources": used_sources,
        "analysis_evidence": evidence_items,
        "recommendation": recommendation,
        "answer": answer,
        "confidence": confidence,
    }



def _build_scan_items(stance: str | None = None, ranking_mode: str = "default") -> tuple[list[MarketScanItem], int]:
    normalized_stance = stance.lower() if stance is not None else None
    companies = list_company_records(universe_code="bist100")
    if not companies:
        companies = list_company_records()
    ranked_payloads: list[tuple[MarketScanItem, float, int]] = []

    for company in companies:
        scan_analysis = _build_scan_analysis(company)
        if scan_analysis is None:
            continue

        recommendation = scan_analysis["recommendation"]
        if recommendation is None:
            continue
        if normalized_stance is not None and recommendation.stance.lower() != normalized_stance:
            continue

        market_snapshot = get_market_snapshot(company.ticker)
        chart_summary = scan_analysis["chart_summary"]
        technical_score = chart_summary.signal_score if chart_summary is not None else 0
        evidence_items = scan_analysis["analysis_evidence"]
        item = MarketScanItem(
            ticker=company.ticker,
            company_name=company.name,
            sector=company.sector,
            stance=recommendation.stance,
            action=recommendation.action,
            confidence=scan_analysis["confidence"],
            score=recommendation.score,
            weighted_score=recommendation.weighted_score,
            last_price=market_snapshot.last_price if market_snapshot is not None else None,
            change_percent=market_snapshot.change_percent if market_snapshot is not None else None,
            volume=market_snapshot.volume if market_snapshot is not None else None,
            market_data_source=market_snapshot.source if market_snapshot is not None else None,
            technical_summary=_build_technical_summary(chart_summary),
            news_impact_summary=_build_news_impact_summary(evidence_items),
            used_sources=scan_analysis["used_sources"],
            summary=scan_analysis["answer"],
            top_positive_factors=_top_factors(evidence_items, "positive"),
            top_negative_factors=_top_factors(evidence_items, "negative"),
        )
        rank_score = _compute_rank_score(item, chart_summary, scan_analysis.get("trade_calibration"), ranking_mode=ranking_mode)
        ranked_payloads.append((item, rank_score, technical_score))

    ranked_items = [
        item
        for item, _rank_score, _technical_score in sorted(
            ranked_payloads,
            key=lambda pair: (pair[1], pair[0].weighted_score, pair[2], pair[0].confidence, pair[0].change_percent or -999, pair[0].volume or 0),
            reverse=True,
        )
    ]
    return ranked_items, len(companies)



def scan_market(stance: str | None = None, limit: int = 20, ranking_mode: str = "default") -> MarketScanResponse:
    ranked_items, universe_size = _build_scan_items(stance=stance, ranking_mode=ranking_mode)
    limited_items = ranked_items[: max(limit, 1)]

    return MarketScanResponse(
        generated_at=datetime.utcnow().isoformat(),
        universe_size=universe_size,
        total=len(limited_items),
        items=limited_items,
    )


def scan_limit_up_candidates(limit: int = 15) -> LimitUpCandidateResponse:
    companies = list_company_records(universe_code="bist100")
    if not companies:
        companies = list_company_records()

    candidates: list[LimitUpCandidateItem] = []
    excluded_already_limit_count = 0
    for company in companies:
        candidate, already_limit = _build_limit_up_candidate(company)
        if already_limit:
            excluded_already_limit_count += 1
            continue
        if candidate is not None:
            candidates.append(candidate)

    ranked = sorted(
        candidates,
        key=lambda item: (
            item.limit_up_score,
            item.change_percent or -999,
            item.daily_volume_ratio or 0,
            item.intraday_volume_ratio_1h or 0,
            item.volume or 0,
        ),
        reverse=True,
    )
    limited_items = ranked[: max(limit, 1)]
    return LimitUpCandidateResponse(
        generated_at=datetime.utcnow().isoformat(),
        universe_size=len(companies),
        total=len(limited_items),
        excluded_already_limit_count=excluded_already_limit_count,
        items=limited_items,
    )



def save_market_scan_snapshot(stance: str | None = None, limit: int = 20) -> ScanSnapshotCreateResponse:
    ensure_runtime_schema()
    result = scan_market(stance=stance, limit=limit)
    provider = get_active_market_data_provider()
    normalized_stance = (stance or "all").lower()

    with SessionLocal() as session:
        snapshot = ScanSnapshot(
            stance_filter=normalized_stance,
            limit_requested=limit,
            universe_size=result.universe_size,
            total_returned=result.total,
            provider=provider,
            items=[item.model_dump() for item in result.items],
            market_data_source_summary=_summarize_market_data_sources(result.items),
            used_source_summary=_summarize_used_sources(result.items),
            runtime_health_summary=_runtime_health_snapshot(),
        )
        session.add(snapshot)
        session.commit()
        session.refresh(snapshot)

    return ScanSnapshotCreateResponse(
        snapshot_id=snapshot.id,
        created_at=snapshot.created_at.isoformat(),
        stance_filter=snapshot.stance_filter,
        total_returned=snapshot.total_returned,
        provider=snapshot.provider,
        market_data_source_summary=snapshot.market_data_source_summary or {},
        used_source_summary=snapshot.used_source_summary or {},
        runtime_health_summary=snapshot.runtime_health_summary or {},
        status="saved",
    )



def get_market_scan_snapshot_history(limit: int = 20, stance: str | None = None, provider: str | None = None) -> ScanSnapshotHistoryResponse:
    ensure_runtime_schema()
    normalized_stance = stance.lower() if stance is not None else None
    normalized_provider = provider.lower() if provider is not None else None

    with SessionLocal() as session:
        statement = select(ScanSnapshot)
        if normalized_stance is not None:
            statement = statement.where(ScanSnapshot.stance_filter == normalized_stance)
        if normalized_provider is not None:
            statement = statement.where(ScanSnapshot.provider == normalized_provider)
        statement = statement.order_by(ScanSnapshot.created_at.desc(), ScanSnapshot.id.desc()).limit(max(limit, 1))

        rows = session.execute(statement).scalars().all()

    items = [
        ScanSnapshotHistoryItem(
            id=row.id,
            created_at=row.created_at.isoformat(),
            stance_filter=row.stance_filter,
            limit_requested=row.limit_requested,
            universe_size=row.universe_size,
            total_returned=row.total_returned,
            provider=row.provider,
            market_data_source_summary=row.market_data_source_summary or {},
            used_source_summary=row.used_source_summary or {},
            runtime_health_summary=row.runtime_health_summary or {},
        )
        for row in rows
    ]

    return ScanSnapshotHistoryResponse(total=len(items), items=items)
