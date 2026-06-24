from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from typing import Any

from pydantic import BaseModel, Field

from app.core.config import settings
from app.data_sources.company_data.provider import list_company_records
from app.models.schemas import IngestGlobalEventRequest, IngestNewsRequest, SectorImpactOverride
from app.services.global_event_service import ingest_global_event
from app.services.news_service import ingest_news


class GlobalNewsWatchCandidate(BaseModel):
    headline: str
    summary: str = ""
    source_name: str
    source_url: str = ""
    published_at: str
    event_category: str
    region: str
    confidence: float = Field(ge=0.0, le=1.0)
    affected_tickers: list[str] = Field(default_factory=list)
    affected_sectors: list[str] = Field(default_factory=list)
    positive_impacts: list[str] = Field(default_factory=list)
    negative_impacts: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    action: str = "watch"
    reason: str = ""


class GlobalNewsWatchResponse(BaseModel):
    generated_at: str
    source_count: int
    fetched_count: int
    candidate_count: int
    ingested_count: int
    source_fetch_counts: dict[str, int] = Field(default_factory=dict)
    source_candidate_counts: dict[str, int] = Field(default_factory=dict)
    source_ingested_counts: dict[str, int] = Field(default_factory=dict)
    candidates: list[GlobalNewsWatchCandidate]


RSS_FEEDS = [
    "https://www.aa.com.tr/tr/rss/default?cat=ekonomi",
    "https://www.trthaber.com/sondakika.rss",
]

GLOBAL_QUERY_TERMS = [
    "iran hormuz oil ceasefire",
    "middle east oil sanctions ceasefire",
    "fed rates inflation global markets",
]

ALLOWED_AUTO_INGEST_CATEGORIES = {
    "company_event",
    "geopolitical_deescalation",
    "energy",
    "rates",
}

GENERIC_COMPANY_WORDS = {
    "sanayi",
    "ticaret",
    "holding",
    "yatirim",
    "yatırım",
    "anonim",
    "sirketi",
    "şirketi",
    "ve",
}

TURKISH_POSITIVE_WORDS = {
    "anlasma",
    "anlaşma",
    "ateskes",
    "ateşkes",
    "baris",
    "barış",
    "acilis",
    "açılış",
    "dustu",
    "düştü",
    "gevseme",
    "gevşeme",
    "ihale",
    "sozlesme",
    "sözleşme",
    "geri alim",
    "geri alım",
    "temettu",
    "temettü",
    "bedelsiz",
}

TURKISH_NEGATIVE_WORDS = {
    "savas",
    "savaş",
    "saldiri",
    "saldırı",
    "gerilim",
    "yaptirim",
    "yaptırım",
    "ambargo",
    "abluka",
    "patlama",
    "iptal",
    "dava",
    "ceza",
    "zarar",
}

SECTOR_KEYWORDS = {
    "Banking": ["banka", "bankacilik", "bankacılık", "kredi", "risk primi"],
    "Airlines": ["havacilik", "havacılık", "ucus", "uçuş", "jet yakiti", "jet yakıtı", "thy", "pegasus"],
    "Airports": ["havalimani", "havalimanı", "tav", "yolcu"],
    "Defense": ["savunma", "savas", "savaş", "guvenlik", "güvenlik"],
    "Energy": ["petrol", "brent", "dogalgaz", "doğalgaz", "enerji", "hurmuz"],
    "Chemicals": ["petrokimya", "rafineri", "tupras", "tüpraş"],
    "Holding": ["holding", "risk istahi", "risk iştahı"],
    "Retail": ["perakende", "enflasyon", "tuketici", "tüketici"],
    "Industrials": ["sanayi", "ihracat", "lojistik"],
    "Steel": ["celik", "çelik", "demir"],
}

CATEGORY_KEYWORDS = {
    "geopolitical_deescalation": ["ateskes", "ateşkes", "baris", "barış", "hurmuz", "açıl", "acil", "mutabakat"],
    "geopolitics": ["savas", "savaş", "saldiri", "saldırı", "gerilim", "abluka", "yaptirim", "yaptırım"],
    "energy": ["petrol", "brent", "dogalgaz", "doğalgaz", "enerji", "hurmuz"],
    "rates": ["faiz", "enflasyon", "merkez bankasi", "merkez bankası", "fed", "tcmb"],
    "company_event": ["kap", "ihale", "sozlesme", "sözleşme", "bedelsiz", "temettu", "temettü", "geri alim", "geri alım"],
}

