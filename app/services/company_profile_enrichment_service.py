import json
from datetime import UTC, datetime
from pathlib import Path

from app.data_sources.company_profile.eodhd_provider import fetch_company_profile as fetch_eodhd_company_profile
from app.data_sources.company_profile.fmp_provider import fetch_company_profile as fetch_fmp_company_profile
from app.data_sources.company_profile.kap_provider import fetch_company_profile as fetch_kap_company_profile
from app.data_sources.company_profile.yahoo_provider import fetch_company_profile as fetch_yahoo_company_profile
from app.models.schemas import CompanyProfileEnrichmentResponse, CompanyProfileUniverseRefreshResponse


DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "company_profiles"
INDEX_FILE = DATA_DIR / "index.json"
MANUAL_OVERRIDE_FILE = DATA_DIR / "manual_overrides.json"


SECTOR_MAP = {
    "basic materials": "Materials",
    "communication services": "Telecom",
    "consumer cyclical": "Consumer Durables",
    "consumer defensive": "Consumer",
    "consumer staples": "Consumer",
    "energy": "Energy",
    "financial services": "Financial Services",
    "healthcare": "Healthcare",
    "industrials": "Industrials",
    "real estate": "Real Estate",
    "technology": "Technology",
    "utilities": "Utilities",
    "financial institutions": "Financial Services",
    "manufacturing": "Industrials",
    "wholesale and retail trade": "Retail",
    "construction and public works": "Industrials",
    "electricity gas and water": "Energy",
    "transportation and storage": "Industrials",
    "education health sports and entertainment services": "Sports",
}

