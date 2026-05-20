from app.agent.router import build_citations, detect_route_type, extract_ticker
from app.data_sources.company_data.provider import list_company_records
from app.data_sources.market_data.provider import get_market_snapshot
from app.models.schemas import AnalysisEvidence, AskResponse, RecommendationPolicyResult
from app.rag.local_retriever import retrieve_documents
from app.services.chart_feature_service import get_chart_feature_summary
from app.services.event_service import get_event_summary
from app.services.fundamental_service import get_fundamental_summary
from app.services.institutional_flow_service import get_institutional_flow_summary
from app.services.macro_event_service import get_macro_event_summary
from app.services.news_impact_service import fetch_optional_news_impact
from app.services.recommendation_policy import derive_recommendation
from app.services.replay_evaluation_service import build_trade_calibration_signals, get_trade_calibration_cached
from app.services.signal_service import get_signal_summary


def _pick_first(evidence_items: list[AnalysisEvidence], category: str, impact: str) -> str | None:
    for item in evidence_items:
        if item.category == category and item.impact == impact:
            return item.detail
    return None



def _highlight_priority(detail: str) -> int:
    lowered = detail.lower()
    generic_markers = [
        "risk algisini degistirebilir",
        "destekleyici",
        "gorunumu",
    ]
    specific_markers = [
        "savunma",
        "ucus",
        "rota",
        "bankacilik",
        "faiz",
        "tedarik",
        "lojistik",
        "yakit",
        "proje",
        "talebi",
        "ema",
        "rsi",
        "destek",
        "direnc",
        "kirilim",
    ]

    score = 0
    if any(marker in lowered for marker in specific_markers):
        score += 2
    if any(marker in lowered for marker in generic_markers):
        score -= 1
    if len(lowered) > 45:
        score += 1
    return score



def _pick_best_by_category(evidence_items: list[AnalysisEvidence], category: str, impact: str) -> str | None:
    candidates = [item.detail for item in evidence_items if item.category == category and item.impact == impact]
    if not candidates:
        return None
    return sorted(candidates, key=_highlight_priority, reverse=True)[0]



def _pick_event_highlight(evidence_items: list[AnalysisEvidence], impact: str) -> str | None:
    for category in ["institutional_flow", "news_impact", "macro_event", "event"]:
        detail = _pick_best_by_category(evidence_items, category, impact)
        if detail is not None:
            return detail
    return None



def _fallback_highlights(evidence_items: list[AnalysisEvidence], impact: str, limit: int = 4) -> list[str]:
    return [item.detail for item in evidence_items if item.impact == impact][:limit]



def _build_trade_calibration_evidence(calibration) -> list[AnalysisEvidence]:
    positive_factors, negative_factors = build_trade_calibration_signals(calibration)
    evidence_items: list[AnalysisEvidence] = []
    for detail in positive_factors:
        evidence_items.append(
            AnalysisEvidence(
                category="trade_calibration",
                impact="positive",
                detail=detail,
                source="replay_trade_calibration_service",
            )
        )
    for detail in negative_factors:
        evidence_items.append(
            AnalysisEvidence(
                category="trade_calibration",
                impact="negative",
                detail=detail,
                source="replay_trade_calibration_service",
            )
        )
    return evidence_items


SECTOR_ALIAS_MAP = {
    "bankacilik": ["Banking"],
    "banka": ["Banking"],
    "enerji": ["Energy", "Utilities"],
    "otomotiv": ["Automotive"],
    "savunma": ["Defense"],
    "telekom": ["Telecom"],
    "perakende": ["Retail"],
    "sigorta": ["Insurance"],
    "holding": ["Holding", "Conglomerates"],
    "konglomera": ["Conglomerates"],
    "teknoloji": ["Technology"],
    "saglik": ["Healthcare"],
    "gida": ["Food"],
    "gayrimenkul": ["Real Estate"],
    "gyo": ["Real Estate"],
    "malzeme": ["Materials"],
    "kimya": ["Chemicals"],
    "maden": ["Mining"],
    "celik": ["Steel"],
    "havacilik": ["Airlines", "Airports"],
}


def _question_lower(question: str) -> str:
    return question.lower().strip()



def _is_generic_market_pick_question(question: str) -> bool:
    lowered = _question_lower(question)
    patterns = [
        "su an alima en uygun hisse",
        "alima en uygun hisse",
        "bugun alinabilecek hisse",
        "bugun alinabilecek hisseler",
        "en uygun hisse",
        "en iyi hisse",
        "hangi hisseler alinabilir",
        "hangi hisse alinabilir",
        "hangi hisseler one cikiyor",
        "alinabilecek hisseler",
        "tavan ihtimali",
        "bugun hangi hisse tavan yapar",
        "hangi hisse tavan yapar",
        "tavan yapabilecek hisse",
        "tavan yapma ihtimali",
        "tavan olabilir",
        "tavana gidebilir",
        "en sert yukselebilecek hisse",
        "bugun acilista",
        "bugün açılışta",
        "acilista hangi",
        "açılışta hangi",
        "hangi hisseleri izleyelim",
        "hangi hisseler izlenir",
        "acilista yukselebilecek",
        "açılışta yükselebilecek",
        "sabah acilista",
        "sabah açılışta",
        "borsa acildiginda",
        "borsa açıldığında",
        "ilk acilista",
        "ilk açılışta",
        "yarin sabah",
        "yarın sabah",
    ]
    return any(pattern in lowered for pattern in patterns)



