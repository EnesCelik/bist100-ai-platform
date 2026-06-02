from sqlalchemy import select

from app.core.config import settings
from app.data_sources.company_data.mock_provider import get_company_record as get_mock_company_record
from app.data_sources.company_data.mock_provider import list_company_records as list_mock_company_records
from app.db.models import CompanyMaster, UniverseMembership
from app.db.session import SessionLocal, ensure_runtime_schema
from app.models.schemas import CompanyResponse
from app.services.company_profile_enrichment_service import get_cached_company_profile_enrichment


def _apply_enrichment_overlay(company: CompanyResponse) -> CompanyResponse:
    enrichment = get_cached_company_profile_enrichment(company.ticker)
    if enrichment is None:
        return company
    return CompanyResponse(
        ticker=company.ticker,
        name=enrichment.get("resolved_name") or company.name,
        sector=enrichment.get("resolved_sector") or company.sector,
        signal_enabled=company.signal_enabled,
        source=enrichment.get("source") or company.source,
    )


def get_company_record(ticker: str) -> CompanyResponse | None:
    ensure_runtime_schema()
    normalized_ticker = ticker.upper()
    with SessionLocal() as session:
        row = session.get(CompanyMaster, normalized_ticker)
    if row is not None and row.is_active:
        return _apply_enrichment_overlay(CompanyResponse(
            ticker=row.ticker,
            name=row.name,
            sector=row.sector,
            signal_enabled=row.signal_enabled,
            source=row.source,
        ))
    if settings.production_data_strict:
        return None
    mock_company = get_mock_company_record(normalized_ticker)
    return _apply_enrichment_overlay(mock_company) if mock_company is not None else None


def list_company_records(universe_code: str | None = None) -> list[CompanyResponse]:
    ensure_runtime_schema()
    normalized_universe = universe_code.lower().strip() if universe_code else None
    with SessionLocal() as session:
        if normalized_universe:
            statement = (
                select(CompanyMaster, UniverseMembership)
                .join(UniverseMembership, CompanyMaster.ticker == UniverseMembership.ticker)
                .where(CompanyMaster.is_active.is_(True), UniverseMembership.is_active.is_(True), UniverseMembership.universe_code == normalized_universe)
                .order_by(CompanyMaster.ticker.asc())
            )
            rows = session.execute(statement).all()
            if rows:
                return [
                    _apply_enrichment_overlay(CompanyResponse(
                        ticker=company.ticker,
                        name=company.name,
                        sector=company.sector,
                        signal_enabled=company.signal_enabled,
                        source=membership.source or company.source,
                    ))
                    for company, membership in rows
                ]
        else:
            rows = session.execute(select(CompanyMaster).where(CompanyMaster.is_active.is_(True)).order_by(CompanyMaster.ticker.asc())).scalars().all()
            if rows:
                return [
                    _apply_enrichment_overlay(CompanyResponse(
                        ticker=row.ticker,
                        name=row.name,
                        sector=row.sector,
                        signal_enabled=row.signal_enabled,
                        source=row.source,
                    ))
                    for row in rows
                ]
    if settings.production_data_strict:
        return []
    return [_apply_enrichment_overlay(company) for company in list_mock_company_records()]
