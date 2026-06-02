from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException
from uuid import uuid4

from app.db.models import PaperDecisionLog
from app.db.session import SessionLocal, ensure_runtime_schema
from app.models.schemas import MarketScanItem, PaperDecisionLogCreateResponse, PaperDecisionLogHistoryResponse, PaperDecisionLogItem, PaperDecisionOutcomeHistoryResponse, PaperDecisionOutcomeResponse, PaperDecisionPerformanceSummaryResponse, PaperDecisionResolvedPerformanceSummaryResponse
from app.services.ask_service import build_analysis_response_for_ticker
from app.services.chart_feature_service import get_chart_feature_summary
from app.data_sources.market_data.provider import get_market_snapshot
from app.services.replay_evaluation_service import _first_material_event, _load_replay_dataframe, get_trade_calibration_cached


def _new_scan_batch_id() -> str:
    return f"scan_{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}_{uuid4().hex[:8]}"


def _normalize_scan_stances(stance: str | None = None, stances: list[str] | None = None) -> list[str]:
    raw_values: list[str] = []
    if stances:
        raw_values.extend(stances)
    elif stance is not None:
        raw_values.append(stance)

    normalized: list[str] = []
    seen: set[str] = set()
    for value in raw_values:
        current = (value or '').strip().lower()
        if not current:
            continue
        if current in seen:
            continue
        seen.add(current)
        normalized.append(current)
    return normalized


def _build_log_item(row: PaperDecisionLog) -> PaperDecisionLogItem:
    latest_snapshot = get_market_snapshot(row.ticker)
    current_price = latest_snapshot.last_price if latest_snapshot is not None else None
    current_return_percent = None
    if current_price is not None and row.decision_price:
        current_return_percent = round(((float(current_price) / float(row.decision_price)) - 1) * 100, 2)

    return PaperDecisionLogItem(
        id=row.id,
        ticker=row.ticker,
        source_mode=row.source_mode,
        question=row.question,
        stance=row.stance,
        action=row.action,
        confidence=float(row.confidence),
        weighted_score=float(row.weighted_score),
        decision_price=float(row.decision_price),
        current_price=current_price,
        current_return_percent=current_return_percent,
        market_data_source=row.market_data_source,
        batch_id=row.capture_batch_id,
        trade_setup=row.trade_setup,
        trend_reference_level=row.trend_reference_level,
        entry_zone_low=row.entry_zone_low,
        entry_zone_high=row.entry_zone_high,
        breakout_buy_trigger=row.breakout_buy_trigger,
        stop_loss_level=row.stop_loss_level,
        take_profit_level=row.take_profit_level,
        calibration_bias=row.calibration_bias,
        recommendation_summary=row.recommendation_summary,
        used_sources=row.used_sources or [],
        created_at=row.created_at.isoformat() if row.created_at is not None else None,
    )


def _create_log_row(ticker: str, question: str, source_mode: str) -> PaperDecisionLog | None:
    analysis = build_analysis_response_for_ticker(ticker, question=question)
    if analysis.recommendation is None:
        return None

    chart = get_chart_feature_summary(ticker)
    snapshot = get_market_snapshot(ticker)
    if snapshot is None:
        return None
    try:
        calibration = get_trade_calibration_cached(ticker, timeframe="1G", horizon_bars=10, sample_size=8, step_bars=5)
    except HTTPException:
        calibration = None

    return PaperDecisionLog(
        ticker=ticker.upper().strip(),
        source_mode=source_mode,
        question=question,
        stance=analysis.recommendation.stance,
        action=analysis.recommendation.action,
        confidence=str(analysis.confidence),
        weighted_score=str(analysis.recommendation.weighted_score),
        decision_price=snapshot.last_price,
        market_data_source=snapshot.source,
        trade_setup=chart.trade_setup if chart is not None else "",
        trend_reference_level=chart.trend_reference_level if chart is not None else None,
        entry_zone_low=chart.entry_zone_low if chart is not None else None,
        entry_zone_high=chart.entry_zone_high if chart is not None else None,
        breakout_buy_trigger=chart.breakout_buy_trigger if chart is not None else None,
        stop_loss_level=chart.stop_loss_level if chart is not None else None,
        take_profit_level=chart.take_profit_level if chart is not None else None,
        calibration_bias=calibration.calibration_bias if calibration is not None else None,
        recommendation_summary=analysis.recommendation.summary,
        used_sources=analysis.used_sources,
    )


