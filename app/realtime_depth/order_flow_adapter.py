"""realtime_depth modulunu, ana mimarinin zaten bildigi OrderBookPressureResponse
sozlesmesine cevirir. Boylece trading_agent_signal_service.py gibi tuketiciler
canli WebSocket kaynagini, REST tabanli get_order_book_pressure() ile ayni
sekle sokup kullanabilir - Garanti'ye ozel karmasiklik burada, tek dosyada kalir.
"""
from __future__ import annotations

from app.models.schemas import OrderBookLevel, OrderBookPressureResponse
from app.realtime_depth.service import get_latest_depth, subscribe_ticker

REALTIME_DEPTH_SOURCE_NAME = "matriks_realtime_depth_ws"


def _pressure_bucket(imbalance: float | None) -> str:
    if imbalance is None:
        return "unavailable"
    if imbalance >= 2.0:
        return "strong_bid_pressure"
    if imbalance >= 1.25:
        return "bid_pressure"
    if imbalance > 0.8:
        return "balanced"
    if imbalance > 0.5:
        return "ask_pressure"
    return "strong_ask_pressure"


def _unavailable(ticker: str, message: str) -> OrderBookPressureResponse:
    return OrderBookPressureResponse(
        ticker=ticker.upper(),
        available=False,
        bid_total_quantity=0,
        ask_total_quantity=0,
        bid_ask_imbalance=None,
        pressure_bucket="unavailable",
        top_bid_price=None,
        top_ask_price=None,
        top_bid_quantity=None,
        top_ask_quantity=None,
        bid_levels=[],
        ask_levels=[],
        source=REALTIME_DEPTH_SOURCE_NAME,
        message=message,
    )


def get_realtime_order_book_pressure(ticker: str, max_age_seconds: float = 30.0) -> OrderBookPressureResponse:
    snapshot = get_latest_depth(ticker, max_age_seconds=max_age_seconds)
    if snapshot is None or (not snapshot.bid_levels and not snapshot.ask_levels):
        # Bu ticker'a henuz abone olunmamis olabilir; ilerideki cagrilar veri
        # bulsun diye simdi abone oluyoruz (bu cagri icin veri hazir olmayacak).
        subscribe_ticker(ticker)
        return _unavailable(ticker, "Canli derinlik verisi henuz yok (yeni abone olundu, birazdan hazir olacak).")

    bid_total = sum(level.quantity for level in snapshot.bid_levels)
    ask_total = sum(level.quantity for level in snapshot.ask_levels)
    imbalance = round(bid_total / ask_total, 3) if ask_total > 0 else None

    return OrderBookPressureResponse(
        ticker=ticker.upper(),
        available=True,
        bid_total_quantity=bid_total,
        ask_total_quantity=ask_total,
        bid_ask_imbalance=imbalance,
        pressure_bucket=_pressure_bucket(imbalance),
        top_bid_price=snapshot.bid_levels[0].price if snapshot.bid_levels else None,
        top_ask_price=snapshot.ask_levels[0].price if snapshot.ask_levels else None,
        top_bid_quantity=snapshot.bid_levels[0].quantity if snapshot.bid_levels else None,
        top_ask_quantity=snapshot.ask_levels[0].quantity if snapshot.ask_levels else None,
        bid_levels=[OrderBookLevel(price=level.price, quantity=level.quantity) for level in snapshot.bid_levels],
        ask_levels=[OrderBookLevel(price=level.price, quantity=level.quantity) for level in snapshot.ask_levels],
        source=REALTIME_DEPTH_SOURCE_NAME,
        message=None,
    )
