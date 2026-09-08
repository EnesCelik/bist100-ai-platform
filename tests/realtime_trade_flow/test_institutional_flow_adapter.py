from app.realtime_trade_flow import institutional_flow_adapter
from app.realtime_trade_flow.trade_message import TradeTick


def _tick(buyer: str, seller: str, quantity: int) -> TradeTick:
    return TradeTick(
        symbol="GARAN",
        trade_id="1",
        price=131.2,
        quantity=quantity,
        side_flag="a",
        timestamp_raw=0,
        buyer_member_code=buyer,
        seller_member_code=seller,
    )


def test_no_trades_yet_subscribes_and_returns_none(monkeypatch):
    subscribed: list[str] = []
    monkeypatch.setattr(institutional_flow_adapter, "get_recent_trades", lambda ticker, max_age_seconds=300.0: [])
    monkeypatch.setattr(institutional_flow_adapter, "subscribe_ticker", subscribed.append)

    result = institutional_flow_adapter.get_realtime_institutional_flow("GARAN")

    assert result is None
    assert subscribed == ["GARAN"]


def test_dominant_buyer_produces_positive_factor(monkeypatch):
    # YKR uc farkli saticidan toplam 9000 lot aliyor (net +9000); satis tarafi
    # uc ayri uyeye (MLB/ZRY/TAC, her biri -3000) dagilmis oldugu icin hicbiri
    # tek basina baskin degil - sadece alici tarafinda net bir baskinlik var.
    trades = [
        _tick(buyer="YKR", seller="MLB", quantity=3000),
        _tick(buyer="YKR", seller="ZRY", quantity=3000),
        _tick(buyer="YKR", seller="TAC", quantity=3000),
    ]
    monkeypatch.setattr(institutional_flow_adapter, "get_recent_trades", lambda ticker, max_age_seconds=300.0: trades)

    result = institutional_flow_adapter.get_realtime_institutional_flow("GARAN")

    assert result is not None
    assert result.positive_factors  # baskin alici tespit edilmis olmali
    assert "Yapı Kredi" in result.positive_factors[0]
    assert not result.negative_factors  # tek bir satici baskin degil, satis dagilmis durumda


def test_balanced_flow_produces_no_dominance_factors(monkeypatch):
    # Alici ve satici hacimleri esit - hicbir taraf baskin degil.
    trades = [_tick(buyer="YKR", seller="MLB", quantity=1000)]
    monkeypatch.setattr(institutional_flow_adapter, "get_recent_trades", lambda ticker, max_age_seconds=300.0: trades)

    result = institutional_flow_adapter.get_realtime_institutional_flow("GARAN")

    assert result is not None
    assert result.positive_factors == []
    assert result.negative_factors == []
