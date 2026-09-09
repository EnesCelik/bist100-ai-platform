"""Sistemin gercek gecmis basari oranini (paper karar gunlugunden) periyodik
olarak olcup onbelleğe alir, boylece analiz confidence hesabi her seferinde
pahali bir geriye-donuk hesap yapmadan gercek performansi gorebilir.

Neden ayri bir onbellek: get_paper_decision_resolved_performance_summary()
yuzlerce kayit icin OHLCV verisi cektigi icin birkaç dakika surebiliyor -
her analiz cagrisinda calistirmak pratik degil. Bu servis onu gunde bir kez
calistirip sonucu diske yazar; confidence hesabi sadece bu dosyayi okur.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from app.services.paper_decision_log_service import get_paper_decision_resolved_performance_summary

logger = logging.getLogger(__name__)

STATE_FILE = Path(__file__).resolve().parents[2] / "data" / "system_accuracy_state.json"
# En az bu kadar karara-baglanmis (win/loss/mixed) kayit yoksa oran gurultuludur,
# confidence'a karistirmiyoruz.
_MIN_DECIDED_SAMPLE = 30


@dataclass
class SystemAccuracySnapshot:
    resolved_win_rate: float | None
    decided_count: int
    computed_at: str


def refresh_system_accuracy_snapshot(limit: int = 500) -> SystemAccuracySnapshot:
    summary = get_paper_decision_resolved_performance_summary(limit=limit)
    snapshot = SystemAccuracySnapshot(
        resolved_win_rate=summary.resolved_win_rate,
        decided_count=summary.decided_count,
        computed_at=datetime.now(UTC).isoformat(),
    )
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(
        json.dumps(
            {
                "resolved_win_rate": snapshot.resolved_win_rate,
                "decided_count": snapshot.decided_count,
                "computed_at": snapshot.computed_at,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return snapshot


def get_cached_system_accuracy() -> SystemAccuracySnapshot | None:
    if not STATE_FILE.exists():
        return None
    try:
        payload = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return SystemAccuracySnapshot(
        resolved_win_rate=payload.get("resolved_win_rate"),
        decided_count=payload.get("decided_count", 0),
        computed_at=payload.get("computed_at", ""),
    )


def get_confidence_adjustment() -> float:
    """Gercek win_rate %50'den ne kadar sapiyorsa, confidence'a o yonde kucuk
    bir ayar uygular. Yeterli ornek yoksa 0 doner (etkisiz)."""
    snapshot = get_cached_system_accuracy()
    if snapshot is None or snapshot.resolved_win_rate is None:
        return 0.0
    if snapshot.decided_count < _MIN_DECIDED_SAMPLE:
        return 0.0
    # +-%50'den sapma, +-0.10 confidence sinirinda kirpilarak ekleniyor -
    # tek basina karari degistirmesin, ama sistemin gercek gecmisini gormezden de gelmesin.
    deviation = snapshot.resolved_win_rate - 0.5
    return max(-0.10, min(0.10, deviation * 0.5))