def _create_log_row_from_scan_item(item: MarketScanItem, batch_id: str | None = None) -> PaperDecisionLog | None:
    normalized_ticker = item.ticker.upper().strip()
    question = f"{normalized_ticker} hangi kosullarda artar ve hangi kosullarda duser?"
    chart = get_chart_feature_summary(normalized_ticker)
    try:
        calibration = get_trade_calibration_cached(normalized_ticker, timeframe="1G", horizon_bars=10, sample_size=8, step_bars=5)
    except HTTPException:
        calibration = None

    return PaperDecisionLog(
        ticker=normalized_ticker,
        source_mode="scan",
        question=question,
        stance=item.stance,
        action=item.action,
        confidence=str(item.confidence),
        weighted_score=str(item.weighted_score),
        decision_price=item.last_price,
        market_data_source=item.market_data_source,
        capture_batch_id=batch_id,
        trade_setup=chart.trade_setup if chart is not None else "",
        trend_reference_level=chart.trend_reference_level if chart is not None else None,
        entry_zone_low=chart.entry_zone_low if chart is not None else None,
        entry_zone_high=chart.entry_zone_high if chart is not None else None,
        breakout_buy_trigger=chart.breakout_buy_trigger if chart is not None else None,
        stop_loss_level=chart.stop_loss_level if chart is not None else None,
        take_profit_level=chart.take_profit_level if chart is not None else None,
        calibration_bias=calibration.calibration_bias if calibration is not None else None,
        recommendation_summary=item.summary,
        used_sources=item.used_sources,
    )


def save_paper_decision_for_ticker(ticker: str, question: str | None = None) -> PaperDecisionLogCreateResponse:
    ensure_runtime_schema()
    effective_question = question or f"{ticker.upper().strip()} hangi kosullarda artar ve hangi kosullarda duser?"
    row = _create_log_row(ticker, effective_question, source_mode="ask")
    if row is None:
        return PaperDecisionLogCreateResponse(saved_count=0, source_mode="ask", tickers=[], stances=[], batch_id=None, status="skipped")

    with SessionLocal() as session:
        session.add(row)
        session.commit()

    return PaperDecisionLogCreateResponse(saved_count=1, source_mode="ask", tickers=[ticker.upper().strip()], stances=[], batch_id=None, status="saved")


def save_paper_decision_from_scan(limit: int = 10, stance: str | None = None, stances: list[str] | None = None) -> PaperDecisionLogCreateResponse:
    from app.services.market_scan_service import scan_market

    ensure_runtime_schema()
    requested_stances = _normalize_scan_stances(stance=stance, stances=stances)
    effective_stances = requested_stances or [None]

    rows: list[PaperDecisionLog] = []
    tickers: list[str] = []
    seen_tickers: set[str] = set()
    batch_id = _new_scan_batch_id()

    for current_stance in effective_stances:
        scan = scan_market(stance=current_stance, limit=limit)
        for item in scan.items:
            normalized_ticker = item.ticker.upper().strip()
            if normalized_ticker in seen_tickers:
                continue
            if item.last_price is None:
                continue
            row = _create_log_row_from_scan_item(item, batch_id=batch_id)
            if row is None:
                continue
            rows.append(row)
            tickers.append(normalized_ticker)
            seen_tickers.add(normalized_ticker)

    if not rows:
        return PaperDecisionLogCreateResponse(
            saved_count=0,
            source_mode="scan",
            tickers=[],
            stances=requested_stances,
            batch_id=None,
            status="skipped",
        )

    with SessionLocal() as session:
        session.add_all(rows)
        session.commit()

    return PaperDecisionLogCreateResponse(
        saved_count=len(rows),
        source_mode="scan",
        tickers=tickers,
        stances=requested_stances,
        batch_id=batch_id,
        status="saved",
    )


