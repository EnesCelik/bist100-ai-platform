import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.core.config import settings


def send_telegram_message(text: str) -> tuple[bool, str]:
    if not settings.telegram_bot_token:
        return False, "Telegram bot token bos."
    if not settings.telegram_chat_id:
        return False, "Telegram chat id bos."

    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    payload = urlencode(
        {
            "chat_id": settings.telegram_chat_id,
            "text": text,
            "disable_web_page_preview": "true",
        }
    ).encode("utf-8")
    request = Request(url, data=payload, method="POST")
    try:
        with urlopen(request, timeout=8) as response:
            body = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        return False, str(exc)
    if not body.get("ok"):
        return False, str(body)
    return True, "Gonderildi."


def get_telegram_updates() -> dict:
    if not settings.telegram_bot_token:
        return {"ok": False, "description": "Telegram bot token bos."}
    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/getUpdates"
    try:
        with urlopen(url, timeout=8) as response:
            return json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        return {"ok": False, "description": str(exc)}
