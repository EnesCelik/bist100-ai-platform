"""Piyasa acilmadan once potansiyel guclu hareket adaylarini yakalayip,
acilistan hemen sonra onceden belirlenmis tetik/iptal seviyeleriyle
teyit edip pozisyon acan iki asamali mekanizma.

Neden bu dosya var: `market_scan_service.scan_opening_candidates()` fiyat
degisimi/hacim oranina dayanir - bu sinyaller ancak piyasa acildiktan
DAKIKALAR sonra anlamli hale gelir (hacim birikmesi gerekir). Bu da
gercekten guclenen hisseleri (orn. 2026-09-11'de EKGYO, EFOR) sistemin
"tek gunluk karar" ani icin cok gec fark etmesine yol aciyordu - kullanici
bunu canli sistemde yakaladi ve "onceden gormeliyiz, teyitten sonra degil"
dedi.

Cozum: `market_scan_service.scan_pre_open_limit_up_candidates()` zaten
ONCEKI GUNUN kapanis gucune ve pre-open referans fiyatina bakarak potansiyel
adaylari SAATLERCE once (piyasa acilmadan) belirleyebiliyor, ve her aday
icin zaten bir `trigger_price` (teyit seviyesi) ve `invalidation_price`
(iptal seviyesi) hesapliyor - bu iki fonksiyon o altyapiyi yeniden
icat etmeden asama asama kullaniyor:

1. `scout_pre_open_candidates()` - pre-open penceresinde (~09:30-09:55)
   veya oncesinde cagrilir, "watch_preopen" etiketli adaylari dondurur.
2. `confirm_and_open_scouted_candidates()` - piyasa acildiktan kisa sure
   sonra cagrilir, her adayin CANLI fiyatini trigger/invalidation
   seviyeleriyle karsilastirir, sadece gercekten teyit edilenleri acar.
"""
from __future__ import annotations

from datetime import datetime

from app.data_sources.market_data.provider import get_market_snapshot
from app.models.schemas import (
    PaperTradeOpenResponse,
    PreOpenScoutCandidate,
    PreOpenScoutConfirmationItem,
    PreOpenScoutConfirmResponse,
    PreOpenScoutResponse,
)
from app.services.market_scan_service import scan_pre_open_limit_up_candidates
from app.services.paper_trade_simulation_service import create_manual_basket
from app.models.schemas import ManualBasketCreateRequest, ManualBasketPositionRequest

# Sadece en yuksek inanc seviyesindeki ("watch_preopen") adaylari aliyoruz -
# "secondary_watch" etiketliler daha zayif sinyal, sermaye tahsisi icin
# yeterince guvenilir degil.
_SCOUT_EXECUTION_ACTION = "watch_preopen"
_DEFAULT_MIN_SCORE = 55.0


def scout_pre_open_candidates(
    limit: int = 10,
    universe_code: str = "bist100",
    min_score: float = _DEFAULT_MIN_SCORE,
) -> PreOpenScoutResponse:
    scan = scan_pre_open_limit_up_candidates(limit=max(limit * 3, limit), universe_code=universe_code)
    filtered = [
        item
        for item in scan.items
        if item.execution_action == _SCOUT_EXECUTION_ACTION and item.limit_up_probability_score >= min_score
    ][:limit]

    return PreOpenScoutResponse(
        generated_at=datetime.utcnow().isoformat(),
        universe_size=scan.universe_size,
        total=len(filtered),
        items=[
            PreOpenScoutCandidate(
                ticker=item.ticker,
                company_name=item.company_name,
                sector=item.sector,
                limit_up_probability_score=item.limit_up_probability_score,
                execution_action=item.execution_action,
                previous_close=item.previous_close,
                trigger_price=item.trigger_price,
                invalidation_price=item.invalidation_price,
                reasons=item.reasons,
                risks=item.risks,
            )
            for item in filtered
        ],
    )