def get_paper_decision_history(limit: int = 20, ticker: str | None = None, source_mode: str | None = None, batch_id: str | None = None) -> PaperDecisionLogHistoryResponse:
    ensure_runtime_schema()
    with SessionLocal() as session:
        query = session.query(PaperDecisionLog)
        if ticker:
            query = query.filter(PaperDecisionLog.ticker == ticker.upper().strip())
        if source_mode:
            query = query.filter(PaperDecisionLog.source_mode == source_mode.lower().strip())
        if batch_id:
            query = query.filter(PaperDecisionLog.capture_batch_id == batch_id.strip())
        if batch_id:
            query = query.filter(PaperDecisionLog.capture_batch_id == batch_id.strip())
        rows = query.order_by(PaperDecisionLog.created_at.desc()).limit(max(limit, 1)).all()

    items = [_build_log_item(row) for row in rows]
    return PaperDecisionLogHistoryResponse(total=len(items), items=items)



def _bullish_like_for_log(row: PaperDecisionLog) -> bool:
    if row.stance.lower() == "bearish" or row.action.lower() == "reduce":
        return False
    return row.trade_setup in {"pullback_buy", "trend_follow", "breakout_watch", "range_trade", ""}


def _build_paper_outcome(row: PaperDecisionLog, timeframe: str = "1G", horizon_bars: int = 10) -> PaperDecisionOutcomeResponse:
    normalized_timeframe = timeframe.upper().strip() or "1G"
    df = _load_replay_dataframe(row.ticker, normalized_timeframe, bars=max(240, horizon_bars + 180))
    decision_ts = row.created_at
    if decision_ts is None:
        raise HTTPException(status_code=400, detail="Decision timestamp missing")
    if decision_ts.tzinfo is None:
        decision_ts = decision_ts.replace(tzinfo=timezone.utc)
    else:
        decision_ts = decision_ts.astimezone(timezone.utc)

    decision_cutoff = df[df["timestamp"] > decision_ts]
    future_df = decision_cutoff.head(max(horizon_bars, 1)).copy()
    evaluated_bars = len(future_df)
    bullish_like = _bullish_like_for_log(row)

    if evaluated_bars == 0:
        return PaperDecisionOutcomeResponse(
            log_id=row.id,
            ticker=row.ticker,
            source_mode=row.source_mode,
            batch_id=row.capture_batch_id,
            timeframe=normalized_timeframe,
            horizon_bars=horizon_bars,
            evaluated_bars=0,
            decision_timestamp=row.created_at.isoformat(),
            decision_price=float(row.decision_price),
            latest_close=None,
            close_return_percent=None,
            max_upside_percent=None,
            max_drawdown_percent=None,
            entry_zone_touched=False,
            breakout_buy_trigger_hit=False,
            take_profit_hit=False,
            stop_loss_hit=False,
            first_material_event=None,
            outcome_label="pending",
            outcome_summary=f"{row.ticker} icin karar kaydindan sonra degerlendirilecek yeni bar henuz olusmadi.",
        )

    entry_zone_touched = bool(((future_df["low"] <= float(row.entry_zone_high or 0)) & (future_df["high"] >= float(row.entry_zone_low or 0))).any()) if row.entry_zone_low is not None and row.entry_zone_high is not None else False
    breakout_buy_trigger_hit = bool((future_df["high"] >= float(row.breakout_buy_trigger or 0)).any()) if row.breakout_buy_trigger is not None else False

    if bullish_like:
        take_profit_hit = bool((future_df["high"] >= float(row.take_profit_level or 0)).any()) if row.take_profit_level is not None else False
        stop_loss_hit = bool((future_df["low"] <= float(row.stop_loss_level or 0)).any()) if row.stop_loss_level is not None else False
        max_upside_percent = round(((float(future_df["high"].max()) / float(row.decision_price)) - 1) * 100, 2)
        max_drawdown_percent = round(((float(future_df["low"].min()) / float(row.decision_price)) - 1) * 100, 2)
    else:
        take_profit_hit = bool((future_df["low"] <= float(row.take_profit_level or 0)).any()) if row.take_profit_level is not None else False
        stop_loss_hit = bool((future_df["high"] >= float(row.stop_loss_level or 0)).any()) if row.stop_loss_level is not None else False
        max_upside_percent = round(((float(future_df["high"].max()) / float(row.decision_price)) - 1) * 100, 2)
        max_drawdown_percent = round(((float(future_df["low"].min()) / float(row.decision_price)) - 1) * 100, 2)

    latest_close = float(future_df.iloc[-1]["close"])
    close_return_percent = round(((latest_close / float(row.decision_price)) - 1) * 100, 2)

    class _LogFeature:
        trade_setup = row.trade_setup or "trend_follow"
        stop_loss_level = float(row.stop_loss_level or 0)
        take_profit_level = float(row.take_profit_level or 0)
        breakout_buy_trigger = float(row.breakout_buy_trigger or 0)
        breakdown_sell_trigger = 0.0
        entry_zone_low = float(row.entry_zone_low or 0)
        entry_zone_high = float(row.entry_zone_high or 0)

    first_material_event = _first_material_event(future_df, _LogFeature())

    if stop_loss_hit and not take_profit_hit:
        outcome_label = "loss"
    elif take_profit_hit and not stop_loss_hit:
        outcome_label = "win"
    elif take_profit_hit and stop_loss_hit:
        outcome_label = "mixed"
    else:
        outcome_label = "open" if close_return_percent is not None else "pending"

    summary = (
        f"{row.ticker} icin kaydedilen {row.action} karari sonraki {evaluated_bars} barda izlendi. "
        f"TP {'goruldu' if take_profit_hit else 'gorulmedi'}, SL {'calisti' if stop_loss_hit else 'calismadi'}, "
        f"kapanis getirisi %{close_return_percent}."
    )
    if first_material_event is not None:
        summary += f" Ilk kritik olay {first_material_event}."

    return PaperDecisionOutcomeResponse(
        log_id=row.id,
        ticker=row.ticker,
        source_mode=row.source_mode,
        batch_id=row.capture_batch_id,
        timeframe=normalized_timeframe,
        horizon_bars=horizon_bars,
        evaluated_bars=evaluated_bars,
        decision_timestamp=row.created_at.isoformat(),
        decision_price=float(row.decision_price),
        latest_close=latest_close,
        close_return_percent=close_return_percent,
        max_upside_percent=max_upside_percent,
        max_drawdown_percent=max_drawdown_percent,
        entry_zone_touched=entry_zone_touched,
        breakout_buy_trigger_hit=breakout_buy_trigger_hit,
        take_profit_hit=take_profit_hit,
        stop_loss_hit=stop_loss_hit,
        first_material_event=first_material_event,
        outcome_label=outcome_label,
        outcome_summary=summary,
    )


