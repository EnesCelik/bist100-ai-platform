from fastapi import HTTPException

from app.models.schemas import CompanyResponse
from app.services.company_universe_service import fetch_company_record


def fetch_company(ticker: str) -> CompanyResponse:
    company = fetch_company_record(ticker)
    if company is None:
        raise HTTPException(
            status_code=404,
            detail=f"Company with ticker '{ticker.upper()}' was not found.",
        )
    return company
