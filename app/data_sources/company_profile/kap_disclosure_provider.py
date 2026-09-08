import json
import logging
from datetime import datetime
from urllib import error, request

from app.core.config import settings

logger = logging.getLogger(__name__)

# KAP'in yeni (Next.js) sitesindeki zengin "disclosure/list/main" ucu, sirket ve
# tarih araligina gore filtreleme yapabiliyor ama bot korumasi arkasinda; dogru
# alan adlariyla denesek bile her zaman ayni jenerik "HTTP 400" hatasini donuyor.
# "disclosure/list/light" ucu ise kimlik dogrulama gerektirmiyor ve calisiyor,
# ama sadece piyasa genelindeki en son 20 bildirimi donuyor, ticker/sirket filtresi yok.
_LIGHT_DISCLOSURE_URL = "https://www.kap.org.tr/tr/api/disclosure/list/light"


def fetch_recent_disclosures() -> list[dict]:
    req = request.Request(
        _LIGHT_DISCLOSURE_URL,
        headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
    )
    try:
        with request.urlopen(req, timeout=settings.kap_timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (error.URLError, error.HTTPError, TimeoutError, ValueError) as exc:
        logger.warning("KAP disclosure light feed fetch failed: %s", exc)
        return []

    disclosures: list[dict] = []
    for item in payload:
        try:
            published_at = datetime.strptime(item["publishDate"], "%d.%m.%Y %H:%M:%S").date().isoformat()
        except (KeyError, ValueError):
            continue
        disclosures.append(
            {
                "company_title": item.get("title") or "",
                "subject": item.get("subject") or "",
                "summary": item.get("summary") or "",
                "published_at": published_at,
                "disclosure_index": item.get("disclosureIndex", 0),
            }
        )
    return disclosures