GEOPOLITICAL_CONTEXT_WORDS = ["iran", "israil", "abd", "hormuz", "hurmuz", "orta dogu", "orta doğu", "yaptirim", "yaptırım", "savas", "savaş", "ateskes", "ateşkes"]

KAP_DEFAULT_MEMBER_TYPES = ["IGS", "DDK"]
KAP_DEFAULT_DISCLOSURE_TYPES = ["ODA", "FR", "DUY", "DG", "CA"]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _strip_html(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", value or "")
    return re.sub(r"\s+", " ", unescape(text)).strip()


def _normalize_text(value: str) -> str:
    return (value or "").casefold()


def _keyword_list(raw_value: str) -> list[str]:
    return [item.strip() for item in (raw_value or "").split(",") if item.strip()]


def _parse_published_at(value: str) -> str:
    raw = (value or "").strip()
    if not raw:
        return _now_iso()
    try:
        if re.fullmatch(r"\d{8}", raw):
            parsed = datetime.strptime(raw, "%Y%m%d").replace(tzinfo=timezone.utc)
            return parsed.isoformat()
        if re.fullmatch(r"\d{2}\.\d{2}\.\d{4}", raw):
            parsed = datetime.strptime(raw, "%d.%m.%Y").replace(tzinfo=timezone.utc)
            return parsed.isoformat()
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
            parsed = datetime.strptime(raw, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            return parsed.isoformat()
        return parsedate_to_datetime(raw).astimezone(timezone.utc).isoformat()
    except Exception:
        return raw


def _fetch_json(url: str, timeout: float = 8.0) -> dict[str, Any] | list[Any] | None:
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "bist100-ai-platform/0.1"})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8", errors="replace"))
    except Exception:
        return None


def _post_json(url: str, payload: dict[str, Any], timeout: float = 8.0) -> dict[str, Any] | list[Any] | None:
    try:
        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=body,
            headers={
                "User-Agent": "bist100-ai-platform/0.1",
                "Content-Type": "application/json",
                "Accept": "application/json, text/plain, */*",
                "Origin": "https://www.kap.org.tr",
                "Referer": "https://www.kap.org.tr/en",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8", errors="replace"))
    except Exception:
        return None


def _fetch_text(url: str, timeout: float = 8.0) -> str | None:
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "bist100-ai-platform/0.1"})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read().decode("utf-8", errors="replace")
    except Exception:
        return None


def _fetch_rss_candidates(limit: int) -> list[dict[str, str]]:
    candidates: list[dict[str, str]] = []
    for feed_url in RSS_FEEDS:
        payload = _fetch_text(feed_url, timeout=settings.kap_timeout_seconds)
        if not payload:
            continue
        try:
            root = ET.fromstring(payload)
        except ET.ParseError:
            continue
        for item in root.findall(".//item")[:limit]:
            title = _strip_html(item.findtext("title") or "")
            summary = _strip_html(item.findtext("description") or "")
            link = _strip_html(item.findtext("link") or feed_url)
            published = _parse_published_at(_strip_html(item.findtext("pubDate") or ""))
            if title:
                candidates.append(
                    {
                        "headline": title,
                        "summary": summary,
                        "source_url": link,
                        "published_at": published,
                        "source_name": "turkey_finance_rss",
                    }
                )
    return candidates[:limit]


def _fetch_gdelt_candidates(limit: int) -> list[dict[str, str]]:
    candidates: list[dict[str, str]] = []
    keywords = _keyword_list(settings.global_news_watch_keywords) or GLOBAL_QUERY_TERMS
    query = " OR ".join(keywords[:8])
    params = {
        "query": query,
        "mode": "ArtList",
        "format": "json",
        "maxrecords": str(min(max(limit, 1), 50)),
        "sort": "DateDesc",
    }
    url = "https://api.gdeltproject.org/api/v2/doc/doc?" + urllib.parse.urlencode(params)
    payload = _fetch_json(url, timeout=8.0)
    if not isinstance(payload, dict):
        return []
    for article in payload.get("articles", [])[:limit]:
        title = _strip_html(str(article.get("title", "")))
        if not title:
            continue
        candidates.append(
            {
                "headline": title,
                "summary": _strip_html(str(article.get("sourceCountry", ""))),
                "source_url": str(article.get("url", "")),
                "published_at": _parse_published_at(str(article.get("seendate", ""))[:8]),
                "source_name": "gdelt",
            }
        )
    return candidates


