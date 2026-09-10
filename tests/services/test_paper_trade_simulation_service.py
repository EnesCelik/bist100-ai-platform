"""Paper-trading simulasyon motorunun temel hesap mantigina testler.

Kapsam bilerek DB/ag gerektirmeyen "saf" fonksiyonlarla sinirli tutuldu:
stop/hedef tetikleme, kar-zarar (PnL) matematigi, kar koruma (profit
protection) mantigi. Bunlar, kullanicinin canli simulasyonda gordugu her
rakamin (orn. "GUBRF -609.4 TL zararla kapandi") arkasindaki gercek
hesaplama - dolayisiyla burada bir hata, ekranda sessizce yanlis bir
zarar/kar rakami olarak cikar.

Iki test (GUBRF ve TUPRS regresyonlari) bilerek 2026-09-10'da canli
sistemden gozlemlenen gercek sayilarla kuruldu - "hesap motoru o gun
gordugumuz rakami hala uretiyor mu" sorusuna dogrudan cevap verir.
"""
from __future__ import annotations

from app.core.config import settings
from app.db.models import PaperTrade
from app.services.paper_trade_simulation_service import (
    _apply_profit_protection,
    _open_unrealized_pnl,
    _outcome_for_trade,
    _realized_pnl,
    _remaining_capital,
    _remaining_percent,
    _return_percent,
    _total_position_pnl,
    _update_trade_with_price,
)


def _make_trade(
    *,
    entry_price: float,
    stop_price: float,
    target_1_price: float,
    target_2_price: float,
    capital_allocated: float = 22000.0,
    current_price: float | None = None,
    realized_percent: float = 0.0,
    realized_return_percent: float = 0.0,
    current_return_percent: float = 0.0,
    max_intraday_return_percent: float = 0.0,
    stop_hit: bool = False,
    hit_2_percent: bool = False,
    hit_3_percent: bool = False,
    hit_limit_up: bool = False,
    profit_protected: bool = False,
) -> PaperTrade:
    """DB'ye hic dokunmadan bellekte bir PaperTrade satiri kurar.

    Not: SQLAlchemy'de mapped_column(default=...) degerleri sadece satir
    DB'ye flush edilirken uygulanir - burada satiri hic commit etmedigimiz
    icin test edilen fonksiyonlarin okudugu her alani elle set ediyoruz."""
    price = current_price if current_price is not None else entry_price
    return PaperTrade(
        ticker="TEST",
        company_name="Test A.S.",
        sector="Test",
        strategy_name="test_strategy",
        scenario="agent_candidate",
        status="open",
        outcome="open",
        opportunity_score=0.0,
        confidence=0.0,
        data_quality="manual",
        entry_price=entry_price,
        capital_allocated=capital_allocated,
        current_price=price,
        max_seen_price=price,
        min_seen_price=price,
        target_1_price=target_1_price,
        target_2_price=target_2_price,
        stop_price=stop_price,
        close_price=None,
        current_return_percent=current_return_percent,
        max_intraday_return_percent=max_intraday_return_percent,
        min_intraday_return_percent=current_return_percent,
        hit_2_percent=hit_2_percent,
        hit_3_percent=hit_3_percent,
        hit_limit_up=hit_limit_up,
        stop_hit=stop_hit,
        profit_protected=profit_protected,
        realized_percent=realized_percent,
        realized_price=None,
        realized_return_percent=realized_return_percent,
        protected_stop_price=None,
        source_scan_payload={},
        why_now=[],
        risks=[],
    )


# ---------------------------------------------------------------------------
# _return_percent: getiri yuzdesi hesabinin temel matematigi
# ---------------------------------------------------------------------------

def test_return_percent_positive_and_negative():
    assert _return_percent(price=102.0, entry_price=100.0) == 2.0
    assert _return_percent(price=98.0, entry_price=100.0) == -2.0


def test_return_percent_zero_entry_price_does_not_divide_by_zero():
    # SINIR DEGERI: entry_price 0 veya negatifse (bozuk veri), ZeroDivisionError
    # patlatmak yerine 0.0 donmeli - ustteki cagiranlar bunu "notr" sayar.
    assert _return_percent(price=100.0, entry_price=0.0) == 0.0


# ---------------------------------------------------------------------------
# _update_trade_with_price: stop/hedef tetikleme mantigi
# Bu, kullanicinin bugun GUBRF'te canli gordugu "stop_hit: true" davranisinin
# kaynagi - burada bir hata olursa sistem stop'u kacirir veya erken tetikler.
# ---------------------------------------------------------------------------

def test_stop_hit_triggers_at_exact_boundary():
    # SINIR DEGERI: fiyat TAM stop seviyesine esitse de tetiklenmeli (<=), sadece
    # altina inince degil - kod "price <= row.stop_price" kullaniyor.
    row = _make_trade(entry_price=100.0, stop_price=97.5, target_1_price=102.0, target_2_price=103.0)
    _update_trade_with_price(row, price=97.5)
    assert row.stop_hit is True


