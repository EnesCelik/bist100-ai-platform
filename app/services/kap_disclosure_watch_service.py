import json

from pydantic import BaseModel, Field

from app.data_sources.company_profile.kap_disclosure_provider import fetch_recent_disclosures
from app.data_sources.company_profile.kap_provider import build_company_name_to_ticker_map
from app.models.schemas import IngestDocumentRequest
from app.rag.ingest import save_document
from app.rag.local_retriever import DOCUMENTS_DIR

SOURCE = "kap_disclosure_light_feed"
STATE_FILE = DOCUMENTS_DIR / "kap_watch_state.json"


class KapDisclosureMatch(BaseModel):
    ticker: str
    document_title: str
    published_at: str
    disclosure_index: int


class KapDisclosureWatchResponse(BaseModel):
    fetched_count: int
    matched_count: int
    ingested_count: int
    last_seen_index: int
    matches: list[KapDisclosureMatch] = Field(default_factory=list)


def _load_last_seen_index() -> int:
    if not STATE_FILE.exists():
        return 0
    return json.loads(STATE_FILE.read_text(encoding="utf-8")).get("last_seen_index", 0)


def _save_last_seen_index(value: int) -> None:
    DOCUMENTS_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps({"last_seen_index": value}, indent=2), encoding="utf-8")


def run_kap_disclosure_watch(ingest: bool = False) -> KapDisclosureWatchResponse:
    disclosures = fetch_recent_disclosures()
    name_to_ticker = build_company_name_to_ticker_map()
    last_seen_index = _load_last_seen_index()
    max_index_seen = last_seen_index

    matches: list[KapDisclosureMatch] = []
    ingested_count = 0

    for item in disclosures:
        max_index_seen = max(max_index_seen, item["disclosure_index"])
        if item["disclosure_index"] <= last_seen_index:
            continue

        ticker = name_to_ticker.get(item["company_title"].strip().upper())
        if ticker is None:
            continue

        matches.append(
            KapDisclosureMatch(
                ticker=ticker,
                document_title=item["subject"],
                published_at=item["published_at"],
                disclosure_index=item["disclosure_index"],
            )
        )

        if ingest:
            body = item["summary"] or "Bu bildirim icin KAP tarafindan metin ozeti yayinlanmadi; ek dosya/form icerigi bu kayda dahil degil."
            content = (
                f"# {item['subject']}\n\n"
                f"{body}\n\n"
                f"Kaynak: KAP bildirimi (disclosure_index {item['disclosure_index']})."
            )
            save_document(
                IngestDocumentRequest(
                    ticker=ticker,
                    document_title=item["subject"],
                    document_type="kap",
                    published_at=item["published_at"],
                    content=content,
                )
            )
            ingested_count += 1

    # Watermark'i sadece gercekten ingest edilen bir calistirmada ilerletiyoruz;
    # aksi halde bir onizleme (ingest=False) bildirimleri "gorulmus" sayip bir
    # daha asla ingest edilememelerine yol acar.
    if ingest:
        _save_last_seen_index(max_index_seen)

    return KapDisclosureWatchResponse(
        fetched_count=len(disclosures),
        matched_count=len(matches),
        ingested_count=ingested_count,
        last_seen_index=max_index_seen,
        matches=matches,
    )
