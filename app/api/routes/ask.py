from fastapi import APIRouter

from app.models.schemas import AskRequest, AskResponse
from app.services.analysis_run_service import log_analysis_run
from app.services.ask_service import answer_question


# Bu router kullanicidan gelen soruyu uygun akisa yonlendirecek.
router = APIRouter(tags=["ask"])


@router.post("/ask", response_model=AskResponse)
def ask_question(payload: AskRequest) -> AskResponse:
    # Endpoint sadece soruyu alip service katmanina devrediyor.
    response = answer_question(payload.question)
    log_analysis_run(response)
    return response
