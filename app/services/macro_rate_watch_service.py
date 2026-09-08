import json
from datetime import date, timedelta

from pydantic import BaseModel

from app.data_sources.company_data.provider import list_company_records
from app.data_sources.macro_data.tcmb_evds_provider import POLICY_FUNDING_RATE_SERIES, fetch_series
from app.models.schemas import IngestMacroEventBulkRequest
from app.services.macro_event_ingest_service import ingest_macro_event_bulk
from app.services.macro_event_service import DATA_DIR as MACRO_EVENTS_DIR

# TP.APIFON4 (agirlikli ortalama fonlama maliyeti) gunluk fonlama karisimina gore
# birkaç baz puan gurultuyle oynayabiliyor; gercek bir politika hareketini gurultuden
# ayirmak icin asgari 0.5 puanlik bir esik kullaniyoruz.
_SIGNIFICANT_CHANGE_THRESHOLD = 0.5

STATE_FILE = MACRO_EVENTS_DIR / "tcmb_rate_watch_state.json"
SOURCE = "tcmb_evds_policy_rate_watch"


class PolicyRateWatchResponse(BaseModel):
    status: str
    latest_value: float | None = None
    latest_date: str | None = None
    previous_value: float | None = None
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


def run_policy_rate_watch(ingest: bool = False) -> PolicyRateWatchResponse:
    series = fetch_series(POLICY_FUNDING_RATE_SERIES, start=date.today() - timedelta(days=120), end=date.today())
    if not series:
        return PolicyRateWatchResponse(status="no_data")

    latest_date, latest_value = series[-1]
    state = _load_state()
    previous_value = state.get("last_value")

    if previous_value is not None and abs(latest_value - previous_value) < _SIGNIFICANT_CHANGE_THRESHOLD:
        return PolicyRateWatchResponse(
            status="unchanged",
            latest_value=latest_value,
            latest_date=latest_date.isoformat(),
            previous_value=previous_value,
        )

    if previous_value is None:
        event_category = "rates"
        event_text = f"TCMB agirlikli ortalama fonlama maliyeti %{latest_value:.2f} seviyesinde (TCMB EVDS, {latest_date.isoformat()})."
    elif latest_value > previous_value:
        # "rates" kategorisindeki hazir sektor kurallari faiz artisini varsayarak
        # yazildigi icin sadece yukselis durumunda otomatik uyguluyoruz.
        event_category = "rates"
        event_text = (
            f"TCMB agirlikli ortalama fonlama maliyeti %{previous_value:.2f}'ten %{latest_value:.2f}'e yukseldi "
            f"(TCMB EVDS, {latest_date.isoformat()})."
        )
    else:
        # Faiz indirimi icin henuz sektor bazli kural seti yazilmadi; olayi
        # kaydediyoruz ama otomatik sektor yorumu uretmiyoruz (derive_impacts
        # taninmayan kategoride bos donuyor).
        event_category = "rate_cut"
        event_text = (
            f"TCMB agirlikli ortalama fonlama maliyeti %{previous_value:.2f}'ten %{latest_value:.2f}'e dustu "
            f"(TCMB EVDS, {latest_date.isoformat()})."
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
                    published_at=latest_date.isoformat(),
                )
            )
            tickers_applied = len(tracked_tickers)
        _save_state({"last_value": latest_value, "last_date": latest_date.isoformat()})

    return PolicyRateWatchResponse(
        status="event_detected",
        latest_value=latest_value,
        latest_date=latest_date.isoformat(),
        previous_value=previous_value,
        event_category=event_category,
        event_text=event_text,
        tickers_applied=tickers_applied,
    )
