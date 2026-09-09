"""get_paper_decision_resolved_performance_summary() icin regresyon testleri.

Bu dosya bilerek "her adimi anlat" mantigiyla yazildi (bkz. konusma) - QA
bakis acisiyla okunabilir olsun diye yorumlar biraz fazla ayrintili.

Neden bu fonksiyon secildi: win_rate hesabi bu proje suresince gercekten
bug'liydi (yanlis payda kullaniliyordu - "resolved_count" yerine
"decided_count" olmasi gerekiyordu). Asagidaki testler o hatanin bir daha
GERI GELMEMESINI garanti eden birer "regresyon testi".
"""
from __future__ import annotations

from app.models.schemas import (
    PaperDecisionLogHistoryResponse,
    PaperDecisionLogItem,
    PaperDecisionOutcomeHistoryResponse,
    PaperDecisionOutcomeResponse,
)
from app.services import paper_decision_log_service as service


def _make_outcome(log_id: int, outcome_label: str, close_return_percent: float | None = None) -> PaperDecisionOutcomeResponse:
    """Bir PaperDecisionOutcomeResponse insa eder. Testte onemli olan tek
    alan outcome_label - digerleri gecerli bir nesne kurmak icin gereken
    ama testin sonucunu etkilemeyen "dolgu" degerler."""
    return PaperDecisionOutcomeResponse(
        log_id=log_id,
        ticker="TEST",
        source_mode="scan",
        timeframe="1G",
        horizon_bars=10,
        evaluated_bars=10,
        decision_timestamp="2026-09-01T10:00:00",
        decision_price=100.0,
        close_return_percent=close_return_percent,
        entry_zone_touched=False,
        breakout_buy_trigger_hit=False,
        take_profit_hit=(outcome_label == "win"),
        stop_loss_hit=(outcome_label == "loss"),
        outcome_label=outcome_label,
        outcome_summary=f"test outcome: {outcome_label}",
    )


def _make_log_item(log_id: int, stance: str = "neutral") -> PaperDecisionLogItem:
    return PaperDecisionLogItem(
        id=log_id,
        ticker="TEST",
        source_mode="scan",
        question="",
        stance=stance,
        action="hold",
        confidence=0.5,
        weighted_score=0.0,
        decision_price=100.0,
        recommendation_summary="",
        used_sources=[],
    )


def _patch_dependencies(monkeypatch, outcome_labels: list[str]) -> None:
    """outcome_labels listesindeki her etiket icin bir sahte karar kaydi
    uretir, get_paper_decision_outcomes/get_paper_decision_history
    cagrilarini bu sahte veriyle degistirir (gercek DB/ag hic devreye
    girmez)."""
    outcomes = [_make_outcome(i, label) for i, label in enumerate(outcome_labels)]
    history_items = [_make_log_item(i) for i in range(len(outcome_labels))]

    monkeypatch.setattr(
        service,
        "get_paper_decision_outcomes",
        lambda **kwargs: PaperDecisionOutcomeHistoryResponse(total=len(outcomes), items=outcomes),
    )
    monkeypatch.setattr(
        service,
        "get_paper_decision_history",
        lambda **kwargs: PaperDecisionLogHistoryResponse(total=len(history_items), items=history_items),
    )


def test_win_rate_excludes_open_outcomes_from_denominator(monkeypatch):
    # REGRESYON TESTI: bu proje suresince gercek bug buydu. 3 win, 2 loss,
    # 1 mixed, 4 open (henuz karara baglanmamis) verelim.
    # Eski (hatali) kod: win_rate = win / resolved_count = 3 / 10 = 0.30
    # Dogru kod:         win_rate = win / decided_count  = 3 / 6  = 0.50
    # "open" sonuclar KARARSIZ demektir (ne kazandi ne kaybetti, hala
    # izleniyor) - paydaya girmemeli.
    labels = ["win", "win", "win", "loss", "loss", "mixed", "open", "open", "open", "open"]
    _patch_dependencies(monkeypatch, labels)

    result = service.get_paper_decision_resolved_performance_summary()

    assert result.decided_count == 6  # 3 win + 2 loss + 1 mixed
    assert result.resolved_win_rate == 0.5
    assert result.resolved_loss_rate == round(2 / 6, 2)


def test_win_rate_is_none_when_nothing_is_decided(monkeypatch):
    # SINIR DEGERI (boundary value): hicbir karar henuz win/loss/mixed
    # olarak sonuclanmamissa (hepsi "open" veya "pending"), payda 0 olur.
    # 0'a bolme hatasi vermek yerine None donmeli - "veri yok" ile
    # "basari orani %0" birbirinden farkli anlamlar tasir.
    labels = ["open", "open", "pending"]
    _patch_dependencies(monkeypatch, labels)

    result = service.get_paper_decision_resolved_performance_summary()

    assert result.decided_count == 0
    assert result.resolved_win_rate is None
    assert result.resolved_loss_rate is None


def test_win_rate_all_wins(monkeypatch):
    # SINIR DEGERI: tum kararlar kazandiysa oran tam olarak 1.0 olmali.
    labels = ["win", "win", "win"]
    _patch_dependencies(monkeypatch, labels)

    result = service.get_paper_decision_resolved_performance_summary()

    assert result.resolved_win_rate == 1.0
    assert result.resolved_loss_rate == 0.0


def test_win_rate_all_losses(monkeypatch):
    # SINIR DEGERI: tum kararlar kaybettiyse oran tam olarak 0.0 olmali.
    labels = ["loss", "loss"]
    _patch_dependencies(monkeypatch, labels)

    result = service.get_paper_decision_resolved_performance_summary()

    assert result.resolved_win_rate == 0.0
    assert result.resolved_loss_rate == 1.0