INDUSTRY_FRAGMENT_MAP = [
    ("airlines", "Airlines"),
    ("airports", "Airports"),
    ("airport", "Airports"),
    ("banks", "Banking"),
    ("bank", "Banking"),
    ("insurance", "Insurance"),
    ("steel", "Steel"),
    ("telecom", "Telecom"),
    ("wireless", "Telecom"),
    ("oil", "Energy"),
    ("gas", "Energy"),
    ("refining", "Energy"),
    ("renewable", "Energy"),
    ("power", "Energy"),
    ("electric utilities", "Utilities"),
    ("electricity gas and steam", "Energy"),
    ("electricity", "Energy"),
    ("utility", "Utilities"),
    ("chemicals", "Chemicals"),
    ("petroleum", "Energy"),
    ("mining", "Mining"),
    ("real estate", "Real Estate"),
    ("reit", "Real Estate"),
    ("gayrimenkul", "Real Estate"),
    ("retail", "Retail"),
    ("wholesale trade", "Retail"),
    ("beverages", "Consumer"),
    ("food", "Food"),
    ("aerospace", "Defense"),
    ("defense", "Defense"),
    ("electronic", "Electronics"),
    ("electrical equipment", "Electronics"),
    ("machinery", "Machinery"),
    ("medical", "Healthcare"),
    ("health", "Healthcare"),
    ("pharma", "Healthcare"),
    ("pharmaceutical", "Healthcare"),
    ("ilaç", "Healthcare"),
    ("sağlık", "Healthcare"),
    ("software", "Technology"),
    ("information technology", "Technology"),
    ("technology", "Technology"),
    ("sports activities", "Sports"),
    ("entertainment", "Sports"),
    ("holding and investment companies", "Holding"),
]


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _load_json_file(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return default


def _load_store() -> dict[str, dict]:
    return _load_json_file(INDEX_FILE, {})


def _save_store(payload: dict[str, dict]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    INDEX_FILE.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")


def _load_manual_overrides() -> dict[str, dict]:
    raw = _load_json_file(MANUAL_OVERRIDE_FILE, {})
    return {ticker.upper(): payload for ticker, payload in raw.items()} if isinstance(raw, dict) else {}


def _normalize_sector(raw_name: str | None, raw_sector: str | None, raw_industry: str | None) -> str | None:
    name_lower = (raw_name or "").lower()
    sector_lower = (raw_sector or "").lower()
    industry_lower = (raw_industry or "").lower()

    if "gyo" in name_lower or "gayrimenkul" in name_lower:
        return "Real Estate"
    if "holding" in name_lower and "yatirim" in name_lower:
        return "Holding"
    if "holding" in name_lower:
        return "Holding"
    if "futbol" in name_lower or "spor" in name_lower:
        return "Sports"
    if "teknoloji" in name_lower:
        return "Technology"
    if "ilaç" in name_lower or "saglik" in name_lower or "sağlık" in name_lower:
        return "Healthcare"
    if "enerji" in name_lower and any(fragment in industry_lower for fragment in ["electrical equipment", "electronic", "power", "energy", "utility", "electricity", "gas and steam"]):
        return "Energy"

    for fragment, normalized in INDUSTRY_FRAGMENT_MAP:
        if fragment in industry_lower:
            return normalized

    if sector_lower in SECTOR_MAP:
        return SECTOR_MAP[sector_lower]

    return raw_sector


def _build_response(ticker: str, payload: dict | None, status: str) -> CompanyProfileEnrichmentResponse:
    current = payload or {}
    return CompanyProfileEnrichmentResponse(
        ticker=ticker.upper(),
        resolved_name=current.get("resolved_name"),
        resolved_sector=current.get("resolved_sector"),
        raw_name=current.get("raw_name"),
        raw_sector=current.get("raw_sector"),
        raw_industry=current.get("raw_industry"),
        provider=current.get("provider"),
        source=current.get("source"),
        updated_at=current.get("updated_at"),
        status=status,
    )


def get_cached_company_profile_enrichment(ticker: str) -> dict | None:
    store = _load_store()
    return store.get(ticker.upper())


def get_company_profile_enrichment(ticker: str) -> CompanyProfileEnrichmentResponse:
    cached = get_cached_company_profile_enrichment(ticker)
    if cached is not None:
        return _build_response(ticker, cached, "cached")

    manual = _load_manual_overrides().get(ticker.upper())
    if manual is not None:
        current = {
            "ticker": ticker.upper(),
            "resolved_name": manual.get("resolved_name"),
            "resolved_sector": manual.get("resolved_sector"),
            "raw_name": manual.get("raw_name"),
            "raw_sector": manual.get("raw_sector"),
            "raw_industry": manual.get("raw_industry"),
            "provider": manual.get("provider", "manual_override"),
            "source": "company_profile_manual_override",
            "updated_at": manual.get("updated_at"),
        }
        return _build_response(ticker, current, "manual_override")

    return _build_response(ticker, None, "missing")


def _persist_refresh_result(ticker: str, raw_payload: dict) -> CompanyProfileEnrichmentResponse:
    resolved_sector = _normalize_sector(raw_payload.get("raw_name"), raw_payload.get("raw_sector"), raw_payload.get("raw_industry"))
    resolved_name = raw_payload.get("raw_name")
    store = _load_store()
    store[ticker.upper()] = {
        "ticker": ticker.upper(),
        "resolved_name": resolved_name,
        "resolved_sector": resolved_sector,
        "raw_name": raw_payload.get("raw_name"),
        "raw_sector": raw_payload.get("raw_sector"),
        "raw_industry": raw_payload.get("raw_industry"),
        "provider": raw_payload.get("provider"),
        "source": "company_profile_enrichment_cache",
        "updated_at": _now_iso(),
    }
    _save_store(store)
    return _build_response(ticker, store[ticker.upper()], "refreshed")


def refresh_company_profile_enrichment(ticker: str) -> CompanyProfileEnrichmentResponse:
    raw_payload = fetch_kap_company_profile(ticker)
    if raw_payload is not None:
        return _persist_refresh_result(ticker, raw_payload)

    raw_payload = fetch_eodhd_company_profile(ticker)
    if raw_payload is not None:
        return _persist_refresh_result(ticker, raw_payload)

    raw_payload = fetch_fmp_company_profile(ticker)
    if raw_payload is not None:
        return _persist_refresh_result(ticker, raw_payload)

    raw_payload = fetch_yahoo_company_profile(ticker)
    if raw_payload is not None:
        return _persist_refresh_result(ticker, raw_payload)

    manual = _load_manual_overrides().get(ticker.upper())
    if manual is not None:
        current = {
            "ticker": ticker.upper(),
            "resolved_name": manual.get("resolved_name"),
            "resolved_sector": manual.get("resolved_sector"),
            "raw_name": manual.get("raw_name"),
            "raw_sector": manual.get("raw_sector"),
            "raw_industry": manual.get("raw_industry"),
            "provider": manual.get("provider", "manual_override"),
            "source": "company_profile_manual_override",
            "updated_at": manual.get("updated_at") or _now_iso(),
        }
        return _build_response(ticker, current, "manual_override")

    cached = get_cached_company_profile_enrichment(ticker)
    if cached is not None:
        return _build_response(ticker, cached, "stale_cache")
    return _build_response(ticker, None, "unavailable")


def refresh_company_profile_enrichment_for_universe(universe_code: str = "bist100", limit: int = 200) -> CompanyProfileUniverseRefreshResponse:
    from app.data_sources.company_data.provider import list_company_records

    companies = list_company_records(universe_code=universe_code)[: max(limit, 1)]
    refreshed: list[str] = []
    for company in companies:
        result = refresh_company_profile_enrichment(company.ticker)
        if result.status in {"refreshed", "manual_override"}:
            refreshed.append(company.ticker)
    return CompanyProfileUniverseRefreshResponse(
        universe_code=universe_code,
        total_requested=len(companies),
        refreshed_count=len(refreshed),
        tickers=refreshed,
        status="refreshed",
    )