def _fetch_x_watch_candidates(limit: int) -> list[dict[str, str]]:
    if not settings.x_finance_watch_enabled or not settings.x_bearer_token:
        return []

    keywords = _keyword_list(settings.x_finance_watch_keywords)
    accounts = _keyword_list(settings.x_finance_watch_accounts)

    keyword_clause = " OR ".join(f'"{keyword}"' for keyword in keywords[:8]) if keywords else ""
    account_clause = " OR ".join(f"from:{account.lstrip('@')}" for account in accounts[:8]) if accounts else ""
    query_parts = [part for part in [keyword_clause, account_clause] if part]
    if not query_parts:
        return []

    query = " OR ".join(f"({part})" for part in query_parts) + " lang:tr -is:retweet"
    params = {
        "query": query,
        "max_results": str(min(max(limit, 10), 50)),
        "tweet.fields": "created_at,author_id,lang,text",
    }
    url = "https://api.x.com/2/tweets/search/recent?" + urllib.parse.urlencode(params)
    try:
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": "bist100-ai-platform/0.1",
                "Authorization": f"Bearer {settings.x_bearer_token}",
            },
        )
        with urllib.request.urlopen(request, timeout=8.0) as response:
            payload = json.loads(response.read().decode("utf-8", errors="replace"))
    except Exception:
        return []

    items = payload.get("data", []) if isinstance(payload, dict) else []
    candidates: list[dict[str, str]] = []
    for item in items[:limit]:
        if not isinstance(item, dict):
            continue
        text = _strip_html(str(item.get("text", "")))
        tweet_id = str(item.get("id", "")).strip()
        if not text or not tweet_id:
            continue
        candidates.append(
            {
                "headline": text[:280],
                "summary": text,
                "source_url": f"https://x.com/i/web/status/{tweet_id}",
                "published_at": _parse_published_at(str(item.get("created_at", ""))),
                "source_name": "x_turkey_finance_watch",
            }
        )
    return candidates


def _extract_first_string(row: dict[str, Any], keys: list[str]) -> str:
    for key in keys:
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return _strip_html(value)
    return ""


def _extract_kap_rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if not isinstance(payload, dict):
        return []

    candidate_keys = [
        "items",
        "data",
        "list",
        "result",
        "disclosures",
        "notifications",
        "content",
    ]
    for key in candidate_keys:
        value = payload.get(key)
        if isinstance(value, list) and value and isinstance(value[0], dict):
            return value
        if isinstance(value, dict):
            nested = _extract_kap_rows(value)
            if nested:
                return nested

    for value in payload.values():
        if isinstance(value, dict):
            nested = _extract_kap_rows(value)
            if nested:
                return nested
    return []


def _build_kap_detail_url(row: dict[str, Any]) -> str:
    direct = _extract_first_string(row, ["url", "detailUrl", "link", "disclosureUrl"])
    if direct:
        if direct.startswith("http"):
            return direct
        return urllib.parse.urljoin("https://www.kap.org.tr", direct)

    for key in ["disclosureIndex", "disclosureId", "id", "basic"]:
        value = row.get(key)
        if isinstance(value, (int, float)):
            return f"https://www.kap.org.tr/en/Bildirim/{int(value)}"
        if isinstance(value, str) and value.strip().isdigit():
            return f"https://www.kap.org.tr/en/Bildirim/{value.strip()}"
    return "https://www.kap.org.tr/en"


