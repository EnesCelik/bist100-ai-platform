from fastapi import APIRouter

from app.models.schemas import HealthResponse, RuntimeHealthResponse
from app.services.runtime_scheduler_service import get_runtime_health


# Bu router sadece sistem ayakta mi sorusuna cevap vermek icin var.
router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    # En basit endpoint: servis yasiyor mu, cevap verebiliyor mu?
    return HealthResponse(status="ok")


@router.get("/health/runtime", response_model=RuntimeHealthResponse)
def runtime_health_check() -> RuntimeHealthResponse:
    return get_runtime_health()