def test_stop_not_hit_just_above_boundary():
    row = _make_trade(entry_price=100.0, stop_price=97.5, target_1_price=102.0, target_2_price=103.0)
    _update_trade_with_price(row, price=97.51)
    assert row.stop_hit is False


def test_stop_hit_is_sticky_across_ticks():
    # Bir kere tetiklenen stop, sonraki tikte fiyat toparlansa bile "tetiklendi"
    # olarak kalmali - "row.stop_hit or price <= stop_price" mantigi bunu saglar.
    row = _make_trade(entry_price=100.0, stop_price=97.5, target_1_price=102.0, target_2_price=103.0)
    _update_trade_with_price(row, price=97.0)
    assert row.stop_hit is True
    _update_trade_with_price(row, price=99.0)  # fiyat toparlandi
    assert row.stop_hit is True  # ama stop hala tetiklenmis sayilmali


def test_hit_2_and_3_percent_track_max_seen_price_not_current_price():
    # Hedeflere "o an" degil "gorulen en yuksek fiyata" gore bakiliyor - fiyat
    # hedefi gecip geri dustugunde bile hedefin vurulmus sayilmasi gerekiyor.
    row = _make_trade(entry_price=100.0, stop_price=95.0, target_1_price=102.0, target_2_price=105.0)
    _update_trade_with_price(row, price=103.0)  # hedef1'i gecti, hedef2'yi gecmedi
    assert row.hit_2_percent is True
    assert row.hit_3_percent is False
    _update_trade_with_price(row, price=101.0)  # geri cekildi
    assert row.hit_2_percent is True  # hala vurulmus sayilmali (sticky)


def test_update_trade_with_price_regression_gubrf_2026_09_10():
    # REGRESYON: 2026-09-10 canli sisteminde GUBRF - giris 523.0, stop 509.925.
    # Fiyat 509.5'e dustugunde gercek sistemde stop_hit: true gozlemlendi.
    row = _make_trade(entry_price=523.0, stop_price=509.925, target_1_price=533.46, target_2_price=538.69)
    _update_trade_with_price(row, price=509.5)
    assert row.stop_hit is True
    assert row.current_return_percent == _return_percent(509.5, 523.0)


# ---------------------------------------------------------------------------
# PnL matematigi: realized/unrealized/toplam kar-zarar
# Iki regresyon testi, kullanicinin bugun ekranda gordugu GERCEK TL rakamlariyla
# kuruldu (bkz. 2026-09-10 simulasyon oturumu).
# ---------------------------------------------------------------------------

def test_open_unrealized_pnl_regression_tuprs_2026_09_10():
    # REGRESYON: TUPRS, 22.000 TL sermaye, hic realize edilmemis (%0), guncel
    # getiri -1.43%. Canli sistemde open_unrealized_pnl = -314.6 TL gozlemlendi.
    row = _make_trade(
        entry_price=420.0,
        stop_price=409.5,
        target_1_price=428.4,
        target_2_price=432.6,
        capital_allocated=22000.0,
        realized_percent=0.0,
        current_return_percent=-1.43,
    )
    assert _open_unrealized_pnl(row) == -314.6


def test_realized_pnl_regression_gubrf_2026_09_10():
    # REGRESYON: GUBRF, 22.000 TL sermaye, %100 realize edildi (tam kapandi),
    # realize getiri -2.77%. Canli sistemde realized_pnl = -609.4 TL gozlemlendi.
    row = _make_trade(
        entry_price=523.0,
        stop_price=509.925,
        target_1_price=533.46,
        target_2_price=538.69,
        capital_allocated=22000.0,
        realized_percent=100.0,
        realized_return_percent=-2.77,
    )
    assert _realized_pnl(row) == -609.4


def test_total_position_pnl_is_sum_of_realized_and_unrealized():
    # Kismen kapatilmis (orn. %50 realize) bir pozisyonda toplam PnL, realize
    # edilen kismin karidi/zarari ile hala acik kalan kismin PnL'inin toplami
    # olmali - iki taraf da ayni capital_allocated uzerinden ama farkli
    # yuzdelerle (realized_percent / kalan yuzde) agirliklandiriliyor.
    row = _make_trade(
        entry_price=100.0,
        stop_price=95.0,
        target_1_price=102.0,
        target_2_price=103.0,
        capital_allocated=10000.0,
        realized_percent=50.0,
        realized_return_percent=2.0,  # ilk yarisi +%2'den realize edildi
        current_return_percent=-1.0,  # kalan yarisi su an -%1'de
    )
    realized = _realized_pnl(row)  # 10000 * 0.5 * 0.02 = 100.0
    unrealized = _open_unrealized_pnl(row)  # 10000 * 0.5 * -0.01 = -50.0
    assert realized == 100.0
    assert unrealized == -50.0
    assert _total_position_pnl(row) == 50.0