def _fetch_kap_disclosures_candidates(limit: int) -> list[dict[str, str]]:
    if not settings.kap_watch_enabled:
        return []

    member_types = _keyword_list(settings.kap_watch_member_types) or KAP_DEFAULT_MEMBER_TYPES
    disclosure_types = _keyword_list(settings.kap_watch_disclosure_types) or KAP_DEFAULT_DISCLOSURE_TYPES
    today = datetime.now().strftime("%d.%m.%Y")
    base_url = settings.kap_backend_base_url.rstrip("/")
    path = settings.kap_disclosure_list_path.strip()
    if not path.startswith("/"):
        path = "/" + path
    endpoint = f"{base_url}{path}"
    payload_candidates = [
        {
            "fromDate": today,
            "toDate": today,
            "memberTypes": member_types,
        },
        {
            "fromDate": today,
            "toDate": today,
            "memberTypes": member_types,
            "notificationTypes": disclosure_types,
        },
        {
            "fromDate": today,
            "toDate": today,
            "memberTypes": member_types,
            "notificationTypes": disclosure_types,
            "fromSrc": "home",
        },
    ]
    rows: list[dict[str, Any]] = []
    for payload in payload_candidates:
        data = _post_json(endpoint, payload, timeout=settings.kap_timeout_seconds)
        rows = _extract_kap_rows(data)
        if rows:
            break

    candidates: list[dict[str, str]] = []
    for row in rows[: limit * 3]:
        headline = _extract_first_string(
            row,
            [
                "title",
                "subject",
                "headline",
                "summary",
                "disclosureType",
                "notificationType",
            ],
        )
        ticker = _extract_first_string(row, ["stockCode", "code", "ticker", "memberCode"])
        company_name = _extract_first_string(row, ["companyName", "titleName", "memberName", "name"])
        disclosure_type = _extract_first_string(row, ["disclosureType", "notificationType", "type"])
        summary = _extract_first_string(row, ["summary", "abstract", "description"])
        published_at = _parse_published_at(
            _extract_first_string(row, ["publishDate", "publishedAt", "date", "disclosureDate", "releaseDate"])
        )
        if not headline:
            parts = [part for part in [ticker, company_name, disclosure_type] if part]
            headline = " | ".join(parts)
        if not headline:
            continue
        candidates.append(
            {
                "headline": headline,
                "summary": " ".join(part for part in [company_name, summary, disclosure_type] if part).strip(),
                "source_url": _build_kap_detail_url(row),
                "published_at": published_at,
                "source_name": "kap_disclosures",
            }
        )
        if len(candidates) >= limit:
            break
    return candidates


def _detect_tickers(text: str) -> list[str]:
    normalized_text = f" {_normalize_text(text)} "
    detected: list[str] = []
    seen: set[str] = set()
    for company in list_company_records():
        ticker = company.ticker.upper()
        if re.search(rf"{re.escape(ticker.casefold())}", normalized_text):
            seen.add(ticker)
            detected.append(ticker)
            continue

        name_tokens = [
            part
            for part in re.split(r"\W+", company.name.casefold())
            if len(part) >= 5 and part not in GENERIC_COMPANY_WORDS
        ]
        meaningful_tokens = name_tokens[:2]
        if len(meaningful_tokens) >= 2 and all(f" {token} " in normalized_text for token in meaningful_tokens):
            if ticker not in seen:
                seen.add(ticker)
                detected.append(ticker)
    return detected[:12]


def _detect_sectors(text: str) -> list[str]:
    normalized = _normalize_text(text)
    sectors = [sector for sector, words in SECTOR_KEYWORDS.items() if any(word in normalized for word in words)]
    if any(word in normalized for word in ["hurmuz", "iran", "abd", "ateskes", "ateşkes", "baris", "barış"]):
        sectors.extend(["Banking", "Airlines", "Airports", "Holding", "Industrials"])
    return list(dict.fromkeys(sectors))[:10]


def _classify_category(text: str) -> str:
    normalized = _normalize_text(text)
    has_geopolitical_context = any(word in normalized for word in GEOPOLITICAL_CONTEXT_WORDS)

    if any(word in normalized for word in CATEGORY_KEYWORDS["company_event"]):
        return "company_event"
    if any(word in normalized for word in CATEGORY_KEYWORDS["rates"]):
        return "rates"
    if any(word in normalized for word in CATEGORY_KEYWORDS["energy"]):
        return "energy"
    if has_geopolitical_context and any(word in normalized for word in CATEGORY_KEYWORDS["geopolitical_deescalation"]):
        return "geopolitical_deescalation"
    if has_geopolitical_context and any(word in normalized for word in CATEGORY_KEYWORDS["geopolitics"]):
        return "geopolitics"
    return "general_market_news"


def _detect_region(text: str) -> str:
    normalized = _normalize_text(text)
    if any(word in normalized for word in ["iran", "hurmuz", "israil", "lübnan", "lubnan", "orta dogu", "orta doğu"]):
        return "middle_east"
    if any(word in normalized for word in ["turkiye", "türkiye", "tcmb", "kap", "bist"]):
        return "turkey"
    return "global"


