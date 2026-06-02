from __future__ import annotations

from collections import defaultdict
from datetime import datetime, time
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app.core.config import settings
from app.data_sources.market_data.provider import get_market_snapshot
from app.db.models import PaperTrade
from app.db.session import SessionLocal, ensure_runtime_schema
from app.models.schemas import (
    OpportunityScanItem,
    PaperTradeDailyReportResponse,
    PaperTradeFinalizeResponse,
    PaperTradeHistoryResponse,
    PaperTradeItem,
    PaperTradeMonitorResponse,
    PaperTradeOpenResponse,
    PaperTradeReduceResponse,
    ManualBasketCreateRequest,
)
from app.services.market_scan_service import scan_opportunities

ISTANBUL_TZ = ZoneInfo("Europe/Istanbul")


def _utcnow() -> datetime:
    return datetime.utcnow()


def _istanbul_now() -> datetime:
    return datetime.now(ISTANBUL_TZ)


def is_market_session(now: datetime | None = None) -> bool:
    current = now.astimezone(ISTANBUL_TZ) if now is not None else _istanbul_now()
    if current.weekday() >= 5:
        return False
    return time(9, 55) <= current.time() <= time(18, 10)


def should_finalize_day(now: datetime | None = None) -> bool:
    current = now.astimezone(ISTANBUL_TZ) if now is not None else _istanbul_now()
    if current.weekday() >= 5:
        return False
    return current.time() >= time(18, 15)


def _return_percent(price: float, entry_price: float) -> float:
    if entry_price <= 0:
        return 0.0
    return round(((price / entry_price) - 1.0) * 100.0, 2)


def _remaining_percent(row: PaperTrade) -> float:
    return round(max(0.0, 100.0 - float(row.realized_percent or 0.0)), 2)


def _remaining_capital(row: PaperTrade) -> float:
    return round(float(row.capital_allocated) * (_remaining_percent(row) / 100.0), 2)


def _realized_pnl(row: PaperTrade) -> float:
    realized_fraction = float(row.realized_percent or 0.0) / 100.0
    return round(float(row.capital_allocated) * realized_fraction * (float(row.realized_return_percent or 0.0) / 100.0), 2)


def _open_unrealized_pnl(row: PaperTrade) -> float:
    remaining_fraction = _remaining_percent(row) / 100.0
    return round(float(row.capital_allocated) * remaining_fraction * (float(row.current_return_percent or 0.0) / 100.0), 2)


def _total_position_pnl(row: PaperTrade) -> float:
    return round(_realized_pnl(row) + _open_unrealized_pnl(row), 2)


def _payload(row: PaperTrade) -> dict:
    return row.source_scan_payload or {}


def _execution_status_from_payload(row: PaperTrade) -> str:
    return str(_payload(row).get("execution_status") or "filled")


def _execution_reason_from_payload(row: PaperTrade) -> str | None:
    reason = _payload(row).get("execution_reason")
    return str(reason) if reason else None


def _planned_capital_from_payload(row: PaperTrade) -> float | None:
    value = _payload(row).get("planned_capital")
    return float(value) if value is not None else None


def _should_mark_no_fill(snapshot) -> tuple[bool, str | None]:
    if snapshot is None or "matriks" not in snapshot.source.lower():
        return False, None
    if snapshot.change_percent >= 9.75:
        return True, "Fiyat tavan bolgesinde; paper trade icin emir gerceklesmis sayilmadi."
    if snapshot.change_percent >= 8.5 and snapshot.best_ask <= 0:
        return True, "Satis kademesi bos gorunuyor; paper trade icin no-fill sayildi."
    return False, None


