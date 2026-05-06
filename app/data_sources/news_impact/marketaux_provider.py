from __future__ import annotations

import json
from datetime import datetime, timedelta
from urllib import error, parse, request

from app.core.config import settings
from app.models.schemas import NewsImpactArticleResponse, NewsImpactResponse

MARKETAUX_SOURCE = "marketaux_news_impact"


def _symbol_candidates(ticker: str) -> list[str]:
    normalized = ticker.upper().strip()
    return [normalized, f"{normalized}.IS", f"{normalized}.TI"]


def get_news_impact(ticker: str, limit: int = 10, days: int = 7) -> NewsImpactResponse | None:
    if not settings.marketaux_api_token:
        return None

    params = {
        "api_token": settings.marketaux_api_token,
        "symbols": ",".join(_symbol_candidates(ticker)),
        "filter_entities": "true",
        "must_have_entities": "true",
        "language": settings.marketaux_language,
        "published_after": (datetime.utcnow() - timedelta(days=max(days, 1))).strftime("%Y-%m-%dT%H:%M"),
        "limit": max(min(limit, 20), 1),
        "sort": "published_at",
    }
    if settings.marketaux_countries:
        params["countries"] = settings.marketaux_countries

    url = f"{settings.marketaux_base_url.rstrip('/')}/news/all?{parse.urlencode(params)}"
    try:
        with request.urlopen(url, timeout=settings.marketaux_timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (error.HTTPError, error.URLError, TimeoutError, json.JSONDecodeError):
        return None

    articles: list[NewsImpactArticleResponse] = []
    sentiments: list[float] = []
    latest_published_at: str | None = None

    for item in payload.get("data", []):
        entities = item.get("entities") or []
        matched_entity = None
        for entity in entities:
            symbol = str(entity.get("symbol") or "").upper()
            if ticker.upper() in symbol:
                matched_entity = entity
                break
        sentiment_score = None
        match_score = None
        if matched_entity is not None:
            if matched_entity.get("sentiment_score") is not None:
                sentiment_score = float(matched_entity.get("sentiment_score"))
                sentiments.append(sentiment_score)
            if matched_entity.get("match_score") is not None:
                match_score = float(matched_entity.get("match_score"))

        published_at = str(item.get("published_at") or item.get("published_on") or "")
        if published_at and (latest_published_at is None or published_at > latest_published_at):
            latest_published_at = published_at

        articles.append(
            NewsImpactArticleResponse(
                headline=str(item.get("title") or item.get("headline") or ""),
                published_at=published_at,
                source=item.get("source") or item.get("publisher") or item.get("domain"),
                url=item.get("url"),
                sentiment_score=sentiment_score,
                match_score=match_score,
            )
        )

    average_sentiment = round(sum(sentiments) / len(sentiments), 4) if sentiments else None
    return NewsImpactResponse(
        ticker=ticker.upper(),
        provider=MARKETAUX_SOURCE,
        total_articles=len(articles),
        average_sentiment=average_sentiment,
        latest_published_at=latest_published_at,
        items=articles,
    )