def _impacts_for(category: str, text: str) -> tuple[list[str], list[str]]:
    normalized = _normalize_text(text)
    positives: list[str] = []
    negatives: list[str] = []
    if category == "geopolitical_deescalation":
        positives.extend([
            "Jeopolitik risk priminin azalmasi BIST risk istahini destekleyebilir",
            "Enerji ve lojistik maliyeti baskisinin azalmasi sektor rotasyonunu pozitif etkileyebilir",
        ])
    elif category == "geopolitics":
        negatives.extend([
            "Jeopolitik risk primi artabilir",
            "Enerji ve lojistik maliyeti baskisi yukselebilir",
        ])
    elif category == "energy":
        has_price_context = any(word in normalized for word in ["petrol fiyat", "brent", "dogalgaz fiyat", "doğalgaz fiyat", "enerji fiyat"])
        has_reserve_context = "rezerv" in normalized
        if has_price_context and not has_reserve_context and any(word in normalized for word in ["dustu", "düştü", "gevse", "gevşe", "geriledi", "gerile"]):
            positives.append("Petrol ve enerji maliyeti baskisinin azalmasi enerji ithalatcisi sektorleri destekleyebilir")
        else:
            negatives.append("Enerji fiyat oynakligi marj ve enflasyon beklentilerini baskilayabilir")
    elif category == "rates":
        negatives.append("Faiz/enflasyon beklentisi riskli varlik degerlemelerini etkileyebilir")
    elif category == "company_event":
        positives.append("Sirket bazli haber akisi hisseye ilgi yaratabilir")
    if any(word in normalized for word in TURKISH_POSITIVE_WORDS):
        positives.append("Baslik tonu pozitif erken sinyal uretiyor")
    if any(word in normalized for word in TURKISH_NEGATIVE_WORDS):
        negatives.append("Baslik tonu risk uyarisi uretiyor")
    return list(dict.fromkeys(positives)), list(dict.fromkeys(negatives))


def _confidence(source_name: str, tickers: list[str], sectors: list[str], positive: list[str], negative: list[str]) -> float:
    score = 0.35
    if source_name in {"kap_disclosures", "turkey_finance_rss"}:
        score += 0.25
    elif source_name in {"gdelt", "global_energy_geopolitics_watch"}:
        score += 0.18
    elif source_name == "x_turkey_finance_watch":
        score += 0.05
    if tickers:
        score += 0.18
    if sectors:
        score += 0.10
    if positive or negative:
        score += 0.08
    return round(min(score, 0.95), 2)


def _determine_action(category: str, tickers: list[str], sectors: list[str], confidence: float, positive: list[str], negative: list[str]) -> str:
    has_material_impact = bool(positive or negative) and category != "general_market_news"
    if category == "company_event" and tickers and confidence >= 0.50:
        return "ingest_company_news"
    if sectors and has_material_impact and confidence >= 0.55:
        return "ingest_global_event"
    if tickers and confidence >= 0.55:
        return "ingest_company_news"
    return "watch"


def _candidate_from_raw(raw: dict[str, str]) -> GlobalNewsWatchCandidate | None:
    headline = raw.get("headline", "").strip()
    summary = raw.get("summary", "").strip()
    if not headline:
        return None
    text = f"{headline} {summary}".strip()
    category = _classify_category(text)
    region = _detect_region(text)
    tickers = _detect_tickers(text)
    sectors = _detect_sectors(text)
    positive, negative = _impacts_for(category, text)
    confidence = _confidence(raw.get("source_name", ""), tickers, sectors, positive, negative)
    action = _determine_action(category, tickers, sectors, confidence, positive, negative)
    return GlobalNewsWatchCandidate(
        headline=headline,
        summary=summary,
        source_name=raw.get("source_name", "unknown"),
        source_url=raw.get("source_url", ""),
        published_at=_parse_published_at(raw.get("published_at", "") or datetime.now().date().isoformat()),
        event_category=category,
        region=region,
        confidence=confidence,
        affected_tickers=tickers,
        affected_sectors=sectors,
        positive_impacts=positive,
        negative_impacts=negative,
        tags=list(dict.fromkeys([category, region, raw.get("source_name", "unknown")])),
        action=action,
        reason="Resmi kaynak/RSS/global haber sinifi ve guven puani ile normalize edildi.",
    )


def _dedupe_candidates(candidates: list[GlobalNewsWatchCandidate]) -> list[GlobalNewsWatchCandidate]:
    seen: set[tuple[str, str]] = set()
    result: list[GlobalNewsWatchCandidate] = []
    for item in candidates:
        key = (item.headline.casefold(), item.source_url)
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _should_auto_ingest(candidate: GlobalNewsWatchCandidate) -> bool:
    if candidate.confidence < settings.global_news_watch_ingest_min_confidence:
        return False
    if candidate.event_category not in ALLOWED_AUTO_INGEST_CATEGORIES:
        return False
    if candidate.action == "ingest_global_event":
        return bool(candidate.affected_sectors)
    if candidate.action == "ingest_company_news":
        return bool(candidate.affected_tickers)
    return False


