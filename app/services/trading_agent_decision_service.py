from sqlalchemy import desc, select

from app.db.models import TradingAgentDecisionLog
from app.db.session import SessionLocal, ensure_runtime_schema
from app.models.schemas import (
    TradingAgentCycleResponse,
    TradingAgentDecisionLogItem,
)


def _decision_item(row: TradingAgentDecisionLog) -> TradingAgentDecisionLogItem:
    return TradingAgentDecisionLogItem(
        id=row.id,
        strategy_name=row.strategy_name,
        phase=row.phase,
        ticker=row.ticker,
        action=row.action,
        score=row.score,
        price=row.price,
        capital_allocated=row.capital_allocated,
        rationale=row.rationale,
        created_at=row.created_at.isoformat() if row.created_at else "",
    )


def save_agent_cycle_decisions(response: TradingAgentCycleResponse) -> int:
    ensure_runtime_schema()
    payload = response.model_dump(mode="json")
    rows: list[TradingAgentDecisionLog] = []

    if response.decisions:
        for decision in response.decisions:
            rows.append(
                TradingAgentDecisionLog(
                    strategy_name=response.strategy_name,
                    phase=response.phase,
                    ticker=decision.ticker,
                    action=decision.action,
                    score=decision.score,
                    price=decision.entry_price,
                    capital_allocated=decision.capital_allocated,
                    rationale=decision.rationale,
                    payload=payload,
                )
            )
    else:
        rows.append(
            TradingAgentDecisionLog(
                strategy_name=response.strategy_name,
                phase=response.phase,
                ticker="",
                action=response.action,
                score=None,
                price=None,
                capital_allocated=None,
                rationale=response.action,
                payload=payload,
            )
        )

    with SessionLocal() as session:
        session.add_all(rows)
        session.commit()
    return len(rows)


def get_latest_agent_decisions(limit: int = 20, strategy_name: str | None = None) -> list[TradingAgentDecisionLogItem]:
    ensure_runtime_schema()
    stmt = select(TradingAgentDecisionLog).order_by(desc(TradingAgentDecisionLog.created_at)).limit(max(limit, 1))
    if strategy_name:
        stmt = (
            select(TradingAgentDecisionLog)
            .where(TradingAgentDecisionLog.strategy_name == strategy_name)
            .order_by(desc(TradingAgentDecisionLog.created_at))
            .limit(max(limit, 1))
        )
    with SessionLocal() as session:
        rows = session.execute(stmt).scalars().all()
    return [_decision_item(row) for row in rows]
