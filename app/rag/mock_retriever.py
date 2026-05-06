from app.models.schemas import RetrievedDocument


# Bu veri gercek vector DB sonucu degil.
# Ilk asamada RAG akisini gostermek icin sahte retrieval sonucu kullaniyoruz.
MOCK_DOCUMENTS = {
    "GARAN": [
        {
            "ticker": "GARAN",
            "document_title": "Garanti BBVA 2025 Faaliyet Raporu",
            "document_type": "activity_report",
            "published_at": "2026-02-20",
            "excerpt": (
                "Banka, dijital bankacilik yatirimlarini surdurdugunu ve kredi riskini "
                "yakindan izledigini belirtti."
            ),
            "source": "mock_rag_retriever",
        },
        {
            "ticker": "GARAN",
            "document_title": "KAP Aciklamasi - Sendikasyon Gelismesi",
            "document_type": "kap",
            "published_at": "2026-03-11",
            "excerpt": (
                "Sendikasyon surecine iliskin aciklamada, uluslararasi fonlama yapisinin "
                "guclu tutulmasina vurgu yapildi."
            ),
            "source": "mock_rag_retriever",
        },
    ],
    "ASELS": [
        {
            "ticker": "ASELS",
            "document_title": "Aselsan 2025 Faaliyet Raporu",
            "document_type": "activity_report",
            "published_at": "2026-02-28",
            "excerpt": (
                "Sirket, savunma projelerinde teslimat temposunu korurken tedarik zinciri "
                "ve proje zamanlamasi risklerine dikkat cekti."
            ),
            "source": "mock_rag_retriever",
        }
    ],
    "THYAO": [
        {
            "ticker": "THYAO",
            "document_title": "THY 2025 Faaliyet Raporu",
            "document_type": "activity_report",
            "published_at": "2026-02-25",
            "excerpt": (
                "Yakit maliyetleri, filo planlamasi ve dis hat talep dengesi temel izleme "
                "alanlari olarak belirtildi."
            ),
            "source": "mock_rag_retriever",
        }
    ],
}


def retrieve_documents(ticker: str) -> list[RetrievedDocument]:
    normalized_ticker = ticker.upper()
    documents = MOCK_DOCUMENTS.get(normalized_ticker, [])
    return [RetrievedDocument(**document) for document in documents]
