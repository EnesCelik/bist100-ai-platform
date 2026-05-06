from fastapi import APIRouter, HTTPException, Query
from sqlalchemy.exc import SQLAlchemyError

from app.models.schemas import (
    GlobalEventSourceCatalogResponse,
    IngestGlobalEventRequest,
    IngestGlobalEventResponse,
    IngestMacroEventBulkRequest,
    IngestMacroEventBulkResponse,
    IngestMacroEventRequest,
    IngestMacroEventResponse,
    MacroEventCleanupResponse,
    PreviewGlobalEventRequest,
    PreviewGlobalEventResponse,
    MacroEventHistoryResponse,
    MacroEventMigrationResponse,
    MacroEventResponse,
)
from app.services.macro_event_cleanup_service import cleanup_legacy_macro_events
from app.services.global_event_service import get_global_event_source_catalog, ingest_global_event, preview_global_event, repair_global_event
from app.services.macro_event_ingest_service import ingest_macro_event, ingest_macro_event_bulk
from app.services.macro_event_service import (
    get_macro_event_history,
    get_macro_event_summary,
    migrate_json_macro_events_to_db,
)


router = APIRouter(tags=["macro-events"])


@router.get("/macro-events/{ticker}", response_model=MacroEventResponse)
def get_macro_event(ticker: str) -> MacroEventResponse:
    macro_event = get_macro_event_summary(ticker)
    if macro_event is None:
        raise HTTPException(status_code=404, detail=f"Macro event bulunamadi: {ticker.upper()}")
    return macro_event


@router.get("/macro-events/history/{ticker}", response_model=MacroEventHistoryResponse)
def get_macro_event_history_route(
    ticker: str,
    limit: int = Query(default=10, ge=1, le=50),
    category: str | None = Query(default=None),
) -> MacroEventHistoryResponse:
    history = get_macro_event_history(ticker, limit=limit, category=category)
    if history.total == 0:
        raise HTTPException(status_code=404, detail=f"Macro event history bulunamadi: {ticker.upper()}")
    return history


@router.post("/macro-events/migrate/from-json", response_model=MacroEventMigrationResponse)
def migrate_macro_events_from_json() -> MacroEventMigrationResponse:
    try:
        return migrate_json_macro_events_to_db()
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=500, detail="Macro event JSON to DB migration failed") from exc


@router.post("/ingest/macro-events", response_model=IngestMacroEventResponse)
def create_macro_event(payload: IngestMacroEventRequest) -> IngestMacroEventResponse:
    return ingest_macro_event(payload)


@router.post("/ingest/macro-events/bulk", response_model=IngestMacroEventBulkResponse)
def create_macro_event_bulk(payload: IngestMacroEventBulkRequest) -> IngestMacroEventBulkResponse:
    return ingest_macro_event_bulk(payload)


@router.post("/macro-events/cleanup/legacy", response_model=MacroEventCleanupResponse)
def cleanup_legacy_macro_events_route() -> MacroEventCleanupResponse:
    return cleanup_legacy_macro_events()


@router.get("/global-events/sources", response_model=GlobalEventSourceCatalogResponse)
def list_global_event_sources() -> GlobalEventSourceCatalogResponse:
    return get_global_event_source_catalog()


@router.post("/global-events/preview", response_model=PreviewGlobalEventResponse)
def preview_global_event_route(payload: PreviewGlobalEventRequest) -> PreviewGlobalEventResponse:
    return preview_global_event(payload)


@router.post("/ingest/global-events", response_model=IngestGlobalEventResponse)
def create_global_event(payload: IngestGlobalEventRequest) -> IngestGlobalEventResponse:
    return ingest_global_event(payload)


@router.post("/ingest/global-events/repair", response_model=IngestGlobalEventResponse)
def repair_global_event_route(payload: IngestGlobalEventRequest) -> IngestGlobalEventResponse:
    return repair_global_event(payload)
