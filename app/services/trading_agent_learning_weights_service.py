from __future__ import annotations

from datetime import datetime

from sqlalchemy import desc, select

from app.db.models import TradingAgentDecisionLog
from app.db.session import SessionLocal, ensure_runtime_schema
from app.models.schemas import TradingAgentLearningWeightsResponse
from app.services.trading_agent_decision_service import build_agent_learning_report


def build_next_session_weight_adjustments(
    trade_date: str | None = None,
    strategy_name: str | None = None,
) -> TradingAgentLearningWeightsResponse:
    report_date = trade_date or _latest_decision_date(strategy_name=strategy_name)
    report = build_agent_learning_report(trade_date=report_date, strategy_name=strategy_name)
    adjustments = {
        "volume_weight_delta": 0.0,
        "risk_penalty_delta": 0.0,
        "cash_buffer_delta_percent": 0.0,
        "min_agent_score_delta": 0.0,
    }
    rationale: list[str] = []

    if report.total_pnl < 0:
        adjustments["risk_penalty_delta"] += 2.0
        adjustments["cash_buffer_delta_percent"] += 5.0
        adjustments["min_agent_score_delta"] += 2.0
        rationale.append("Gunluk toplam PnL negatif; sonraki seansta risk cezasi ve nakit tamponu artirilmali.")

    weak_holds = [item for item in report.action_outcomes if item.assessment == "hold_under_pressure"]
    if weak_holds:
        adjustments["min_agent_score_delta"] += 1.5
        adjustments["risk_penalty_delta"] += 1.0
        rationale.append("Baski altinda kalan hold kararlari var; giris esigi ve risk cezasi sikilastirilmali.")

    protected = [item for item in report.action_outcomes if item.assessment in {"protected_or_improved", "risk_limited_loss"}]
    if protected:
        adjustments["volume_weight_delta"] += 1.0
        rationale.append("Risk azaltma/kar koruma aksiyonlari islevsel; hacim teyidi olan adaylar bir tik desteklenebilir.")

    if report.total_pnl > 0 and not weak_holds:
        adjustments["cash_buffer_delta_percent"] -= 3.0
        rationale.append("Gunluk sonuc pozitif ve zayif hold yok; sonraki seansta standart risk alinabilir.")

    if not rationale:
        rationale.append("Ogrenme verisi notr; agirliklarda degisiklik onerilmiyor.")

    return TradingAgentLearningWeightsResponse(
        generated_at=datetime.utcnow().isoformat(),
        trade_date=report.trade_date,
        strategy_name=report.strategy_name,
        adjustments={key: round(value, 2) for key, value in adjustments.items()},
        rationale=rationale,
    )


def _latest_decision_date(strategy_name: str | None = None) -> str | None:
    ensure_runtime_schema()
    stmt = select(TradingAgentDecisionLog).order_by(desc(TradingAgentDecisionLog.created_at)).limit(1)
    if strategy_name:
        stmt = (
            select(TradingAgentDecisionLog)
            .where(TradingAgentDecisionLog.strategy_name == strategy_name)
            .order_by(desc(TradingAgentDecisionLog.created_at))
            .limit(1)
        )
    with SessionLocal() as session:
        row = session.execute(stmt).scalar_one_or_none()
    if row is None or row.created_at is None:
        return None
    return row.created_at.date().isoformat()