def _extract_requested_sectors(question: str) -> list[str]:
    lowered = _question_lower(question)
    sectors: list[str] = []
    seen: set[str] = set()
    for alias, mapped in SECTOR_ALIAS_MAP.items():
        if alias not in lowered:
            continue
        for sector in mapped:
            if sector in seen:
                continue
            seen.add(sector)
            sectors.append(sector)
    return sectors



def _is_sector_question(question: str) -> bool:
    lowered = _question_lower(question)
    if "sektor" in lowered or "daha avantajli" in lowered:
        return True
    return len(_extract_requested_sectors(question)) >= 1



def _scan_item_to_recommendation(item) -> RecommendationPolicyResult:
    return RecommendationPolicyResult(
        stance=item.stance,
        action=item.action,
        score=item.score,
        weighted_score=item.weighted_score,
        summary=f"Scan siralamasinda one cikan aday {item.ticker}; weighted score {item.weighted_score} ve confidence {item.confidence}.",
    )



def _scan_item_to_evidence(item) -> list[AnalysisEvidence]:
    evidence: list[AnalysisEvidence] = []
    source = item.used_sources[0] if item.used_sources else "market_scan_service"
    for detail in item.top_positive_factors[:3]:
        evidence.append(AnalysisEvidence(category="market_scan", impact="positive", detail=detail, source=source))
    for detail in item.top_negative_factors[:3]:
        evidence.append(AnalysisEvidence(category="market_scan", impact="negative", detail=detail, source=source))
    return evidence


def _is_today_sensitive_question(question: str) -> bool:
    lowered = _question_lower(question)
    markers = [
        "bugun",
        "su an",
        "şu an",
        "simdi",
        "anlik",
        "tavan",
        "gun ici",
        "gün içi",
    ]
    return any(marker in lowered for marker in markers)


def _is_limit_up_question(question: str) -> bool:
    lowered = _question_lower(question)
    markers = [
        "tavan ihtimali",
        "tavan yapar",
        "tavan olabilir",
        "tavan yapabilecek",
        "tavana gider",
        "tavana gidebilir",
        "en sert yukselebilecek",
    ]
    return any(marker in lowered for marker in markers)


def _is_opening_candidate_question(question: str) -> bool:
    lowered = _question_lower(question)
    markers = [
        "acilista",
        "açılışta",
        "sabah acilis",
        "sabah açılış",
        "borsa acildiginda",
        "borsa açıldığında",
        "ilk acilis",
        "ilk açılış",
        "yarin sabah",
        "yarın sabah",
        "ertesi seans",
        "ertesi gun",
        "ertesi gün",
    ]
    return any(marker in lowered for marker in markers)


def _is_trading_agent_question(question: str) -> bool:
    lowered = _question_lower(question)
    markers = [
        "bugun ne alalim",
        "bugün ne alalım",
        "ne alalim",
        "ne alalım",
        "ne yapalim",
        "ne yapalım",
        "son durum",
        "simulasyon",
        "simülasyon",
        "sepet",
        "pozisyon",
        "kalan para",
        "agent",
    ]
    return any(marker in lowered for marker in markers)


def _build_trading_agent_response(question: str) -> AskResponse:
    from app.services.trading_agent_service import get_trading_agent_status

    status = get_trading_agent_status()
    trade_lines = [
        f"{item.ticker}: giris {item.entry_price}, guncel {item.current_price}, getiri %{round(item.current_return_percent, 2)}, kalan sermaye {round(item.remaining_capital, 2)}, toplam PnL {round(item.total_position_pnl, 2)}"
        for item in status.open_trades[:8]
    ]
    decision_lines = [
        f"{item.ticker or '-'} {item.action} ({item.phase}): {item.rationale}"
        for item in status.latest_decisions[:5]
    ]
    action_lines = [
        f"{item.ticker}: {item.action} - {item.rationale}"
        for item in status.position_decisions[:6]
    ]

    if trade_lines:
        answer = (
            f"Agent durumuna gore aktif strateji {status.active_strategy_name}. "
            f"Acik paper trade sayisi {status.open_trade_count}, kapanmis trade sayisi {status.closed_trade_count}, "
            f"deployed sermaye {status.deployed_capital} TL, portfoy equity {status.portfolio_equity} TL, "
            f"kullanilabilir nakit {status.available_cash} TL, realize PnL {status.total_realized_pnl} TL, "
            f"acik PnL {status.total_open_unrealized_pnl} TL, toplam PnL {status.total_position_pnl} TL, "
            f"risk seviyesi {status.portfolio_risk_level}. "
            f"Pozisyonlar: {'; '.join(trade_lines)}."
        )
    else:
        answer = "Agent tarafinda acik paper trade yok. Yeni sepet icin once opening-plan calistirilmasi gerekir."

    if action_lines:
        answer += f" Aksiyon plani: {'; '.join(action_lines)}."
    answer += f" Nakit karari: {status.cash_action}. {status.cash_rationale}"
    answer += f" Sonraki kontrol onerisi: {status.recommended_next_check_minutes} dk."
    if decision_lines:
        answer += f" Son karar izleri: {'; '.join(decision_lines)}."
    answer += " Not: Ask cevabi yeni islem acmaz; sadece agent durumunu ve karar izlerini okur."

    return AskResponse(
        question=question,
        route_type="analysis_query",
        answer=answer,
        used_sources=["trading_agent_status", "paper_trade_simulation", "trading_agent_decision_log"],
        confidence=0.72 if status.open_trades else 0.45,
        reasoning_summary="Soru gunluk al/sat veya simulasyon karar niyeti tasidigi icin trading agent status ve karar loglari uzerinden yanitlandi; chat cevabi yan etki olarak yeni trade acmadi.",
        recommendation=None,
        analysis_evidence=[],
        citations=[],
    )



