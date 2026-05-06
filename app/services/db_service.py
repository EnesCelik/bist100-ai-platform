from sqlalchemy.exc import SQLAlchemyError

from app.db.session import check_database_connection, init_database
from app.models.schemas import DatabaseHealthResponse, DatabaseInitResponse


def get_database_health() -> DatabaseHealthResponse:
    try:
        check_database_connection()
        return DatabaseHealthResponse(status="ok", database="reachable")
    except SQLAlchemyError as exc:
        return DatabaseHealthResponse(status="error", database=str(exc.__class__.__name__))


def initialize_database() -> DatabaseInitResponse:
    try:
        init_database()
        return DatabaseInitResponse(status="initialized")
    except SQLAlchemyError as exc:
        return DatabaseInitResponse(status=f"error:{exc.__class__.__name__}")
