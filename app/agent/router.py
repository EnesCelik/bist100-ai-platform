from app.data_sources.company_data.provider import list_company_records
from app.models.schemas import AskResponse, Citation, RetrievedDocument


MARKET_KEYWORDS = [
    "fiyat",
    "price",
    "hacim",
    "volume",
    "alis",
    "satis",
    "bid",
    "ask",
]

ANALYSIS_KEYWORDS = [
    "neden artar",
    "neden duser",
    "hangi kosullarda",
    "hangi durumda",
    "yukselir",
    "duser",
    "artar",
    "baski",
    "kosullar",
    "alima en uygun",
    "alim icin uygun",
    "bugun alinabilecek",
    "en uygun hisse",
    "en iyi hisse",
    "hangi hisseler",
    "hangi hisse",
    "hangi sektor",
    "sektor",
    "daha avantajli",
]

DOCUMENT_KEYWORDS = [
    "rapor",
    "kap",
    "faaliyet",
    "sunum",
    "risk",
    "borcluluk",
]



def build_citations(documents: list[RetrievedDocument]) -> list[Citation]:
    # Retrieval sonucundaki dokumanlari daha sade bir citation listesine ceviriyoruz.
    return [
        Citation(
            ticker=document.ticker,
            document_title=document.document_title,
            document_type=document.document_type,
            published_at=document.published_at,
            source=document.source,
        )
        for document in documents
    ]


def detect_route_type(question: str) -> str:
    # Soruyu kucuk harfe cevirerek anahtar kelime aramalarini kolaylastiriyoruz.
    lowered_question = question.lower()

    # Market data anahtar kelimelerinden biri geciyorsa tool_query adayi olur.
    has_market_keyword = any(keyword in lowered_question for keyword in MARKET_KEYWORDS)
    # Dokuman/RAG anahtar kelimeleri geciyorsa rag_query adayi olur.
    has_document_keyword = any(keyword in lowered_question for keyword in DOCUMENT_KEYWORDS)
    # Analiz tipindeki sorulari ayri ele almak istiyoruz.
    has_analysis_keyword = any(keyword in lowered_question for keyword in ANALYSIS_KEYWORDS)

    if has_analysis_keyword:
        return "analysis_query"

    # Ikisi birden geciyorsa hibrit akisa yonlendiriyoruz.
    if has_market_keyword and has_document_keyword:
        return "hybrid_query"
    if has_market_keyword:
        return "tool_query"
    if has_document_keyword:
        return "rag_query"

    # Genel piyasa ve sektor sorularini da analiz tarafina daha yakin kabul ediyoruz.
    generic_market_markers = ["hisse", "sektor", "alim", "alima", "avantajli", "uygun"]
    if any(marker in lowered_question for marker in generic_market_markers):
        return "analysis_query"

    return "rag_query"


def extract_ticker(question: str) -> str | None:
    upper_question = question.upper()
    candidates = sorted((company.ticker for company in list_company_records()), key=len, reverse=True)
    for ticker in candidates:
        if ticker in upper_question:
            return ticker
    return None
