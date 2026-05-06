from fastapi import HTTPException

from app.data_sources.news_impact.provider import get_news_impact
from app.models.schemas import NewsImpactResponse


def fetch_news_impact(ticker: str, limit: int = 10, days: int = 7) -> NewsImpactResponse:
    payload = get_news_impact(ticker, limit=limit, days=days)
    if payload is None:
        raise HTTPException(status_code=404, detail=f"News impact data for ticker '{ticker.upper()}' was not found or provider is not configured.")
    return payload



def fetch_optional_news_impact(ticker: str, limit: int = 10, days: int = 7) -> NewsImpactResponse | None:
    return get_news_impact(ticker, limit=limit, days=days)