def _trade_item(row: PaperTrade) -> PaperTradeItem:
    return PaperTradeItem(
        id=row.id,
        ticker=row.ticker,
        company_name=row.company_name,
        sector=row.sector,
        strategy_name=row.strategy_name,
        scenario=row.scenario,
        status=row.status,
        outcome=row.outcome,
        opportunity_score=float(row.opportunity_score),
        confidence=float(row.confidence),
        data_quality=row.data_quality,
        entry_price=float(row.entry_price),
        capital_allocated=float(row.capital_allocated),
        current_price=float(row.current_price),
        max_seen_price=float(row.max_seen_price),
        min_seen_price=float(row.min_seen_price),
        target_1_price=float(row.target_1_price),
        target_2_price=float(row.target_2_price),
        stop_price=float(row.stop_price),
        close_price=float(row.close_price) if row.close_price is not None else None,
        current_return_percent=float(row.current_return_percent),
        max_intraday_return_percent=float(row.max_intraday_return_percent),
        min_intraday_return_percent=float(row.min_intraday_return_percent),
        hit_2_percent=bool(row.hit_2_percent),
        hit_3_percent=bool(row.hit_3_percent),
        hit_limit_up=bool(row.hit_limit_up),
        stop_hit=bool(row.stop_hit),
        profit_protected=bool(row.profit_protected),
        realized_percent=float(row.realized_percent),
        realized_price=float(row.realized_price) if row.realized_price is not None else None,
        realized_return_percent=float(row.realized_return_percent),
        remaining_percent=_remaining_percent(row),
        remaining_capital=_remaining_capital(row),
        realized_pnl=_realized_pnl(row),
        open_unrealized_pnl=_open_unrealized_pnl(row),
        total_position_pnl=_total_position_pnl(row),
        protected_stop_price=float(row.protected_stop_price) if row.protected_stop_price is not None else None,
        execution_status=_execution_status_from_payload(row),
        execution_reason=_execution_reason_from_payload(row),
        planned_capital=_planned_capital_from_payload(row),
        why_now=row.why_now or [],
        risks=row.risks or [],
        opened_at=row.opened_at.isoformat() if row.opened_at is not None else None,
        last_checked_at=row.last_checked_at.isoformat() if row.last_checked_at is not None else None,
        closed_at=row.closed_at.isoformat() if row.closed_at is not None else None,
    )


def _update_trade_with_price(row: PaperTrade, price: float, checked_at: datetime | None = None) -> None:
    checked = checked_at or _utcnow()
    row.current_price = price
    row.max_seen_price = max(float(row.max_seen_price), price)
    row.min_seen_price = min(float(row.min_seen_price), price)
    row.current_return_percent = _return_percent(price, float(row.entry_price))
    row.max_intraday_return_percent = _return_percent(float(row.max_seen_price), float(row.entry_price))
    row.min_intraday_return_percent = _return_percent(float(row.min_seen_price), float(row.entry_price))
    row.hit_2_percent = bool(row.hit_2_percent or row.max_seen_price >= row.target_1_price)
    row.hit_3_percent = bool(row.hit_3_percent or row.max_seen_price >= row.target_2_price)
    row.hit_limit_up = bool(row.hit_limit_up or row.max_intraday_return_percent >= 9.8)
    _apply_profit_protection(row)
    # Once profit protection raises the stop above entry, historical min_seen_price
    # can sit below the new stop. Only current/future checks should trigger it.
    row.stop_hit = bool(row.stop_hit or price <= row.stop_price)
    row.last_checked_at = checked


def _apply_profit_protection(row: PaperTrade) -> None:
    if not settings.paper_trade_protect_profit_enabled:
        return

    entry_price = float(row.entry_price)
    max_return = float(row.max_intraday_return_percent)
    realized_percent = float(row.realized_percent or 0.0)

    if max_return >= settings.paper_trade_protect_level_2_percent:
        target_realized = settings.paper_trade_protect_level_2_realized_percent
        stop_gain = settings.paper_trade_protect_level_2_stop_gain_percent
    elif max_return >= settings.paper_trade_protect_level_1_percent:
        target_realized = settings.paper_trade_protect_level_1_realized_percent
        stop_gain = settings.paper_trade_protect_level_1_stop_gain_percent
    else:
        return

    protected_stop = round(entry_price * (1 + (stop_gain / 100.0)), 4)
    if protected_stop > float(row.stop_price):
        row.stop_price = protected_stop
        row.protected_stop_price = protected_stop

    if target_realized > realized_percent:
        row.profit_protected = True
        row.realized_percent = target_realized
        row.realized_price = float(row.max_seen_price)
        row.realized_return_percent = _return_percent(float(row.realized_price), entry_price)


