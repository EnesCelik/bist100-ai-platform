from app.models.schemas import EventResponse


# Sirket-ozel event katmani gercek veriyle beslenmedigi surece
# analiz tarafina mock event eklemiyoruz.
def get_event_summary(ticker: str) -> EventResponse | None:
    return None