def _confirmation_status(
    trigger_price: float | None,
    invalidation_price: float | None,
    live_price: float | None,
) -> tuple[str, str]:
    """Saf karar fonksiyonu (ag/DB'ye dokunmaz) - test edilebilir olsun diye ayri.

    - live_price yoksa (Matriks disi kaynak / veri gelmedi): "pending"
    - live_price invalidation_price'a inmis/altina dusmusse: "invalidated"
    - live_price trigger_price'a ulasmis/gecmisse: "confirmed"
    - ikisinin arasindaysa: "pending" (henuz karar anı degil)
    """
    if live_price is None:
        return "pending", "Canli fiyat alinamadi (Matriks disi kaynak veya veri yok)."
    if invalidation_price is not None and live_price <= invalidation_price:
        return "invalidated", f"Fiyat iptal seviyesinin ({invalidation_price}) altina/esitine dustu."
    if trigger_price is not None and live_price >= trigger_price:
        return "confirmed", f"Fiyat tetik seviyesini ({trigger_price}) gecti/esitledi."
    return "pending", "Fiyat tetik ile iptal seviyesi arasinda; henuz teyit yok."


def _allocate_scout_capital(
    confirmed: list[PreOpenScoutCandidate],
    total_capital: float,
    cash_buffer: float,
    max_single_position_percent: float = 0.22,
) -> dict[str, float]:
    """Skora agirlikli, tek pozisyona ust sinirli sermaye dagilimi.

    `trading_agent_signal_service.allocate_capital_by_score` ile ayni
    felsefe (skor-50 tabani, oransal dagilim, tek pozisyon tavani) ama
    farkli bir aday tipi (PreOpenScoutCandidate) uzerinde calistigi icin
    ayri, kucuk bir fonksiyon olarak tutuluyor."""
    investable = max(total_capital - cash_buffer, 0.0)
    if not confirmed or investable <= 0:
        return {}

    weights = {item.ticker: max(item.limit_up_probability_score - 50.0, 5.0) for item in confirmed}
    total_weight = sum(weights.values()) or 1.0
    max_single = total_capital * max_single_position_percent
    raw = {ticker: investable * weight / total_weight for ticker, weight in weights.items()}
    return {ticker: round(min(amount, max_single), 2) for ticker, amount in raw.items()}


def confirm_and_open_scouted_candidates(
    strategy_name: str,
    limit: int = 10,
    universe_code: str = "bist100",
    min_score: float = _DEFAULT_MIN_SCORE,
    total_capital: float = 100000.0,
    cash_buffer: float = 10000.0,
) -> PreOpenScoutConfirmResponse:
    scout = scout_pre_open_candidates(limit=limit, universe_code=universe_code, min_score=min_score)

    confirmation_items: list[PreOpenScoutConfirmationItem] = []
    confirmed_candidates: list[PreOpenScoutCandidate] = []
    live_prices: dict[str, float] = {}

    for candidate in scout.items:
        snapshot = get_market_snapshot(candidate.ticker, force_refresh=True)
        live_price = (
            float(snapshot.last_price) if snapshot is not None and "matriks" in snapshot.source.lower() else None
        )
        status, reason = _confirmation_status(candidate.trigger_price, candidate.invalidation_price, live_price)
        if live_price is not None:
            live_prices[candidate.ticker] = live_price
        confirmation_items.append(
            PreOpenScoutConfirmationItem(
                ticker=candidate.ticker,
                status=status,
                live_price=live_price,
                trigger_price=candidate.trigger_price,
                invalidation_price=candidate.invalidation_price,
                capital_allocated=None,
                reason=reason,
            )
        )
        if status == "confirmed":
            confirmed_candidates.append(candidate)

    allocations = _allocate_scout_capital(confirmed_candidates, total_capital=total_capital, cash_buffer=cash_buffer)
    for item in confirmation_items:
        if item.ticker in allocations:
            item.capital_allocated = allocations[item.ticker]

    opened: PaperTradeOpenResponse | None = None
    if allocations:
        basket = ManualBasketCreateRequest(
            strategy_name=strategy_name,
            positions=[
                ManualBasketPositionRequest(
                    ticker=ticker,
                    entry_price=live_prices[ticker],
                    capital_allocated=capital,
                    scenario="pre_open_scout_confirmed",
                )
                for ticker, capital in allocations.items()
            ],
        )
        opened = create_manual_basket(basket)

    return PreOpenScoutConfirmResponse(
        generated_at=datetime.utcnow().isoformat(),
        strategy_name=strategy_name,
        checked_count=len(confirmation_items),
        confirmed_count=len(confirmed_candidates),
        items=confirmation_items,
        opened=opened,
    )