def test_remaining_capital_after_partial_realize():
    row = _make_trade(
        entry_price=100.0,
        stop_price=95.0,
        target_1_price=102.0,
        target_2_price=103.0,
        capital_allocated=10000.0,
        realized_percent=50.0,
    )
    assert _remaining_percent(row) == 50.0
    assert _remaining_capital(row) == 5000.0


def test_remaining_percent_cannot_go_negative():
    # SINIR DEGERI: realized_percent 100'u gecerse (olmamali ama), kalan yuzde
    # negatife dusmemeli - max(0.0, ...) ile korunuyor.
    row = _make_trade(
        entry_price=100.0,
        stop_price=95.0,
        target_1_price=102.0,
        target_2_price=103.0,
        realized_percent=120.0,
    )
    assert _remaining_percent(row) == 0.0


# ---------------------------------------------------------------------------
# Kar koruma (profit protection): belirli bir getiriye ulasinca pozisyonun bir
# kismini otomatik "realize edilmis" saymasi ve stop'u yukari cekmesi.
# ---------------------------------------------------------------------------

def test_profit_protection_locks_in_gains_at_level_1_boundary():
    assert settings.paper_trade_protect_profit_enabled is True
    row = _make_trade(
        entry_price=100.0,
        stop_price=95.0,
        target_1_price=110.0,
        target_2_price=120.0,
        capital_allocated=10000.0,
        max_intraday_return_percent=settings.paper_trade_protect_level_1_percent,  # tam esik: %2
    )
    _apply_profit_protection(row)
    assert row.profit_protected is True
    assert row.realized_percent == settings.paper_trade_protect_level_1_realized_percent  # %50
    expected_stop = round(100.0 * (1 + settings.paper_trade_protect_level_1_stop_gain_percent / 100.0), 4)
    assert row.stop_price == expected_stop
    assert row.stop_price > 100.0  # stop artik giris fiyatinin USTUNDE - "kar korumasi"


def test_profit_protection_does_not_undo_higher_existing_realized_percent():
    # Seviye 2 tetiklenip %70 realize edilmisken, fiyat gerileyip max_intraday
    # tekrar hesaplansa bile (max_seen_price hic dusmez, bu senaryo teorik) -
    # zaten daha yuksek realized_percent varsa asagi cekilmemeli.
    row = _make_trade(
        entry_price=100.0,
        stop_price=95.0,
        target_1_price=110.0,
        target_2_price=120.0,
        max_intraday_return_percent=settings.paper_trade_protect_level_1_percent,  # sadece seviye 1'i tetikler (%2)
        realized_percent=70.0,  # ama zaten seviye 2'den %70 realize edilmis
    )
    _apply_profit_protection(row)
    assert row.realized_percent == 70.0  # %50'ye DUSMEMELI


def test_profit_protection_level_2_locks_in_more_than_level_1():
    row = _make_trade(
        entry_price=100.0,
        stop_price=95.0,
        target_1_price=110.0,
        target_2_price=120.0,
        max_intraday_return_percent=settings.paper_trade_protect_level_2_percent,  # %3
    )
    _apply_profit_protection(row)
    assert row.realized_percent == settings.paper_trade_protect_level_2_realized_percent  # %70


# ---------------------------------------------------------------------------
# _outcome_for_trade: win/loss/neutral siniflandirmasi
# ---------------------------------------------------------------------------

def test_outcome_is_win_when_target_hit():
    row = _make_trade(entry_price=100.0, stop_price=95.0, target_1_price=102.0, target_2_price=103.0, hit_2_percent=True)
    assert _outcome_for_trade(row) == "win"


def test_outcome_is_loss_when_stop_hit():
    row = _make_trade(entry_price=100.0, stop_price=95.0, target_1_price=102.0, target_2_price=103.0, stop_hit=True)
    assert _outcome_for_trade(row) == "loss"


def test_outcome_is_loss_when_return_below_threshold_even_without_stop_hit():
    # -%2.5 esigi, stop_price'tan BAGIMSIZ ayri bir "kotu gidiyor" isareti.
    row = _make_trade(
        entry_price=100.0, stop_price=95.0, target_1_price=102.0, target_2_price=103.0,
        current_return_percent=-2.6,
    )
    assert _outcome_for_trade(row) == "loss"


def test_outcome_is_neutral_otherwise():
    row = _make_trade(
        entry_price=100.0, stop_price=95.0, target_1_price=102.0, target_2_price=103.0,
        current_return_percent=0.3,
    )
    assert _outcome_for_trade(row) == "neutral"
