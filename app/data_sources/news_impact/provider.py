from app.core.config import settings
from app.models.schemas import NewsImpactResponse

from app.data_sources.news_impact.marketaux_provider import get_news_impact as get_marketaux_news_impact


def get_news_impact(ticker: str, limit: int = 10, days: int = 7) -> NewsImpactResponse | None:
    provider = settings.news_impact_provider.lower().strip()
    if provider == "marketaux":
        return get_marketaux_news_impact(ticker, limit=limit, days=days)
    return None
