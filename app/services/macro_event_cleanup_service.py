import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.db.models import MacroEventRecord
from app.db.session import SessionLocal
from app.models.schemas import MacroEventCleanupResponse


DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "macro_events"
INDEX_FILE = DATA_DIR / "index.json"
LEGACY_POSITIVE = "Bolgesel guvenlik gundemi savunma talebini destekleyebilir"
NORMALIZED_POSITIVE = "Kuresel guvenlik gundemi risk algisini degistirebilir"


def _load_events() -> list[dict]:
    if not INDEX_FILE.exists():
        return []

    with INDEX_FILE.open("r", encoding="utf-8") as file:
        return json.load(file)


def _save_events(events: list[dict]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with INDEX_FILE.open("w", encoding="utf-8") as file:
        json.dump(events, file, indent=2, ensure_ascii=False)


def _needs_cleanup(event: dict) -> bool:
    return (
        event.get("latest_macro_event") == "Hurmuz Bogazi gerilimi ve petrol lojistigi riski"
        and event.get("event_category") == "geopolitics"
        and event.get("region") == "middle_east"
        and event.get("published_at") == "2026-04-17"
        and LEGACY_POSITIVE in event.get("positive_impacts", [])
    )


def cleanup_legacy_macro_events() -> MacroEventCleanupResponse:
    try:
        updated_count = 0
        with SessionLocal() as session:
            rows = session.execute(select(MacroEventRecord)).scalars().all()
            for row in rows:
                event = {
                    "latest_macro_event": row.latest_macro_event,
                    "event_category": row.event_category,
                    "region": row.region,
                    "published_at": row.published_at,
                    "positive_impacts": row.positive_impacts,
                }
                if _needs_cleanup(event):
                    row.positive_impacts = [
                        NORMALIZED_POSITIVE if item == LEGACY_POSITIVE else item
                        for item in row.positive_impacts
                    ]
                    updated_count += 1
            if updated_count > 0:
                session.commit()
        return MacroEventCleanupResponse(
            updated_count=updated_count,
            status="cleaned" if updated_count > 0 else "no_changes",
        )
    except SQLAlchemyError:
        events = _load_events()
        updated_count = 0

        for event in events:
            if _needs_cleanup(event):
                event["positive_impacts"] = [
                    NORMALIZED_POSITIVE if item == LEGACY_POSITIVE else item
                    for item in event.get("positive_impacts", [])
                ]
                updated_count += 1

        if updated_count > 0:
            _save_events(events)

        return MacroEventCleanupResponse(
            updated_count=updated_count,
            status="cleaned" if updated_count > 0 else "no_changes",
        )
