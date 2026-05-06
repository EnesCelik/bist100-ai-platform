from fastapi import APIRouter

from app.models.schemas import IngestDocumentRequest, IngestDocumentResponse
from app.services.ingest_service import ingest_document as run_ingest


# Bu router sisteme yeni dokuman eklemek icin kullanilacak.
router = APIRouter(tags=["ingest"])


@router.post("/ingest/documents", response_model=IngestDocumentResponse)
def ingest_document(payload: IngestDocumentRequest) -> IngestDocumentResponse:
    # Endpoint gelen dokumani service katmanina devrediyor.
    return run_ingest(payload)
