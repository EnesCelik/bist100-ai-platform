import json
from pathlib import Path

from app.data_sources.company_data.provider import get_company_record, list_company_records
from app.models.schemas import (
    GlobalEventSourceCatalogResponse,
    GlobalEventSourceItem,
    IngestGlobalEventRequest,
    IngestGlobalEventResponse,
    IngestMacroEventRequest,
    PreviewGlobalEventRequest,
    PreviewGlobalEventResponse,
    SectorImpactOverride,
)
from app.services.macro_event_ingest_service import ingest_macro_event, replace_macro_event


CATALOG_FILE = Path(__file__).resolve().parents[2] / "data" / "reference" / "global_event_sources.json"

IGNORED_PLACEHOLDER_VALUES = {"", "string", "null", "none", "n/a", "na", "-"}

SECTOR_ALIAS_MAP = {
    "bankacilik": ["Banking"],
    "banka": ["Banking"],
    "enerji": ["Energy", "Utilities"],
    "otomotiv": ["Automotive"],
    "savunma": ["Defense"],
    "telekom": ["Telecom"],
    "perakende": ["Retail"],
    "sigorta": ["Insurance"],
    "holding": ["Holding", "Conglomerates"],
    "konglomerates": ["Conglomerates"],
    "conglomerates": ["Conglomerates"],
    "teknoloji": ["Technology"],
    "saglik": ["Healthcare"],
    "gida": ["Food"],
    "gayrimenkul": ["Real Estate"],
    "gyo": ["Real Estate"],
    "malzeme": ["Materials"],
    "kimya": ["Chemicals"],
    "maden": ["Mining"],
    "celik": ["Steel"],
    "havacilik": ["Airlines", "Airports"],
}


def _load_catalog() -> list[dict]:
    if not CATALOG_FILE.exists():
        return []
    with CATALOG_FILE.open("r", encoding="utf-8") as file:
        return json.load(file)


def get_global_event_source_catalog() -> GlobalEventSourceCatalogResponse:
    items = [GlobalEventSourceItem(**item) for item in _load_catalog()]
    return GlobalEventSourceCatalogResponse(total=len(items), items=items)


