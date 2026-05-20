from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app.core.config import settings
from app.data_sources.company_data.provider import get_company_record, list_company_records
from app.data_sources.market_data.provider import get_active_market_data_provider, get_market_ohlcv, get_market_snapshot, get_order_book_pressure
from app.db.models import ScanSnapshot
from app.db.session import SessionLocal, ensure_runtime_schema
from app.models.schemas import (
    AnalysisEvidence,
    CompanyResponse,
    LimitUpCandidateItem,
    LimitUpCandidateResponse,
    LiveMomentumRadarItem,
    LiveMomentumRadarResponse,
    MarketScanItem,
    MarketScanResponse,
    OpeningCandidateItem,
    OpeningCandidateResponse,
    OpportunityScanItem,
    OpportunityScanResponse,
    PreMarketWatchlistItem,
    PreMarketWatchlistResponse,
    ScanSnapshotCreateResponse,
    ScanSnapshotHistoryItem,
    ScanSnapshotHistoryResponse,
    ScanUniverseCoverageResponse,
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


def _chart_scale_is_compatible(chart_summary, reference_price: float | None) -> bool:
    if chart_summary is None or reference_price is None or reference_price <= 0:
        return True

    levels = [
        getattr(chart_summary, "ema20", 0),
        getattr(chart_summary, "nearest_support", 0),
        getattr(chart_summary, "nearest_resistance", 0),
        getattr(chart_summary, "breakout_buy_trigger", 0),
        getattr(chart_summary, "breakdown_sell_trigger", 0),
    ]
    positive_levels = [float(level) for level in levels if level is not None and float(level) > 0]
    if not positive_levels:
        return True

    median_level = sorted(positive_levels)[len(positive_levels) // 2]
    ratio = median_level / reference_price
    return 0.65 <= ratio <= 1.45


def _discard_incompatible_chart_summary(chart_summary, reference_price: float | None):
    if _chart_scale_is_compatible(chart_summary, reference_price):
        return chart_summary
    return None


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


def _configured_momentum_tickers() -> list[str]:
    return [ticker.strip().upper() for ticker in settings.momentum_universe_tickers.split(",") if ticker.strip()]


def _momentum_company_records(universe_code: str = "bist100") -> tuple[list[CompanyResponse], dict[str, list[str]]]:
    records = list_company_records(universe_code=universe_code)
    if not records:
        records = list_company_records()

    source_map: dict[str, list[str]] = {}
    merged: dict[str, CompanyResponse] = {}
    for record in records:
        ticker = record.ticker.upper()
        merged[ticker] = record
        source_map.setdefault(ticker, []).append(universe_code)

    for ticker in _configured_momentum_tickers():
        if ticker in merged:
            source_map.setdefault(ticker, []).append("configured_momentum_universe")
            continue
        record = get_company_record(ticker) or CompanyResponse(
            ticker=ticker,
            name=ticker,
            sector="Momentum Watch",
            signal_enabled=False,
            source="configured_momentum_universe",
        )
        merged[ticker] = record
        source_map.setdefault(ticker, []).append("configured_momentum_universe")

    return list(merged.values()), source_map


def get_scan_universe_coverage(universe_code: str = "bist100") -> ScanUniverseCoverageResponse:
    base_records = list_company_records(universe_code=universe_code)
    if not base_records:
        base_records = list_company_records()
    all_records = list_company_records()
    scanned_records, _source_map = _momentum_company_records(universe_code=universe_code)
    configured = _configured_momentum_tickers()
    master_tickers = {record.ticker.upper() for record in all_records}

    return ScanUniverseCoverageResponse(
        generated_at=datetime.utcnow().isoformat(),
        requested_universe_code=universe_code,
        base_universe_size=len(base_records),
        all_active_company_count=len(all_records),
        configured_momentum_tickers=configured,
        configured_missing_from_master=[ticker for ticker in configured if ticker not in master_tickers],
        scanned_universe_size=len(scanned_records),
        scanned_tickers=sorted(record.ticker for record in scanned_records),
    )



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


def _market_elapsed_fraction(now: datetime | None = None) -> float:
    current = now.astimezone(ZoneInfo("Europe/Istanbul")) if now is not None else datetime.now(ZoneInfo("Europe/Istanbul"))
    session_start = current.replace(hour=9, minute=55, second=0, microsecond=0)
    session_end = current.replace(hour=18, minute=10, second=0, microsecond=0)
    if current <= session_start:
        return 0.08
    if current >= session_end:
        return 1.0
    elapsed = (current - session_start).total_seconds()
    total = max((session_end - session_start).total_seconds(), 1)
    # Opening and closing auctions concentrate volume, so early-session expected volume
    # should not be interpreted linearly.
    return _clamp((elapsed / total) ** 0.72, 0.08, 1.0)


def _volume_momentum_bucket(expected_volume_ratio: float | None, intraday_ratio: float | None) -> str:
    best_ratio = max(expected_volume_ratio or 0.0, intraday_ratio or 0.0)
    if best_ratio >= 2.5:
        return "volume_surge"
    if best_ratio >= 1.5:
        return "strong_volume"
    if best_ratio >= 0.9:
        return "healthy_volume"
    if best_ratio >= 0.55:
        return "thin_volume"
    return "very_thin_volume"


def _confirmation_component(change_percent: float | None, expected_volume_ratio: float | None, intraday_ratio: float | None) -> tuple[float, str, list[str], list[str]]:
    reasons: list[str] = []
    risks: list[str] = []
    bucket = _volume_momentum_bucket(expected_volume_ratio, intraday_ratio)
    change = change_percent or 0.0
    best_ratio = max(expected_volume_ratio or 0.0, intraday_ratio or 0.0)

    if change >= 2.0 and best_ratio >= 1.5:
        reasons.append("Fiyat artisi hacimle teyit ediliyor")
        return 10.0, bucket, reasons, risks
    if change >= 0.8 and best_ratio >= 0.9:
        reasons.append("Pozitif fiyat hareketi hacimle destekleniyor")
        return 5.0, bucket, reasons, risks
    if change >= 0.0 and best_ratio < 0.55:
        risks.append("Pozitif/yatay fiyat hareketinde hacim teyidi zayif")
        return -4.0, bucket, reasons, risks
    if change < 0.0 and best_ratio >= 1.0:
        risks.append("Hacim artarken fiyat negatif; satis baskisi teyidi olabilir")
        return -10.0, bucket, reasons, risks
    if change < 0.0:
        risks.append("Fiyat negatif bolgede, momentum teyidi yok")
        return -6.0, bucket, reasons, risks
    return 0.0, bucket, reasons, risks



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
    if 0.0 <= change_percent < 1.0:
        reasons.append("Gunun geri kalani icin hala hareket alani var")
        return 5.0, reasons, risks
    if -1.0 <= change_percent < 0.0:
        risks.append("Gun ici fiyat henuz pozitife donmedi")
        return -2.0, reasons, risks
    risks.append("Gun ici performans tavan kosusu icin henuz zayif")
    return -4.0, reasons, risks


def _volume_pressure_component(market_snapshot, daily_chart, intraday_1h) -> tuple[float, float | None, float | None, float | None, str, list[str], list[str]]:
    reasons: list[str] = []
    risks: list[str] = []
    daily_ratio = None
    expected_ratio = None
    intraday_ratio = None
    score = 0.0

    if market_snapshot is not None and daily_chart is not None and daily_chart.avg_volume > 0:
        daily_ratio = round(market_snapshot.volume / max(daily_chart.avg_volume, 1), 2)
        expected_ratio = round(daily_ratio / _market_elapsed_fraction(), 2)
        if expected_ratio >= 2.5:
            score += 18.0
            reasons.append("Zamana gore hacim akisi cok guclu")
        elif expected_ratio >= 1.5:
            score += 12.0
            reasons.append("Zamana gore hacim akisi guclu")
        elif expected_ratio >= 0.9:
            score += 6.0
            reasons.append("Zamana gore hacim akisi saglikli")
        elif expected_ratio < 0.55:
            score -= 9.0
            risks.append("Zamana gore hacim teyidi zayif")

        if daily_ratio >= 2.0:
            score += 14.0
            reasons.append("Gunluk hacim ortalamanin cok uzerinde")
        elif daily_ratio >= 1.35:
            score += 9.0
            reasons.append("Gunluk hacim ortalamanin belirgin uzerinde")
        elif daily_ratio >= 1.0:
            score += 5.0
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

    confirmation_score, momentum_bucket, confirmation_reasons, confirmation_risks = _confirmation_component(
        market_snapshot.change_percent if market_snapshot is not None else None,
        expected_ratio,
        intraday_ratio,
    )
    score += confirmation_score
    reasons.extend(confirmation_reasons)
    risks.extend(confirmation_risks)

    return score, daily_ratio, expected_ratio, intraday_ratio, momentum_bucket, reasons, risks


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


def _order_book_pressure_component(ticker: str) -> tuple[float, str | None, float | None, list[str], list[str]]:
    pressure = get_order_book_pressure(ticker, levels=10)
    if not pressure.available:
        return 0.0, pressure.pressure_bucket, pressure.bid_ask_imbalance, [], []

    if pressure.pressure_bucket == "strong_bid_pressure":
        return 12.0, pressure.pressure_bucket, pressure.bid_ask_imbalance, ["Derinlikte guclu alis baskisi var"], []
    if pressure.pressure_bucket == "bid_pressure":
        return 7.0, pressure.pressure_bucket, pressure.bid_ask_imbalance, ["Derinlik alis tarafini destekliyor"], []
    if pressure.pressure_bucket == "balanced":
        return 0.0, pressure.pressure_bucket, pressure.bid_ask_imbalance, [], []
    if pressure.pressure_bucket == "ask_pressure":
        return -7.0, pressure.pressure_bucket, pressure.bid_ask_imbalance, [], ["Derinlik satis tarafini destekliyor"]
    if pressure.pressure_bucket == "strong_ask_pressure":
        return -12.0, pressure.pressure_bucket, pressure.bid_ask_imbalance, [], ["Derinlikte guclu satis baskisi var"]
    return 0.0, pressure.pressure_bucket, pressure.bid_ask_imbalance, [], []


def _opening_gap_risk(change_percent: float | None, daily_chart) -> str:
    if change_percent is None:
        return "unknown"
    rsi = daily_chart.rsi14 if daily_chart is not None else 50
    if change_percent >= 7.5 or rsi >= 78:
        return "high"
    if change_percent >= 4.8 or rsi >= 72:
        return "medium"
    return "low"


def _closing_strength_proxy(daily_chart, intraday_1h, intraday_4h) -> float | None:
    charts = [chart for chart in (daily_chart, intraday_1h, intraday_4h) if chart is not None]
    if not charts:
        return None

    score = 42.0
    weights = (0.45, 0.35, 0.2)
    for chart, weight in zip((daily_chart, intraday_1h, intraday_4h), weights, strict=False):
        if chart is None:
            continue
        if chart.signal_bias == "bullish":
            score += 12.0 * weight
        elif chart.signal_bias == "bearish":
            score -= 12.0 * weight

        if chart.structure_bias == "bullish":
            score += 7.0 * weight
        elif chart.structure_bias == "bearish":
            score -= 7.0 * weight

        if chart.breakout_state == "confirmed_breakout_up":
            score += 16.0 * weight
        elif chart.breakout_state == "breakout_watch_up":
            score += 9.0 * weight
        elif chart.breakout_state in {"breakout_watch_down", "confirmed_breakout_down"}:
            score -= 12.0 * weight

        if 58 <= chart.price_position_percent <= 92:
            score += 7.0 * weight
        elif chart.price_position_percent > 96:
            score -= 4.0 * weight
        elif chart.price_position_percent < 28:
            score -= 5.0 * weight

    return round(_clamp(score, 0.0, 100.0), 2)


def _opening_change_component(change_percent: float | None) -> tuple[float, list[str], list[str], bool]:
    reasons: list[str] = []
    risks: list[str] = []
    if change_percent is None:
        return 0.0, reasons, ["Gunluk degisim okunamadi"], False
    if change_percent >= 9.3:
        return -100.0, reasons, ["Hisse zaten tavan bolgesinde"], True
    if 1.0 <= change_percent <= 5.8:
        reasons.append("Onceki seans pozitif ama halen kovalamaca bandina tasinmamis")
        return 18.0, reasons, risks, False
    if 5.8 < change_percent < 9.3:
        reasons.append("Guclu momentum var")
        risks.append("Yuksek kapanis primi nedeniyle gap/kovalama riski artiyor")
        return 8.0, reasons, risks, False
    if 0.0 <= change_percent < 1.0:
        reasons.append("Yatay kapanis, ertesi seans kirilim icin hareket alani birakiyor")
        return 7.0, reasons, risks, False
    if -0.8 <= change_percent < 0.0:
        risks.append("Acilis sonrasi fiyat henuz pozitife donmedi")
        return -2.0, reasons, risks, False
    if -2.5 <= change_percent < -0.8:
        risks.append("Acilis teyidi zayif; fiyat negatif bolgeye dondu")
        return -14.0, reasons, risks, False
    risks.append("Acilis teyidi bozuldu; satis baskisi belirgin")
    return -26.0, reasons, risks, False


def _opening_volume_component(market_snapshot, daily_chart) -> tuple[float, float | None, float | None, str, list[str], list[str]]:
    reasons: list[str] = []
    risks: list[str] = []
    if market_snapshot is None or daily_chart is None or daily_chart.avg_volume <= 0:
        return 0.0, None, None, "unknown", reasons, ["Hacim ortalamasi okunamadi"]

    ratio = round(market_snapshot.volume / max(daily_chart.avg_volume, 1), 2)
    expected_ratio = round(ratio / _market_elapsed_fraction(), 2)
    score = 0.0
    if expected_ratio >= 2.5:
        score += 18.0
        reasons.append("Zamana gore hacim akisi cok guclu")
    elif expected_ratio >= 1.5:
        score += 12.0
        reasons.append("Zamana gore hacim akisi guclu")
    elif expected_ratio >= 0.9:
        score += 6.0
        reasons.append("Zamana gore hacim akisi saglikli")
    elif expected_ratio < 0.55:
        score -= 10.0
        risks.append("Zamana gore hacim teyidi zayif")

    if ratio >= 2.0:
        score += 12.0
        reasons.append("Toplam hacim ortalamanin cok uzerinde")
    elif ratio >= 1.35:
        score += 8.0
        reasons.append("Toplam hacim ortalamanin belirgin uzerinde")
    elif ratio >= 1.0:
        score += 4.0
        reasons.append("Toplam hacim ortalama ustunde")
    elif ratio < 0.65:
        score -= 5.0
        risks.append("Toplam hacim teyidi zayif")

    confirmation_score, momentum_bucket, confirmation_reasons, confirmation_risks = _confirmation_component(
        market_snapshot.change_percent,
        expected_ratio,
        None,
    )
    score += confirmation_score
    reasons.extend(confirmation_reasons)
    risks.extend(confirmation_risks)
    return score, ratio, expected_ratio, momentum_bucket, reasons, risks


def _opening_technical_component(daily_chart, intraday_1h, intraday_4h) -> tuple[float, list[str], list[str]]:
    reasons: list[str] = []
    risks: list[str] = []
    score = 0.0

    for label, chart, weight in (("gunluk", daily_chart, 1.0), ("1H", intraday_1h, 1.05), ("4H", intraday_4h, 0.85)):
        if chart is None:
            continue
        if chart.signal_bias == "bullish":
            score += 7.0 * weight
            reasons.append(f"{label} teknik bias pozitif")
        elif chart.signal_bias == "bearish":
            score -= 8.0 * weight
            risks.append(f"{label} teknik bias negatif")

        if chart.structure_bias == "bullish":
            score += 4.0 * weight
        elif chart.structure_bias == "bearish":
            score -= 4.0 * weight

        if chart.breakout_state == "confirmed_breakout_up":
            score += 12.0 * weight
            reasons.append(f"{label} yukari kirilim teyidi var")
        elif chart.breakout_state == "breakout_watch_up":
            score += 8.0 * weight
            reasons.append(f"{label} acilis icin yukari kirilim izleme bolgesinde")
        elif chart.breakout_state in {"breakout_watch_down", "confirmed_breakout_down"}:
            score -= 9.0 * weight
            risks.append(f"{label} asagi kirilim riski var")

    if daily_chart is not None:
        if 52 <= daily_chart.rsi14 <= 70:
            score += 5.0
            reasons.append("RSI devam momentumu icin saglikli bantta")
        elif daily_chart.rsi14 > 78:
            score -= 9.0
            risks.append("Gunluk RSI asiri isinmis")
        elif daily_chart.rsi14 < 42:
            score -= 6.0
            risks.append("Gunluk RSI momentum tarafi zayif")

    return score, reasons, risks


def _opening_calibration_component(trade_calibration) -> tuple[float, list[str], list[str]]:
    reasons: list[str] = []
    risks: list[str] = []
    if trade_calibration is None:
        return 0.0, reasons, risks
    if trade_calibration.calibration_bias == "supportive":
        reasons.append("Gecmis replay kalibrasyonu benzer setup icin destekleyici")
        return 5.0, reasons, risks
    if trade_calibration.calibration_bias == "fragile":
        risks.append("Gecmis replay kalibrasyonu benzer setup icin kirilgan")
        return -7.0, reasons, risks
    return 0.0, reasons, risks


def _pick_opening_trigger(daily_chart, intraday_1h, intraday_4h) -> float | None:
    for chart in (intraday_1h, intraday_4h, daily_chart):
        if chart is not None and chart.breakout_buy_trigger > 0:
            return chart.breakout_buy_trigger
    return None


def _pick_opening_invalidation(daily_chart, intraday_1h, intraday_4h) -> float | None:
    for chart in (intraday_1h, intraday_4h, daily_chart):
        if chart is not None and chart.breakdown_sell_trigger > 0:
            return chart.breakdown_sell_trigger
    return None


def _is_fresh_matriks_snapshot(market_snapshot) -> bool:
    return market_snapshot is not None and "matriks" in market_snapshot.source.lower() and "_cache" not in market_snapshot.source.lower()


def _opportunity_target_move(scenario: str) -> str:
    return {
        "limit_up_candidate": "tavan/sert momentum",
        "intraday_gain_candidate": "2-3% intraday",
        "reversal_candidate": "eksiden artiya donus",
        "breakout_candidate": "kirilim sonrasi ivme",
        "avoid_or_invalidated": "islemden kacin/teyit bekle",
    }.get(scenario, "watch")


def _scenario_from_components(market_snapshot, daily_chart, intraday_1h, intraday_4h, spread_proxy: str, expected_volume_ratio: float | None) -> tuple[str, list[str], list[str], float]:
    reasons: list[str] = []
    risks: list[str] = []
    change = market_snapshot.change_percent
    expected_ratio = expected_volume_ratio or 0.0
    one_h_breakout = intraday_1h.breakout_state if intraday_1h is not None else ""
    four_h_breakout = intraday_4h.breakout_state if intraday_4h is not None else ""
    daily_bias = daily_chart.signal_bias if daily_chart is not None else "neutral"
    intraday_bias = intraday_1h.signal_bias if intraday_1h is not None else "neutral"

    if spread_proxy == "wide_spread":
        risks.append("Spread genis; emir kalitesi zayif")

    if change >= 3.0 and expected_ratio >= 1.4:
        reasons.append("Gun ici fiyat ivmesi hacimle destekleniyor")
        if 3.0 <= change <= 7.5:
            return "limit_up_candidate", reasons, risks, 78.0
        risks.append("Fiyat primi yuksek; kovalamaca riski artiyor")
        return "limit_up_candidate", reasons, risks, 68.0

    if 0.4 <= change < 3.0 and expected_ratio >= 0.8:
        reasons.append("Pozitif fiyat hareketi zaman ayarli hacimle destekleniyor")
        if intraday_bias == "bullish":
            reasons.append("1H teknik bias yukari")
        return "intraday_gain_candidate", reasons, risks, 64.0

    if -2.5 <= change < 0.4:
        if expected_ratio >= 0.9 and intraday_bias in {"bullish", "neutral"}:
            reasons.append("Fiyat zayif/yatay ama hacim akisi toparlanma icin izlenebilir")
            if one_h_breakout in {"support_test", "breakout_watch_up", "resistance_test"}:
                reasons.append("1H yapi tepki/kirilim bolgesinde")
            return "reversal_candidate", reasons, risks, 56.0
        risks.append("Fiyat zayif ve hacim teyidi yetersiz")
        return "avoid_or_invalidated", reasons, risks, 30.0

    if one_h_breakout in {"breakout_watch_up", "confirmed_breakout_up", "resistance_test"} or four_h_breakout in {"breakout_watch_up", "confirmed_breakout_up", "resistance_test"}:
        if expected_ratio >= 0.7 and daily_bias != "bearish":
            reasons.append("Kirilim bolgesi hacimle izlenebilir")
            return "breakout_candidate", reasons, risks, 58.0

    risks.append("Senaryo teyidi zayif")
    return "avoid_or_invalidated", reasons, risks, 25.0


def _build_opportunity_item(company) -> OpportunityScanItem | None:
    market_snapshot = get_market_snapshot(company.ticker, force_refresh=True)
    if not _is_fresh_matriks_snapshot(market_snapshot):
        return None

    daily_chart = get_chart_feature_summary(company.ticker, timeframe="1G")
    daily_chart = _discard_incompatible_chart_summary(daily_chart, market_snapshot.last_price)
    intraday_1h = _discard_incompatible_chart_summary(
        get_chart_feature_summary(company.ticker, timeframe="1H"),
        market_snapshot.last_price,
    )
    intraday_4h = _discard_incompatible_chart_summary(
        get_chart_feature_summary(company.ticker, timeframe="4H"),
        market_snapshot.last_price,
    )
    volume_score, daily_volume_ratio, expected_volume_ratio, intraday_volume_ratio, volume_bucket, volume_reasons, volume_risks = _volume_pressure_component(market_snapshot, daily_chart, intraday_1h)
    technical_score, technical_reasons, technical_risks = _technical_pressure_component(daily_chart, intraday_1h, intraday_4h)
    liquidity_score, spread, spread_proxy, liquidity_reasons, liquidity_risks = _liquidity_component(market_snapshot)
    book_score, book_pressure, book_imbalance, book_reasons, book_risks = _order_book_pressure_component(company.ticker)
    scenario, scenario_reasons, scenario_risks, scenario_base = _scenario_from_components(
        market_snapshot,
        daily_chart,
        intraday_1h,
        intraday_4h,
        spread_proxy,
        expected_volume_ratio,
    )

    score = scenario_base + (volume_score * 0.42) + (technical_score * 0.35) + (liquidity_score * 0.55) + book_score
    if scenario == "reversal_candidate":
        score = min(score, 76.0)
    if scenario == "avoid_or_invalidated":
        score = min(score, 42.0)
    if market_snapshot.change_percent >= 8.5:
        score -= 8.0
        scenario_risks.append("Gunluk prim cok yuksek; risk/odul bozulabilir")

    score = _clamp(score, 0.0, 100.0)
    if score < 38:
        return None

    reasons = list(dict.fromkeys(scenario_reasons + volume_reasons + technical_reasons + liquidity_reasons + book_reasons))[:7]
    risks = list(dict.fromkeys(scenario_risks + volume_risks + technical_risks + liquidity_risks + book_risks))[:7]
    confidence = _clamp(0.35 + (score / 100.0 * 0.45) + (0.1 if expected_volume_ratio and expected_volume_ratio >= 1.0 else 0.0), 0.25, 0.86)

    return OpportunityScanItem(
        ticker=company.ticker,
        company_name=company.name,
        sector=company.sector,
        scenario=scenario,
        opportunity_score=round(score, 2),
        confidence=round(confidence, 2),
        target_move=_opportunity_target_move(scenario),
        last_price=market_snapshot.last_price,
        change_percent=market_snapshot.change_percent,
        distance_to_limit_percent=round(max(0.0, 10.0 - market_snapshot.change_percent), 2),
        volume=market_snapshot.volume,
        daily_volume_ratio=daily_volume_ratio,
        expected_volume_ratio=expected_volume_ratio,
        volume_momentum_bucket=volume_bucket,
        technical_bias=daily_chart.signal_bias if daily_chart is not None else None,
        intraday_bias_1h=intraday_1h.signal_bias if intraday_1h is not None else None,
        intraday_bias_4h=intraday_4h.signal_bias if intraday_4h is not None else None,
        breakout_state_1h=intraday_1h.breakout_state if intraday_1h is not None else None,
        breakout_state_4h=intraday_4h.breakout_state if intraday_4h is not None else None,
        spread_percent=spread,
        order_flow_proxy=spread_proxy,
        order_book_pressure=book_pressure,
        bid_ask_imbalance=book_imbalance,
        trigger_price=_pick_opening_trigger(daily_chart, intraday_1h, intraday_4h),
        invalidation_price=_pick_opening_invalidation(daily_chart, intraday_1h, intraday_4h),
        why_now=reasons,
        risks=risks,
        data_quality="fresh_matriks",
    )


def _build_opening_candidate(company) -> tuple[OpeningCandidateItem | None, bool]:
    market_snapshot = get_market_snapshot(company.ticker, force_refresh=True)
    if market_snapshot is None:
        return None, False
    if "matriks" not in market_snapshot.source.lower():
        return None, False

    change_score, change_reasons, change_risks, already_limit = _opening_change_component(market_snapshot.change_percent)
    if already_limit:
        return None, True

    daily_chart = _discard_incompatible_chart_summary(
        get_chart_feature_summary(company.ticker, timeframe="1G"),
        market_snapshot.last_price,
    )
    intraday_1h = _discard_incompatible_chart_summary(
        get_chart_feature_summary(company.ticker, timeframe="1H"),
        market_snapshot.last_price,
    )
    intraday_4h = _discard_incompatible_chart_summary(
        get_chart_feature_summary(company.ticker, timeframe="4H"),
        market_snapshot.last_price,
    )
    trade_calibration = get_trade_calibration_cached(company.ticker, timeframe="1G", horizon_bars=5, sample_size=8, step_bars=5, use_cache_only=True)

    volume_score, daily_volume_ratio, expected_volume_ratio, volume_momentum_bucket, volume_reasons, volume_risks = _opening_volume_component(market_snapshot, daily_chart)
    technical_score, technical_reasons, technical_risks = _opening_technical_component(daily_chart, intraday_1h, intraday_4h)
    liquidity_score, spread, order_proxy, liquidity_reasons, liquidity_risks = _liquidity_component(market_snapshot)
    book_score, book_pressure, book_imbalance, book_reasons, book_risks = _order_book_pressure_component(company.ticker)
    calibration_score, calibration_reasons, calibration_risks = _opening_calibration_component(trade_calibration)
    closing_strength = _closing_strength_proxy(daily_chart, intraday_1h, intraday_4h)

    strength_score = ((closing_strength or 45.0) - 45.0) * 0.28
    score = _clamp(
        24.0
        + change_score
        + volume_score
        + technical_score
        + (liquidity_score * 0.65)
        + book_score
        + calibration_score
        + strength_score,
        0.0,
        100.0,
    )
    if market_snapshot.change_percent < -1.0:
        score = min(score, 49.0)
    elif market_snapshot.change_percent < 0.0:
        score = min(score, 54.0)
    if score < 44:
        return None, False

    reasons = list(dict.fromkeys(change_reasons + volume_reasons + technical_reasons + liquidity_reasons + book_reasons + calibration_reasons))[:6]
    risks = list(dict.fromkeys(change_risks + volume_risks + technical_risks + liquidity_risks + book_risks + calibration_risks))[:6]

    return OpeningCandidateItem(
        ticker=company.ticker,
        company_name=company.name,
        sector=company.sector,
        opening_score=round(score, 2),
        probability_bucket=_probability_bucket(score),
        last_price=market_snapshot.last_price,
        change_percent=market_snapshot.change_percent,
        volume=market_snapshot.volume,
        daily_volume_ratio=daily_volume_ratio,
        expected_volume_ratio=expected_volume_ratio,
        volume_momentum_bucket=volume_momentum_bucket,
        closing_strength_proxy=closing_strength,
        technical_bias=daily_chart.signal_bias if daily_chart is not None else None,
        intraday_bias_1h=intraday_1h.signal_bias if intraday_1h is not None else None,
        intraday_bias_4h=intraday_4h.signal_bias if intraday_4h is not None else None,
        breakout_state_1h=intraday_1h.breakout_state if intraday_1h is not None else None,
        breakout_state_4h=intraday_4h.breakout_state if intraday_4h is not None else None,
        opening_trigger=_pick_opening_trigger(daily_chart, intraday_1h, intraday_4h),
        invalidation_level=_pick_opening_invalidation(daily_chart, intraday_1h, intraday_4h),
        spread_percent=spread,
        order_flow_proxy=order_proxy,
        order_book_pressure=book_pressure,
        bid_ask_imbalance=book_imbalance,
        gap_risk=_opening_gap_risk(market_snapshot.change_percent, daily_chart),
        reasons=reasons,
        risks=risks,
    ), False


def _build_limit_up_candidate(company) -> tuple[LimitUpCandidateItem | None, bool]:
    market_snapshot = get_market_snapshot(company.ticker, force_refresh=True)
    if market_snapshot is None:
        return None, False
    if "matriks" not in market_snapshot.source.lower():
        return None, False

    if market_snapshot.change_percent < 0:
        return None, False
    if market_snapshot.change_percent >= 9.3:
        return None, True

    daily_chart = get_chart_feature_summary(company.ticker, timeframe="1G")
    intraday_1h = get_chart_feature_summary(company.ticker, timeframe="1H")
    intraday_4h = get_chart_feature_summary(company.ticker, timeframe="4H")

    change_score, change_reasons, change_risks = _change_runway_component(market_snapshot.change_percent)
    volume_score, daily_volume_ratio, expected_volume_ratio, intraday_volume_ratio, volume_momentum_bucket, volume_reasons, volume_risks = _volume_pressure_component(market_snapshot, daily_chart, intraday_1h)
    technical_score, technical_reasons, technical_risks = _technical_pressure_component(daily_chart, intraday_1h, intraday_4h)
    liquidity_score, spread, order_proxy, liquidity_reasons, liquidity_risks = _liquidity_component(market_snapshot)
    book_score, book_pressure, book_imbalance, book_reasons, book_risks = _order_book_pressure_component(company.ticker)

    score = _clamp(28.0 + change_score + volume_score + technical_score + liquidity_score + book_score, 0.0, 100.0)
    if score < 42:
        return None, False

    reasons = list(dict.fromkeys(change_reasons + volume_reasons + technical_reasons + liquidity_reasons + book_reasons))[:5]
    risks = list(dict.fromkeys(change_risks + volume_risks + technical_risks + liquidity_risks + book_risks))[:5]

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
        expected_volume_ratio=expected_volume_ratio,
        intraday_volume_ratio_1h=intraday_volume_ratio,
        volume_momentum_bucket=volume_momentum_bucket,
        technical_bias=daily_chart.signal_bias if daily_chart is not None else None,
        intraday_bias_1h=intraday_1h.signal_bias if intraday_1h is not None else None,
        breakout_state_1h=intraday_1h.breakout_state if intraday_1h is not None else None,
        spread_percent=spread,
        order_flow_proxy=order_proxy,
        order_book_pressure=book_pressure,
        bid_ask_imbalance=book_imbalance,
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



def _build_scan_items(stance: str | None = None, ranking_mode: str = "default", universe_code: str = "bist100") -> tuple[list[MarketScanItem], int]:
    normalized_stance = stance.lower() if stance is not None else None
    companies, _source_map = _momentum_company_records(universe_code=universe_code)
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



def scan_market(stance: str | None = None, limit: int = 20, ranking_mode: str = "default", universe_code: str = "bist100") -> MarketScanResponse:
    ranked_items, universe_size = _build_scan_items(stance=stance, ranking_mode=ranking_mode, universe_code=universe_code)
    limited_items = ranked_items[: max(limit, 1)]

    return MarketScanResponse(
        generated_at=datetime.utcnow().isoformat(),
        universe_size=universe_size,
        total=len(limited_items),
        items=limited_items,
    )


def scan_limit_up_candidates(limit: int = 15, universe_code: str = "bist100") -> LimitUpCandidateResponse:
    companies, _source_map = _momentum_company_records(universe_code=universe_code)

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


def scan_opening_candidates(limit: int = 15, universe_code: str = "bist100") -> OpeningCandidateResponse:
    companies, _source_map = _momentum_company_records(universe_code=universe_code)

    candidates: list[OpeningCandidateItem] = []
    excluded_already_limit_count = 0
    for company in companies:
        candidate, already_limit = _build_opening_candidate(company)
        if already_limit:
            excluded_already_limit_count += 1
            continue
        if candidate is not None:
            candidates.append(candidate)

    ranked = sorted(
        candidates,
        key=lambda item: (
            item.opening_score,
            item.daily_volume_ratio or 0,
            item.closing_strength_proxy or 0,
            item.change_percent or -999,
            item.volume or 0,
        ),
        reverse=True,
    )
    limited_items = ranked[: max(limit, 1)]
    return OpeningCandidateResponse(
        generated_at=datetime.utcnow().isoformat(),
        universe_size=len(companies),
        total=len(limited_items),
        excluded_already_limit_count=excluded_already_limit_count,
        items=limited_items,
    )


def scan_opportunities(limit: int = 15, include_avoid: bool = False, universe_code: str = "bist100") -> OpportunityScanResponse:
    companies, _source_map = _momentum_company_records(universe_code=universe_code)

    opportunities: list[OpportunityScanItem] = []
    for company in companies:
        item = _build_opportunity_item(company)
        if item is None:
            continue
        if not include_avoid and item.scenario == "avoid_or_invalidated":
            continue
        opportunities.append(item)

    scenario_priority = {
        "limit_up_candidate": 4,
        "intraday_gain_candidate": 3,
        "breakout_candidate": 3,
        "reversal_candidate": 2,
        "avoid_or_invalidated": 0,
    }
    ranked = sorted(
        opportunities,
        key=lambda item: (
            item.opportunity_score,
            scenario_priority.get(item.scenario, 1),
            item.expected_volume_ratio or 0,
            item.change_percent or -999,
            item.volume or 0,
        ),
        reverse=True,
    )
    limited_items = ranked[: max(limit, 1)]
    scenario_counts: dict[str, int] = {}
    for item in limited_items:
        scenario_counts[item.scenario] = scenario_counts.get(item.scenario, 0) + 1

    return OpportunityScanResponse(
        generated_at=datetime.utcnow().isoformat(),
        universe_size=len(companies),
        total=len(limited_items),
        scenario_counts=scenario_counts,
        items=limited_items,
    )


def _live_momentum_scenario(change_percent: float, best_ask: float) -> str:
    if change_percent >= 9.75 or (change_percent >= 8.5 and best_ask <= 0):
        return "limit_up_locked"
    if change_percent >= 7.0:
        return "limit_up_watch"
    if change_percent >= 3.0:
        return "strong_intraday_momentum"
    if change_percent > 0:
        return "positive_momentum"
    return "not_positive"


def _score_live_momentum_item(company: CompanyResponse, universe_sources: list[str]) -> LiveMomentumRadarItem | None:
    market_snapshot = get_market_snapshot(company.ticker, force_refresh=True)
    if market_snapshot is None or "matriks" not in market_snapshot.source.lower():
        return None
    if market_snapshot.change_percent <= 0:
        return None

    daily_chart = _discard_incompatible_chart_summary(
        get_chart_feature_summary(company.ticker, timeframe="1G"),
        market_snapshot.last_price,
    )
    volume_score, daily_ratio, expected_ratio, _intraday_ratio, volume_bucket, volume_reasons, volume_risks = _volume_pressure_component(
        market_snapshot,
        daily_chart,
        None,
    )
    liquidity_score, spread, order_proxy, liquidity_reasons, liquidity_risks = _liquidity_component(market_snapshot)
    scenario = _live_momentum_scenario(market_snapshot.change_percent, market_snapshot.best_ask)
    distance_to_limit = round(max(0.0, 10.0 - market_snapshot.change_percent), 2)

    score = 18.0
    reasons: list[str] = []
    risks: list[str] = []

    if scenario == "limit_up_locked":
        score += 48.0
        reasons.append("Tavan bolgesinde veya satis kademesi bos gorunuyor")
    elif scenario == "limit_up_watch":
        score += 39.0
        reasons.append("Tavana yakin guclu fiyat momentumu var")
        risks.append("Yuksek prim nedeniyle kovalamaca riski yuksek")
    elif scenario == "strong_intraday_momentum":
        score += 29.0
        reasons.append("Gun ici guclu pozitif momentum var")
    else:
        score += 12.0
        reasons.append("Hisse gun ici pozitif bolgede")

    score += min(max(market_snapshot.change_percent, 0.0) * 3.0, 24.0)
    score += max(volume_score, -8.0)
    score += liquidity_score * 0.75

    if distance_to_limit <= 0.25:
        score += 12.0
    elif distance_to_limit <= 2.0:
        score += 8.0
    elif distance_to_limit <= 5.0:
        score += 4.0

    if daily_chart is not None:
        if daily_chart.signal_bias == "bullish":
            score += 8.0
            reasons.append("Gunluk teknik bias pozitif")
        elif daily_chart.signal_bias == "bearish":
            score -= 7.0
            risks.append("Gunluk teknik bias negatif")
        if daily_chart.breakout_state in {"confirmed_breakout_up", "breakout_watch_up"}:
            score += 5.0
            reasons.append("Teknik kirilim/izleme bolgesi destekliyor")
    else:
        risks.append("Teknik veri uyumsuz veya eksik")

    if market_snapshot.best_ask <= 0 and market_snapshot.change_percent >= 8.5:
        score += 6.0
        reasons.append("Satis kademesi bos; tavan kilidi ihtimali")

    reasons.extend(volume_reasons + liquidity_reasons)
    risks.extend(volume_risks + liquidity_risks)
    final_score = round(_clamp(score, 0.0, 100.0), 2)

    return LiveMomentumRadarItem(
        ticker=company.ticker,
        company_name=company.name,
        sector=company.sector,
        universe_sources=list(dict.fromkeys(universe_sources)),
        scenario=scenario,
        momentum_score=final_score,
        probability_bucket=_probability_bucket(final_score),
        last_price=market_snapshot.last_price,
        change_percent=market_snapshot.change_percent,
        distance_to_limit_percent=distance_to_limit,
        volume=market_snapshot.volume,
        daily_volume_ratio=daily_ratio,
        expected_volume_ratio=expected_ratio,
        volume_momentum_bucket=volume_bucket,
        technical_bias=daily_chart.signal_bias if daily_chart is not None else None,
        spread_percent=spread,
        order_flow_proxy=order_proxy,
        best_bid=market_snapshot.best_bid,
        best_ask=market_snapshot.best_ask,
        is_limit_up_like=scenario == "limit_up_locked",
        data_quality="fresh_matriks",
        reasons=list(dict.fromkeys(reasons))[:7],
        risks=list(dict.fromkeys(risks))[:7],
    )


def scan_live_momentum_radar(limit: int = 15, universe_code: str = "bist100") -> LiveMomentumRadarResponse:
    companies, source_map = _momentum_company_records(universe_code=universe_code)
    items: list[LiveMomentumRadarItem] = []
    positive_count = 0
    for company in companies:
        item = _score_live_momentum_item(company, source_map.get(company.ticker.upper(), [universe_code]))
        if item is None:
            continue
        positive_count += 1
        items.append(item)

    scenario_priority = {
        "limit_up_locked": 4,
        "limit_up_watch": 3,
        "strong_intraday_momentum": 2,
        "positive_momentum": 1,
        "not_positive": 0,
    }
    ranked = sorted(
        items,
        key=lambda item: (
            scenario_priority.get(item.scenario, 0),
            item.momentum_score,
            item.change_percent,
            item.expected_volume_ratio or 0,
            item.volume,
        ),
        reverse=True,
    )
    limited_items = ranked[: max(limit, 1)]
    scenario_counts: dict[str, int] = {}
    for item in limited_items:
        scenario_counts[item.scenario] = scenario_counts.get(item.scenario, 0) + 1

    return LiveMomentumRadarResponse(
        generated_at=datetime.utcnow().isoformat(),
        universe_size=len(companies),
        positive_count=positive_count,
        total=len(limited_items),
        scenario_counts=scenario_counts,
        items=limited_items,
    )


def _close_position_percent(open_price: float, high: float, low: float, close: float) -> float:
    candle_range = high - low
    if candle_range <= 0:
        return 50.0 if close >= open_price else 25.0
    return round(_clamp(((close - low) / candle_range) * 100.0, 0.0, 100.0), 2)


def _pre_market_setup_type(score: float, close_position: float, previous_change: float, volume_ratio: float | None, chart_summary) -> str:
    if previous_change >= 6.0 and close_position >= 70:
        return "high_momentum_gap_watch"
    if close_position >= 72 and (volume_ratio or 0) >= 1.0:
        return "closing_strength_breakout_watch"
    if chart_summary is not None and chart_summary.signal_bias == "bullish" and close_position >= 55:
        return "technical_continuation_watch"
    if score >= 45:
        return "secondary_watch"
    return "low_conviction_watch"


def _score_pre_market_watchlist_item(company: CompanyResponse, universe_sources: list[str]) -> PreMarketWatchlistItem | None:
    ohlcv = get_market_ohlcv(company.ticker, timeframe="1G", bars=30)
    if ohlcv is None or not ohlcv.candles:
        return None
    if "matriks" not in ohlcv.source.lower():
        return None

    candles = ohlcv.candles
    last = candles[-1]
    if last.open <= 0 or last.close <= 0:
        return None

    previous_change = round(((last.close - last.open) / last.open) * 100.0, 2)
    close_position = _close_position_percent(last.open, last.high, last.low, last.close)
    previous_volumes = [bar.volume for bar in candles[-11:-1] if bar.volume > 0]
    avg_volume = sum(previous_volumes) / len(previous_volumes) if previous_volumes else None
    volume_ratio = round(last.volume / avg_volume, 2) if avg_volume else None
    five_day_momentum = None
    if len(candles) >= 6 and candles[-6].close > 0:
        five_day_momentum = round(((last.close - candles[-6].close) / candles[-6].close) * 100.0, 2)

    chart_summary = _discard_incompatible_chart_summary(
        get_chart_feature_summary(company.ticker, timeframe="1G"),
        last.close,
    )

    score = 24.0
    reasons: list[str] = []
    risks: list[str] = []

    if previous_change >= 8.0:
        score += 16.0
        reasons.append("Onceki gun cok guclu pozitif kapanis")
        risks.append("Yuksek onceki gun primi nedeniyle gap/kar realizasyonu riski")
    elif previous_change >= 3.0:
        score += 18.0
        reasons.append("Onceki gun guclu pozitif kapanis")
    elif previous_change >= 1.0:
        score += 12.0
        reasons.append("Onceki gun pozitif kapanis")
    elif previous_change >= -0.5:
        score += 4.0
        reasons.append("Onceki gun dengeli kapanis")
    else:
        score -= 8.0
        risks.append("Onceki gun zayif kapanis")

    if close_position >= 82:
        score += 18.0
        reasons.append("Gunluk mum tepeye yakin kapandi")
    elif close_position >= 65:
        score += 11.0
        reasons.append("Kapanis gunluk araligin ust bolgesinde")
    elif close_position <= 35:
        score -= 9.0
        risks.append("Kapanis mumun alt bolgesinde")

    if volume_ratio is not None:
        if volume_ratio >= 1.8:
            score += 15.0
            reasons.append("Kapanis hacmi son ortalamanin cok uzerinde")
        elif volume_ratio >= 1.15:
            score += 9.0
            reasons.append("Kapanis hacmi ortalama uzerinde")
        elif volume_ratio < 0.65:
            score -= 6.0
            risks.append("Kapanis hacmi zayif")
    else:
        risks.append("Hacim ortalamasi hesaplanamadi")

    if five_day_momentum is not None:
        if 2.0 <= five_day_momentum <= 18.0:
            score += 9.0
            reasons.append("Son 5 gun momentum pozitif")
        elif five_day_momentum > 22.0:
            score += 3.0
            risks.append("Son 5 gun hareketi asiri isindi")
        elif five_day_momentum < -4.0:
            score -= 5.0
            risks.append("Son 5 gun momentum negatif")

    if chart_summary is not None:
        if chart_summary.signal_bias == "bullish":
            score += 11.0
            reasons.append("Gunluk teknik bias pozitif")
        elif chart_summary.signal_bias == "bearish":
            score -= 9.0
            risks.append("Gunluk teknik bias negatif")
        if chart_summary.breakout_state in {"confirmed_breakout_up", "breakout_watch_up", "resistance_test"}:
            score += 7.0
            reasons.append("Teknik kirilim/direnc izleme bolgesi")
    else:
        risks.append("Gunluk teknik veri eksik veya uyumsuz")

    final_score = round(_clamp(score, 0.0, 100.0), 2)
    if final_score < 42.0:
        return None

    setup_type = _pre_market_setup_type(final_score, close_position, previous_change, volume_ratio, chart_summary)
    return PreMarketWatchlistItem(
        ticker=company.ticker,
        company_name=company.name,
        sector=company.sector,
        universe_sources=list(dict.fromkeys(universe_sources)),
        pre_market_score=final_score,
        probability_bucket=_probability_bucket(final_score),
        previous_close=last.close,
        previous_change_percent=previous_change,
        five_day_momentum_percent=five_day_momentum,
        close_position_percent=close_position,
        volume_ratio=volume_ratio,
        technical_bias=chart_summary.signal_bias if chart_summary is not None else None,
        breakout_state=chart_summary.breakout_state if chart_summary is not None else None,
        trigger_price=chart_summary.breakout_buy_trigger if chart_summary is not None else None,
        invalidation_price=chart_summary.breakdown_sell_trigger if chart_summary is not None else None,
        setup_type=setup_type,
        data_quality=ohlcv.source,
        reasons=list(dict.fromkeys(reasons))[:7],
        risks=list(dict.fromkeys(risks))[:7],
    )


def scan_pre_market_watchlist(limit: int = 15, universe_code: str = "bist100") -> PreMarketWatchlistResponse:
    companies, source_map = _momentum_company_records(universe_code=universe_code)
    items: list[PreMarketWatchlistItem] = []
    for company in companies:
        item = _score_pre_market_watchlist_item(company, source_map.get(company.ticker.upper(), [universe_code]))
        if item is not None:
            items.append(item)

    ranked = sorted(
        items,
        key=lambda item: (
            item.pre_market_score,
            item.previous_change_percent,
            item.close_position_percent,
            item.volume_ratio or 0,
            item.five_day_momentum_percent or -999,
        ),
        reverse=True,
    )
    limited_items = ranked[: max(limit, 1)]
    setup_counts: dict[str, int] = {}
    for item in limited_items:
        setup_counts[item.setup_type] = setup_counts.get(item.setup_type, 0) + 1

    return PreMarketWatchlistResponse(
        generated_at=datetime.utcnow().isoformat(),
        universe_size=len(companies),
        total=len(limited_items),
        setup_counts=setup_counts,
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