def _build_generic_market_pick_response(question: str) -> AskResponse:
    from app.services.market_scan_service import get_scan_universe_coverage, scan_limit_up_candidates, scan_market, scan_pre_market_watchlist

    if _is_opening_candidate_question(question):
        pre_market_scan = scan_pre_market_watchlist(limit=5)
        coverage = get_scan_universe_coverage()
        if not pre_market_scan.items:
            return AskResponse(
                question=question,
                route_type="analysis_query",
                answer=(
                    "Pre-market izleme taramasindan esik ustu guclu aday cikmadi. "
                    f"Tarama evreni: {coverage.scanned_universe_size} hisse "
                    f"({coverage.base_universe_size} ana evren + {len(coverage.configured_momentum_tickers)} ek momentum ticker)."
                ),
                used_sources=["pre_market_watchlist_scan"],
                confidence=0.35,
                reasoning_summary="Acilis oncesi soru icin onceki gun kapanis gucu, gunluk hacim, 5 gun momentum ve gunluk teknik bias ile pre-market watchlist taramasi calisti ancak aday donmedi.",
                recommendation=None,
                analysis_evidence=[],
                citations=[],
            )
        top = pre_market_scan.items[0]
        alternates = ", ".join(f"{item.ticker} ({item.probability_bucket}, skor {item.pre_market_score})" for item in pre_market_scan.items[1:4])
        reason_text = "; ".join(top.reasons[:3])
        risk_text = "; ".join(top.risks[:2])
        answer = (
            f"Kesin acilis tahmini veremem; ama pre-market izleme taramasina gore en guclu aday {top.ticker} ({top.company_name}). "
            f"Bu cevap {coverage.scanned_universe_size} hisselik izleme evreni taranarak uretildi "
            f"({coverage.base_universe_size} ana evren + {len(coverage.configured_momentum_tickers)} ek momentum ticker). "
            f"Pre-market skoru {top.pre_market_score}/100, kategori {top.probability_bucket}, onceki kapanis {top.previous_close}, "
            f"onceki degisim %{top.previous_change_percent}, kapanis gucu {top.close_position_percent}, hacim orani {top.volume_ratio}. "
            f"Izleme tetigi {top.trigger_price}, iptal seviyesi {top.invalidation_price}, kurgu {top.setup_type}. "
            f"Gerekce: {reason_text}."
        )
        if risk_text:
            answer += f" Risk: {risk_text}."
        if alternates:
            answer += f" Alternatif adaylar: {alternates}."
        return AskResponse(
            question=question,
            route_type="analysis_query",
            answer=answer,
            used_sources=["pre_market_watchlist_scan", "matriks_ohlcv", "chart_feature_signal_service"],
            confidence=0.72 if top.probability_bucket == "high" else 0.62,
            reasoning_summary="Acilis oncesi soru, onceki gun kapanis gucu, hacim teyidi, 5 gun momentum, gunluk teknik bias ve kirilim durumu ile pre-market watchlist skoru kullanilarak yanitlandi.",
            recommendation=None,
            analysis_evidence=[],
            citations=[],
        )

    if _is_limit_up_question(question):
        limit_scan = scan_limit_up_candidates(limit=5)
        if not limit_scan.items:
            return AskResponse(
                question=question,
                route_type="analysis_query",
                answer="Su an tavan aday taramasindan yeterince guclu aday cikmadi.",
                used_sources=["limit_up_candidate_scan"],
                confidence=0.35,
                reasoning_summary="Tavan odakli soru icin ozel limit-up candidate taramasi calisti ancak esik ustu aday donmedi.",
                recommendation=None,
                analysis_evidence=[],
                citations=[],
            )
        top = limit_scan.items[0]
        alternates = ", ".join(f"{item.ticker} ({item.probability_bucket}, skor {item.limit_up_score})" for item in limit_scan.items[1:4])
        reason_text = "; ".join(top.reasons[:3])
        risk_text = "; ".join(top.risks[:2])
        answer = (
            f"Kesin tavan tahmini veremem; ama tavan odakli taramaya gore su an en guclu aday {top.ticker} ({top.company_name}). "
            f"Limit-up skoru {top.limit_up_score}/100, kategori {top.probability_bucket}, son fiyat {top.last_price}, gunluk degisim %{top.change_percent}, tavana kalan yaklasik %{top.distance_to_limit_percent}. "
            f"Tetik seviye {top.entry_trigger}, iptal seviyesi {top.invalidation_level}. "
            f"Gerekce: {reason_text}."
        )
        if risk_text:
            answer += f" Risk: {risk_text}."
        if alternates:
            answer += f" Alternatif adaylar: {alternates}."
        return AskResponse(
            question=question,
            route_type="analysis_query",
            answer=answer,
            used_sources=["limit_up_candidate_scan", "matriks_market_data_tool", "chart_feature_signal_service"],
            confidence=0.72 if top.probability_bucket == "high" else 0.62,
            reasoning_summary="Tavan sorusu, gunluk yuzde ivmesi, hacim baskisi, 1H/4H teknik durum ve bid/ask spread proxy'si ile ozel limit-up candidate skoru kullanilarak yanitlandi.",
            recommendation=None,
            analysis_evidence=[],
            citations=[],
        )

    ranking_mode = "today" if _is_today_sensitive_question(question) else "default"
    scan = scan_market(limit=5, ranking_mode=ranking_mode)
    if not scan.items:
        return AskResponse(
            question=question,
            route_type="analysis_query",
            answer="Su an genel market taramasindan aday cikmadi.",
            used_sources=["market_scan_service"],
            confidence=0.25,
            reasoning_summary="Genel piyasa taramasi denendi ancak uygun aday donmedi.",
            recommendation=None,
            analysis_evidence=[],
            citations=[],
        )

    top = scan.items[0]
    alternates = ", ".join(f"{item.ticker}" for item in scan.items[1:4])
    answer = (
        f"Su an mevcut market taramasina gore en guclu aday {top.ticker} ({top.company_name}) gorunuyor. "
        f"Stance {top.stance}, aksiyon {top.action}, weighted score {top.weighted_score}, confidence {top.confidence}. "
        f"Kisa gerekce: {top.summary}"
    )
    reasoning_summary = "Ticker belirtilmeden gelen genel alım sorusu, soru bugun/anlik baglami tasiyorsa gun ici momentum destekli scan ile yanitlandi."
    if alternates:
        answer += f" Alternatif olarak {alternates} de yakindan izlenebilir."

    used_sources = list(dict.fromkeys(source for item in scan.items[:3] for source in item.used_sources)) or ["market_scan_service"]
    return AskResponse(
        question=question,
        route_type="analysis_query",
        answer=answer,
        used_sources=used_sources,
        confidence=max(0.55, min(0.9, top.confidence)),
        reasoning_summary=reasoning_summary,
        recommendation=_scan_item_to_recommendation(top),
        analysis_evidence=_scan_item_to_evidence(top),
        citations=[],
    )