def _outcome_for_trade(row: PaperTrade) -> str:
    if row.hit_3_percent or row.hit_2_percent:
        return "win"
    if row.stop_hit or row.current_return_percent <= -2.5:
        return "loss"
    return "neutral"


def _close_if_fully_realized(row: PaperTrade) -> None:
    if float(row.realized_percent or 0.0) < 100.0 or row.status == "closed":
        return
    row.status = "closed"
    row.close_price = float(row.realized_price) if row.realized_price is not None else float(row.current_price)
    row.current_return_percent = _return_percent(float(row.close_price), float(row.entry_price))
    row.outcome = _outcome_for_trade(row)
    row.closed_at = _utcnow()


def _create_trade_from_opportunity(item: OpportunityScanItem) -> PaperTrade | None:
    if item.last_price is None or item.last_price <= 0:
        return None
    entry_price = float(item.last_price)
    stop_price = float(item.invalidation_price) if item.invalidation_price and item.invalidation_price > 0 else round(entry_price * 0.975, 4)
    if stop_price >= entry_price:
        stop_price = round(entry_price * 0.975, 4)

    return PaperTrade(
        ticker=item.ticker,
        company_name=item.company_name,
        sector=item.sector,
        strategy_name="auto_opportunity",
        scenario=item.scenario,
        status="open",
        outcome="open",
        opportunity_score=item.opportunity_score,
        confidence=item.confidence,
        data_quality=item.data_quality,
        entry_price=entry_price,
        capital_allocated=0.0,
        current_price=entry_price,
        max_seen_price=entry_price,
        min_seen_price=entry_price,
        target_1_price=round(entry_price * 1.02, 4),
        target_2_price=round(entry_price * 1.03, 4),
        stop_price=stop_price,
        close_price=None,
        current_return_percent=0.0,
        max_intraday_return_percent=0.0,
        min_intraday_return_percent=0.0,
        hit_2_percent=False,
        hit_3_percent=False,
        hit_limit_up=False,
        stop_hit=False,
        profit_protected=False,
        realized_percent=0.0,
        realized_price=None,
        realized_return_percent=0.0,
        protected_stop_price=None,
        source_scan_payload=item.model_dump(),
        why_now=item.why_now,
        risks=item.risks,
        opened_at=_utcnow(),
        last_checked_at=_utcnow(),
    )


