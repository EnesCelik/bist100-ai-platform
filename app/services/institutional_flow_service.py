from app.models.schemas import InstitutionalFlowResponse
from app.realtime_trade_flow.institutional_flow_adapter import get_realtime_institutional_flow


def get_institutional_flow_summary(ticker: str) -> InstitutionalFlowResponse | None:
    return get_realtime_institutional_flow(ticker)
