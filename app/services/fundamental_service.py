from app.models.schemas import FundamentalResponse


# Gercek ve guvenilir temel veri katmani gelene kadar analiz tarafinda
# yapay temel yorum uretmiyoruz. Bu servis bilerek bos doner.
def get_fundamental_summary(ticker: str) -> FundamentalResponse | None:
    return None