def _build_sector_comparison_response(question: str) -> AskResponse:
    from app.services.market_scan_service import scan_market

    ranking_mode = "today" if _is_today_sensitive_question(question) else "default"
    scan = scan_market(limit=max(len(list_company_records()), 20), ranking_mode=ranking_mode)
    if not scan.items:
        return AskResponse(
            question=question,
            route_type="analysis_query",
            answer="Sektor karsilastirmasi icin yeterli scan verisi donmedi.",
            used_sources=["market_scan_service"],
            confidence=0.25,
            reasoning_summary="Sektor karsilastirmasi denendi ancak scan verisi alinmadi.",
            recommendation=None,
            analysis_evidence=[],
            citations=[],
        )

    requested_sectors = _extract_requested_sectors(question)
    sector_buckets: dict[str, list] = {}
    for item in scan.items:
        sector_buckets.setdefault(item.sector, []).append(item)

    if requested_sectors:
        candidates = [(sector, sector_buckets.get(sector, [])) for sector in requested_sectors if sector_buckets.get(sector)]
    else:
        candidates = list(sector_buckets.items())

    if not candidates:
        return AskResponse(
            question=question,
            route_type="analysis_query",
            answer="Sorudaki sektorler mevcut scan evreninde eslesmedi.",
            used_sources=["market_scan_service"],
            confidence=0.25,
            reasoning_summary="Sektor niyeti algilandi ancak scan icinde eslesen sektor bulunamadi.",
            recommendation=None,
            analysis_evidence=[],
            citations=[],
        )

    ranked = []
    for sector, items in candidates:
        avg_weighted = round(sum(item.weighted_score for item in items) / len(items), 2)
        bullish_share = round(sum(1 for item in items if item.stance == "bullish") / len(items), 2)
        top_item = sorted(items, key=lambda item: (item.weighted_score, item.confidence), reverse=True)[0]
        ranked.append((sector, avg_weighted, bullish_share, top_item, len(items)))

    ranked.sort(key=lambda row: (row[1], row[2], row[4]), reverse=True)
    best_sector, avg_weighted, bullish_share, top_item, sector_count = ranked[0]

    if len(ranked) >= 2:
        comparison_lines = [
            f"{sector}: ortalama weighted score {avg}, bullish oran {share}, one cikan hisse {leader.ticker}"
            for sector, avg, share, leader, _count in ranked[:3]
        ]
        answer = (
            f"Mevcut scan gorunume gore {best_sector} su an daha avantajli gorunuyor. "
            f"Bu sektorde ortalama weighted score {avg_weighted} ve bullish oran {bullish_share}. "
            f"One cikan temsilci {top_item.ticker}. "
            f"Karsilastirma: {'; '.join(comparison_lines)}."
        )
    else:
        answer = (
            f"Mevcut scan gorunume gore {best_sector} su an one cikiyor. "
            f"Ortalama weighted score {avg_weighted}, bullish oran {bullish_share}, one cikan hisse {top_item.ticker}."
        )

    used_sources = list(dict.fromkeys(source for _sector, _avg, _share, leader, _count in ranked[:3] for source in leader.used_sources)) or ["market_scan_service"]
    evidence = _scan_item_to_evidence(top_item)
    return AskResponse(
        question=question,
        route_type="analysis_query",
        answer=answer,
        used_sources=used_sources,
        confidence=max(0.5, min(0.85, top_item.confidence)),
        reasoning_summary="Sektor sorusu, scan sonuclari sektor bazinda gruplanip ortalama score ve bullish yogunluguna gore karsilastirilerek yanitlandi.",
        recommendation=None,
        analysis_evidence=evidence,
        citations=[],
    )



