import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.db.models import NewsItem
from app.db.session import SessionLocal
from app.models.schemas import (
    IngestNewsRequest,
    IngestNewsResponse,
    NewsCleanupResponse,
    NewsHistoryResponse,
    NewsItemResponse,
    NewsMigrationResponse,
)


DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "news"
INDEX_FILE = DATA_DIR / "index.json"
DB_SOURCE = "postgres_news_store"
JSON_SOURCE = "json_news_store"


def _load_news_json() -> list[dict]:
    if not INDEX_FILE.exists():
        return []

    with INDEX_FILE.open("r", encoding="utf-8") as file:
        return json.load(file)


def _save_news_json(items: list[dict]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with INDEX_FILE.open("w", encoding="utf-8") as file:
        json.dump(items, file, indent=2, ensure_ascii=False)


def _news_key(item: dict) -> tuple[str, str, str, str]:
    return (
        item.get("ticker", "").upper(),
        item.get("headline", "").strip(),
        item.get("published_at", "").strip(),
        item.get("source_url", "").strip(),
    )


def _normalize_payload(payload: IngestNewsRequest) -> dict:
    return {
        "ticker": payload.ticker.upper(),
        "headline": payload.headline,
        "summary": payload.summary,
        "source_url": payload.source_url,
        "publisher": payload.publisher,
        "published_at": payload.published_at,
        "tags": payload.tags,
    }


def _serialize_news_row(row: NewsItem) -> dict:
    return {
        "ticker": row.ticker,
        "headline": row.headline,
        "summary": row.summary,
        "source_url": row.source_url,
        "publisher": row.publisher,
        "published_at": row.published_at,
        "tags": row.tags,
        "source": row.source,
    }


def _find_existing_db_news(session, item: dict) -> NewsItem | None:
    statement = select(NewsItem).where(
        NewsItem.ticker == item["ticker"],
        NewsItem.headline == item["headline"],
        NewsItem.published_at == item["published_at"],
        NewsItem.source_url == item["source_url"],
    )
    return session.execute(statement).scalar_one_or_none()


def ingest_news(payload: IngestNewsRequest) -> IngestNewsResponse:
    new_item = _normalize_payload(payload)

    try:
        with SessionLocal() as session:
            existing = _find_existing_db_news(session, new_item)
            if existing is not None:
                return IngestNewsResponse(
                    ticker=new_item["ticker"],
                    headline=new_item["headline"],
                    published_at=new_item["published_at"],
                    status="skipped",
                )

            session.add(
                NewsItem(
                    ticker=new_item["ticker"],
                    headline=new_item["headline"],
                    summary=new_item["summary"],
                    source_url=new_item["source_url"],
                    publisher=new_item["publisher"],
                    published_at=new_item["published_at"],
                    tags=new_item["tags"],
                    source=DB_SOURCE,
                )
            )
            session.commit()

        return IngestNewsResponse(
            ticker=new_item["ticker"],
            headline=new_item["headline"],
            published_at=new_item["published_at"],
            status="saved",
        )
    except SQLAlchemyError:
        news_items = _load_news_json()
        fallback_item = {**new_item, "source": JSON_SOURCE}

        if _news_key(fallback_item) in {_news_key(item) for item in news_items}:
            return IngestNewsResponse(
                ticker=fallback_item["ticker"],
                headline=fallback_item["headline"],
                published_at=fallback_item["published_at"],
                status="skipped",
            )

        news_items.append(fallback_item)
        news_items.sort(key=lambda item: (item.get("ticker", ""), item.get("published_at", "")))
        _save_news_json(news_items)

        return IngestNewsResponse(
            ticker=fallback_item["ticker"],
            headline=fallback_item["headline"],
            published_at=fallback_item["published_at"],
            status="saved",
        )


def cleanup_duplicate_news() -> NewsCleanupResponse:
    try:
        with SessionLocal() as session:
            rows = session.execute(
                select(NewsItem).order_by(NewsItem.ticker, NewsItem.published_at, NewsItem.headline, NewsItem.id)
            ).scalars().all()

            seen: set[tuple[str, str, str, str]] = set()
            removed_count = 0
            for row in rows:
                key = _news_key(_serialize_news_row(row))
                if key in seen:
                    session.delete(row)
                    removed_count += 1
                    continue
                seen.add(key)

            if removed_count > 0:
                session.commit()

        return NewsCleanupResponse(
            removed_count=removed_count,
            status="cleaned" if removed_count > 0 else "no_changes",
        )
    except SQLAlchemyError:
        news_items = _load_news_json()
        seen: set[tuple[str, str, str, str]] = set()
        cleaned_items: list[dict] = []
        removed_count = 0

        for item in sorted(news_items, key=lambda entry: (entry.get("ticker", ""), entry.get("published_at", ""), entry.get("headline", ""))):
            key = _news_key(item)
            if key in seen:
                removed_count += 1
                continue
            seen.add(key)
            cleaned_items.append(item)

        if removed_count > 0:
            _save_news_json(cleaned_items)

        return NewsCleanupResponse(
            removed_count=removed_count,
            status="cleaned" if removed_count > 0 else "no_changes",
        )


def get_news_history(ticker: str, limit: int = 10, tag: str | None = None) -> NewsHistoryResponse:
    normalized_ticker = ticker.upper()
    normalized_tag = tag.lower() if tag is not None else None

    try:
        with SessionLocal() as session:
            rows = session.execute(select(NewsItem).where(NewsItem.ticker == normalized_ticker)).scalars().all()
            matching = [
                _serialize_news_row(row)
                for row in rows
                if normalized_tag is None or normalized_tag in [t.lower() for t in row.tags]
            ]
    except SQLAlchemyError:
        matching = [
            item
            for item in _load_news_json()
            if item.get("ticker", "").upper() == normalized_ticker
            and (normalized_tag is None or normalized_tag in [t.lower() for t in item.get("tags", [])])
        ]

    sorted_items = sorted(matching, key=lambda item: (item.get("published_at", ""), item.get("headline", "")), reverse=True)
    limited_items = sorted_items[: max(limit, 1)]

    return NewsHistoryResponse(
        ticker=normalized_ticker,
        total=len(limited_items),
        items=[NewsItemResponse(**item) for item in limited_items],
    )


def find_news_item(ticker: str, headline: str, published_at: str) -> dict | None:
    normalized_ticker = ticker.upper()
    try:
        with SessionLocal() as session:
            statement = select(NewsItem).where(
                NewsItem.ticker == normalized_ticker,
                NewsItem.headline == headline,
                NewsItem.published_at == published_at,
            )
            row = session.execute(statement).scalar_one_or_none()
            if row is not None:
                return _serialize_news_row(row)
    except SQLAlchemyError:
        pass

    for item in _load_news_json():
        if (
            item.get("ticker", "").upper() == normalized_ticker
            and item.get("headline", "") == headline
            and item.get("published_at", "") == published_at
        ):
            return item
    return None


def migrate_json_news_to_db() -> NewsMigrationResponse:
    json_items = _load_news_json()
    if not json_items:
        return NewsMigrationResponse(total_json_records=0, migrated_count=0, skipped_count=0, status="no_changes")

    migrated_count = 0
    skipped_count = 0

    with SessionLocal() as session:
        for item in json_items:
            normalized_item = {
                "ticker": item.get("ticker", "").upper(),
                "headline": item.get("headline", ""),
                "summary": item.get("summary", ""),
                "source_url": item.get("source_url", ""),
                "publisher": item.get("publisher", ""),
                "published_at": item.get("published_at", ""),
                "tags": item.get("tags", []),
                "source": item.get("source", JSON_SOURCE),
            }
            existing = _find_existing_db_news(session, normalized_item)
            if existing is not None:
                skipped_count += 1
                continue

            session.add(
                NewsItem(
                    ticker=normalized_item["ticker"],
                    headline=normalized_item["headline"],
                    summary=normalized_item["summary"],
                    source_url=normalized_item["source_url"],
                    publisher=normalized_item["publisher"],
                    published_at=normalized_item["published_at"],
                    tags=normalized_item["tags"],
                    source=normalized_item["source"],
                )
            )
            migrated_count += 1

        if migrated_count > 0:
            session.commit()

    return NewsMigrationResponse(
        total_json_records=len(json_items),
        migrated_count=migrated_count,
        skipped_count=skipped_count,
        status="migrated" if migrated_count > 0 else "no_changes",
    )
