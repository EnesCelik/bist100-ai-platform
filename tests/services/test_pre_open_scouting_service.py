"""Pre-open scouting (asama-1 tarama + asama-2 teyit/acma) mantigina testler.

2026-09-11'de kullanicinin canli sistemde yakaladigi soruna dogrudan cevap:
opening-plan gunde bir kez, piyasa acilir acilmaz calisiyordu ve gercekte
guclenen hisseleri (orn. EFOR) kaciriyordu - cunku hacim teyidine dayali
skorlama hacim birikmeden anlamsizdi. Cozum onceki gunun kapanis gucunden
ureyen bir "scout" listesi + acilistan sonra trigger/invalidation
seviyeleriyle teyit eden ayri bir asama. Burada test edilen, o teyit
kararinin (`_confirmation_status`) ve sermaye dagitiminin (`_allocate_scout_capital`)
saf mantigi - ag/DB gerektirmeyen kisim."""
from __future__ import annotations

from app.models.schemas import PreOpenScoutCandidate
from app.services.pre_open_scouting_service import _allocate_scout_capital, _confirmation_status


def _make_candidate(ticker: str, score: float) -> PreOpenScoutCandidate:
    return PreOpenScoutCandidate(
        ticker=ticker,
        company_name=ticker,
        sector="Test",
        limit_up_probability_score=score,
        execution_action="watch_preopen",
        previous_close=100.0,
        trigger_price=104.0,
        invalidation_price=97.0,
        reasons=[],
        risks=[],
    )


# ---------------------------------------------------------------------------
# _confirmation_status: canli fiyatin trigger/invalidation'a gore siniflandirilmasi
# ---------------------------------------------------------------------------

def test_confirmed_when_price_at_or_above_trigger():
    # SINIR DEGERI: tam trigger'a esit olsa da onaylanmali (>=).
    status, _ = _confirmation_status(trigger_price=104.0, invalidation_price=97.0, live_price=104.0)
    assert status == "confirmed"


def test_confirmed_when_price_above_trigger():
    status, _ = _confirmation_status(trigger_price=104.0, invalidation_price=97.0, live_price=105.5)
    assert status == "confirmed"


def test_invalidated_when_price_at_or_below_invalidation():
    # SINIR DEGERI: tam invalidation seviyesine esit olsa da iptal sayilmali (<=).
    status, _ = _confirmation_status(trigger_price=104.0, invalidation_price=97.0, live_price=97.0)
    assert status == "invalidated"


def test_pending_between_trigger_and_invalidation():
    status, _ = _confirmation_status(trigger_price=104.0, invalidation_price=97.0, live_price=100.0)
    assert status == "pending"


def test_pending_when_live_price_missing():
    # Matriks disi/eksik veri: asla "confirmed" sayilmamali - sessizce yanlis
    # fiyattan pozisyon acmayi onlemenin garantisi.
    status, reason = _confirmation_status(trigger_price=104.0, invalidation_price=97.0, live_price=None)
    assert status == "pending"
    assert "Canli fiyat" in reason


def test_pending_when_trigger_and_invalidation_both_missing():
    status, _ = _confirmation_status(trigger_price=None, invalidation_price=None, live_price=110.0)
    assert status == "pending"


# ---------------------------------------------------------------------------
# _allocate_scout_capital: skor agirlikli, tek pozisyona ust sinirli dagilim
# ---------------------------------------------------------------------------

def test_allocate_capital_empty_when_no_confirmed_candidates():
    assert _allocate_scout_capital([], total_capital=100000.0, cash_buffer=10000.0) == {}


def test_allocate_capital_splits_proportional_to_score_above_50():
    # Iki aday, biri digerinden guclu (agirlik = skor - 50, taban 5).
    strong = _make_candidate("STRONG", score=90.0)  # agirlik 40
    weak = _make_candidate("WEAK", score=60.0)  # agirlik 10
    allocations = _allocate_scout_capital([strong, weak], total_capital=100000.0, cash_buffer=10000.0, max_single_position_percent=1.0)
    investable = 90000.0
    assert allocations["STRONG"] == round(investable * 40 / 50, 2)
    assert allocations["WEAK"] == round(investable * 10 / 50, 2)


def test_allocate_capital_respects_max_single_position_cap():
    # Tek aday olsa bile tum yatirilabilir sermayeyi tek pozisyona vermez -
    # tek pozisyon tavani (max_single_position_percent * total_capital) uygulanir.
    only = _make_candidate("ONLY", score=95.0)
    allocations = _allocate_scout_capital([only], total_capital=100000.0, cash_buffer=10000.0, max_single_position_percent=0.22)
    assert allocations["ONLY"] == 22000.0  # 90000 tum yatirilabilir sermaye olurdu ama tavan 22000


def test_allocate_capital_score_floor_prevents_zero_weight():
    # Skor 50 veya altinda bile olsa agirlik en az 5 - sifir bolme riski yok,
    # cok zayif bir aday da orantisiz kucuk de olsa pay alir (secilmis olmasi
    # zaten bir onaydir, agirligin sifira dusmesi anlamsiz olurdu).
    borderline = _make_candidate("BORDERLINE", score=50.0)
    strong = _make_candidate("STRONG", score=90.0)
    allocations = _allocate_scout_capital([borderline, strong], total_capital=100000.0, cash_buffer=10000.0, max_single_position_percent=1.0)
    assert allocations["BORDERLINE"] > 0
    assert allocations["BORDERLINE"] < allocations["STRONG"]


def test_allocate_capital_zero_when_investable_is_zero_or_negative():
    only = _make_candidate("ONLY", score=90.0)
    assert _allocate_scout_capital([only], total_capital=10000.0, cash_buffer=10000.0) == {}
    assert _allocate_scout_capital([only], total_capital=10000.0, cash_buffer=15000.0) == {}
