from datetime import datetime
from zoneinfo import ZoneInfo

from app.core.config import settings
from app.models.schemas import TradingAgentMorningTelegramResponse
from app.services.market_calendar_service import check_bist_trading_day
from app.services.market_scan_service import scan_intraday_upside_candidates, scan_pre_market_watchlist
from app.services.telegram_service import send_telegram_message
from app.services.technical_indicator_text_service import humanize_label

ISTANBUL_TZ = ZoneInfo("Europe/Istanbul")


def _build_morning_telegram_message(limit: int) -> tuple[str, list[str]]:
    scan = scan_pre_market_watchlist(limit=limit)
    today = datetime.now(ISTANBUL_TZ).date().isoformat()
    lines = [
        f"BIST agent pre-market izleme listesi - {today}",
        f"Pre-market aday sayisi: {scan.total}/{scan.universe_size}",
        "",
        "Not: Bu liste onceki gun kapanis/hacim/grafik verisiyle ve mevcut pre-open Matriks snapshot ile uretilir; gercek emir gondermez.",
        "",
    ]
    tickers: list[str] = []
    if not scan.items:
        lines.append("Bugun pre-market esik ustu izleme adayi bulunamadi.")
        return "\n".join(lines), tickers

    for index, item in enumerate(scan.items, 1):
        tickers.append(item.ticker)
        top_reason = item.reasons[0] if item.reasons else "Ek sinyal yok"
        top_risk = item.risks[0] if item.risks else "Belirgin ek risk yok"
        trigger_text = f"{item.trigger_price}" if item.trigger_price is not None else "-"
        invalidation_text = f"{item.invalidation_price}" if item.invalidation_price is not None else "-"
        technical_text = humanize_label(item.technical_bias) if item.technical_bias else "-"
        lines.append(f"{index}. {item.ticker} | skor {round(item.pre_market_score, 2)} | kurgu {humanize_label(item.setup_type)}")
        lines.append(
            f"   kapanis {item.previous_close} | degisim %{item.previous_change_percent} | kapanis gucu {item.close_position_percent} | hacim {item.volume_ratio}x"
        )
        lines.append(
            f"   tetik {trigger_text} | zayiflama {invalidation_text} | teknik {technical_text}"
        )
        lines.append(f"   neden: {top_reason}")
        lines.append(f"   risk: {top_risk}")
    return "\n".join(lines), tickers


def _build_intraday_telegram_message(slot: str, limit: int) -> tuple[str, list[str]]:
    scan = scan_intraday_upside_candidates(limit=limit)
    now_local = datetime.now(ISTANBUL_TZ)
    lines = [
        f"BIST agent canli momentum listesi - {now_local.date().isoformat()} {slot}",
        f"Canli pozitif sayisi: {scan.positive_count}/{scan.universe_size}",
        "",
        "Not: Bu liste acilis sonrasi canli fiyat, hacim hizi, spread ve tavan/no-fill kontroluyle uretilir; gercek emir gondermez.",
        "",
    ]
    tickers: list[str] = []
    if not scan.items:
        lines.append("Su an canli momentum filtresini gecen aday bulunamadi.")
        return "\n".join(lines), tickers

    for index, item in enumerate(scan.items, 1):
        tickers.append(item.ticker)
        action = humanize_label(item.execution_action)
        scenario = humanize_label(item.scenario)
        risk_text = f" | risk: {item.risks[0]}" if item.risks else ""
        lines.append(
            f"{index}. {item.ticker} | skor {round(item.upside_score, 2)} | "
            f"son {item.last_price} | degisim %{item.change_percent} | "
            f"tavana kalan %{item.distance_to_limit_percent} | hacim hizi {item.expected_volume_ratio}x | "
            f"karar {action} | kurgu {scenario}{risk_text}"
        )
    return "\n".join(lines), tickers


def send_morning_opening_telegram(force: bool = False) -> TradingAgentMorningTelegramResponse:
    now_local = datetime.now(ISTANBUL_TZ)
    if not settings.telegram_bot_token:
        return TradingAgentMorningTelegramResponse(
            generated_at=datetime.utcnow().isoformat(),
            status="skipped",
            reason="Telegram bot token bos.",
            chat_id_configured=bool(settings.telegram_chat_id),
            candidate_count=0,
            tickers=[],
            calendar_warning=None,
        )
    if not settings.telegram_chat_id:
        return TradingAgentMorningTelegramResponse(
            generated_at=datetime.utcnow().isoformat(),
            status="skipped",
            reason="Telegram chat id bos.",
            chat_id_configured=False,
            candidate_count=0,
            tickers=[],
            calendar_warning=None,
        )
    calendar_check = check_bist_trading_day(now_local)
    if not force and not calendar_check.is_trading_day:
        return TradingAgentMorningTelegramResponse(
            generated_at=datetime.utcnow().isoformat(),
            status="skipped",
            reason=f"not_bist_trading_day:{calendar_check.reason}",
            chat_id_configured=bool(settings.telegram_chat_id),
            candidate_count=0,
            tickers=[],
            calendar_warning=calendar_check.calendar_warning,
        )

    message, tickers = _build_morning_telegram_message(limit=max(settings.agent_morning_telegram_limit, 1))
    if calendar_check.calendar_warning:
        message += f"\n\nTakvim uyarisi: {calendar_check.calendar_warning}"
    sent, reason = send_telegram_message(message)
    return TradingAgentMorningTelegramResponse(
        generated_at=datetime.utcnow().isoformat(),
        status="sent" if sent else "skipped",
        reason=reason,
        chat_id_configured=bool(settings.telegram_chat_id),
        candidate_count=len(tickers),
        tickers=tickers,
        calendar_warning=calendar_check.calendar_warning,
    )


def send_intraday_momentum_telegram(slot: str, force: bool = False) -> TradingAgentMorningTelegramResponse:
    now_local = datetime.now(ISTANBUL_TZ)
    if not settings.telegram_bot_token:
        return TradingAgentMorningTelegramResponse(
            generated_at=datetime.utcnow().isoformat(),
            status="skipped",
            reason="Telegram bot token bos.",
            chat_id_configured=bool(settings.telegram_chat_id),
            candidate_count=0,
            tickers=[],
            calendar_warning=None,
        )
    if not settings.telegram_chat_id:
        return TradingAgentMorningTelegramResponse(
            generated_at=datetime.utcnow().isoformat(),
            status="skipped",
            reason="Telegram chat id bos.",
            chat_id_configured=False,
            candidate_count=0,
            tickers=[],
            calendar_warning=None,
        )
    calendar_check = check_bist_trading_day(now_local)
    if not force and not calendar_check.is_trading_day:
        return TradingAgentMorningTelegramResponse(
            generated_at=datetime.utcnow().isoformat(),
            status="skipped",
            reason=f"not_bist_trading_day:{calendar_check.reason}",
            chat_id_configured=bool(settings.telegram_chat_id),
            candidate_count=0,
            tickers=[],
            calendar_warning=calendar_check.calendar_warning,
        )

    message, tickers = _build_intraday_telegram_message(slot=slot, limit=max(settings.agent_intraday_telegram_limit, 1))
    if calendar_check.calendar_warning:
        message += f"\n\nTakvim uyarisi: {calendar_check.calendar_warning}"
    sent, reason = send_telegram_message(message)
    return TradingAgentMorningTelegramResponse(
        generated_at=datetime.utcnow().isoformat(),
        status="sent" if sent else "skipped",
        reason=reason,
        chat_id_configured=bool(settings.telegram_chat_id),
        candidate_count=len(tickers),
        tickers=tickers,
        calendar_warning=calendar_check.calendar_warning,
    )
