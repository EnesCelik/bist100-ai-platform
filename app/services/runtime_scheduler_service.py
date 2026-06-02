from __future__ import annotations

import asyncio
import json
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from app.core.config import settings
from app.data_sources.company_data.provider import list_company_records
from app.data_sources.market_data.provider import get_market_ohlcv, get_market_snapshot
from app.models.schemas import RuntimeHealthResponse
from app.services.market_calendar_service import check_bist_trading_day
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
    last_trading_agent_started_at: str | None = None
    last_trading_agent_completed_at: str | None = None
    last_trading_agent_status: str | None = None
    last_trading_agent_message: str | None = None
    last_trading_agent_opening_date: str | None = None
    last_trading_agent_finalize_date: str | None = None
    last_trading_agent_report_date: str | None = None
    last_agent_morning_telegram_date: str | None = None
    last_agent_morning_telegram_started_at: str | None = None
    last_agent_morning_telegram_completed_at: str | None = None
    last_agent_morning_telegram_status: str | None = None
    last_agent_morning_telegram_message: str | None = None
    last_agent_intraday_telegram_dates: dict[str, str] | None = None
    last_agent_intraday_telegram_started_at: str | None = None
    last_agent_intraday_telegram_completed_at: str | None = None
    last_agent_intraday_telegram_status: str | None = None
    last_agent_intraday_telegram_message: str | None = None


_runtime_state = SchedulerRuntimeState()
_scheduler_task: asyncio.Task | None = None
_stop_event: asyncio.Event | None = None
_STATE_PATH = Path(__file__).resolve().parents[2] / "data" / "runtime_scheduler_state.json"


def _utc_now_iso() -> str:
    return datetime.utcnow().isoformat()


