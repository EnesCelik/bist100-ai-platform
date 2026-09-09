"""BIST acilis oncesi (pre-open) esitleme verisinden alici/satici baskisini
cikarir.

Acilis auksiyonunda henuz gercek islem olmadan borsa, teorik eslesme
fiyati/miktari ile birlikte o fiyattan eslesmeden kalan fazla alis/satis
miktarini da yayinlar. Bu, piyasa acilmadan once hangi hissede alici mi
satici mi baskin oldugunu gormemizi saglar. Sadece pre-open penceresinde
(BIST icin yaklasik 09:30-09:55 TR) anlamli veri doner - normal seansta
bu alanlar bos/sifir gelir ve `available=False` doner.
"""
from __future__ import annotations

from datetime import datetime

from app.data_sources.company_data.provider import list_company_records
from app.data_sources.market_data.matriks_provider import fetch_pre_open_equilibrium
from app.models.schemas import (
    PreOpenImbalanceResponse,
    PreOpenImbalanceScanItem,
    PreOpenImbalanceScanResponse,
)

PRE_OPEN_SOURCE_NAME = "matriks_pre_open_equilibrium"
# Net dengesizlik, teorik eslesme hacminin bu yuzdesini asarsa "guclu" sayilir.
_STRONG_THRESHOLD_PERCENT = 50.0
_MODERATE_THRESHOLD_PERCENT = 15.0


def _pressure_bucket(imbalance_percent: float | None) -> str:
    if imbalance_percent is None:
        return "unavailable"
    if imbalance_percent >= _STRONG_THRESHOLD_PERCENT:
        return "strong_buy_pressure"
    if imbalance_percent >= _MODERATE_THRESHOLD_PERCENT:
        return "buy_pressure"
    if imbalance_percent > -_MODERATE_THRESHOLD_PERCENT:
        return "balanced"
    if imbalance_percent > -_STRONG_THRESHOLD_PERCENT:
        return "sell_pressure"
    return "strong_sell_pressure"


def _unavailable(ticker: str, message: str) -> PreOpenImbalanceResponse:
    return PreOpenImbalanceResponse(
        ticker=ticker.upper(),
        available=False,
        equilibrium_price=None,
        equilibrium_quantity=None,
        remaining_bid_quantity=None,
        remaining_ask_quantity=None,
        net_imbalance_quantity=None,
        imbalance_percent=None,
        pressure_bucket="unavailable",
        source=PRE_OPEN_SOURCE_NAME,
        message=message,
    )


def get_pre_open_imbalance(ticker: str) -> PreOpenImbalanceResponse:
    data = fetch_pre_open_equilibrium(ticker)
    if data is None:
        return _unavailable(
            ticker,
            "Acilis oncesi esitleme verisi su an yok (piyasa acik olabilir ya da "
            "veri henuz yayinlanmadi - bu alanlar sadece BIST pre-open penceresinde dolar).",
        )

    remaining_bid = data["remaining_bid_quantity"] or 0
    remaining_ask = data["remaining_ask_quantity"] or 0
    equilibrium_quantity = data["equilibrium_quantity"] or 0
    net_imbalance = remaining_bid - remaining_ask
    imbalance_percent = (
        round(net_imbalance / equilibrium_quantity * 100, 1) if equilibrium_quantity > 0 else None
    )

    return PreOpenImbalanceResponse(
        ticker=ticker.upper(),
        available=True,
        equilibrium_price=data["equilibrium_price"],
        equilibrium_quantity=data["equilibrium_quantity"],
        remaining_bid_quantity=remaining_bid,
        remaining_ask_quantity=remaining_ask,
        net_imbalance_quantity=net_imbalance,
        imbalance_percent=imbalance_percent,
        pressure_bucket=_pressure_bucket(imbalance_percent),
        source=PRE_OPEN_SOURCE_NAME,
        message=None,
    )


def scan_pre_open_imbalance(limit: int = 10, universe_code: str = "bist100") -> PreOpenImbalanceScanResponse:
    companies = list_company_records(universe_code=universe_code)
    items: list[PreOpenImbalanceScanItem] = []

    for company in companies:
        result = get_pre_open_imbalance(company.ticker)
        if not result.available:
            continue
        items.append(
            PreOpenImbalanceScanItem(
                ticker=result.ticker,
                company_name=company.name,
                sector=company.sector,
                equilibrium_price=result.equilibrium_price,
                equilibrium_quantity=result.equilibrium_quantity,
                remaining_bid_quantity=result.remaining_bid_quantity or 0,
                remaining_ask_quantity=result.remaining_ask_quantity or 0,
                imbalance_percent=result.imbalance_percent,
                pressure_bucket=result.pressure_bucket,
            )
        )

    ranked_by_imbalance = sorted(
        items,
        key=lambda item: item.imbalance_percent if item.imbalance_percent is not None else 0.0,
        reverse=True,
    )
    top_buy_pressure = [item for item in ranked_by_imbalance if (item.imbalance_percent or 0) > 0][: max(limit, 1)]
    top_sell_pressure = list(
        reversed([item for item in ranked_by_imbalance if (item.imbalance_percent or 0) < 0][-max(limit, 1) :])
    )

    return PreOpenImbalanceScanResponse(
        generated_at=datetime.utcnow().isoformat(),
        universe_size=len(companies),
        available_count=len(items),
        top_buy_pressure=top_buy_pressure,
        top_sell_pressure=top_sell_pressure,
    )
