import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.data_sources.company_data.provider import get_company_record
from app.db.models import MacroEventRecord
from app.db.session import SessionLocal
from app.models.schemas import (
    MacroEventHistoryItem,
    MacroEventHistoryResponse,
    MacroEventMigrationResponse,
    MacroEventResponse,
)
from app.services.macro_rule_mapping import derive_impacts


DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "macro_events"
INDEX_FILE = DATA_DIR / "index.json"
DB_SOURCE = "postgres_macro_event_store"
JSON_SOURCE = "json_macro_event_store"


def _load_macro_events_json() -> list[dict]:
    if not INDEX_FILE.exists():
        return []

    with INDEX_FILE.open("r", encoding="utf-8") as file:
        return json.load(file)


def _save_macro_events_json(items: list[dict]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with INDEX_FILE.open("w", encoding="utf-8") as file:
        json.dump(items, file, indent=2, ensure_ascii=False)


def _serialize_macro_row(row: MacroEventRecord) -> dict:
    return {
        "ticker": row.ticker,
        "latest_macro_event": row.latest_macro_event,
        "event_category": row.event_category,
        "region": row.region,
        "published_at": row.published_at,
        "positive_impacts": row.positive_impacts,
        "negative_impacts": row.negative_impacts,
        "source": row.source,
    }


def _macro_key(item: dict) -> tuple[str, str, str]:
    return (
        item.get("ticker", "").upper(),
        item.get("latest_macro_event", "").strip(),
        item.get("published_at", "").strip(),
    )


def _find_existing_db_macro_event(session, item: dict) -> MacroEventRecord | None:
    statement = select(MacroEventRecord).where(
        MacroEventRecord.ticker == item["ticker"],
        MacroEventRecord.latest_macro_event == item["latest_macro_event"],
        MacroEventRecord.published_at == item["published_at"],
    )
    return session.execute(statement).scalar_one_or_none()


def _load_macro_events() -> list[dict]:
    try:
        with SessionLocal() as session:
            rows = session.execute(select(MacroEventRecord)).scalars().all()
            return [_serialize_macro_row(row) for row in rows]
    except SQLAlchemyError:
        return _load_macro_events_json()


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            ordered.append(item)
    return ordered


def _build_macro_event_record(raw_event: dict) -> MacroEventHistoryItem:
    normalized_ticker = raw_event["ticker"].upper()
    company = get_company_record(normalized_ticker)
    sector = company.sector if company is not None else None
    derived_positive, derived_negative = derive_impacts(
        normalized_ticker,
        sector,
        raw_event.get("event_category"),
        raw_event.get("region"),
    )

    positive_impacts = _dedupe(raw_event.get("positive_impacts", []) + derived_positive)
    negative_impacts = _dedupe(raw_event.get("negative_impacts", []) + derived_negative)

    return MacroEventHistoryItem(
        ticker=normalized_ticker,
        latest_macro_event=raw_event["latest_macro_event"],
        event_category=raw_event.get("event_category", "unknown"),
        region=raw_event.get("region", "unknown"),
        published_at=raw_event.get("published_at", ""),
        positive_impacts=positive_impacts,
        negative_impacts=negative_impacts,
        source=raw_event.get("source", JSON_SOURCE),
    )


def get_macro_event_summary(ticker: str) -> MacroEventResponse | None:
    history = get_macro_event_history(ticker, limit=1)
    if history.total == 0:
        return None

    latest = history.items[0]
    return MacroEventResponse(
        ticker=latest.ticker,
        latest_macro_event=latest.latest_macro_event,
        positive_impacts=latest.positive_impacts,
        negative_impacts=latest.negative_impacts,
        source=latest.source,
    )


def get_macro_event_history(
    ticker: str,
    limit: int = 10,
    category: str | None = None,
) -> MacroEventHistoryResponse:
    normalized_ticker = ticker.upper()
    normalized_category = category.lower() if category is not None else None

    matching_events = [
        item
        for item in _load_macro_events()
        if item.get("ticker", "").upper() == normalized_ticker
        and (normalized_category is None or item.get("event_category", "").lower() == normalized_category)
    ]

    deduped_by_key: dict[tuple[str, str, str], dict] = {}
    for item in matching_events:
        deduped_by_key[_macro_key(item)] = item

    sorted_events = sorted(
        deduped_by_key.values(),
        key=lambda item: (item.get("published_at", ""), item.get("latest_macro_event", "")),
        reverse=True,
    )

    limited_events = sorted_events[: max(limit, 1)]
    history_items = [_build_macro_event_record(event) for event in limited_events]

    return MacroEventHistoryResponse(
        ticker=normalized_ticker,
        total=len(history_items),
        items=history_items,
    )


def migrate_json_macro_events_to_db() -> MacroEventMigrationResponse:
    json_items = _load_macro_events_json()
    if not json_items:
        return MacroEventMigrationResponse(total_json_records=0, migrated_count=0, skipped_count=0, status="no_changes")

    migrated_count = 0
    skipped_count = 0

    with SessionLocal() as session:
        for item in json_items:
            normalized_item = {
                "ticker": item.get("ticker", "").upper(),
                "latest_macro_event": item.get("latest_macro_event", ""),
                "event_category": item.get("event_category", "unknown"),
                "region": item.get("region", "unknown"),
                "published_at": item.get("published_at", ""),
                "positive_impacts": item.get("positive_impacts", []),
                "negative_impacts": item.get("negative_impacts", []),
                "source": item.get("source", JSON_SOURCE),
            }
            existing = _find_existing_db_macro_event(session, normalized_item)
            if existing is not None:
                skipped_count += 1
                continue

            session.add(
                MacroEventRecord(
                    ticker=normalized_item["ticker"],
                    latest_macro_event=normalized_item["latest_macro_event"],
                    event_category=normalized_item["event_category"],
                    region=normalized_item["region"],
                    published_at=normalized_item["published_at"],
                    positive_impacts=normalized_item["positive_impacts"],
                    negative_impacts=normalized_item["negative_impacts"],
                    source=normalized_item["source"],
                )
            )
            migrated_count += 1

        if migrated_count > 0:
            session.commit()

    return MacroEventMigrationResponse(
        total_json_records=len(json_items),
        migrated_count=migrated_count,
        skipped_count=skipped_count,
        status="migrated" if migrated_count > 0 else "no_changes",
    )