def evaluate_paper_decision_outcome(log_id: int, timeframe: str = "1G", horizon_bars: int = 10) -> PaperDecisionOutcomeResponse:
    ensure_runtime_schema()
    with SessionLocal() as session:
        row = session.get(PaperDecisionLog, log_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Paper decision log bulunamadi: {log_id}")
    return _build_paper_outcome(row, timeframe=timeframe, horizon_bars=horizon_bars)


def get_paper_decision_outcomes(limit: int = 20, ticker: str | None = None, source_mode: str | None = None, batch_id: str | None = None, timeframe: str = "1G", horizon_bars: int = 10) -> PaperDecisionOutcomeHistoryResponse:
    ensure_runtime_schema()
    with SessionLocal() as session:
        query = session.query(PaperDecisionLog)
        if ticker:
            query = query.filter(PaperDecisionLog.ticker == ticker.upper().strip())
        if source_mode:
            query = query.filter(PaperDecisionLog.source_mode == source_mode.lower().strip())
        if batch_id:
            query = query.filter(PaperDecisionLog.capture_batch_id == batch_id.strip())
        rows = query.order_by(PaperDecisionLog.created_at.desc()).limit(max(limit, 1)).all()

    items = [_build_paper_outcome(row, timeframe=timeframe, horizon_bars=horizon_bars) for row in rows]
    return PaperDecisionOutcomeHistoryResponse(total=len(items), items=items)



def get_paper_decision_performance_summary(limit: int = 50, ticker: str | None = None, source_mode: str | None = None, batch_id: str | None = None, timeframe: str = "1G", horizon_bars: int = 10) -> PaperDecisionPerformanceSummaryResponse:
    outcomes = get_paper_decision_outcomes(
        limit=limit,
        ticker=ticker,
        source_mode=source_mode,
        batch_id=batch_id,
        timeframe=timeframe,
        horizon_bars=horizon_bars,
    )
    history = get_paper_decision_history(limit=limit, ticker=ticker, source_mode=source_mode, batch_id=batch_id)

    items = outcomes.items
    total_logs = len(items)

    pending_count = sum(1 for item in items if item.outcome_label == "pending")
    open_count = sum(1 for item in items if item.outcome_label == "open")
    win_count = sum(1 for item in items if item.outcome_label == "win")
    loss_count = sum(1 for item in items if item.outcome_label == "loss")
    mixed_count = sum(1 for item in items if item.outcome_label == "mixed")
    resolved_items = [item for item in items if item.outcome_label != "pending"]
    resolved_count = len(resolved_items)

    bullish_count = sum(1 for item in history.items if item.stance.lower() == "bullish")
    neutral_count = sum(1 for item in history.items if item.stance.lower() == "neutral")
    bearish_count = sum(1 for item in history.items if item.stance.lower() == "bearish")

    source_mode_counts: dict[str, int] = {}
    calibration_bias_counts: dict[str, int] = {}
    for item in history.items:
        source_mode_counts[item.source_mode] = source_mode_counts.get(item.source_mode, 0) + 1
        bias_key = (item.calibration_bias or "unknown").lower()
        calibration_bias_counts[bias_key] = calibration_bias_counts.get(bias_key, 0) + 1

    win_rate = round(win_count / resolved_count, 2) if resolved_count else None
    loss_rate = round(loss_count / resolved_count, 2) if resolved_count else None

    close_returns = [item.close_return_percent for item in resolved_items if item.close_return_percent is not None]
    max_upside = [item.max_upside_percent for item in resolved_items if item.max_upside_percent is not None]
    max_drawdown = [item.max_drawdown_percent for item in resolved_items if item.max_drawdown_percent is not None]

    average_close_return_percent = round(sum(close_returns) / len(close_returns), 2) if close_returns else None
    average_max_upside_percent = round(sum(max_upside) / len(max_upside), 2) if max_upside else None
    average_max_drawdown_percent = round(sum(max_drawdown) / len(max_drawdown), 2) if max_drawdown else None

    summary = (
        f"Toplam {total_logs} paper karar kaydinin {pending_count} adedi henuz yeni bar bekliyor. "
        f"Cozulen kayit sayisi {resolved_count}; win {win_count}, loss {loss_count}, mixed {mixed_count}, open {open_count}. "
        f"Stance dagilimi bullish {bullish_count}, neutral {neutral_count}, bearish {bearish_count}."
    )
    if average_close_return_percent is not None:
        summary += f" Ortalama kapanis getirisi %{average_close_return_percent}."

    return PaperDecisionPerformanceSummaryResponse(
        timeframe=timeframe.upper().strip() or "1G",
        batch_id=batch_id,
        horizon_bars=horizon_bars,
        total_logs=total_logs,
        pending_count=pending_count,
        open_count=open_count,
        win_count=win_count,
        loss_count=loss_count,
        mixed_count=mixed_count,
        resolved_count=resolved_count,
        bullish_count=bullish_count,
        neutral_count=neutral_count,
        bearish_count=bearish_count,
        source_mode_counts=source_mode_counts,
        calibration_bias_counts=calibration_bias_counts,
        win_rate=win_rate,
        loss_rate=loss_rate,
        average_close_return_percent=average_close_return_percent,
        average_max_upside_percent=average_max_upside_percent,
        average_max_drawdown_percent=average_max_drawdown_percent,
        summary=summary,
    )


def get_paper_decision_resolved_performance_summary(limit: int = 50, ticker: str | None = None, source_mode: str | None = None, batch_id: str | None = None, timeframe: str = "1G", horizon_bars: int = 10) -> PaperDecisionResolvedPerformanceSummaryResponse:
    outcomes = get_paper_decision_outcomes(
        limit=limit,
        ticker=ticker,
        source_mode=source_mode,
        batch_id=batch_id,
        timeframe=timeframe,
        horizon_bars=horizon_bars,
    )
    history = get_paper_decision_history(limit=limit, ticker=ticker, source_mode=source_mode, batch_id=batch_id)

    outcome_by_id = {item.log_id: item for item in outcomes.items}
    history_by_id = {item.id: item for item in history.items}

    resolved_items = [item for item in outcomes.items if item.outcome_label != "pending"]
    pending_count = sum(1 for item in outcomes.items if item.outcome_label == "pending")
    resolved_count = len(resolved_items)
    total_logs = len(outcomes.items)

    win_count = sum(1 for item in resolved_items if item.outcome_label == "win")
    loss_count = sum(1 for item in resolved_items if item.outcome_label == "loss")
    mixed_count = sum(1 for item in resolved_items if item.outcome_label == "mixed")
    open_count = sum(1 for item in resolved_items if item.outcome_label == "open")

    resolution_rate = round(resolved_count / total_logs, 2) if total_logs else None
    resolved_win_rate = round(win_count / resolved_count, 2) if resolved_count else None
    resolved_loss_rate = round(loss_count / resolved_count, 2) if resolved_count else None

    positive_close_count = sum(1 for item in resolved_items if item.close_return_percent is not None and item.close_return_percent > 0)
    resolved_positive_close_rate = round(positive_close_count / resolved_count, 2) if resolved_count else None

    bullish_resolved_count = 0
    neutral_resolved_count = 0
    bearish_resolved_count = 0
    for item in resolved_items:
        history_item = history_by_id.get(item.log_id)
        if history_item is None:
            continue
        stance = history_item.stance.lower()
        if stance == "bullish":
            bullish_resolved_count += 1
        elif stance == "neutral":
            neutral_resolved_count += 1
        elif stance == "bearish":
            bearish_resolved_count += 1

    close_returns = [item.close_return_percent for item in resolved_items if item.close_return_percent is not None]
    max_upside = [item.max_upside_percent for item in resolved_items if item.max_upside_percent is not None]
    max_drawdown = [item.max_drawdown_percent for item in resolved_items if item.max_drawdown_percent is not None]

    average_close_return_percent = round(sum(close_returns) / len(close_returns), 2) if close_returns else None
    average_max_upside_percent = round(sum(max_upside) / len(max_upside), 2) if max_upside else None
    average_max_drawdown_percent = round(sum(max_drawdown) / len(max_drawdown), 2) if max_drawdown else None

    best_ticker = None
    best_close_return_percent = None
    worst_ticker = None
    worst_close_return_percent = None
    comparable = [item for item in resolved_items if item.close_return_percent is not None]
    if comparable:
        best_item = max(comparable, key=lambda item: item.close_return_percent)
        worst_item = min(comparable, key=lambda item: item.close_return_percent)
        best_ticker = best_item.ticker
        best_close_return_percent = best_item.close_return_percent
        worst_ticker = worst_item.ticker
        worst_close_return_percent = worst_item.close_return_percent

    summary = (
        f"Secilen pencere icinde {total_logs} kaydin {resolved_count} adedi cozuldu, {pending_count} adedi beklemede. "
        f"Resolved tarafta win {win_count}, loss {loss_count}, mixed {mixed_count}, open {open_count}."
    )
    if average_close_return_percent is not None:
        summary += f" Ortalama resolved kapanis getirisi %{average_close_return_percent}."
    if best_ticker is not None and worst_ticker is not None:
        summary += f" En iyi {best_ticker} (%{best_close_return_percent}), en zayif {worst_ticker} (%{worst_close_return_percent})."

    return PaperDecisionResolvedPerformanceSummaryResponse(
        timeframe=timeframe.upper().strip() or "1G",
        batch_id=batch_id,
        horizon_bars=horizon_bars,
        total_logs=total_logs,
        resolved_count=resolved_count,
        pending_count=pending_count,
        resolution_rate=resolution_rate,
        win_count=win_count,
        loss_count=loss_count,
        mixed_count=mixed_count,
        open_count=open_count,
        resolved_win_rate=resolved_win_rate,
        resolved_loss_rate=resolved_loss_rate,
        resolved_positive_close_rate=resolved_positive_close_rate,
        bullish_resolved_count=bullish_resolved_count,
        neutral_resolved_count=neutral_resolved_count,
        bearish_resolved_count=bearish_resolved_count,
        average_close_return_percent=average_close_return_percent,
        average_max_upside_percent=average_max_upside_percent,
        average_max_drawdown_percent=average_max_drawdown_percent,
        best_ticker=best_ticker,
        best_close_return_percent=best_close_return_percent,
        worst_ticker=worst_ticker,
        worst_close_return_percent=worst_close_return_percent,
        summary=summary,
    )
