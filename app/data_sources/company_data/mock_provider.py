from app.models.schemas import CompanyResponse


# Simdilik veritabani kullanmiyoruz; endpoint mantigini anlamak icin sabit veriyle basliyoruz.
MOCK_COMPANIES = {
    "GARAN": {
        "ticker": "GARAN",
        "name": "Garanti BBVA",
        "sector": "Banking",
        "signal_enabled": False,
    },
    "THYAO": {
        "ticker": "THYAO",
        "name": "Turkish Airlines",
        "sector": "Airlines",
        "signal_enabled": False,
    },
    "ASELS": {
        "ticker": "ASELS",
        "name": "Aselsan",
        "sector": "Defense",
        "signal_enabled": False,
    },
    "EREGL": {
        "ticker": "EREGL",
        "name": "Eregli Demir Celik",
        "sector": "Steel",
        "signal_enabled": False,
    },
}


def get_company_record(ticker: str) -> CompanyResponse | None:
    normalized_ticker = ticker.upper()
    company = MOCK_COMPANIES.get(normalized_ticker)
    if company is None:
        return None
    return CompanyResponse(**company)


def list_company_records() -> list[CompanyResponse]:
    return [CompanyResponse(**company) for company in MOCK_COMPANIES.values()]
