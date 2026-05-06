from fastapi import APIRouter

from app.models.schemas import DatabaseHealthResponse, DatabaseInitResponse
from app.services.db_service import get_database_health, initialize_database


router = APIRouter(tags=["db"])


@router.get("/db/health", response_model=DatabaseHealthResponse)
def db_health() -> DatabaseHealthResponse:
    return get_database_health()


@router.post("/db/init", response_model=DatabaseInitResponse)
def db_init() -> DatabaseInitResponse:
    return initialize_database()