def _try_generic_analysis_answer(question: str) -> AskResponse | None:
    if _is_trading_agent_question(question):
        return _build_trading_agent_response(question)
    if _is_generic_market_pick_question(question):
        return _build_generic_market_pick_response(question)
    if _is_sector_question(question):
        return _build_sector_comparison_response(question)
    return None


def _build_trade_level_note(chart_feature_summary) -> str | None:
    if chart_feature_summary is None:
        return None
    return (
        f"Teknik referans olarak {chart_feature_summary.trend_reference_level} trend seviyesi, "
        f"{chart_feature_summary.entry_zone_low}-{chart_feature_summary.entry_zone_high} giris bolgesi, "
        f"{chart_feature_summary.breakout_buy_trigger} yukari teyit, "
        f"{chart_feature_summary.stop_loss_level} ise risk seviyesi olarak izlenebilir."
    )


def _build_analysis_answer(ticker: str, evidence_items: list[AnalysisEvidence]) -> str:
    rise_highlights = [
        _pick_first(evidence_items, "signal", "positive"),
        _pick_first(evidence_items, "trade_level", "positive"),
        _pick_first(evidence_items, "fundamental", "positive"),
        _pick_event_highlight(evidence_items, "positive"),
    ]
    fall_highlights = [
        _pick_first(evidence_items, "signal", "negative"),
        _pick_first(evidence_items, "trade_level", "negative"),
        _pick_first(evidence_items, "fundamental", "negative"),
        _pick_event_highlight(evidence_items, "negative"),
    ]

    rise_items = [item for item in rise_highlights if item is not None]
    fall_items = [item for item in fall_highlights if item is not None]

    if len(rise_items) < 4:
        for detail in _fallback_highlights(evidence_items, "positive"):
            if detail not in rise_items:
                rise_items.append(detail)
            if len(rise_items) >= 4:
                break

    if len(fall_items) < 4:
        for detail in _fallback_highlights(evidence_items, "negative"):
            if detail not in fall_items:
                fall_items.append(detail)
            if len(fall_items) >= 4:
                break

    return (
        f"{ticker} icin yukselisi destekleyebilecek kosullar: {', '.join(rise_items[:4])}. "
        f"Dususu tetikleyebilecek kosullar: {', '.join(fall_items[:4])}."
    )



def _calculate_analysis_confidence(
    evidence_items: list[AnalysisEvidence],
    recommendation: RecommendationPolicyResult | None,
) -> float:
    categories = {item.category for item in evidence_items}
    confidence_groups = set(categories)
    if {"technical_feature", "signal", "trade_level"} & confidence_groups:
        confidence_groups.discard("technical_feature")
        confidence_groups.discard("signal")
        confidence_groups.discard("trade_level")
        confidence_groups.add("technical_stack")
    positive_count = sum(1 for item in evidence_items if item.impact == "positive")
    negative_count = sum(1 for item in evidence_items if item.impact == "negative")

    confidence = 0.32
    confidence += min(len(confidence_groups), 6) * 0.05
    confidence += min(len(evidence_items), 12) * 0.008

    if positive_count > 0 and negative_count > 0:
        confidence += 0.03

    if recommendation is not None:
        weighted_strength = abs(recommendation.weighted_score)
        if weighted_strength >= 4:
            confidence += 0.06
        elif weighted_strength >= 2:
            confidence += 0.04
        elif weighted_strength >= 1:
            confidence += 0.02

    if (
        {"signal", "fundamental"}.issubset(categories)
        or {"technical_feature", "fundamental"}.issubset(categories)
        or {"trade_level", "fundamental"}.issubset(categories)
    ):
        confidence += 0.03
    if "technical_feature" in categories:
        confidence += 0.01
    if "trade_level" in categories:
        confidence += 0.01
    if "macro_event" in categories:
        confidence += 0.02
    if "institutional_flow" in categories:
        confidence += 0.01
    if "news_impact" in categories:
        confidence += 0.02

    calibration_impacts = [item.impact for item in evidence_items if item.category == "trade_calibration"]
    if any(impact == "positive" for impact in calibration_impacts):
        confidence += 0.01
    if any(impact == "negative" for impact in calibration_impacts):
        confidence -= 0.02

    return round(max(0.2, min(confidence, 0.92)), 2)



