import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.core.config import settings


def send_telegram_message(text: str) -> tuple[bool, str]:
    if not settings.telegram_bot_token:
        return False, "telegram_bot_token is empty"
    if not settings.telegram_chat_id:
        return False, "telegram_chat_id is empty"

    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    payload = urlencode(
        {
            "chat_id": settings.telegram_chat_id,
            "text": text,
            "disable_web_page_preview": "true",
        }
    ).encode("utf-8")
    request = Request(url, data=payload, method="POST")
    with urlopen(request, timeout=20) as response:
        body = json.loads(response.read().decode("utf-8"))
    if not body.get("ok"):
        return False, str(body)
    return True, "sent"


def get_telegram_updates() -> dict:
    if not settings.telegram_bot_token:
        return {"ok": False, "description": "telegram_bot_token is empty"}
    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/getUpdates"
    with urlopen(url, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))
