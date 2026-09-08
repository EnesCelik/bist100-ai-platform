from __future__ import annotations

import contextlib
import io
import re
import threading
from datetime import UTC, datetime, timedelta
from typing import Any

import isyatirimhisse as isy
import pandas as pd

from app.models.schemas import FundamentalResponse

FUNDAMENTAL_SOURCE = "isyatirimhisse_financial_statements"

# Bankalar/finans kuruluslari (financial_group=2/3) ile sanayi sirketleri (financial_group=1)
# ayni kalem kodlarini farkli anlamlarda kullaniyor (orn. GARAN icin kod "2AA" bilancoda
# "Finansal Borclar" degil "Bankanin dahil oldugu risk grubunun mevduati" anlamina geliyor).
# Bu yuzden kalemleri kod yerine normalize edilmis isim eslesmesiyle buluyoruz.
_FINANCIAL_GROUPS = ("1", "2", "3")
_CACHE_TTL = timedelta(hours=24)
_PERIOD_PATTERN = re.compile(r"^(\d{4})/(\d{1,2})$")

_CACHE: dict[str, tuple[datetime, FundamentalResponse | None]] = {}
_CACHE_LOCK = threading.Lock()


def _normalize_item_name(raw_name: Any) -> str:
    name = str(raw_name).strip().upper()
    # Python'un varsayilan upper() cevrimi kucuk "i"yi ASCII "I" yapar ama kaynak
    # veride bazi basliklar zaten noktali "I" ile geliyor; ikisini tek forma indirger.
    name = name.replace("İ", "I")
    name = re.sub(r"^\d+(\.\d+)?\s+", "", name)
    name = re.sub(r"^[IVXLCM]+\.\s+", "", name)
    return name.strip()


def _find_row(df: pd.DataFrame, include_any: list[str], exclude_any: list[str] | None = None) -> pd.Series | None:
    normalized = df["FINANCIAL_ITEM_NAME_TR"].map(_normalize_item_name)
    included = normalized.apply(lambda name: any(term in name for term in include_any))
    if exclude_any:
        excluded = normalized.apply(lambda name: any(term in name for term in exclude_any))
        included = included & ~excluded
    matches = df[included]
    return matches.iloc[0] if not matches.empty else None