def open_top_opportunity_trades(limit: int = 5, min_score: float = 70.0, max_open_trades: int | None = None) -> PaperTradeOpenResponse:
    ensure_runtime_schema()
    max_open = max(max_open_trades if max_open_trades is not None else settings.scheduler_paper_trade_max_open_trades, 1)

    opened_rows: list[PaperTrade] = []
    skipped_count = 0
    with SessionLocal() as session:
        open_tickers = {
            row[0]
            for row in session.execute(
                select(PaperTrade.ticker).where(PaperTrade.status == "open")
            ).all()
        }
        open_capacity = max(max_open - len(open_tickers), 0)
        effective_limit = min(max(limit, 1), open_capacity)

        if effective_limit <= 0:
            return PaperTradeOpenResponse(
                opened_count=0,
                skipped_count=0,
                open_trade_count=len(open_tickers),
                tickers=[],
                items=[],
            )

        scan = scan_opportunities(limit=max(effective_limit * 3, effective_limit), include_avoid=False)

        for item in scan.items:
            if len(opened_rows) >= effective_limit:
                break
            if item.opportunity_score < min_score:
                skipped_count += 1
                continue
            if item.scenario == "avoid_or_invalidated" or item.data_quality != "fresh_matriks":
                skipped_count += 1
                continue
            if item.ticker in open_tickers:
                skipped_count += 1
                continue
            row = _create_trade_from_opportunity(item)
            if row is None:
                skipped_count += 1
                continue
            session.add(row)
            opened_rows.append(row)
            open_tickers.add(item.ticker)

        session.commit()
        for row in opened_rows:
            session.refresh(row)

        open_trade_count = session.scalar(select(PaperTrade).where(PaperTrade.status == "open").count()) if False else len(open_tickers)
        items = [_trade_item(row) for row in opened_rows]

    return PaperTradeOpenResponse(
        opened_count=len(items),
        skipped_count=skipped_count,
        open_trade_count=open_trade_count,
        tickers=[item.ticker for item in items],
        items=items,
    )


def monitor_open_trades() -> PaperTradeMonitorResponse:
    ensure_runtime_schema()
    updated_rows: list[PaperTrade] = []
    checked_count = 0

    with SessionLocal() as session:
        rows = session.execute(select(PaperTrade).where(PaperTrade.status == "open").order_by(PaperTrade.opened_at.asc())).scalars().all()
        checked_count = len(rows)
        for row in rows:
            snapshot = get_market_snapshot(row.ticker, force_refresh=True)
            if snapshot is None or "matriks" not in snapshot.source.lower():
                continue
            _update_trade_with_price(row, float(snapshot.last_price))
            updated_rows.append(row)

        session.commit()
        for row in updated_rows:
            session.refresh(row)
        items = [_trade_item(row) for row in updated_rows]

    return PaperTradeMonitorResponse(checked_count=checked_count, updated_count=len(items), items=items)


def finalize_open_trades() -> PaperTradeFinalizeResponse:
    ensure_runtime_schema()
    finalized_rows: list[PaperTrade] = []

    with SessionLocal() as session:
        rows = session.execute(select(PaperTrade).where(PaperTrade.status == "open").order_by(PaperTrade.opened_at.asc())).scalars().all()
        for row in rows:
            snapshot = get_market_snapshot(row.ticker, force_refresh=True)
            if snapshot is not None and "matriks" in snapshot.source.lower():
                _update_trade_with_price(row, float(snapshot.last_price))
            row.close_price = row.current_price
            row.current_return_percent = _return_percent(float(row.close_price), float(row.entry_price))
            row.outcome = _outcome_for_trade(row)
            row.status = "closed"
            row.closed_at = _utcnow()
            finalized_rows.append(row)

        session.commit()
        for row in finalized_rows:
            session.refresh(row)
        items = [_trade_item(row) for row in finalized_rows]

    return PaperTradeFinalizeResponse(
        finalized_count=len(items),
        win_count=sum(1 for item in items if item.outcome == "win"),
        loss_count=sum(1 for item in items if item.outcome == "loss"),
        neutral_count=sum(1 for item in items if item.outcome == "neutral"),
        items=items,
    )


