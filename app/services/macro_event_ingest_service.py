import json
from pathlib import Path

from sqlalchemy.exc import SQLAlchemyError

from app.db.models import MacroEventRecord
from app.db.session import SessionLocal
from app.models.schemas import (
    IngestMacroEventBulkRequest,
    IngestMacroEventBulkResponse,
    IngestMacroEventRequest,
    IngestMacroEventResponse,
)
from app.services.macro_event_service import _find_existing_db_macro_event, _macro_key


DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "macro_events"
INDEX_FILE = DATA_DIR / "index.json"
DB_SOURCE = "postgres_macro_event_store"
JSON_SOURCE = "json_macro_event_store"


def _load_events() -> list[dict]:
    if not INDEX_FILE.exists():
        return []

    with INDEX_FILE.open("r", encoding="utf-8") as file:
        return json.load(file)


def _save_events(events: list[dict]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with INDEX_FILE.open("w", encoding="utf-8") as file:
        json.dump(events, file, indent=2, ensure_ascii=False)


def _build_event_record(ticker: str, payload: IngestMacroEventRequest, source: str) -> dict:
    return {
        "ticker": ticker.upper(),
        "latest_macro_event": payload.latest_macro_event,
        "positive_impacts": payload.positive_impacts,
        "negative_impacts": payload.negative_impacts,
        "event_category": payload.event_category,
        "region": payload.region,
        "published_at": payload.published_at,
        "source": source,
    }


def _build_bulk_event_record(ticker: str, payload: IngestMacroEventBulkRequest, source: str) -> dict:
    return {
        "ticker": ticker.upper(),
        "latest_macro_event": payload.latest_macro_event,
        "positive_impacts": payload.base_positive_impacts,
        "negative_impacts": payload.base_negative_impacts,
        "event_category": payload.event_category,
        "region": payload.region,
        "published_at": payload.published_at,
        "source": source,
    }


def replace_macro_event(payload: IngestMacroEventRequest) -> IngestMacroEventResponse:
    new_event = _build_event_record(payload.ticker, payload, DB_SOURCE)
    try:
        with SessionLocal() as session:
            existing_rows = session.query(MacroEventRecord).filter(
                MacroEventRecord.ticker == new_event["ticker"],
                MacroEventRecord.latest_macro_event == new_event["latest_macro_event"],
                MacroEventRecord.published_at == new_event["published_at"],
            ).all()
            for row in existing_rows:
                session.delete(row)
            session.add(
                MacroEventRecord(
                    ticker=new_event["ticker"],
                    latest_macro_event=new_event["latest_macro_event"],
                    event_category=new_event["event_category"],
                    region=new_event["region"],
                    published_at=new_event["published_at"],
                    positive_impacts=new_event["positive_impacts"],
                    negative_impacts=new_event["negative_impacts"],
                    source=new_event["source"],
                )
            )
            session.commit()
    except SQLAlchemyError:
        events = _load_events()
        fallback_event = _build_event_record(payload.ticker, payload, JSON_SOURCE)
        target_key = _macro_key(fallback_event)
        events = [item for item in events if _macro_key(item) != target_key]
        events.append(fallback_event)
        events.sort(key=lambda item: (item.get("ticker", ""), item.get("published_at", "")))
        _save_events(events)
        return IngestMacroEventResponse(
            ticker=fallback_event["ticker"],
            latest_macro_event=fallback_event["latest_macro_event"],
            published_at=fallback_event["published_at"],
            status="repaired",
        )

    return IngestMacroEventResponse(
        ticker=new_event["ticker"],
        latest_macro_event=new_event["latest_macro_event"],
        published_at=new_event["published_at"],
        status="repaired",
    )


def ingest_macro_event(payload: IngestMacroEventRequest) -> IngestMacroEventResponse:
    new_event = _build_event_record(payload.ticker, payload, DB_SOURCE)
    try:
        with SessionLocal() as session:
            existing = _find_existing_db_macro_event(session, new_event)
            if existing is not None:
                existing.event_category = new_event["event_category"]
                existing.region = new_event["region"]
                existing.positive_impacts = new_event["positive_impacts"]
                existing.negative_impacts = new_event["negative_impacts"]
                existing.source = new_event["source"]
                session.commit()
                return IngestMacroEventResponse(
                    ticker=new_event["ticker"],
                    latest_macro_event=new_event["latest_macro_event"],
                    published_at=new_event["published_at"],
                    status="updated",
                )

            session.add(
                MacroEventRecord(
                    ticker=new_event["ticker"],
                    latest_macro_event=new_event["latest_macro_event"],
                    event_category=new_event["event_category"],
                    region=new_event["region"],
                    published_at=new_event["published_at"],
                    positive_impacts=new_event["positive_impacts"],
                    negative_impacts=new_event["negative_impacts"],
                    source=new_event["source"],
                )
            )
            session.commit()
    except SQLAlchemyError:
        events = _load_events()
        fallback_event = _build_event_record(payload.ticker, payload, JSON_SOURCE)
        target_key = _macro_key(fallback_event)
        replaced = False
        for index, current in enumerate(events):
            if _macro_key(current) != target_key:
                continue
            events[index] = fallback_event
            replaced = True
            break
        if not replaced:
            events.append(fallback_event)
        events.sort(key=lambda item: (item.get("ticker", ""), item.get("published_at", "")))
        _save_events(events)
        return IngestMacroEventResponse(
            ticker=fallback_event["ticker"],
            latest_macro_event=fallback_event["latest_macro_event"],
            published_at=fallback_event["published_at"],
            status="updated" if replaced else "saved",
        )

    return IngestMacroEventResponse(
        ticker=new_event["ticker"],
        latest_macro_event=new_event["latest_macro_event"],
        published_at=new_event["published_at"],
        status="saved",
    )


def ingest_macro_event_bulk(payload: IngestMacroEventBulkRequest) -> IngestMacroEventBulkResponse:
    saved_tickers: list[str] = []
    updated_any = False
    try:
        with SessionLocal() as session:
            for ticker in payload.tickers:
                new_event = _build_bulk_event_record(ticker, payload, DB_SOURCE)
                existing = _find_existing_db_macro_event(session, new_event)
                if existing is not None:
                    existing.event_category = new_event["event_category"]
                    existing.region = new_event["region"]
                    existing.positive_impacts = new_event["positive_impacts"]
                    existing.negative_impacts = new_event["negative_impacts"]
                    existing.source = new_event["source"]
                    updated_any = True
                    saved_tickers.append(new_event["ticker"])
                    continue
                session.add(
                    MacroEventRecord(
                        ticker=new_event["ticker"],
                        latest_macro_event=new_event["latest_macro_event"],
                        event_category=new_event["event_category"],
                        region=new_event["region"],
                        published_at=new_event["published_at"],
                        positive_impacts=new_event["positive_impacts"],
                        negative_impacts=new_event["negative_impacts"],
                        source=new_event["source"],
                    )
                )
                saved_tickers.append(new_event["ticker"])
            session.commit()
    except SQLAlchemyError:
        events = _load_events()
        updated_in_json = False
        for ticker in payload.tickers:
            new_event = _build_bulk_event_record(ticker, payload, JSON_SOURCE)
            target_key = _macro_key(new_event)
            replaced = False
            for index, current in enumerate(events):
                if _macro_key(current) != target_key:
                    continue
                events[index] = new_event
                replaced = True
                updated_in_json = True
                break
            if not replaced:
                events.append(new_event)
            saved_tickers.append(new_event["ticker"])
        events.sort(key=lambda item: (item.get("ticker", ""), item.get("published_at", "")))
        _save_events(events)
        return IngestMacroEventBulkResponse(
            tickers=saved_tickers,
            latest_macro_event=payload.latest_macro_event,
            published_at=payload.published_at,
            status="updated" if updated_in_json else "saved",
        )

    return IngestMacroEventBulkResponse(
        tickers=saved_tickers,
        latest_macro_event=payload.latest_macro_event,
        published_at=payload.published_at,
        status="updated" if updated_any else "saved",
    )
