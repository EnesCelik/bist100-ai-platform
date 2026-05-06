from app.models.schemas import IngestDocumentRequest, IngestDocumentResponse
from app.rag.ingest import save_document


def ingest_document(payload: IngestDocumentRequest) -> IngestDocumentResponse:
    return save_document(payload)
