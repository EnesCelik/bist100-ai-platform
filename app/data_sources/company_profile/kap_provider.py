import re
from functools import lru_cache
from urllib import error, request

from app.core.config import settings


_SECTOR_ROW_PATTERN = re.compile(
    r'\\"sectorName\\":\\"([^\\"]+)\\".*?'
    r'\\"stockCode\\":\\"([^\\"]+)\\".*?'
    r'\\"title\\":\\"([^\\"]+)\\"',
    re.S,
)

_MAIN_ROW_PATTERN = re.compile(
    r'\\"mainSectorName\\":\\"([^\\"]+)\\".*?'
    r'\\"stockCode\\":\\"([^\\"]+)\\".*?'
    r'\\"title\\":\\"([^\\"]+)\\"',
    re.S,
)


def _expand_stock_codes(raw_stock_code: str) -> list[str]:
    parts = [part.strip().upper() for part in raw_stock_code.split(",")]
    return [part for part in parts if part]


@lru_cache(maxsize=1)
def _load_sector_index() -> dict[str, dict]:
    req = request.Request(settings.kap_sectors_url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with request.urlopen(req, timeout=settings.kap_timeout_seconds) as response:
            html = response.read().decode("utf-8", "ignore")
    except (error.URLError, error.HTTPError, TimeoutError):
        return {}

    sector_rows: dict[str, tuple[str, str]] = {}
    for sector_name, stock_code, title in _SECTOR_ROW_PATTERN.findall(html):
        for ticker in _expand_stock_codes(stock_code):
            sector_rows[ticker] = (sector_name, title)

    main_rows: dict[str, tuple[str, str]] = {}
    for main_sector_name, stock_code, title in _MAIN_ROW_PATTERN.findall(html):
        for ticker in _expand_stock_codes(stock_code):
            main_rows[ticker] = (main_sector_name, title)

    payload: dict[str, dict] = {}
    for ticker in set(sector_rows) | set(main_rows):
        sector_name, sector_title = sector_rows.get(ticker, (None, None))
        main_sector_name, main_title = main_rows.get(ticker, (None, None))
        raw_name = sector_title or main_title
        raw_sector = main_sector_name or sector_name
        raw_industry = sector_name
        if not any([raw_name, raw_sector, raw_industry]):
            continue
        payload[ticker] = {
            "ticker": ticker,
            "raw_name": raw_name,
            "raw_sector": raw_sector,
            "raw_industry": raw_industry,
            "provider": "kap_official_sectors",
        }
    return payload


def fetch_company_profile(ticker: str) -> dict | None:
    return _load_sector_index().get(ticker.upper())