def _load_persistent_state() -> None:
    if not _STATE_PATH.exists():
        return
    try:
        payload = json.loads(_STATE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    value = payload.get("last_agent_morning_telegram_date")
    if isinstance(value, str) and value:
        _runtime_state.last_agent_morning_telegram_date = value
    intraday_dates = payload.get("last_agent_intraday_telegram_dates")
    if isinstance(intraday_dates, dict):
        _runtime_state.last_agent_intraday_telegram_dates = {
            str(slot): str(sent_date)
            for slot, sent_date in intraday_dates.items()
            if slot and sent_date
        }


def _save_persistent_state() -> None:
    try:
        _STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        _STATE_PATH.write_text(
            json.dumps(
                {
                    "last_agent_morning_telegram_date": _runtime_state.last_agent_morning_telegram_date,
                    "last_agent_intraday_telegram_dates": _runtime_state.last_agent_intraday_telegram_dates or {},
                    "updated_at": _utc_now_iso(),
                },
                ensure_ascii=True,
                indent=2,
            ),
            encoding="utf-8",
        )
    except OSError:
        return


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
        paper_trade_enabled=settings.scheduler_enabled and settings.paper_trade_enabled and settings.scheduler_paper_trade_enabled,
        last_paper_trade_started_at=_runtime_state.last_paper_trade_started_at,
        last_paper_trade_completed_at=_runtime_state.last_paper_trade_completed_at,
        last_paper_trade_status=_runtime_state.last_paper_trade_status,
        last_paper_trade_message=_runtime_state.last_paper_trade_message,
        trading_agent_enabled=settings.scheduler_enabled and settings.scheduler_trading_agent_enabled,
        last_trading_agent_started_at=_runtime_state.last_trading_agent_started_at,
        last_trading_agent_completed_at=_runtime_state.last_trading_agent_completed_at,
        last_trading_agent_status=_runtime_state.last_trading_agent_status,
        last_trading_agent_message=_runtime_state.last_trading_agent_message,
        agent_morning_telegram_enabled=settings.scheduler_enabled and settings.scheduler_agent_morning_telegram_enabled,
        last_agent_morning_telegram_started_at=_runtime_state.last_agent_morning_telegram_started_at,
        last_agent_morning_telegram_completed_at=_runtime_state.last_agent_morning_telegram_completed_at,
        last_agent_morning_telegram_status=_runtime_state.last_agent_morning_telegram_status,
        last_agent_morning_telegram_message=_runtime_state.last_agent_morning_telegram_message,
        agent_intraday_telegram_enabled=settings.scheduler_enabled and settings.scheduler_agent_intraday_telegram_enabled,
        last_agent_intraday_telegram_started_at=_runtime_state.last_agent_intraday_telegram_started_at,
        last_agent_intraday_telegram_completed_at=_runtime_state.last_agent_intraday_telegram_completed_at,
        last_agent_intraday_telegram_status=_runtime_state.last_agent_intraday_telegram_status,
        last_agent_intraday_telegram_message=_runtime_state.last_agent_intraday_telegram_message,
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


def _run_trading_agent_job(job_name: str) -> None:
    from app.models.schemas import TradingAgentOpeningPlanRequest
    from app.services.trading_agent_service import (
        get_agent_daily_report,
        run_finalize_cycle,
        run_monitor_cycle,
        run_opening_plan,
    )

    _runtime_state.last_trading_agent_started_at = _utc_now_iso()
    _runtime_state.last_trading_agent_status = "running"
    try:
        if job_name == "opening":
            result = run_opening_plan(
                TradingAgentOpeningPlanRequest(
                    strategy_name=f"agent_opening_basket_{datetime.now(ZoneInfo('Europe/Istanbul')).strftime('%Y_%m_%d')}",
                    limit=max(settings.scheduler_paper_trade_open_limit, 1),
                    total_capital=settings.scheduler_trading_agent_total_capital,
                    cash_buffer=settings.scheduler_trading_agent_cash_buffer,
                    min_opening_score=settings.scheduler_trading_agent_min_opening_score,
                )
            )
            message = f"opening opened={result.opened.opened_count if result.opened else 0}, action={result.action}"
        elif job_name == "finalize":
            result = run_finalize_cycle()
            message = f"finalized={result.finalized.finalized_count if result.finalized else 0}"
        elif job_name == "report":
            result = get_agent_daily_report()
            message = f"report total={result.report.total_trades if result.report else 0}"
        else:
            result = run_monitor_cycle()
            message = f"monitor updated={result.monitored.updated_count if result.monitored else 0}"

        _runtime_state.last_trading_agent_completed_at = _utc_now_iso()
        _runtime_state.last_trading_agent_status = "ok"
        _runtime_state.last_trading_agent_message = message
    except Exception as exc:  # noqa: BLE001
        _runtime_state.last_trading_agent_completed_at = _utc_now_iso()
        _runtime_state.last_trading_agent_status = "error"
        _runtime_state.last_trading_agent_message = f"{job_name}: {exc}"


def _run_agent_morning_telegram_once() -> None:
    from app.services.trading_agent_telegram_service import send_morning_opening_telegram

    _runtime_state.last_agent_morning_telegram_started_at = _utc_now_iso()
    _runtime_state.last_agent_morning_telegram_status = "running"
    try:
        result = send_morning_opening_telegram(force=False)
        _runtime_state.last_agent_morning_telegram_completed_at = _utc_now_iso()
        _runtime_state.last_agent_morning_telegram_status = result.status
        _runtime_state.last_agent_morning_telegram_message = (
            f"reason={result.reason}, chat_id_configured={result.chat_id_configured}, tickers={','.join(result.tickers) if result.tickers else 'none'}"
        )
    except Exception as exc:  # noqa: BLE001
        _runtime_state.last_agent_morning_telegram_completed_at = _utc_now_iso()
        _runtime_state.last_agent_morning_telegram_status = "error"
        _runtime_state.last_agent_morning_telegram_message = str(exc)


def _run_agent_intraday_telegram_once(slot: str) -> None:
    from app.services.trading_agent_telegram_service import send_intraday_momentum_telegram

    _runtime_state.last_agent_intraday_telegram_started_at = _utc_now_iso()
    _runtime_state.last_agent_intraday_telegram_status = "running"
    try:
        result = send_intraday_momentum_telegram(slot=slot, force=False)
        _runtime_state.last_agent_intraday_telegram_completed_at = _utc_now_iso()
        _runtime_state.last_agent_intraday_telegram_status = result.status
        _runtime_state.last_agent_intraday_telegram_message = (
            f"slot={slot}, reason={result.reason}, chat_id_configured={result.chat_id_configured}, "
            f"tickers={','.join(result.tickers) if result.tickers else 'none'}"
        )
    except Exception as exc:  # noqa: BLE001
        _runtime_state.last_agent_intraday_telegram_completed_at = _utc_now_iso()
        _runtime_state.last_agent_intraday_telegram_status = "error"
        _runtime_state.last_agent_intraday_telegram_message = f"slot={slot}: {exc}"


def _time_reached(now_local: datetime, hour: int, minute: int) -> bool:
    return (now_local.hour, now_local.minute) >= (hour, minute)


def _time_in_send_window(now_local: datetime, hour: int, minute: int, window_minutes: int = 10) -> bool:
    slot_time = now_local.replace(hour=hour, minute=minute, second=0, microsecond=0)
    return slot_time <= now_local < slot_time + timedelta(minutes=window_minutes)


def _parse_time_slot(value: str) -> tuple[int, int] | None:
    if ":" not in value:
        return None
    hour_text, minute_text = value.split(":", 1)
    try:
        hour = int(hour_text)
        minute = int(minute_text)
    except ValueError:
        return None
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None
    return hour, minute


def _intraday_telegram_slots() -> list[tuple[str, int, int]]:
    slots: list[tuple[str, int, int]] = []
    for raw_value in settings.scheduler_agent_intraday_telegram_times.split(","):
        slot = raw_value.strip()
        parsed = _parse_time_slot(slot)
        if parsed is None:
            continue
        slots.append((slot, parsed[0], parsed[1]))
    return slots


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
    next_trading_agent_monitor_at = datetime.utcnow()

    while _stop_event is not None and not _stop_event.is_set():
        now = datetime.utcnow()
        now_local = datetime.now(ZoneInfo("Europe/Istanbul"))
        local_date = now_local.date().isoformat()
        calendar_check = check_bist_trading_day(now_local)
        is_trading_day = calendar_check.is_trading_day

        if now >= next_cleanup_at:
            await asyncio.to_thread(_run_cleanup_once)
            next_cleanup_at = datetime.utcnow() + timedelta(minutes=cleanup_interval)

        # Morning Telegram is time-sensitive; do not let long prefetch/cache jobs block it.
        morning_telegram_pending = (
            settings.scheduler_agent_morning_telegram_enabled
            and is_trading_day
            and _runtime_state.last_agent_morning_telegram_date != local_date
            and not _time_reached(
                now_local,
                settings.scheduler_trading_agent_opening_hour,
                settings.scheduler_trading_agent_opening_minute,
            )
        )
        if morning_telegram_pending and _time_reached(
            now_local,
            settings.scheduler_agent_morning_telegram_hour,
            settings.scheduler_agent_morning_telegram_minute,
        ):
            await asyncio.to_thread(_run_agent_morning_telegram_once)
            _runtime_state.last_agent_morning_telegram_date = local_date
            _save_persistent_state()

        if settings.scheduler_prefetch_enabled and now >= next_prefetch_at and not morning_telegram_pending:
            await asyncio.to_thread(_run_prefetch_once)
            next_prefetch_at = datetime.utcnow() + timedelta(minutes=prefetch_interval)

        if settings.scheduler_agent_intraday_telegram_enabled and is_trading_day:
            sent_slots = _runtime_state.last_agent_intraday_telegram_dates or {}
            for slot, hour, minute in _intraday_telegram_slots():
                if sent_slots.get(slot) == local_date:
                    continue
                if _time_in_send_window(now_local, hour, minute) and not _time_reached(
                    now_local,
                    settings.scheduler_trading_agent_finalize_hour,
                    settings.scheduler_trading_agent_finalize_minute,
                ):
                    await asyncio.to_thread(_run_agent_intraday_telegram_once, slot)
                    sent_slots[slot] = local_date
                    _runtime_state.last_agent_intraday_telegram_dates = sent_slots
                    _save_persistent_state()

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

        if settings.paper_trade_enabled and settings.scheduler_paper_trade_enabled and now >= next_paper_trade_at:
            await asyncio.to_thread(_run_paper_trade_once)
            next_paper_trade_at = datetime.utcnow() + timedelta(minutes=paper_trade_interval)

        if settings.scheduler_trading_agent_enabled and not is_trading_day:
            _runtime_state.last_trading_agent_status = "skipped"
            _runtime_state.last_trading_agent_message = f"market_closed:{calendar_check.reason}"
            next_trading_agent_monitor_at = datetime.utcnow() + timedelta(minutes=paper_trade_interval)

        if settings.scheduler_trading_agent_enabled and is_trading_day:
            if (
                _runtime_state.last_trading_agent_opening_date != local_date
                and _time_reached(
                    now_local,
                    settings.scheduler_trading_agent_opening_hour,
                    settings.scheduler_trading_agent_opening_minute,
                )
                and not _time_reached(
                    now_local,
                    settings.scheduler_trading_agent_finalize_hour,
                    settings.scheduler_trading_agent_finalize_minute,
                )
            ):
                await asyncio.to_thread(_run_trading_agent_job, "opening")
                _runtime_state.last_trading_agent_opening_date = local_date

            if now >= next_trading_agent_monitor_at and not _time_reached(
                now_local,
                settings.scheduler_trading_agent_finalize_hour,
                settings.scheduler_trading_agent_finalize_minute,
            ):
                await asyncio.to_thread(_run_trading_agent_job, "monitor")
                next_trading_agent_monitor_at = datetime.utcnow() + timedelta(minutes=paper_trade_interval)

            if (
                _runtime_state.last_trading_agent_finalize_date != local_date
                and _time_reached(
                    now_local,
                    settings.scheduler_trading_agent_finalize_hour,
                    settings.scheduler_trading_agent_finalize_minute,
                )
            ):
                await asyncio.to_thread(_run_trading_agent_job, "finalize")
                _runtime_state.last_trading_agent_finalize_date = local_date

            if (
                _runtime_state.last_trading_agent_report_date != local_date
                and _time_reached(
                    now_local,
                    settings.scheduler_trading_agent_report_hour,
                    settings.scheduler_trading_agent_report_minute,
                )
            ):
                await asyncio.to_thread(_run_trading_agent_job, "report")
                _runtime_state.last_trading_agent_report_date = local_date

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
    _load_persistent_state()
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