def _to_float(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if result == result else None  # NaN kontrolu


def _sorted_periods(df: pd.DataFrame) -> list[str]:
    periods = [column for column in df.columns if _PERIOD_PATTERN.fullmatch(str(column))]
    return sorted(periods, key=lambda period: tuple(int(part) for part in period.split("/")))


def _latest_period_with_value(row: pd.Series, periods: list[str]) -> str | None:
    for period in reversed(periods):
        if _to_float(row.get(period)) is not None:
            return period
    return None


def _prior_year_period(period: str) -> str:
    match = _PERIOD_PATTERN.fullmatch(period)
    year, month = match.groups()
    return f"{int(year) - 1}/{month}"


def _fetch_financial_rows(ticker: str) -> tuple[str, pd.DataFrame] | None:
    end_year = datetime.now(UTC).year
    for financial_group in _FINANCIAL_GROUPS:
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                df = isy.fetch_financials(
                    ticker,
                    start_year=end_year - 2,
                    end_year=end_year,
                    financial_group=financial_group,
                )
        except Exception:
            continue
        if df is not None and not df.empty:
            return financial_group, df
    return None


def _build_fundamental_response(ticker: str) -> FundamentalResponse | None:
    fetched = _fetch_financial_rows(ticker)
    if fetched is None:
        return None
    financial_group, df = fetched
    is_bank_like = financial_group in {"2", "3"}

    assets_row = _find_row(df, ["TOPLAM VARLIKLAR", "AKTIF TOPLAMI", "TOPLAM AKTIFLER"])
    equity_row = _find_row(df, ["ÖZKAYNAKLAR"], exclude_any=["ANA ORTAKLIĞA", "AZINLIK"])
    net_income_row = _find_row(df, ["DÖNEM KARI", "NET DÖNEM KARI"], exclude_any=["VERGI", "DAĞILIM", "AZINLIK"])
    revenue_row = _find_row(df, ["SATIŞ GELIRLERI", "NET FAIZ GELIRI"])

    if assets_row is None or equity_row is None or net_income_row is None:
        return None

    periods = _sorted_periods(df)
    latest_period = _latest_period_with_value(assets_row, periods)
    if latest_period is None:
        return None
    prior_period = _prior_year_period(latest_period)

    assets = _to_float(assets_row.get(latest_period))
    equity = _to_float(equity_row.get(latest_period))
    net_income = _to_float(net_income_row.get(latest_period))
    net_income_prior = _to_float(net_income_row.get(prior_period))
    revenue = _to_float(revenue_row.get(latest_period)) if revenue_row is not None else None
    revenue_prior = _to_float(revenue_row.get(prior_period)) if revenue_row is not None else None

    positive_factors: list[str] = []
    risk_factors: list[str] = []

    revenue_label = "faaliyet geliri" if is_bank_like else "satis geliri"

    if revenue is not None and revenue_prior:
        revenue_growth = (revenue - revenue_prior) / abs(revenue_prior) * 100
        if revenue_growth >= 10:
            positive_factors.append(f"{revenue_label.capitalize()} bir onceki yilin ayni donemine gore %{revenue_growth:.1f} buyudu")
        elif revenue_growth <= -5:
            risk_factors.append(f"{revenue_label.capitalize()} bir onceki yilin ayni donemine gore %{abs(revenue_growth):.1f} geriledi")

    if net_income is not None and net_income_prior is not None:
        if net_income < 0 <= net_income_prior:
            risk_factors.append(f"Sirket {latest_period} doneminde zarar acikladi, bir onceki yil ayni donemde kardaydi")
        elif net_income_prior != 0:
            net_income_growth = (net_income - net_income_prior) / abs(net_income_prior) * 100
            if net_income_growth >= 10:
                positive_factors.append(f"Net kar bir onceki yilin ayni donemine gore %{net_income_growth:.1f} artti")
            elif net_income_growth <= -10:
                risk_factors.append(f"Net kar bir onceki yilin ayni donemine gore %{abs(net_income_growth):.1f} geriledi")

    if revenue and net_income is not None:
        net_margin = net_income / revenue * 100
        if net_margin >= 10:
            positive_factors.append(f"Net kar marji %{net_margin:.1f} ile guclu")
        elif net_margin < 0:
            risk_factors.append(f"Net kar marji negatif (%{net_margin:.1f})")

    if equity:
        period_month = int(latest_period.split("/")[1])
        annualized_net_income = net_income * (12 / period_month) if net_income is not None else None
        if annualized_net_income is not None:
            roe = annualized_net_income / equity * 100
            if roe >= 20:
                positive_factors.append(f"Yillik bazda ozkaynak karliligi (ROE) %{roe:.1f} ile guclu")
            elif roe < 5:
                risk_factors.append(f"Yillik bazda ozkaynak karliligi (ROE) %{roe:.1f} ile zayif")

        if assets is not None:
            leverage = assets / equity
            leverage_risk_threshold = 15.0 if is_bank_like else 4.0
            if not is_bank_like and leverage < 1.5:
                positive_factors.append(f"Borcluluk seviyesi dusuk, varlik/ozkaynak orani {leverage:.1f}x")
            elif leverage >= leverage_risk_threshold:
                risk_factors.append(f"Kaldirac orani {leverage:.1f}x ile yuksek")

    if not positive_factors and not risk_factors:
        return None

    summary = f"{ticker} icin son aciklanan {latest_period} donemi mali tablolarina gore {len(positive_factors)} olumlu, {len(risk_factors)} riskli faktor tespit edildi."

    return FundamentalResponse(
        ticker=ticker,
        summary=summary,
        positive_factors=positive_factors[:4],
        risk_factors=risk_factors[:4],
        source=FUNDAMENTAL_SOURCE,
    )


def get_fundamental_summary(ticker: str, use_cache_only: bool = False) -> FundamentalResponse | None:
    normalized_ticker = ticker.strip().upper()
    if not normalized_ticker:
        return None

    now = datetime.now(UTC)
    with _CACHE_LOCK:
        cached = _CACHE.get(normalized_ticker)
    if cached is not None and now - cached[0] < _CACHE_TTL:
        return cached[1]

    if use_cache_only:
        # Tum evreni tarayan toplu scan akislari icin: her ticker basina
        # ~3-10 saniyelik canli fetch'i burada tetiklemek /scan/market'i
        # dakikalarca bloke ediyordu. Cache soguksa bu turu atlayip
        # bekleyen istekleri hizli tutuyoruz; tekil ticker sorgusu (ask_service)
        # hala canli fetch yapar ve cache'i isitir.
        return None

    try:
        response = _build_fundamental_response(normalized_ticker)
    except Exception:
        response = None

    with _CACHE_LOCK:
        _CACHE[normalized_ticker] = (now, response)
    return response
