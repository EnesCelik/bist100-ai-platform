from __future__ import annotations

import asyncio
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime, timedelta

from app.core.config import settings
from app.data_sources.company_data.provider import list_company_records
from app.data_sources.market_data.provider import get_market_ohlcv, get_market_snapshot
from app.models.schemas import RuntimeHealthResponse
from app.services.market_data_cache_service import cleanup_market_data_cache


@dataclass
class SchedulerRuntimeState:
    last_cleanup_started_at: str | None = None
    last_cleanup_completed_at: str | None = None
    last_cleanup_status: str | None = None
    last_cleanup_message: str | None = None
    last_prefetch_started_at: str | None = None
    last_prefetch_completed_at: str | None = None
    last_prefetch_status: str | None = None
    last_prefetch_message: str | None = None
    last_paper_log_started_at: str | None = None
    last_paper_log_completed_at: str | None = None
    last_paper_log_status: str | None = None
    last_paper_log_message: str | None = None
    last_paper_trade_started_at: str | None = None
    last_paper_trade_completed_at: str | None = None
    last_paper_trade_status: str | None = None
    last_paper_trade_message: str | None = None


_runtime_state = SchedulerRuntimeState()
_scheduler_task: asyncio.Task | None = None
_stop_event: asyncio.Event | None = None


def _utc_now_iso() -> str:
    return datetime.utcnow().isoformat()


def _prefetch_tickers() -> list[str]:
    configured = [ticker.strip().upper() for ticker in settings.scheduler_prefetch_tickers.split(",") if ticker.strip()]
    if configured:
        return configured
    return [company.ticker for company in list_company_records()]


def _prefetch_timeframes() -> list[str]:
    values = [value.strip().upper() for value in settings.scheduler_prefetch_timeframes.split(",") if value.strip()]
    return values or ["1G"]


def get_runtime_health() -> RuntimeHealthResponse:
    return RuntimeHealthResponse(
        status="ok",
        scheduler_enabled=settings.scheduler_enabled,
        cleanup_enabled=settings.scheduler_enabled,
        prefetch_enabled=settings.scheduler_enabled and settings.scheduler_prefetch_enabled,
        paper_log_enabled=settings.scheduler_enabled and settings.scheduler_paper_log_enabled,
        last_cleanup_started_at=_runtime_state.last_cleanup_started_at,
        last_cleanup_completed_at=_runtime_state.last_cleanup_completed_at,
        last_cleanup_status=_runtime_state.last_cleanup_status,
        last_cleanup_message=_runtime_state.last_cleanup_message,
        last_prefetch_started_at=_runtime_state.last_prefetch_started_at,
        last_prefetch_completed_at=_runtime_state.last_prefetch_completed_at,
        last_prefetch_status=_runtime_state.last_prefetch_status,
        last_prefetch_message=_runtime_state.last_prefetch_message,
        last_paper_log_started_at=_runtime_state.last_paper_log_started_at,
        last_paper_log_completed_at=_runtime_state.last_paper_log_completed_at,
        last_paper_log_status=_runtime_state.last_paper_log_status,
        last_paper_log_message=_runtime_state.last_paper_log_message,
        paper_trade_enabled=settings.scheduler_enabled and settings.scheduler_paper_trade_enabled,
        last_paper_trade_started_at=_runtime_state.last_paper_trade_started_at,
        last_paper_trade_completed_at=_runtime_state.last_paper_trade_completed_at,
        last_paper_trade_status=_runtime_state.last_paper_trade_status,
        last_paper_trade_message=_runtime_state.last_paper_trade_message,
    )


def _run_cleanup_once() -> None:
    _runtime_state.last_cleanup_started_at = _utc_now_iso()
    _runtime_state.last_cleanup_status = "running"
    try:
        result = cleanup_market_data_cache()
        _runtime_state.last_cleanup_completed_at = _utc_now_iso()
        _runtime_state.last_cleanup_status = "ok"
        _runtime_state.last_cleanup_message = (
            f"snapshot_deleted={result.snapshot_deleted}, ohlcv_deleted={result.ohlcv_deleted}"
        )
    except Exception as exc:  # noqa: BLE001
        _runtime_state.last_cleanup_completed_at = _utc_now_iso()
        _runtime_state.last_cleanup_status = "error"
        _runtime_state.last_cleanup_message = str(exc)


def _run_prefetch_once() -> None:
    _runtime_state.last_prefetch_started_at = _utc_now_iso()
    _runtime_state.last_prefetch_status = "running"
    try:
        tickers = _prefetch_tickers()
        timeframes = _prefetch_timeframes()
        snapshot_hits = 0
        ohlcv_hits = 0
        for ticker in tickers:
            if get_market_snapshot(ticker) is not None:
                snapshot_hits += 1
            for timeframe in timeframes:
                payload = get_market_ohlcv(ticker, timeframe=timeframe, bars=settings.scheduler_prefetch_bars)
                if payload is not None:
                    ohlcv_hits += 1
        _runtime_state.last_prefetch_completed_at = _utc_now_iso()
        _runtime_state.last_prefetch_status = "ok"
        _runtime_state.last_prefetch_message = (
            f"tickers={len(tickers)}, snapshots={snapshot_hits}, ohlcv_payloads={ohlcv_hits}"
        )
    except Exception as exc:  # noqa: BLE001
        _runtime_state.last_prefetch_completed_at = _utc_now_iso()
        _runtime_state.last_prefetch_status = "error"
        _runtime_state.last_prefetch_message = str(exc)


