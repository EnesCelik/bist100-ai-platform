import json
import re
from pathlib import Path

from app.models.schemas import IngestDocumentRequest, IngestDocumentResponse
from app.rag.local_retriever import DOCUMENTS_DIR, INDEX_FILE


def _slugify(value: str) -> str:
    # Dosya ismi icin sade, tekrar kullanilabilir bir slug uretiyoruz.
    lowered_value = value.lower()
    normalized_value = re.sub(r"[^a-z0-9]+", "_", lowered_value)
    return normalized_value.strip("_")


def _load_index() -> list[dict]:
    return json.loads(INDEX_FILE.read_text(encoding="utf-8"))


def _write_index(items: list[dict]) -> None:
    INDEX_FILE.write_text(
        json.dumps(items, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def save_document(payload: IngestDocumentRequest) -> IngestDocumentResponse:
    DOCUMENTS_DIR.mkdir(parents=True, exist_ok=True)

    file_name = f"{payload.ticker.lower()}_{_slugify(payload.document_title)}.md"
    file_path = DOCUMENTS_DIR / file_name

    # Gelen icerigi markdown dosyasi olarak diske yaziyoruz.
    file_path.write_text(payload.content, encoding="utf-8")

    index_items = _load_index()

    # Ayni ticker + baslik icin eski kayit varsa cift kayit olusmasin diye temizliyoruz.
    filtered_items = [
        item
        for item in index_items
        if not (
            item["ticker"] == payload.ticker.upper()
            and item["document_title"] == payload.document_title
        )
    ]

    filtered_items.append(
        {
            "ticker": payload.ticker.upper(),
            "document_title": payload.document_title,
            "document_type": payload.document_type,
            "published_at": payload.published_at,
            "file_path": file_name,
        }
    )

    _write_index(filtered_items)

    return IngestDocumentResponse(
        ticker=payload.ticker.upper(),
        document_title=payload.document_title,
        file_path=file_name,
        status="saved",
    )
