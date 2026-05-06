import json
from pathlib import Path

from sqlalchemy import select

from app.data_sources.company_data.mock_provider import MOCK_COMPANIES
from app.data_sources.company_data.provider import get_company_record, list_company_records
from app.db.models import CompanyMaster, UniverseMembership
from app.db.session import SessionLocal, ensure_runtime_schema
from app.models.schemas import (
    CompanyListResponse,
    CompanyMigrationResponse,
    CompanyResponse,
    UniverseSeedInfo,
    UniverseSeedListResponse,
    UniverseSeedLoadResponse,
    UniverseUpsertRequest,
    UniverseUpsertResponse,
)


def fetch_company_list(universe_code: str | None = None, limit: int = 200) -> CompanyListResponse:
    items = list_company_records(universe_code=universe_code)[: max(limit, 1)]
    return CompanyListResponse(total=len(items), universe_code=universe_code, items=items)


def fetch_company_record(ticker: str) -> CompanyResponse | None:
    return get_company_record(ticker)


def migrate_mock_companies_to_db(universe_code: str = "demo_core", universe_name: str = "Demo Core Universe") -> CompanyMigrationResponse:
    ensure_runtime_schema()
    company_upserted = 0
    membership_upserted = 0
    normalized_universe = universe_code.lower().strip()
    with SessionLocal() as session:
        for payload in MOCK_COMPANIES.values():
            ticker = payload["ticker"].upper()
            company = session.get(CompanyMaster, ticker)
            if company is None:
                company = CompanyMaster(ticker=ticker)
                session.add(company)
            company.name = payload["name"]
            company.sector = payload["sector"]
            company.signal_enabled = payload["signal_enabled"]
            company.is_active = True
            company.source = "mock_company_seed"
            company_upserted += 1

            membership = session.execute(
                select(UniverseMembership).where(
                    UniverseMembership.ticker == ticker,
                    UniverseMembership.universe_code == normalized_universe,
                )
            ).scalar_one_or_none()
            if membership is None:
                membership = UniverseMembership(ticker=ticker, universe_code=normalized_universe)
                session.add(membership)
            membership.universe_name = universe_name
            membership.is_active = True
            membership.source = "mock_company_seed"
            membership_upserted += 1

        session.commit()

    return CompanyMigrationResponse(
        total_seed_records=len(MOCK_COMPANIES),
        company_upserted=company_upserted,
        membership_upserted=membership_upserted,
        universe_code=normalized_universe,
        status="migrated",
        source="mock_company_seed",
        note="Bu endpoint demo/mock dataset'i DB'ye tasir; current BIST100 constituent listesini cekmez.",
    )


def upsert_company_universe(payload: UniverseUpsertRequest, sync_memberships: bool = False) -> UniverseUpsertResponse:
    ensure_runtime_schema()
    normalized_universe = payload.universe_code.lower().strip()
    company_upserted = 0
    membership_upserted = 0
    active_tickers: set[str] = set()
    with SessionLocal() as session:
        for item in payload.items:
            ticker = item.ticker.upper()
            active_tickers.add(ticker)
            company = session.get(CompanyMaster, ticker)
            if company is None:
                company = CompanyMaster(ticker=ticker)
                session.add(company)
            company.name = item.name
            company.sector = item.sector
            company.signal_enabled = item.signal_enabled
            company.is_active = item.is_active
            company.source = payload.source
            company_upserted += 1

            membership = session.execute(
                select(UniverseMembership).where(
                    UniverseMembership.ticker == ticker,
                    UniverseMembership.universe_code == normalized_universe,
                )
            ).scalar_one_or_none()
            if membership is None:
                membership = UniverseMembership(ticker=ticker, universe_code=normalized_universe)
                session.add(membership)
            membership.universe_name = payload.universe_name
            membership.is_active = item.is_active
            membership.source = payload.source
            membership_upserted += 1

        if sync_memberships:
            memberships = session.execute(
                select(UniverseMembership).where(UniverseMembership.universe_code == normalized_universe)
            ).scalars().all()
            for membership in memberships:
                if membership.ticker not in active_tickers:
                    membership.is_active = False
                    membership.source = payload.source

        session.commit()

    return UniverseUpsertResponse(
        universe_code=normalized_universe,
        total_items=len(payload.items),
        company_upserted=company_upserted,
        membership_upserted=membership_upserted,
        source=payload.source,
        status="saved",
    )


SEED_DIR = Path(__file__).resolve().parents[2] / "data" / "seeds"


def _read_seed_payload(seed_path: Path) -> dict | None:
    try:
        return json.loads(seed_path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def list_universe_seed_files() -> UniverseSeedListResponse:
    SEED_DIR.mkdir(parents=True, exist_ok=True)
    items: list[UniverseSeedInfo] = []
    for seed_path in sorted(SEED_DIR.glob("*.json")):
        payload = _read_seed_payload(seed_path) or {}
        records = payload.get("items") or []
        items.append(
            UniverseSeedInfo(
                seed_name=seed_path.stem,
                path=str(seed_path),
                item_count=len(records),
                universe_code=payload.get("universe_code"),
                source=payload.get("source"),
            )
        )
    return UniverseSeedListResponse(total=len(items), items=items)


def load_universe_seed(seed_name: str) -> UniverseSeedLoadResponse:
    SEED_DIR.mkdir(parents=True, exist_ok=True)
    normalized_seed = seed_name.strip().removesuffix('.json')
    seed_path = SEED_DIR / f"{normalized_seed}.json"
    payload = _read_seed_payload(seed_path)
    if payload is None:
        raise FileNotFoundError(f"Seed file '{normalized_seed}' bulunamadi")

    request = UniverseUpsertRequest(**payload)
    result = upsert_company_universe(request, sync_memberships=True)
    return UniverseSeedLoadResponse(
        seed_name=normalized_seed,
        universe_code=result.universe_code,
        total_items=result.total_items,
        company_upserted=result.company_upserted,
        membership_upserted=result.membership_upserted,
        source=result.source,
        status="loaded",
        note="Seed yuklemesi hedef universe'u seed dosyasiyla senkronize eder.",
    )