def _run_paper_log_once() -> None:
    from app.services.paper_decision_log_service import save_paper_decision_from_scan

    _runtime_state.last_paper_log_started_at = _utc_now_iso()
    _runtime_state.last_paper_log_status = "running"
    try:
        configured_stances = [value.strip().lower() for value in settings.scheduler_paper_log_stances.split(",") if value.strip()]
        result = save_paper_decision_from_scan(
            limit=max(settings.scheduler_paper_log_limit, 1),
            stance=settings.scheduler_paper_log_stance or None,
            stances=configured_stances or None,
        )
        _runtime_state.last_paper_log_completed_at = _utc_now_iso()
        _runtime_state.last_paper_log_status = "ok"
        _runtime_state.last_paper_log_message = (
            f"saved_count={result.saved_count}, source_mode={result.source_mode}, tickers={len(result.tickers)}, stances={','.join(result.stances) if result.stances else 'default'}, batch_id={result.batch_id or 'none'}"
        )
    except Exception as exc:  # noqa: BLE001
        _runtime_state.last_paper_log_completed_at = _utc_now_iso()
        _runtime_state.last_paper_log_status = "error"
        _runtime_state.last_paper_log_message = str(exc)


def _run_paper_trade_once() -> None:
    from app.services.paper_trade_simulation_service import finalize_open_trades, run_paper_trade_cycle, should_finalize_day

    _runtime_state.last_paper_trade_started_at = _utc_now_iso()
    _runtime_state.last_paper_trade_status = "running"
    try:
        if should_finalize_day():
            result = finalize_open_trades()
            message = f"finalized_count={result.finalized_count}, wins={result.win_count}, losses={result.loss_count}, neutral={result.neutral_count}"
        else:
            result = run_paper_trade_cycle(
                open_limit=max(settings.scheduler_paper_trade_open_limit, 1),
                min_score=settings.scheduler_paper_trade_min_score,
                max_open_trades=settings.scheduler_paper_trade_max_open_trades,
            )
            message = (
                f"monitor_checked={result['monitor_checked_count']}, "
                f"monitor_updated={result['monitor_updated_count']}, "
                f"opened_count={result['opened_count']}, "
                f"opened_tickers={','.join(result['opened_tickers']) if result['opened_tickers'] else 'none'}"
            )
        _runtime_state.last_paper_trade_completed_at = _utc_now_iso()
        _runtime_state.last_paper_trade_status = "ok"
        _runtime_state.last_paper_trade_message = message
    except Exception as exc:  # noqa: BLE001
        _runtime_state.last_paper_trade_completed_at = _utc_now_iso()
        _runtime_state.last_paper_trade_status = "error"
        _runtime_state.last_paper_trade_message = str(exc)


async def _scheduler_loop() -> None:
    cleanup_interval = max(settings.scheduler_cleanup_interval_minutes, 1)
    prefetch_interval = max(settings.scheduler_prefetch_interval_minutes, 1)
    paper_log_interval = max(settings.scheduler_paper_log_interval_minutes, 1)
    paper_trade_interval = max(settings.scheduler_paper_trade_interval_minutes, 1)
    prefetch_initial_delay = max(settings.scheduler_prefetch_initial_delay_minutes, 0)
    paper_log_initial_delay = max(settings.scheduler_paper_log_initial_delay_minutes, 0)
    next_cleanup_at = datetime.utcnow()
    next_prefetch_at = datetime.utcnow() + timedelta(minutes=prefetch_initial_delay)
    next_paper_log_at = datetime.utcnow() + timedelta(minutes=paper_log_initial_delay)
    next_paper_trade_at = datetime.utcnow()

    while _stop_event is not None and not _stop_event.is_set():
        now = datetime.utcnow()

        if now >= next_cleanup_at:
            await asyncio.to_thread(_run_cleanup_once)
            next_cleanup_at = datetime.utcnow() + timedelta(minutes=cleanup_interval)

        if settings.scheduler_prefetch_enabled and now >= next_prefetch_at:
            await asyncio.to_thread(_run_prefetch_once)
            next_prefetch_at = datetime.utcnow() + timedelta(minutes=prefetch_interval)

        if settings.scheduler_paper_log_enabled and now >= next_paper_log_at:
            prefetch_ready = (
                not settings.scheduler_paper_log_wait_for_prefetch
                or not settings.scheduler_prefetch_enabled
                or _runtime_state.last_prefetch_status == "ok"
                or _runtime_state.last_prefetch_status == "error"
            )
            if prefetch_ready:
                await asyncio.to_thread(_run_paper_log_once)
                next_paper_log_at = datetime.utcnow() + timedelta(minutes=paper_log_interval)

        if settings.scheduler_paper_trade_enabled and now >= next_paper_trade_at:
            await asyncio.to_thread(_run_paper_trade_once)
            next_paper_trade_at = datetime.utcnow() + timedelta(minutes=paper_trade_interval)

        try:
            await asyncio.wait_for(_stop_event.wait(), timeout=15)
        except TimeoutError:
            continue


async def start_runtime_scheduler() -> None:
    global _scheduler_task, _stop_event
    if not settings.scheduler_enabled:
        return
    if _scheduler_task is not None and not _scheduler_task.done():
        return
    _stop_event = asyncio.Event()
    _scheduler_task = asyncio.create_task(_scheduler_loop(), name="runtime-scheduler")


async def stop_runtime_scheduler() -> None:
    global _scheduler_task, _stop_event
    if _stop_event is not None:
        _stop_event.set()
    if _scheduler_task is not None:
        _scheduler_task.cancel()
        with suppress(asyncio.CancelledError):
            await _scheduler_task
    _scheduler_task = None
    _stop_event = None
