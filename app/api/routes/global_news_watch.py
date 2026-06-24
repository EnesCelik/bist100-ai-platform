from fastapi import APIRouter, Query

from app.services.global_news_watch_service import GlobalNewsWatchResponse, run_global_news_watch


router = APIRouter(tags=["global-news-watch"])


@router.post("/global-news/watch/run", response_model=GlobalNewsWatchResponse)
def run_global_news_watch_route(
    limit: int = Query(default=20, ge=1, le=50),
    ingest: bool = Query(default=False),
) -> GlobalNewsWatchResponse:
    return run_global_news_watch(limit=limit, ingest=ingest)