def reduce_open_trades(
    tickers: list[str],
    strategy_name: str | None = None,
    reduce_percent: float = 50.0,
) -> PaperTradeReduceResponse:
    ensure_runtime_schema()
    normalized_tickers = {ticker.upper().strip() for ticker in tickers if ticker.strip()}
    normalized_strategy = strategy_name.strip() if strategy_name else None
    target_realized = max(0.0, min(float(reduce_percent), 100.0))
    updated_rows: list[PaperTrade] = []
    skipped_count = 0

    if not normalized_tickers or target_realized <= 0:
        return PaperTradeReduceResponse(reduced_count=0, skipped_count=len(normalized_tickers), items=[])

    with SessionLocal() as session:
        statement = select(PaperTrade).where(PaperTrade.status == "open", PaperTrade.ticker.in_(normalized_tickers))
        if normalized_strategy:
            statement = statement.where(PaperTrade.strategy_name == normalized_strategy)
        rows = session.execute(statement.order_by(PaperTrade.opened_at.asc())).scalars().all()
        found_tickers = {row.ticker for row in rows}
        skipped_count += len(normalized_tickers - found_tickers)

        for row in rows:
            current_realized = float(row.realized_percent or 0.0)
            if current_realized >= target_realized:
                skipped_count += 1
                continue
            snapshot = get_market_snapshot(row.ticker, force_refresh=True)
            if snapshot is not None and "matriks" in snapshot.source.lower():
                _update_trade_with_price(row, float(snapshot.last_price))
            current_realized_return = float(row.realized_return_percent or 0.0)
            incremental_percent = target_realized - current_realized
            incremental_return = _return_percent(float(row.current_price), float(row.entry_price))
            weighted_return = (
                ((current_realized * current_realized_return) + (incremental_percent * incremental_return))
                / target_realized
            )
            weighted_price = float(row.entry_price) * (1 + (weighted_return / 100.0))
            row.profit_protected = True
            row.realized_percent = target_realized
            row.realized_price = round(weighted_price, 4)
            row.realized_return_percent = round(weighted_return, 2)
            _close_if_fully_realized(row)
            row.source_scan_payload = {
                **(row.source_scan_payload or {}),
                "manual_reduce": {
                    "target_realized_percent": target_realized,
                    "incremental_realized_percent": incremental_percent,
                    "incremental_realized_price": float(row.current_price),
                    "incremental_realized_return_percent": incremental_return,
                    "realized_price": row.realized_price,
                    "realized_return_percent": row.realized_return_percent,
                    "created_at": _utcnow().isoformat(),
                },
            }
            updated_rows.append(row)

        session.commit()
        for row in updated_rows:
            session.refresh(row)
        items = [_trade_item(row) for row in updated_rows]

    return PaperTradeReduceResponse(reduced_count=len(items), skipped_count=skipped_count, items=items)


def close_fully_realized_trades(strategy_name: str | None = None) -> PaperTradeFinalizeResponse:
    ensure_runtime_schema()
    normalized_strategy = strategy_name.strip() if strategy_name else None
    closed_rows: list[PaperTrade] = []

    with SessionLocal() as session:
        statement = select(PaperTrade).where(PaperTrade.status == "open", PaperTrade.realized_percent >= 100.0)
        if normalized_strategy:
            statement = statement.where(PaperTrade.strategy_name == normalized_strategy)
        rows = session.execute(statement.order_by(PaperTrade.opened_at.asc())).scalars().all()
        for row in rows:
            _close_if_fully_realized(row)
            closed_rows.append(row)

        session.commit()
        for row in closed_rows:
            session.refresh(row)
        items = [_trade_item(row) for row in closed_rows]

    return PaperTradeFinalizeResponse(
        finalized_count=len(items),
        win_count=sum(1 for item in items if item.outcome == "win"),
        loss_count=sum(1 for item in items if item.outcome == "loss"),
        neutral_count=sum(1 for item in items if item.outcome == "neutral"),
        items=items,
    )


def get_paper_trades(limit: int = 50, status: str | None = None, strategy_name: str | None = None) -> PaperTradeHistoryResponse:
    ensure_runtime_schema()
    normalized_status = status.lower().strip() if status else None
    normalized_strategy = strategy_name.strip() if strategy_name else None
    with SessionLocal() as session:
        statement = select(PaperTrade)
        if normalized_status:
            statement = statement.where(PaperTrade.status == normalized_status)
        if normalized_strategy:
            statement = statement.where(PaperTrade.strategy_name == normalized_strategy)
        rows = session.execute(statement.order_by(PaperTrade.opened_at.desc()).limit(max(limit, 1))).scalars().all()
        items = [_trade_item(row) for row in rows]
    return PaperTradeHistoryResponse(total=len(items), items=items)