def build_analysis_response_for_ticker(ticker: str, question: str | None = None) -> AskResponse:
    normalized_ticker = ticker.upper()
    effective_question = question or f"{normalized_ticker} hangi kosullarda artar ve hangi kosullarda duser?"

    chart_feature_summary = get_chart_feature_summary(normalized_ticker)
    signal_summary = get_signal_summary(normalized_ticker)
    fundamental_summary = get_fundamental_summary(normalized_ticker)
    institutional_flow_summary = get_institutional_flow_summary(normalized_ticker)
    event_summary = get_event_summary(normalized_ticker)
    macro_event_summary = get_macro_event_summary(normalized_ticker)
    news_impact_summary = fetch_optional_news_impact(normalized_ticker, limit=5, days=7)
    trade_calibration = get_trade_calibration_cached(normalized_ticker, timeframe="1G", horizon_bars=10, sample_size=8, step_bars=5)

    if (
        chart_feature_summary is None
        and signal_summary is None
        and fundamental_summary is None
        and institutional_flow_summary is None
        and event_summary is None
        and macro_event_summary is None
        and news_impact_summary is None
        and trade_calibration is None
    ):
        return AskResponse(
            question=effective_question,
            route_type="analysis_query",
            answer=f"{normalized_ticker} icin analiz verisi bulunamadi.",
            used_sources=["analysis_router"],
            confidence=0.2,
            reasoning_summary="Analiz akisi secildi ancak ilgili ticker icin teknik, sinyal, temel, kurumsal akim, olay veya makro olay verisi mevcut degildi.",
            recommendation=None,
            analysis_evidence=[],
            citations=[],
        )

    used_sources: list[str] = []
    analysis_evidence: list[AnalysisEvidence] = []

    if chart_feature_summary is not None:
        used_sources.append(chart_feature_summary.source)
        analysis_evidence.extend(
            [
                AnalysisEvidence(
                    category="technical_feature",
                    impact="positive",
                    detail=factor,
                    source=chart_feature_summary.source,
                )
                for factor in chart_feature_summary.positive_factors
            ]
        )
        analysis_evidence.extend(
            [
                AnalysisEvidence(
                    category="technical_feature",
                    impact="negative",
                    detail=factor,
                    source=chart_feature_summary.source,
                )
                for factor in chart_feature_summary.negative_factors
            ]
        )
        analysis_evidence.extend(
            [
                AnalysisEvidence(
                    category="trade_level",
                    impact="positive",
                    detail=factor,
                    source=chart_feature_summary.source,
                )
                for factor in chart_feature_summary.trade_level_positive_factors
            ]
        )
        analysis_evidence.extend(
            [
                AnalysisEvidence(
                    category="trade_level",
                    impact="negative",
                    detail=factor,
                    source=chart_feature_summary.source,
                )
                for factor in chart_feature_summary.trade_level_negative_factors
            ]
        )

    if signal_summary is not None:
        used_sources.append(signal_summary.source)
        analysis_evidence.extend(
            [
                AnalysisEvidence(
                    category="signal",
                    impact="positive",
                    detail=factor,
                    source=signal_summary.source,
                )
                for factor in signal_summary.positive_factors
            ]
        )
        analysis_evidence.extend(
            [
                AnalysisEvidence(
                    category="signal",
                    impact="negative",
                    detail=factor,
                    source=signal_summary.source,
                )
                for factor in signal_summary.negative_factors
            ]
        )

    if fundamental_summary is not None:
        used_sources.append(fundamental_summary.source)
        analysis_evidence.extend(
            [
                AnalysisEvidence(
                    category="fundamental",
                    impact="positive",
                    detail=factor,
                    source=fundamental_summary.source,
                )
                for factor in fundamental_summary.positive_factors
            ]
        )
        analysis_evidence.extend(
            [
                AnalysisEvidence(
                    category="fundamental",
                    impact="negative",
                    detail=factor,
                    source=fundamental_summary.source,
                )
                for factor in fundamental_summary.risk_factors
            ]
        )

    if institutional_flow_summary is not None:
        used_sources.append(institutional_flow_summary.source)
        analysis_evidence.extend(
            [
                AnalysisEvidence(
                    category="institutional_flow",
                    impact="positive",
                    detail=factor,
                    source=institutional_flow_summary.source,
                )
                for factor in institutional_flow_summary.positive_factors
            ]
        )
        analysis_evidence.extend(
            [
                AnalysisEvidence(
                    category="institutional_flow",
                    impact="negative",
                    detail=factor,
                    source=institutional_flow_summary.source,
                )
                for factor in institutional_flow_summary.negative_factors
            ]
        )

    if event_summary is not None:
        used_sources.append(event_summary.source)
        analysis_evidence.extend(
            [
                AnalysisEvidence(
                    category="event",
                    impact="positive",
                    detail=factor,
                    source=event_summary.source,
                )
                for factor in event_summary.supportive_events
            ]
        )
        analysis_evidence.extend(
            [
                AnalysisEvidence(
                    category="event",
                    impact="negative",
                    detail=factor,
                    source=event_summary.source,
                )
                for factor in event_summary.pressure_events
            ]
        )

    if macro_event_summary is not None:
        used_sources.append(macro_event_summary.source)
        analysis_evidence.extend(
            [
                AnalysisEvidence(
                    category="macro_event",
                    impact="positive",
                    detail=factor,
                    source=macro_event_summary.source,
                )
                for factor in macro_event_summary.positive_impacts
            ]
        )
        analysis_evidence.extend(
            [
                AnalysisEvidence(
                    category="macro_event",
                    impact="negative",
                    detail=factor,
                    source=macro_event_summary.source,
                )
                for factor in macro_event_summary.negative_impacts
            ]
        )

    analysis_evidence.extend(_build_trade_calibration_evidence(trade_calibration))
    if trade_calibration is not None and "replay_trade_calibration_service" not in used_sources:
        used_sources.append("replay_trade_calibration_service")

    if news_impact_summary is not None:
        used_sources.append(news_impact_summary.provider)
        if news_impact_summary.average_sentiment is not None:
            if news_impact_summary.average_sentiment >= 0.08:
                analysis_evidence.append(
                    AnalysisEvidence(
                        category="news_impact",
                        impact="positive",
                        detail=f"Son {news_impact_summary.total_articles} haberde pozitif haber akisi one cikiyor",
                        source=news_impact_summary.provider,
                    )
                )
            elif news_impact_summary.average_sentiment <= -0.08:
                analysis_evidence.append(
                    AnalysisEvidence(
                        category="news_impact",
                        impact="negative",
                        detail=f"Son {news_impact_summary.total_articles} haberde negatif haber akisi baskin",
                        source=news_impact_summary.provider,
                    )
                )
        for article in news_impact_summary.items[:3]:
            if not article.headline:
                continue
            score = article.sentiment_score
            if score is None:
                continue
            if score >= 0.12:
                analysis_evidence.append(
                    AnalysisEvidence(
                        category="news_impact",
                        impact="positive",
                        detail=f"Guncel haber etkisi pozitif: {article.headline}",
                        source=news_impact_summary.provider,
                    )
                )
            elif score <= -0.12:
                analysis_evidence.append(
                    AnalysisEvidence(
                        category="news_impact",
                        impact="negative",
                        detail=f"Guncel haber etkisi negatif: {article.headline}",
                        source=news_impact_summary.provider,
                    )
                )

    recommendation = derive_recommendation(analysis_evidence)
    answer = _build_analysis_answer(normalized_ticker, analysis_evidence)
    trade_level_note = _build_trade_level_note(chart_feature_summary)
    if trade_level_note is not None:
        answer = f"{answer} {trade_level_note}"
    confidence = _calculate_analysis_confidence(analysis_evidence, recommendation)

    reasoning_layers = ["teknik feature", "sinyal", "temel", "kurumsal akim", "sirket olayi"]
    if any(item.category == "news_impact" for item in analysis_evidence):
        reasoning_layers.append("guncel haber etkisi")
    if any(item.category == "macro_event" for item in analysis_evidence):
        reasoning_layers.append("makro olay")

    return AskResponse(
        question=effective_question,
        route_type="analysis_query",
        answer=answer,
        used_sources=list(dict.fromkeys(used_sources)) or ["analysis_router"],
        confidence=confidence,
        reasoning_summary=(
            f"Analiz sorusu {', '.join(reasoning_layers)} katmanlari birlestirilerek yanitlandi. "
            "Kisa ozet uretilirken bu katmanlardan temsil niteliginde maddeler secildi; recommendation ise tum evidence listesi uzerinden hesaplandi."
        ),
        recommendation=recommendation,
        analysis_evidence=analysis_evidence,
        citations=[],
    )



