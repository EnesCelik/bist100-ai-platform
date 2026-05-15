from collections import defaultdict
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import desc, select

from app.db.models import TradingAgentDecisionLog
from app.db.session import SessionLocal, ensure_runtime_schema
from app.models.schemas import (
    TradingAgentActionOutcomeItem,
    TradingAgentCycleResponse,
    TradingAgentDecisionLogItem,
    TradingAgentLearningReportResponse,
)
from app.services.paper_trade_simulation_service import get_paper_trades

ISTANBUL_TZ = ZoneInfo("Europe/Istanbul")


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


def _is_report_date(row: TradingAgentDecisionLog, report_date: str) -> bool:
    if row.created_at is None:
        return False
    created = row.created_at.replace(tzinfo=ZoneInfo("UTC")).astimezone(ISTANBUL_TZ)
    return created.date().isoformat() == report_date


def _assessment_for(action: str, status: str, pnl: float, realized_percent: float) -> str:
    if action in {"exit", "simulated_reduce", "reduce_or_exit"}:
        if realized_percent >= 100 and pnl < 0:
            return "risk_limited_loss"
        if realized_percent > 0 and pnl < 0:
            return "partial_risk_reduction"
        if pnl >= 0:
            return "protected_or_improved"
    if action.startswith("hold") and pnl > 0:
        return "hold_worked"
    if action.startswith("hold") and pnl < 0:
        return "hold_under_pressure"
    if action.startswith("watch") and status == "open":
        return "still_pending"
    return "neutral"


def build_agent_learning_report(
    trade_date: str | None = None,
    strategy_name: str | None = None,
) -> TradingAgentLearningReportResponse:
    ensure_runtime_schema()
    report_date = trade_date or datetime.now(ISTANBUL_TZ).date().isoformat()
    normalized_strategy = strategy_name.strip() if strategy_name else None

    with SessionLocal() as session:
        statement = select(TradingAgentDecisionLog).order_by(TradingAgentDecisionLog.created_at.asc())
        if normalized_strategy:
            statement = statement.where(TradingAgentDecisionLog.strategy_name == normalized_strategy)
        rows = [row for row in session.execute(statement).scalars().all() if _is_report_date(row, report_date)]

    open_trades = get_paper_trades(limit=200, status="open", strategy_name=normalized_strategy).items
    closed_trades = get_paper_trades(limit=200, status="closed", strategy_name=normalized_strategy).items
    trades_by_ticker = {trade.ticker: trade for trade in [*closed_trades, *open_trades]}

    grouped: dict[tuple[str, str], list[TradingAgentDecisionLog]] = defaultdict(list)
    for row in rows:
        if not row.ticker:
            continue
        grouped[(row.ticker, row.action)].append(row)

    action_outcomes: list[TradingAgentActionOutcomeItem] = []
    for (ticker, action), decision_rows in grouped.items():
        latest = decision_rows[-1]
        trade = trades_by_ticker.get(ticker)
        if trade is None:
            continue
        assessment = _assessment_for(action, trade.status, trade.total_position_pnl, trade.realized_percent)
        action_outcomes.append(
            TradingAgentActionOutcomeItem(
                ticker=ticker,
                action=action,
                phase=latest.phase,
                decision_count=len(decision_rows),
                latest_decision_at=latest.created_at.isoformat() if latest.created_at else "",
                trade_status=trade.status,
                outcome=trade.outcome,
                realized_percent=trade.realized_percent,
                current_return_percent=trade.current_return_percent,
                total_position_pnl=trade.total_position_pnl,
                assessment=assessment,
                rationale=latest.rationale,
            )
        )

    action_outcomes.sort(key=lambda item: (item.total_position_pnl, item.decision_count), reverse=True)
    best = action_outcomes[0] if action_outcomes else None
    worst = action_outcomes[-1] if action_outcomes else None

    realized_pnl = round(sum(trade.total_position_pnl for trade in closed_trades), 2)
    open_unrealized_pnl = round(sum(trade.total_position_pnl for trade in open_trades), 2)
    total_pnl = round(realized_pnl + open_unrealized_pnl, 2)

    lessons: list[str] = []
    next_rules: list[str] = []
    reduce_rows = [item for item in action_outcomes if item.action in {"reduce_or_exit", "simulated_reduce", "exit"}]
    weak_holds = [item for item in action_outcomes if item.action.startswith("hold") and item.total_position_pnl < 0]
    positive_holds = [item for item in action_outcomes if item.action.startswith("hold") and item.total_position_pnl > 0]

    if reduce_rows:
        lessons.append("Risk azaltma aksiyonlari zarar buyumesini sinirlamak icin aktif kullanildi.")
        next_rules.append("Stopa cok yaklasan pozisyonlarda once %50 azalt, stop kirilirsa kalani %100 kapat.")
    if weak_holds:
        tickers = ", ".join(item.ticker for item in weak_holds[:3])
        lessons.append(f"{tickers} icin hold/watch kararlari henuz baski altinda.")
        next_rules.append("Hold karari verilen hisselerde 15 dk icinde fiyat teyidi gelmezse watch_for_reversal'a dusur.")
    if positive_holds:
        tickers = ", ".join(item.ticker for item in positive_holds[:3])
        lessons.append(f"{tickers} goreli guclu kaldigi icin tasima karari desteklendi.")
    if total_pnl < 0:
        next_rules.append("Sepet toplam PnL negatife dondugunde nakit tamponu yeni alim icin kullanma.")
    if not lessons:
        lessons.append("Yeterli karar-sonuc verisi olusmadi; izleme devam etmeli.")
    if not next_rules:
        next_rules.append("Bir sonraki seansta ayni kurallarla izlemeye devam et.")

    summary = (
        f"{report_date} icin {len(rows)} agent karari incelendi. "
        f"Toplam PnL {total_pnl} TL, realized PnL {realized_pnl} TL, acik PnL {open_unrealized_pnl} TL."
    )

    return TradingAgentLearningReportResponse(
        generated_at=datetime.utcnow().isoformat(),
        trade_date=report_date,
        strategy_name=normalized_strategy,
        decision_count=len(rows),
        unique_ticker_count=len({row.ticker for row in rows if row.ticker}),
        open_trade_count=len(open_trades),
        closed_trade_count=len(closed_trades),
        total_pnl=total_pnl,
        realized_pnl=realized_pnl,
        open_unrealized_pnl=open_unrealized_pnl,
        action_outcomes=action_outcomes,
        best_action=f"{best.ticker}:{best.action}" if best else None,
        worst_action=f"{worst.ticker}:{worst.action}" if worst else None,
        lessons=lessons,
        next_session_rules=next_rules,
        summary=summary,
    )
