"""realtime_trade_flow modulunu, ana mimarinin zaten bildigi
InstitutionalFlowResponse sozlesmesine cevirir. Boylece institutional_flow_service.py
gibi tuketiciler Garanti'ye ozel karmasikligi (WebSocket, protobuf, MQTT) hic
gormeden canli "Pay Islem Tarafi Esanli" verisini kullanabilir.

Yontem: her eslesen islemde alici/satici uye kodu geliyor (bkz. trade_message.py).
Bir uyenin belirli bir pencerede alici oldugu islemlerin toplami eksi satici
oldugu islemlerin toplami, o uyenin net pozisyonunu verir - taraf bayraginin
("a"/"s") tam anlamini bilmeye gerek kalmadan dogrudan hesaplanabilen, saglam
bir metrik.
"""
from __future__ import annotations

from collections import defaultdict

from app.models.schemas import InstitutionalFlowResponse
from app.realtime_trade_flow.member_codes import resolve_member_name
from app.realtime_trade_flow.service import get_recent_trades, subscribe_ticker

REALTIME_TRADE_FLOW_SOURCE_NAME = "matriks_realtime_trade_flow_ws"
_TOP_MEMBER_COUNT = 3
# En guclu taraf, karsi tarafin en az bu kat kadar agir basiyorsa yorum uretilir.
_DOMINANCE_RATIO = 1.5


def get_realtime_institutional_flow(ticker: str, max_age_seconds: float = 300.0) -> InstitutionalFlowResponse | None:
    trades = get_recent_trades(ticker, max_age_seconds=max_age_seconds)
    if not trades:
        # Bu ticker'a henuz abone olunmamis olabilir; ilerideki cagrilar veri
        # bulsun diye simdi abone oluyoruz (bu cagri icin veri hazir olmayacak).
        subscribe_ticker(ticker)
        return None

    member_net: dict[str, int] = defaultdict(int)
    total_quantity = 0
    for trade in trades:
        if trade.buyer_member_code:
            member_net[trade.buyer_member_code] += trade.quantity
        if trade.seller_member_code:
            member_net[trade.seller_member_code] -= trade.quantity
        total_quantity += trade.quantity

    ranked = sorted(member_net.items(), key=lambda item: item[1], reverse=True)
    top_buyers = [(code, qty) for code, qty in ranked if qty > 0][:_TOP_MEMBER_COUNT]
    top_sellers = sorted(
        ((code, qty) for code, qty in ranked if qty < 0), key=lambda item: item[1]
    )[:_TOP_MEMBER_COUNT]

    buyer_text = ", ".join(
        f"{resolve_member_name(code)} (+{qty:,} lot)" for code, qty in top_buyers
    ) or "yok"
    seller_text = ", ".join(
        f"{resolve_member_name(code)} ({qty:,} lot)" for code, qty in top_sellers
    ) or "yok"

    latest_view = (
        f"Son {len(trades)} eslesmede toplam {total_quantity:,} lot islem gordu. "
        f"En guclu net alici uye(ler): {buyer_text}. En guclu net satici uye(ler): {seller_text}."
    )

    positive_factors: list[str] = []
    negative_factors: list[str] = []

    if top_buyers:
        leader_code, leader_qty = top_buyers[0]
        opposing_qty = abs(top_sellers[0][1]) if top_sellers else 0
        if opposing_qty == 0 or leader_qty >= opposing_qty * _DOMINANCE_RATIO:
            positive_factors.append(
                f"{resolve_member_name(leader_code)} net {leader_qty:,} lot ile baskin alici konumunda."
            )

    if top_sellers:
        leader_code, leader_qty = top_sellers[0]
        opposing_qty = top_buyers[0][1] if top_buyers else 0
        if opposing_qty == 0 or abs(leader_qty) >= opposing_qty * _DOMINANCE_RATIO:
            negative_factors.append(
                f"{resolve_member_name(leader_code)} net {abs(leader_qty):,} lot ile baskin satici konumunda."
            )

    return InstitutionalFlowResponse(
        ticker=ticker.upper(),
        latest_view=latest_view,
        positive_factors=positive_factors,
        negative_factors=negative_factors,
        source=REALTIME_TRADE_FLOW_SOURCE_NAME,
    )