def answer_question(question: str) -> AskResponse:
    route_type = detect_route_type(question)
    ticker = extract_ticker(question)

    if route_type == "analysis_query":
        if ticker is None:
            generic_response = _try_generic_analysis_answer(question)
            if generic_response is not None:
                return generic_response
            return AskResponse(
                question=question,
                route_type=route_type,
                answer="Analiz sorusu algilandi ancak soru icinde ticker veya genel piyasa kapsami netlesmedi.",
                used_sources=["router_only"],
                confidence=0.25,
                reasoning_summary="Analiz niyeti algilandi ancak hangi ticker veya hangi genel piyasa kapsami icin yanit uretilecegi belirlenemedi.",
                recommendation=None,
                analysis_evidence=[],
                citations=[],
            )

        return build_analysis_response_for_ticker(ticker, question)

    if route_type == "tool_query":
        if ticker is None:
            return AskResponse(
                question=question,
                route_type=route_type,
                answer="Bu soru market data istiyor gibi gorunuyor ama ticker bulunamadi.",
                used_sources=["router_only"],
                confidence=0.25,
                reasoning_summary="Market data niyeti algilandi ancak soru icinde ticker bulunamadi.",
                recommendation=None,
                analysis_evidence=[],
                citations=[],
            )

        market_snapshot = get_market_snapshot(ticker, force_refresh=True)
        if market_snapshot is None:
            return AskResponse(
                question=question,
                route_type=route_type,
                answer=f"{ticker} icin market data bulunamadi.",
                used_sources=["market_data_tool"],
                confidence=0.3,
                reasoning_summary="Tool query secildi fakat ilgili ticker icin market data donmedi.",
                recommendation=None,
                analysis_evidence=[],
                citations=[],
            )

        return AskResponse(
            question=question,
            route_type=route_type,
            answer=(
                f"{market_snapshot.ticker} icin son fiyat {market_snapshot.last_price}, "
                f"gunluk degisim %{market_snapshot.change_percent} ve hacim {market_snapshot.volume}."
            ),
            used_sources=[market_snapshot.source],
            confidence=0.9,
            reasoning_summary="Soru market data odakliydi; ticker bulundu ve tool cevabi dogrudan kullanildi.",
            recommendation=None,
            analysis_evidence=[],
            citations=[],
        )

    if route_type == "hybrid_query":
        if ticker is None:
            return AskResponse(
                question=question,
                route_type=route_type,
                answer="Bu soru hibrit gorunuyor ama ticker bulunamadi.",
                used_sources=["router_only"],
                confidence=0.25,
                reasoning_summary="Hibrit niyet algilandi ancak soru icinde ticker bulunamadi.",
                recommendation=None,
                analysis_evidence=[],
                citations=[],
            )

        market_snapshot = get_market_snapshot(ticker)
        documents = retrieve_documents(ticker, question)

        if market_snapshot is None and not documents:
            return AskResponse(
                question=question,
                route_type=route_type,
                answer=f"{ticker} icin ne market data ne de dokuman sonucu bulundu.",
                used_sources=["router_only"],
                confidence=0.2,
                reasoning_summary="Hibrit akisa gidildi ancak ne tool ne de retrieval sonucu bulundu.",
                recommendation=None,
                analysis_evidence=[],
                citations=[],
            )

        market_sentence = "Market data bulunamadi."
        source_list: list[str] = []

        if market_snapshot is not None:
            market_sentence = (
                f"Son fiyat {market_snapshot.last_price}, gunluk degisim "
                f"%{market_snapshot.change_percent}."
            )
            source_list.append(market_snapshot.source)

        document_sentence = "Dokuman retrieval sonucu bulunamadi."
        if documents:
            top_document = documents[0]
            document_sentence = (
                f"Dokuman tarafinda {top_document.document_title} icinde su vurgu bulundu: "
                f"{top_document.excerpt}"
            )
            source_list.append(top_document.source)

        return AskResponse(
            question=question,
            route_type=route_type,
            answer=f"{ticker} icin hibrit ozet: {market_sentence} {document_sentence}",
            used_sources=source_list or ["router_only"],
            confidence=0.82 if market_snapshot is not None and documents else 0.6,
            reasoning_summary=(
                "Soru hem market data hem dokuman ipucu tasidigi icin hibrit akisa yonlendirildi. "
                "Tool sonucu ile en uygun dokuman retrieval sonucu birlestirildi."
            ),
            recommendation=None,
            analysis_evidence=[],
            citations=build_citations(documents),
        )

    if ticker is None:
        generic_response = _try_generic_analysis_answer(question)
        if generic_response is not None:
            return generic_response
        return AskResponse(
            question=question,
            route_type=route_type,
            answer="Bu soru dokuman odakli gorunuyor ama ticker veya genel piyasa kapsami bulunamadi.",
            used_sources=["router_only"],
            confidence=0.25,
            reasoning_summary="Ticker bulunamadi ve soru genel piyasa/sktor kapsaminda da yeterince net eslesmedi.",
            recommendation=None,
            analysis_evidence=[],
            citations=[],
        )

    documents = retrieve_documents(ticker, question)
    if not documents:
        return AskResponse(
            question=question,
            route_type=route_type,
            answer=f"{ticker} icin dokuman retrieval sonucu bulunamadi.",
            used_sources=["local_json_markdown_retriever"],
            confidence=0.3,
            reasoning_summary="RAG akisi secildi fakat ilgili ticker icin dokuman bulunamadi.",
            recommendation=None,
            analysis_evidence=[],
            citations=[],
        )

    top_document = documents[0]
    return AskResponse(
        question=question,
        route_type=route_type,
        answer=(
            f"{ticker} icin dokuman cevabi: {top_document.document_title} "
            f"({top_document.published_at}) icinde su bilgi bulundu: {top_document.excerpt}"
        ),
        used_sources=[top_document.source],
        confidence=0.88,
        reasoning_summary=(
            "Soru dokuman odakliydi; ticker bulundu ve soru niyetine uygun en yuksek skorlu dokuman secildi."
        ),
        recommendation=None,
        analysis_evidence=[],
        citations=build_citations(documents),
    )
