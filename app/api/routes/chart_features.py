from fastapi import APIRouter, Query

from app.models.schemas import ChartFeatureResponse
from app.services.chart_feature_service import fetch_chart_feature_summary

router = APIRouter(tags=["chart-features"])


@router.get("/chart-features/{ticker}", response_model=ChartFeatureResponse)
def get_chart_features(
    ticker: str,
    timeframe: str = Query(default="1G"),
) -> ChartFeatureResponse:
    return fetch_chart_feature_summary(ticker, timeframe=timeframe)
