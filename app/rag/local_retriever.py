import json
from pathlib import Path

from app.models.schemas import RetrievedDocument


DOCUMENTS_DIR = Path(__file__).resolve().parents[2] / "data" / "documents"
INDEX_FILE = DOCUMENTS_DIR / "index.json"


def _load_index() -> list[dict]:
    # Index dosyasi, hangi ticker icin hangi markdown dosyasinin okunacagini soyler.
    return json.loads(INDEX_FILE.read_text(encoding="utf-8"))


def _read_excerpt(file_name: str) -> str:
    # Markdown dosyasini okuyup ilk anlamli paragrafi excerpt olarak kullaniyoruz.
    content = (DOCUMENTS_DIR / file_name).read_text(encoding="utf-8")
    lines = [line.strip() for line in content.splitlines() if line.strip()]

    # Baslik satirlarini atlayip ilk metin satirini almak istiyoruz.
    body_lines = [line for line in lines if not line.startswith("#")]
    return body_lines[0] if body_lines else ""


def _score_document(document: RetrievedDocument, question: str | None) -> tuple[int, str]:
    # Daha yuksek skor alan dokumanlar one gelsin istiyoruz.
    score = 0
    lowered_question = (question or "").lower()

    # Soru KAP diyorsa KAP dokumanlarini one al.
    if "kap" in lowered_question and document.document_type == "kap":
        score += 5

    # Soru rapor/faaliyet diyorsa faaliyet raporlarini one al.
    if (
        ("rapor" in lowered_question or "faaliyet" in lowered_question)
        and document.document_type == "activity_report"
    ):
        score += 5

    # "son" veya "guncel" gibi ifadelerde daha yeni tarihi one alacagiz.
    if "son" in lowered_question or "guncel" in lowered_question:
        score += 3

    # Baslik sorudaki kelimelerle eslesiyorsa biraz daha avantaj ver.
    title_tokens = document.document_title.lower().split()
    if any(token in lowered_question for token in title_tokens):
        score += 1

    return score, document.published_at


def retrieve_documents(ticker: str, question: str | None = None) -> list[RetrievedDocument]:
    normalized_ticker = ticker.upper()
    retrieved_documents: list[RetrievedDocument] = []

    for item in _load_index():
        if item["ticker"] != normalized_ticker:
            continue

        retrieved_documents.append(
            RetrievedDocument(
                ticker=item["ticker"],
                document_title=item["document_title"],
                document_type=item["document_type"],
                published_at=item["published_at"],
                excerpt=_read_excerpt(item["file_path"]),
                source="local_json_markdown_retriever",
            )
        )

    # Once soru uyumuna gore, sonra tarihe gore azalan sekilde sirala.
    return sorted(
        retrieved_documents,
        key=lambda document: _score_document(document, question),
        reverse=True,
    )