def get_daily_paper_trade_report(trade_date: str | None = None, strategy_name: str | None = None) -> PaperTradeDailyReportResponse:
    ensure_runtime_schema()
    report_date = trade_date or _istanbul_now().date().isoformat()
    normalized_strategy = strategy_name.strip() if strategy_name else None

    with SessionLocal() as session:
        statement = select(PaperTrade)
        if normalized_strategy:
            statement = statement.where(PaperTrade.strategy_name == normalized_strategy)
        rows = session.execute(statement.order_by(PaperTrade.opened_at.desc())).scalars().all()

    items = [
        _trade_item(row)
        for row in rows
        if row.opened_at is not None and row.opened_at.replace(tzinfo=ZoneInfo("UTC")).astimezone(ISTANBUL_TZ).date().isoformat() == report_date
    ]
    finalized = [item for item in items if item.status == "closed"]
    scenario_counts: dict[str, int] = defaultdict(int)
    scenario_returns: dict[str, list[float]] = defaultdict(list)
    for item in items:
        scenario_counts[item.scenario] += 1
        scenario_returns[item.scenario].append(item.max_intraday_return_percent)

    scenario_averages = {
        scenario: sum(values) / len(values)
        for scenario, values in scenario_returns.items()
        if values
    }
    best_scenario = max(scenario_averages, key=scenario_averages.get) if scenario_averages else None
    worst_scenario = min(scenario_averages, key=scenario_averages.get) if scenario_averages else None
    average_max_return = round(sum(item.max_intraday_return_percent for item in items) / len(items), 2) if items else None
    average_close_return = round(sum(item.current_return_percent for item in finalized) / len(finalized), 2) if finalized else None
    hit_2_count = sum(1 for item in items if item.hit_2_percent)
    hit_3_count = sum(1 for item in items if item.hit_3_percent)
    hit_limit_count = sum(1 for item in items if item.hit_limit_up)
    no_fill_count = sum(1 for item in items if item.execution_status == "no_fill" or item.outcome == "no_fill")
    profit_protected_count = sum(1 for item in items if item.profit_protected)
    win_count = sum(1 for item in finalized if item.outcome == "win")
    loss_count = sum(1 for item in finalized if item.outcome == "loss")
    neutral_count = sum(1 for item in finalized if item.outcome == "neutral")
    summary = (
        f"{report_date} icin {len(items)} paper trade acildi. "
        f"{hit_2_count} tanesi +%2, {hit_3_count} tanesi +%3, {hit_limit_count} tanesi tavan benzeri hareket gordu. "
        f"{no_fill_count} tanesi emir gerceklesmedi sayildi. "
        f"Ortalama maksimum getiri %{average_max_return if average_max_return is not None else 0}."
    )

    return PaperTradeDailyReportResponse(
        trade_date=report_date,
        strategy_name=normalized_strategy,
        total_trades=len(items),
        open_count=sum(1 for item in items if item.status == "open"),
        finalized_count=len(finalized),
        hit_2_percent_count=hit_2_count,
        hit_3_percent_count=hit_3_count,
        hit_limit_up_count=hit_limit_count,
        profit_protected_count=profit_protected_count,
        win_count=win_count,
        loss_count=loss_count,
        neutral_count=neutral_count,
        average_max_return_percent=average_max_return,
        average_close_return_percent=average_close_return,
        best_scenario=best_scenario,
        worst_scenario=worst_scenario,
        scenario_counts=dict(scenario_counts),
        summary=summary,
    )


