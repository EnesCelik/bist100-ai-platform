from datetime import datetime
from zoneinfo import ZoneInfo

from app.core.config import settings
from app.models.schemas import TradingAgentMorningTelegramResponse
from app.services.market_calendar_service import check_bist_trading_day
from app.services.market_scan_service import scan_opening_candidates
from app.services.telegram_service import send_telegram_message

ISTANBUL_TZ = ZoneInfo("Europe/Istanbul")


def _build_morning_telegram_message(limit: int) -> tuple[str, list[str]]:
    scan = scan_opening_candidates(limit=limit)
    today = datetime.now(ISTANBUL_TZ).date().isoformat()
    lines = [
        f"BIST agent sabah listesi - {today}",
        f"Strict filtreyi gecen aday sayisi: {scan.total}/{scan.universe_size}",
        "",
        "Not: Bu liste paper-trade/izleme amaclidir; gercek emir gondermez.",
        "",
    ]
    tickers: list[str] = []
    if not scan.items:
        lines.append("Bugun esik ustu acilis adayi bulunamadi.")
        return "\n".join(lines), tickers

    for index, item in enumerate(scan.items, 1):
        tickers.append(item.ticker)
        lines.append(
            f"{index}. {item.ticker} | skor {round(item.opening_score, 2)} | "
            f"son {item.last_price} | degisim %{item.change_percent} | "
            f"closing strength {item.closing_strength_proxy}"
        )
    return "\n".join(lines), tickers


def send_morning_opening_telegram(force: bool = False) -> TradingAgentMorningTelegramResponse:
    now_local = datetime.now(ISTANBUL_TZ)
    if not settings.telegram_bot_token:
        return TradingAgentMorningTelegramResponse(
            generated_at=datetime.utcnow().isoformat(),
            status="skipped",
            reason="telegram_bot_token is empty",
            chat_id_configured=bool(settings.telegram_chat_id),
            candidate_count=0,
            tickers=[],
            calendar_warning=None,
        )
    if not settings.telegram_chat_id:
        return TradingAgentMorningTelegramResponse(
            generated_at=datetime.utcnow().isoformat(),
            status="skipped",
            reason="telegram_chat_id is empty",
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
