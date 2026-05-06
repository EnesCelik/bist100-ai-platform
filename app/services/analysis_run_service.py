from datetime import date, datetime, time

from sqlalchemy import cast, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.types import Float

from app.agent.router import extract_ticker
from app.db.models import AnalysisRun
from app.db.session import SessionLocal, ensure_runtime_schema
from app.models.schemas import AskResponse, AnalysisRunHistoryItem, AnalysisRunHistoryResponse


def log_analysis_run(response: AskResponse) -> None:
    try:
        ensure_runtime_schema()
        with SessionLocal() as session:
            recommendation = response.recommendation
            session.add(
                AnalysisRun(
                    ticker=(extract_ticker(response.question) or "UNKNOWN").upper(),
                    question=response.question,
                    route_type=response.route_type,
                    stance=recommendation.stance if recommendation is not None else "none",
                    action=recommendation.action if recommendation is not None else "none",
                    confidence=str(response.confidence),
                    used_sources=response.used_sources,
                    recommendation_summary=(
                        recommendation.summary if recommendation is not None else response.reasoning_summary
                    ),
                )
            )
            session.commit()
    except SQLAlchemyError:
        return


def get_analysis_run_history(
    limit: int = 20,
    ticker: str | None = None,
    route_type: str | None = None,
    stance: str | None = None,
    action: str | None = None,
    min_confidence: float | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> AnalysisRunHistoryResponse:
    ensure_runtime_schema()
    normalized_ticker = ticker.upper() if ticker is not None else None
    normalized_route_type = route_type.lower() if route_type is not None else None
    normalized_stance = stance.lower() if stance is not None else None
    normalized_action = action.lower() if action is not None else None

    with SessionLocal() as session:
        statement = select(AnalysisRun)

        if normalized_ticker is not None:
            statement = statement.where(AnalysisRun.ticker == normalized_ticker)
        if normalized_route_type is not None:
            statement = statement.where(AnalysisRun.route_type == normalized_route_type)
        if normalized_stance is not None:
            statement = statement.where(AnalysisRun.stance == normalized_stance)
        if normalized_action is not None:
            statement = statement.where(AnalysisRun.action == normalized_action)
        if min_confidence is not None:
            statement = statement.where(cast(AnalysisRun.confidence, Float) >= min_confidence)
        if date_from is not None:
            statement = statement.where(AnalysisRun.created_at >= datetime.combine(date_from, time.min))
        if date_to is not None:
            statement = statement.where(AnalysisRun.created_at <= datetime.combine(date_to, time.max))

        statement = statement.order_by(AnalysisRun.created_at.desc(), AnalysisRun.id.desc()).limit(max(limit, 1))
        rows = session.execute(statement).scalars().all()

    return AnalysisRunHistoryResponse(
        total=len(rows),
        items=[
            AnalysisRunHistoryItem(
                id=row.id,
                ticker=row.ticker,
                question=row.question,
                route_type=row.route_type,
                stance=row.stance,
                action=row.action,
                confidence=float(row.confidence),
                used_sources=row.used_sources,
                recommendation_summary=row.recommendation_summary,
                created_at=row.created_at.isoformat() if row.created_at is not None else None,
            )
            for row in rows
        ],
    )
