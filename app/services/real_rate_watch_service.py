"""TCMB politika faizi ile TUFE YoY farkindan reel faizi izler.

Reel faiz = politika faizi (agirlikli ortalama fonlama maliyeti) - TUFE yillik
degisim. Nominal faiz sabit kalsa bile enflasyon yon degistirdiginde reel faiz
degisir - bu da hisse senedi degerlemeleri icin salt nominal faizden daha
anlamli bir gostergedir (dusen/negatif reel faiz risk istahini destekler,
yukselen reel faiz sikilastirma etkisi yapar).

Kategori mantigi mevcut "rates"/"rate_cut" sektor kurallarini (macro_rule_mapping.py)
yeniden kullanir: reel faiz yukselisi -> "rates" (sikilastirma), reel faiz
dususu -> "rate_cut" (gevseme). Boylece yeni sektor kurali yazmaya gerek kalmadi.
"""
from __future__ import annotations

import json
from datetime import date, timedelta

from pydantic import BaseModel

from app.data_sources.company_data.provider import list_company_records
from app.data_sources.macro_data.tcmb_evds_provider import (
    CPI_INDEX_SERIES,
    POLICY_FUNDING_RATE_SERIES,
    fetch_series,
)
from app.models.schemas import IngestMacroEventBulkRequest
from app.services.macro_event_ingest_service import ingest_macro_event_bulk
from app.services.macro_event_service import DATA_DIR as MACRO_EVENTS_DIR

_SIGNIFICANT_CHANGE_THRESHOLD = 0.5  # puan
_YOY_TOLERANCE_DAYS = 45  # 12 ay onceki nokta bu toleransin disindaysa YoY guvenilmez sayilir

STATE_FILE = MACRO_EVENTS_DIR / "tcmb_real_rate_watch_state.json"
SOURCE = "tcmb_evds_real_rate_watch"


class RealRateWatchResponse(BaseModel):
    status: str
    policy_rate: float | None = None
    cpi_yoy_percent: float | None = None
    real_rate: float | None = None
    latest_date: str | None = None
    previous_real_rate: float | None = None
    event_category: str | None = None
    event_text: str | None = None
    tickers_applied: int = 0


def _load_state() -> dict:
    if not STATE_FILE.exists():
        return {}
    return json.loads(STATE_FILE.read_text(encoding="utf-8"))


def _save_state(state: dict) -> None:
    MACRO_EVENTS_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def _compute_cpi_yoy() -> tuple[date, float] | None:
    series = fetch_series(CPI_INDEX_SERIES, start=date.today() - timedelta(days=760), end=date.today())
    if len(series) < 2:
        return None
    latest_date, latest_index = series[-1]
    target_date = latest_date.replace(year=latest_date.year - 1)
    year_ago_date, year_ago_index = min(series[:-1], key=lambda point: abs((point[0] - target_date).days))
    if abs((year_ago_date - target_date).days) > _YOY_TOLERANCE_DAYS:
        return None
    yoy_percent = (latest_index / year_ago_index - 1) * 100
    return latest_date, yoy_percent


def run_real_rate_watch(ingest: bool = False) -> RealRateWatchResponse:
    policy_series = fetch_series(POLICY_FUNDING_RATE_SERIES, start=date.today() - timedelta(days=30), end=date.today())
    if not policy_series:
        return RealRateWatchResponse(status="no_data")
    _, policy_rate = policy_series[-1]

    cpi_result = _compute_cpi_yoy()
    if cpi_result is None:
        return RealRateWatchResponse(status="no_data", policy_rate=policy_rate)
    latest_date, cpi_yoy = cpi_result

    real_rate = round(policy_rate - cpi_yoy, 2)
    state = _load_state()
    previous_real_rate = state.get("last_real_rate")

    if previous_real_rate is not None and abs(real_rate - previous_real_rate) < _SIGNIFICANT_CHANGE_THRESHOLD:
        return RealRateWatchResponse(
            status="unchanged",
            policy_rate=policy_rate,
            cpi_yoy_percent=round(cpi_yoy, 2),
            real_rate=real_rate,
            latest_date=latest_date.isoformat(),
            previous_real_rate=previous_real_rate,
        )

    if previous_real_rate is None:
        event_category = "rates" if real_rate > 0 else "rate_cut"
        event_text = (
            f"TCMB reel faizi %{real_rate:.2f} seviyesinde (politika faizi %{policy_rate:.2f}, "
            f"TUFE yillik %{cpi_yoy:.2f}, TCMB EVDS, {latest_date.isoformat()})."
        )
    elif real_rate > previous_real_rate:
        event_category = "rates"
        event_text = (
            f"TCMB reel faizi %{previous_real_rate:.2f}'ten %{real_rate:.2f}'e yukseldi "
            f"(politika faizi %{policy_rate:.2f}, TUFE yillik %{cpi_yoy:.2f}, TCMB EVDS, {latest_date.isoformat()})."
        )
    else:
        event_category = "rate_cut"
        event_text = (
            f"TCMB reel faizi %{previous_real_rate:.2f}'ten %{real_rate:.2f}'e dustu "
            f"(politika faizi %{policy_rate:.2f}, TUFE yillik %{cpi_yoy:.2f}, TCMB EVDS, {latest_date.isoformat()})."
        )

    tickers_applied = 0
    if ingest:
        tracked_tickers = [company.ticker for company in list_company_records()]
        if tracked_tickers:
            ingest_macro_event_bulk(
                IngestMacroEventBulkRequest(
                    tickers=tracked_tickers,
                    latest_macro_event=event_text,
                    base_positive_impacts=[],
                    base_negative_impacts=[],
                    event_category=event_category,
                    region="turkey",
                    # CPI verisi aylarca gecikmeli yayinlandigi icin latest_date'i
                    # (TUFE referans ayi) degil, bugunku tespit tarihini kullaniyoruz -
                    # aksi halde bu olay her zaman daha taze nominal faiz olaylarinin
                    # gerisinde kalir ve get_macro_event_summary'de "en son" olarak hic
                    # secilmez.
                    published_at=date.today().isoformat(),
                )
            )
            tickers_applied = len(tracked_tickers)
        _save_state({"last_real_rate": real_rate, "last_date": latest_date.isoformat()})

    return RealRateWatchResponse(
        status="event_detected",
        policy_rate=policy_rate,
        cpi_yoy_percent=round(cpi_yoy, 2),
        real_rate=real_rate,
        latest_date=latest_date.isoformat(),
        previous_real_rate=previous_real_rate,
        event_category=event_category,
        event_text=event_text,
        tickers_applied=tickers_applied,
    )
