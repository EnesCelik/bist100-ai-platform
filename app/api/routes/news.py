from fastapi import APIRouter, HTTPException, Query
from sqlalchemy.exc import SQLAlchemyError

from app.models.schemas import (
    ConvertNewsToMacroRequest,
    ConvertNewsToMacroResponse,
    IngestNewsRequest,
    IngestNewsResponse,
    NewsCleanupResponse,
    NewsHistoryResponse,
    NewsMigrationResponse,
)
from app.services.news_service import (
    cleanup_duplicate_news,
    get_news_history,
    ingest_news,
    migrate_json_news_to_db,
)
from app.services.news_to_macro_service import convert_news_to_macro_event


router = APIRouter(tags=["news"])


@router.post("/ingest/news", response_model=IngestNewsResponse)
def create_news(payload: IngestNewsRequest) -> IngestNewsResponse:
    return ingest_news(payload)


@router.post("/news/migrate/from-json", response_model=NewsMigrationResponse)
def migrate_news_from_json() -> NewsMigrationResponse:
    try:
        return migrate_json_news_to_db()
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=500, detail="News JSON to DB migration failed") from exc


@router.post("/news/cleanup/duplicates", response_model=NewsCleanupResponse)
def cleanup_news_duplicates() -> NewsCleanupResponse:
    return cleanup_duplicate_news()


@router.post("/news/convert-to-macro", response_model=ConvertNewsToMacroResponse)
def convert_news(payload: ConvertNewsToMacroRequest) -> ConvertNewsToMacroResponse:
    try:
        return convert_news_to_macro_event(payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/news/history/{ticker}", response_model=NewsHistoryResponse)
def get_news_history_route(
    ticker: str,
    limit: int = Query(default=10, ge=1, le=50),
    tag: str | None = Query(default=None),
) -> NewsHistoryResponse:
    history = get_news_history(ticker, limit=limit, tag=tag)
    if history.total == 0:
        raise HTTPException(status_code=404, detail=f"News history bulunamadi: {ticker.upper()}")
    return history