def _dedupe(values: list[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        current = (value or "").strip()
        if not current:
            continue
        key = current.lower()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(current)
    return normalized


def _normalize_sector_name(raw_value: str) -> list[str]:
    current = (raw_value or "").strip()
    lowered = current.lower()
    if lowered in IGNORED_PLACEHOLDER_VALUES:
        return []
    if lowered in SECTOR_ALIAS_MAP:
        return SECTOR_ALIAS_MAP[lowered]

    matched: list[str] = []
    seen: set[str] = set()
    for company in list_company_records():
        if company.sector.lower() == lowered and company.sector not in seen:
            seen.add(company.sector)
            matched.append(company.sector)
    return matched or [current]


def _normalize_sectors(values: list[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        for sector in _normalize_sector_name(value):
            if sector in seen:
                continue
            seen.add(sector)
            normalized.append(sector)
    return normalized


def _derive_tickers(affected_sectors: list[str], affected_tickers: list[str]) -> list[str]:
    normalized_tickers = []
    for ticker in affected_tickers:
        current = ticker.upper().strip()
        if not current or current.lower() in IGNORED_PLACEHOLDER_VALUES:
            continue
        normalized_tickers.append(current)
    seen = set(normalized_tickers)
    derived = list(normalized_tickers)
    if affected_sectors:
        for company in list_company_records():
            if company.sector not in affected_sectors:
                continue
            if company.ticker in seen:
                continue
            seen.add(company.ticker)
            derived.append(company.ticker)
    return derived


def _normalize_sector_overrides(values: list[SectorImpactOverride]) -> list[SectorImpactOverride]:
    normalized: list[SectorImpactOverride] = []
    for override in values:
        sectors = _normalize_sectors(override.sectors)
        positive_impacts = _dedupe(override.positive_impacts)
        negative_impacts = _dedupe(override.negative_impacts)
        if not sectors:
            continue
        if not positive_impacts and not negative_impacts:
            continue
        normalized.append(
            SectorImpactOverride(
                sectors=sectors,
                positive_impacts=positive_impacts,
                negative_impacts=negative_impacts,
            )
        )
    return normalized


def _build_ticker_impacts(
    ticker: str,
    base_positive_impacts: list[str],
    base_negative_impacts: list[str],
    sector_overrides: list[SectorImpactOverride],
) -> tuple[list[str], list[str]]:
    company = get_company_record(ticker)
    sector = company.sector if company is not None else None

    positive_impacts = list(base_positive_impacts)
    negative_impacts = list(base_negative_impacts)

    if sector is not None:
        for override in sector_overrides:
            if sector not in override.sectors:
                continue
            positive_impacts.extend(override.positive_impacts)
            negative_impacts.extend(override.negative_impacts)

    return _dedupe(positive_impacts), _dedupe(negative_impacts)


def preview_global_event(payload: PreviewGlobalEventRequest) -> PreviewGlobalEventResponse:
    normalized_sectors = _normalize_sectors(payload.affected_sectors)
    _normalize_sector_overrides(payload.sector_impact_overrides)
    derived_tickers = _derive_tickers(normalized_sectors, payload.affected_tickers)
    return PreviewGlobalEventResponse(
        headline=payload.headline,
        event_category=payload.event_category,
        region=payload.region,
        published_at=payload.published_at,
        source_name=payload.source_name,
        affected_sectors=normalized_sectors,
        derived_tickers=derived_tickers,
        sector_count=len(normalized_sectors),
        ticker_count=len(derived_tickers),
        status="previewed",
    )


def _ingest_global_event(payload: IngestGlobalEventRequest, repair_existing: bool = False) -> IngestGlobalEventResponse:
    normalized_sectors = _normalize_sectors(payload.affected_sectors)
    normalized_sector_overrides = _normalize_sector_overrides(payload.sector_impact_overrides)
    derived_tickers = _derive_tickers(normalized_sectors, payload.affected_tickers)
    if not derived_tickers:
        return IngestGlobalEventResponse(
            headline=payload.headline,
            event_category=payload.event_category,
            region=payload.region,
            published_at=payload.published_at,
            source_name=payload.source_name,
            affected_sectors=normalized_sectors,
            tickers=[],
            ticker_count=0,
            status="skipped",
        )

    saved_tickers: list[str] = []
    for ticker in derived_tickers:
        positive_impacts, negative_impacts = _build_ticker_impacts(
            ticker=ticker,
            base_positive_impacts=_dedupe(payload.base_positive_impacts),
            base_negative_impacts=_dedupe(payload.base_negative_impacts),
            sector_overrides=normalized_sector_overrides,
        )
        writer = replace_macro_event if repair_existing else ingest_macro_event
        writer(
            IngestMacroEventRequest(
                ticker=ticker,
                latest_macro_event=payload.headline,
                positive_impacts=positive_impacts,
                negative_impacts=negative_impacts,
                event_category=payload.event_category,
                region=payload.region,
                published_at=payload.published_at,
            )
        )
        saved_tickers.append(ticker)

    return IngestGlobalEventResponse(
        headline=payload.headline,
        event_category=payload.event_category,
        region=payload.region,
        published_at=payload.published_at,
        source_name=payload.source_name,
        affected_sectors=normalized_sectors,
        tickers=saved_tickers,
        ticker_count=len(saved_tickers),
        status="saved",
    )


def ingest_global_event(payload: IngestGlobalEventRequest) -> IngestGlobalEventResponse:
    return _ingest_global_event(payload, repair_existing=False)


def repair_global_event(payload: IngestGlobalEventRequest) -> IngestGlobalEventResponse:
    return _ingest_global_event(payload, repair_existing=True)
