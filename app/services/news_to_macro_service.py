import json
from pathlib import Path

from sqlalchemy.exc import SQLAlchemyError

from app.db.models import MacroEventRecord
from app.db.session import SessionLocal
from app.models.schemas import ConvertNewsToMacroRequest, ConvertNewsToMacroResponse
from app.services.macro_event_service import _find_existing_db_macro_event, _macro_key
from app.services.news_service import find_news_item


MACRO_INDEX_FILE = Path(__file__).resolve().parents[2] / "data" / "macro_events" / "index.json"
DB_SOURCE = "news_to_macro_converter"


def _load_json(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def _save_json(path: Path, items: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(items, file, indent=2, ensure_ascii=False)


def _derive_event_category(news_item: dict) -> str:
    tags = [tag.lower() for tag in news_item.get("tags", [])]
    if "energy" in tags:
        return "energy"
    if "geopolitics" in tags:
        return "geopolitics"
    if "trade" in tags:
        return "trade"
    if "rates" in tags or "risk_off" in tags:
        return "rates"
    return "geopolitics"


def _derive_region(news_item: dict) -> str:
    text = f"{news_item.get('headline', '')} {news_item.get('summary', '')}".lower()
    tags = [tag.lower() for tag in news_item.get("tags", [])]
    if "middle_east" in tags or "hurmuz" in text or "orta dogu" in text:
        return "middle_east"
    return "global"


def _derive_base_impacts(news_item: dict, event_category: str) -> tuple[list[str], list[str]]:
    text = f"{news_item.get('headline', '')} {news_item.get('summary', '')}".lower()
    positives: list[str] = []
    negatives: list[str] = []

    if event_category == "geopolitics":
        positives.append("Kuresel guvenlik gundemi risk algisini degistirebilir")
        negatives.append("Jeopolitik risk primi artabilir")
    if event_category == "energy":
        positives.append("Enerji fiyat hareketleri sektorler arasi ayrismayi artirabilir")
        negatives.append("Enerji ve lojistik maliyetleri yukselebilir")
    if event_category == "trade":
        positives.append("Kuresel ticaret akisi tema bazli ayrismayi artirabilir")
        negatives.append("Ticaret ve lojistik maliyetleri yukselebilir")
    if event_category == "rates":
        positives.append("Kuresel faiz beklentileri varlik fiyatlamasini yeniden sekillendirebilir")
        negatives.append("Faiz ve risk primi baskisi artabilir")

    if "maliyet" in text or "lojistik" in text:
        negatives.append("Enerji ve lojistik maliyetleri yukselebilir")
    if "talep" in text or "gorunurlugu" in text:
        positives.append("Tema bazli beklentiler hissede ilgiyi destekleyebilir")

    positives = list(dict.fromkeys(positives))
    negatives = list(dict.fromkeys(negatives))
    return positives, negatives


def convert_news_to_macro_event(payload: ConvertNewsToMacroRequest) -> ConvertNewsToMacroResponse:
    news_item = find_news_item(payload.ticker, payload.headline, payload.published_at)
    if news_item is None:
        raise ValueError("News item not found")

    event_category = _derive_event_category(news_item)
    region = _derive_region(news_item)
    positive_impacts, negative_impacts = _derive_base_impacts(news_item, event_category)

    new_record = {
        "ticker": payload.ticker.upper(),
        "latest_macro_event": payload.headline,
        "positive_impacts": positive_impacts,
        "negative_impacts": negative_impacts,
        "event_category": event_category,
        "region": region,
        "published_at": payload.published_at,
        "source": DB_SOURCE,
    }

    try:
        with SessionLocal() as session:
            existing = _find_existing_db_macro_event(session, new_record)
            if existing is not None:
                return ConvertNewsToMacroResponse(
                    ticker=new_record["ticker"],
                    latest_macro_event=new_record["latest_macro_event"],
                    event_category=event_category,
                    region=region,
                    published_at=new_record["published_at"],
                    status="skipped",
                )
            session.add(
                MacroEventRecord(
                    ticker=new_record["ticker"],
                    latest_macro_event=new_record["latest_macro_event"],
                    event_category=new_record["event_category"],
                    region=new_record["region"],
                    published_at=new_record["published_at"],
                    positive_impacts=new_record["positive_impacts"],
                    negative_impacts=new_record["negative_impacts"],
                    source=new_record["source"],
                )
            )
            session.commit()
    except SQLAlchemyError:
        macro_events = _load_json(MACRO_INDEX_FILE)
        fallback_record = {**new_record, "source": DB_SOURCE}
        existing_keys = {_macro_key(item) for item in macro_events}
        if _macro_key(fallback_record) in existing_keys:
            return ConvertNewsToMacroResponse(
                ticker=fallback_record["ticker"],
                latest_macro_event=fallback_record["latest_macro_event"],
                event_category=event_category,
                region=region,
                published_at=fallback_record["published_at"],
                status="skipped",
            )
        macro_events.append(fallback_record)
        macro_events.sort(key=lambda item: (item.get("ticker", ""), item.get("published_at", "")))
        _save_json(MACRO_INDEX_FILE, macro_events)
        return ConvertNewsToMacroResponse(
            ticker=fallback_record["ticker"],
            latest_macro_event=fallback_record["latest_macro_event"],
            event_category=event_category,
            region=region,
            published_at=fallback_record["published_at"],
            status="saved",
        )

    return ConvertNewsToMacroResponse(
        ticker=new_record["ticker"],
        latest_macro_event=new_record["latest_macro_event"],
        event_category=event_category,
        region=region,
        published_at=new_record["published_at"],
        status="saved",
    )
