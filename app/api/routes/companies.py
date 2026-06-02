from fastapi import APIRouter, HTTPException, Query

from app.core.config import settings
from app.models.schemas import CompanyListResponse, CompanyMigrationResponse, CompanyProfileEnrichmentResponse, CompanyProfileUniverseRefreshResponse, CompanyResponse, UniverseSeedListResponse, UniverseSeedLoadResponse, UniverseUpsertRequest, UniverseUpsertResponse
from app.services.company_service import fetch_company
from app.services.company_universe_service import fetch_company_list, list_universe_seed_files, load_universe_seed, migrate_mock_companies_to_db, upsert_company_universe
from app.services.company_profile_enrichment_service import get_company_profile_enrichment, refresh_company_profile_enrichment, refresh_company_profile_enrichment_for_universe


router = APIRouter(tags=["companies"])


@router.get("/companies", response_model=CompanyListResponse)
def list_companies(
    universe_code: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=500),
) -> CompanyListResponse:
    return fetch_company_list(universe_code=universe_code, limit=limit)


@router.get("/companies/{ticker}", response_model=CompanyResponse)
def get_company(ticker: str) -> CompanyResponse:
    return fetch_company(ticker)


@router.post("/companies/migrate/from-mock", response_model=CompanyMigrationResponse)
def migrate_companies_from_mock(
    universe_code: str = Query(default="demo_core"),
    universe_name: str = Query(default="Demo Core Universe"),
) -> CompanyMigrationResponse:
    if settings.production_data_strict:
        raise HTTPException(status_code=403, detail="Mock company migration is disabled while PRODUCTION_DATA_STRICT=true")
    return migrate_mock_companies_to_db(universe_code=universe_code, universe_name=universe_name)


@router.post("/companies/universe/upsert", response_model=UniverseUpsertResponse)
def upsert_companies_for_universe(payload: UniverseUpsertRequest) -> UniverseUpsertResponse:
    if not payload.items:
        raise HTTPException(status_code=400, detail="Universe upsert icin en az bir sirket gerekir")
    return upsert_company_universe(payload)


@router.get("/companies/universe/seeds", response_model=UniverseSeedListResponse)
def list_company_universe_seeds() -> UniverseSeedListResponse:
    return list_universe_seed_files()


@router.post("/companies/universe/load-seed", response_model=UniverseSeedLoadResponse)
def load_company_universe_seed(seed_name: str = Query(..., min_length=1)) -> UniverseSeedLoadResponse:
    try:
        return load_universe_seed(seed_name)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/companies/profile-enrichment/refresh-universe", response_model=CompanyProfileUniverseRefreshResponse)
def refresh_company_profile_enrichment_universe_route(
    universe_code: str = Query(default="bist100"),
    limit: int = Query(default=100, ge=1, le=500),
) -> CompanyProfileUniverseRefreshResponse:
    return refresh_company_profile_enrichment_for_universe(universe_code=universe_code, limit=limit)


@router.get("/companies/profile-enrichment/{ticker}", response_model=CompanyProfileEnrichmentResponse)
def get_company_profile_enrichment_route(ticker: str) -> CompanyProfileEnrichmentResponse:
    return get_company_profile_enrichment(ticker)


@router.post("/companies/profile-enrichment/{ticker}", response_model=CompanyProfileEnrichmentResponse)
def refresh_company_profile_enrichment_route(ticker: str) -> CompanyProfileEnrichmentResponse:
    return refresh_company_profile_enrichment(ticker)