def create_manual_basket(request: ManualBasketCreateRequest) -> PaperTradeOpenResponse:
    ensure_runtime_schema()
    returned_rows: list[PaperTrade] = []
    actual_opened_count = 0
    strategy_name = request.strategy_name.strip() or "manual_morning_basket"

    with SessionLocal() as session:
        existing_open_tickers = {
            row[0]
            for row in session.execute(
                select(PaperTrade.ticker).where(
                    PaperTrade.status == "open",
                    PaperTrade.strategy_name == strategy_name,
                )
            ).all()
        }
        skipped_count = 0
        for position in request.positions:
            ticker = position.ticker.upper().strip()
            if ticker in existing_open_tickers:
                skipped_count += 1
                continue
            snapshot = get_market_snapshot(ticker, force_refresh=True)
            current_price = float(snapshot.last_price) if snapshot is not None and "matriks" in snapshot.source.lower() else float(position.entry_price)
            no_fill, no_fill_reason = _should_mark_no_fill(snapshot)
            planned_capital = float(position.capital_allocated)
            row = PaperTrade(
                ticker=ticker,
                company_name=ticker,
                sector="",
                strategy_name=strategy_name,
                scenario=position.scenario,
                status="closed" if no_fill else "open",
                outcome="no_fill" if no_fill else "open",
                opportunity_score=0.0,
                confidence=0.0,
                data_quality="no_fill" if no_fill else "manual",
                entry_price=float(position.entry_price),
                capital_allocated=0.0 if no_fill else planned_capital,
                current_price=current_price,
                max_seen_price=max(float(position.entry_price), current_price),
                min_seen_price=min(float(position.entry_price), current_price),
                target_1_price=round(float(position.entry_price) * 1.02, 4),
                target_2_price=round(float(position.entry_price) * 1.03, 4),
                stop_price=round(float(position.entry_price) * 0.975, 4),
                close_price=current_price if no_fill else None,
                current_return_percent=0.0,
                max_intraday_return_percent=0.0,
                min_intraday_return_percent=0.0,
                hit_2_percent=False,
                hit_3_percent=False,
                hit_limit_up=False,
                stop_hit=False,
                profit_protected=False,
                realized_percent=0.0,
                realized_price=None,
                realized_return_percent=0.0,
                protected_stop_price=None,
                source_scan_payload={
                    "manual_position": position.model_dump(),
                    "execution_status": "no_fill" if no_fill else "filled",
                    "execution_reason": no_fill_reason if no_fill else "Paper trade girisi gerceklesmis varsayildi.",
                    "planned_capital": planned_capital,
                },
                why_now=["Manuel simülasyon sepeti"],
                risks=[no_fill_reason] if no_fill and no_fill_reason else [],
                opened_at=_utcnow(),
                last_checked_at=_utcnow(),
                closed_at=_utcnow() if no_fill else None,
            )
            if not no_fill:
                _update_trade_with_price(row, current_price)
            session.add(row)
            returned_rows.append(row)
            if no_fill:
                skipped_count += 1
            else:
                actual_opened_count += 1
                existing_open_tickers.add(ticker)

        session.commit()
        for row in returned_rows:
            session.refresh(row)
        open_count = len(existing_open_tickers)
        items = [_trade_item(row) for row in returned_rows]

    return PaperTradeOpenResponse(
        opened_count=actual_opened_count,
        skipped_count=skipped_count,
        open_trade_count=open_count,
        tickers=[item.ticker for item in items if item.status == "open"],
        items=items,
    )


def run_paper_trade_cycle(open_limit: int = 5, min_score: float = 70.0, max_open_trades: int | None = None) -> dict:
    monitor_result = monitor_open_trades()
    open_result = open_top_opportunity_trades(limit=open_limit, min_score=min_score, max_open_trades=max_open_trades) if is_market_session() else None
    return {
        "monitor_checked_count": monitor_result.checked_count,
        "monitor_updated_count": monitor_result.updated_count,
        "opened_count": open_result.opened_count if open_result is not None else 0,
        "opened_tickers": open_result.tickers if open_result is not None else [],
    }
