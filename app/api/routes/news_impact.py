from fastapi import APIRouter, Query

from app.models.schemas import NewsImpactResponse
from app.services.news_impact_service import fetch_news_impact


router = APIRouter(tags=["news-impact"])


@router.get("/news-impact/{ticker}", response_model=NewsImpactResponse)
def get_news_impact_for_ticker(
    ticker: str,
    limit: int = Query(default=10, ge=1, le=20),
    days: int = Query(default=7, ge=1, le=30),
) -> NewsImpactResponse:
    return fetch_news_impact(ticker, limit=limit, days=days)
