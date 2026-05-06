from app.models.schemas import InstitutionalFlowResponse


# Kurumsal akim icin guvenilir veri kaynagi baglanana kadar
# yapay fon yorumu uretmiyoruz.
def get_institutional_flow_summary(ticker: str) -> InstitutionalFlowResponse | None:
    return None