def _ingest_candidate(candidate: GlobalNewsWatchCandidate) -> bool:
    if candidate.action == "ingest_global_event" and candidate.affected_sectors:
        response = ingest_global_event(
            IngestGlobalEventRequest(
                headline=candidate.headline,
                event_category=candidate.event_category,
                region=candidate.region,
                published_at=candidate.published_at[:10],
                source_name=candidate.source_name,
                affected_sectors=candidate.affected_sectors,
                affected_tickers=candidate.affected_tickers,
                base_positive_impacts=candidate.positive_impacts,
                base_negative_impacts=candidate.negative_impacts,
                sector_impact_overrides=[
                    SectorImpactOverride(
                        sectors=["Airlines", "Airports"],
                        positive_impacts=["Haber havacilik/ulasim maliyet ve risk algisini etkileyebilir"],
                        negative_impacts=[],
                    )
                ],
            )
        )
        return response.status == "saved" and response.ticker_count > 0

    if candidate.action == "ingest_company_news" and candidate.affected_tickers:
        saved = False
        for ticker in candidate.affected_tickers:
            response = ingest_news(
                IngestNewsRequest(
                    ticker=ticker,
                    headline=candidate.headline,
                    summary=candidate.summary,
                    source_url=candidate.source_url,
                    publisher=candidate.source_name,
                    published_at=candidate.published_at[:10],
                    tags=candidate.tags,
                )
            )
            saved = saved or response.status == "saved"
        return saved
    return False


def run_global_news_watch(limit: int = 20, ingest: bool = False) -> GlobalNewsWatchResponse:
    raw_items: list[dict[str, str]] = []
    sources = {source.strip() for source in settings.global_news_watch_sources.split(",") if source.strip()}
    source_fetch_counts: dict[str, int] = {}
    if "turkey_finance_rss" in sources:
        rss_items = _fetch_rss_candidates(limit=limit)
        raw_items.extend(rss_items)
        source_fetch_counts["turkey_finance_rss"] = len(rss_items)
    if "gdelt" in sources or "global_energy_geopolitics_watch" in sources:
        gdelt_items = _fetch_gdelt_candidates(limit=limit)
        raw_items.extend(gdelt_items)
        source_fetch_counts["gdelt"] = len(gdelt_items)
    if "kap_disclosures" in sources:
        kap_items = _fetch_kap_disclosures_candidates(limit=limit)
        raw_items.extend(kap_items)
        source_fetch_counts["kap_disclosures"] = len(kap_items)
    if "x_turkey_finance_watch" in sources:
        x_items = _fetch_x_watch_candidates(limit=limit)
        raw_items.extend(x_items)
        source_fetch_counts["x_turkey_finance_watch"] = len(x_items)

    candidates = [candidate for raw in raw_items if (candidate := _candidate_from_raw(raw)) is not None]
    candidates = _dedupe_candidates(candidates)
    candidates = sorted(
        candidates,
        key=lambda item: (item.confidence, bool(item.affected_tickers), bool(item.affected_sectors), item.source_name == "kap_disclosures"),
        reverse=True,
    )[:limit]
    source_candidate_counts: dict[str, int] = {}
    for candidate in candidates:
        source_candidate_counts[candidate.source_name] = source_candidate_counts.get(candidate.source_name, 0) + 1

    ingested_count = 0
    source_ingested_counts: dict[str, int] = {}
    if ingest:
        for candidate in candidates:
            if not _should_auto_ingest(candidate):
                continue
            if _ingest_candidate(candidate):
                ingested_count += 1
                source_ingested_counts[candidate.source_name] = source_ingested_counts.get(candidate.source_name, 0) + 1

    return GlobalNewsWatchResponse(
        generated_at=_now_iso(),
        source_count=len(sources),
        fetched_count=len(raw_items),
        candidate_count=len(candidates),
        ingested_count=ingested_count,
        source_fetch_counts=source_fetch_counts,
        source_candidate_counts=source_candidate_counts,
        source_ingested_counts=source_ingested_counts,
        candidates=candidates,
    )
