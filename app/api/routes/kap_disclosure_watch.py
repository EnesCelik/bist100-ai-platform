from fastapi import APIRouter, Query

from app.services.kap_disclosure_watch_service import KapDisclosureWatchResponse, run_kap_disclosure_watch


router = APIRouter(tags=["kap-disclosure-watch"])


@router.post("/kap-disclosures/watch/run", response_model=KapDisclosureWatchResponse)
def run_kap_disclosure_watch_route(
    ingest: bool = Query(default=False),
) -> KapDisclosureWatchResponse:
    return run_kap_disclosure_watch(ingest=ingest)
