import json
import logging
from datetime import date
from urllib import error, request

from app.core.config import settings

logger = logging.getLogger(__name__)

# TCMB Agirlikli Ortalama Fonlama Maliyeti - ilan edilen "1 hafta repo" faizinden
# daha guvenilir bir efektif politika faizi proxy'si, cunku TCMB fonlamanin
# tamamini ayni orandan saglamiyor.
POLICY_FUNDING_RATE_SERIES = "TP.APIFON4"
USDTRY_BUYING_RATE_SERIES = "TP.DK.USD.A.YTL"
# TUFE Genel Endeks (2003=100) - aylik seri. Canli olarak dogrulandi (2026-09):
# EVDS gercek veri donduruyor, YoY hesabi icin index/index_12ay_once orani kullanilir.
CPI_INDEX_SERIES = "TP.FG.J0"


def _parse_evds_date(raw_date: str) -> date | None:
    parts = raw_date.split("-")
    try:
        if len(parts) == 3:
            # Gunluk seri: "GG-AA-YYYY"
            day, month, year = (int(part) for part in parts)
            return date(year, month, day)
        if len(parts) == 2:
            # Aylik seri: "YYYY-A" (ay sifirla doldurulmamis olabilir)
            year, month = (int(part) for part in parts)
            return date(year, month, 1)
    except (TypeError, ValueError):
        return None
    return None


def fetch_series(series_code: str, start: date, end: date) -> list[tuple[date, float]]:
    query = f"series={series_code}&startDate={start.strftime('%d-%m-%Y')}&endDate={end.strftime('%d-%m-%Y')}&type=json"
    url = f"{settings.tcmb_evds_base_url.rstrip('/')}/{query}"
    req = request.Request(url, headers={"key": settings.tcmb_evds_api_key})
    try:
        with request.urlopen(req, timeout=settings.tcmb_evds_timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        logger.warning("TCMB EVDS request for %s failed: HTTP %s - %s", series_code, exc.code, exc.read().decode("utf-8", "ignore"))
        return []
    except (error.URLError, TimeoutError, ValueError) as exc:
        logger.warning("TCMB EVDS request for %s failed: %s", series_code, exc)
        return []

    value_key = series_code.replace(".", "_")
    points: list[tuple[date, float]] = []
    for item in payload.get("items", []):
        raw_value = item.get(value_key)
        raw_date = item.get("Tarih")
        if raw_value in (None, "") or not raw_date:
            continue
        parsed_date = _parse_evds_date(raw_date)
        if parsed_date is None:
            continue
        try:
            points.append((parsed_date, float(raw_value)))
        except (TypeError, ValueError):
            continue

    return sorted(points, key=lambda point: point[0])
