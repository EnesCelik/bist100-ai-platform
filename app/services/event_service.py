"""Sirket-ozel KAP bildirimlerini (kap_disclosure_watch_service ile yerel
RAG deposuna ingest edilen belgeler) event katmanina baglar.

Cogu KAP bildirim turunun yonu (destekleyici mi baskilayici mi) icerigi
okumadan guvenilir sekilde belirlenemez - orn. "Sermaye Artirimi" bedelli mi
bedelsiz mi, ic kaynaktan mi bilinmeden pozitif/negatif etiketlemek yanlis
olur. Bu yuzden SADECE yonu evrensel olarak nette olan iki bildirim turunu
(pay geri alimi, kar payi dagitimi) destekleyici/baskilayici sayiyoruz.
Diger turler latest_event'te goruntuleniyor (kullanici bilgilensin diye)
ama supportive/pressure listelerine hic girmiyor - derive_recommendation'a
yanlis yonde bir sinyal vermektense hic vermemeyi tercih ediyoruz.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.models.schemas import EventResponse
from app.rag.local_retriever import retrieve_documents

SOURCE = "kap_disclosure_local_store"
_RECENCY_WINDOW_DAYS = 14
_MAX_EVENTS = 3

_SUPPORTIVE_TITLE_KEYWORDS = ("geri alinmasina", "kar payi dagitim")


def _normalize_title(title: str) -> str:
    replacements = {"ı": "i", "İ": "i", "ş": "s", "ğ": "g", "ü": "u", "ö": "o", "ç": "c"}
    lowered = title.lower()
    for source_char, target_char in replacements.items():
        lowered = lowered.replace(source_char.lower(), target_char)
    return lowered


def get_event_summary(ticker: str) -> EventResponse | None:
    documents = retrieve_documents(ticker)
    kap_documents = [doc for doc in documents if doc.document_type == "kap"]
    if not kap_documents:
        return None

    cutoff = (datetime.now(UTC) - timedelta(days=_RECENCY_WINDOW_DAYS)).date().isoformat()
    recent = sorted(
        (doc for doc in kap_documents if doc.published_at >= cutoff),
        key=lambda doc: doc.published_at,
        reverse=True,
    )
    if not recent:
        return None

    supportive_events: list[str] = []
    pressure_events: list[str] = []
    for doc in recent[:_MAX_EVENTS]:
        normalized_title = _normalize_title(doc.document_title)
        if any(keyword in normalized_title for keyword in _SUPPORTIVE_TITLE_KEYWORDS):
            supportive_events.append(f"KAP: {doc.document_title} ({doc.published_at})")
        # Yonu net olmayan turler (ozel durum aciklamasi, sermaye artirimi vb.)
        # bilerek supportive/pressure listelerine eklenmiyor.

    latest_event = f"{recent[0].document_title} ({recent[0].published_at})"

    return EventResponse(
        ticker=ticker.upper(),
        latest_event=latest_event,
        supportive_events=supportive_events,
        pressure_events=pressure_events,
        source=SOURCE,
    )
