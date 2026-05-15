from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes.analysis_runs import router as analysis_runs_router
from app.api.routes.ask import router as ask_router
from app.api.routes.chart_features import router as chart_features_router
from app.api.routes.companies import router as companies_router
from app.api.routes.db import router as db_router
from app.api.routes.health import router as health_router
from app.api.routes.ingest import router as ingest_router
from app.api.routes.macro_events import router as macro_events_router
from app.api.routes.news import router as news_router
from app.api.routes.news_impact import router as news_impact_router
from app.api.routes.paper_decision_log import router as paper_decision_log_router
from app.api.routes.paper_trades import router as paper_trades_router
from app.api.routes.replay_evaluation import router as replay_evaluation_router
from app.api.routes.scan import router as scan_router
from app.api.routes.market_data import router as market_data_router
from app.api.routes.trading_agent import router as trading_agent_router
from app.core.config import settings
from app.services.runtime_scheduler_service import start_runtime_scheduler, stop_runtime_scheduler


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await start_runtime_scheduler()
    try:
        yield
    finally:
        await stop_runtime_scheduler()


def create_app() -> FastAPI:
    # FastAPI uygulamasini tek bir yerde olusturuyoruz.
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="BIST100 knowledge, research and signal platform",
        lifespan=lifespan,
    )

    # Tum route'lari burada merkezi olarak uygulamaya baglayacagiz.
    app.include_router(health_router, prefix=settings.api_v1_prefix)
    app.include_router(analysis_runs_router, prefix=settings.api_v1_prefix)
    app.include_router(ask_router, prefix=settings.api_v1_prefix)
    app.include_router(chart_features_router, prefix=settings.api_v1_prefix)
    app.include_router(companies_router, prefix=settings.api_v1_prefix)
    app.include_router(db_router, prefix=settings.api_v1_prefix)
    app.include_router(ingest_router, prefix=settings.api_v1_prefix)
    app.include_router(market_data_router, prefix=settings.api_v1_prefix)
    app.include_router(macro_events_router, prefix=settings.api_v1_prefix)
    app.include_router(news_router, prefix=settings.api_v1_prefix)
    app.include_router(news_impact_router, prefix=settings.api_v1_prefix)
    app.include_router(replay_evaluation_router, prefix=settings.api_v1_prefix)
    app.include_router(paper_decision_log_router, prefix=settings.api_v1_prefix)
    app.include_router(paper_trades_router, prefix=settings.api_v1_prefix)
    app.include_router(scan_router, prefix=settings.api_v1_prefix)
    app.include_router(trading_agent_router, prefix=settings.api_v1_prefix)

    return app


# Uvicorn bu degiskeni import ederek uygulamayi ayaga kaldiracak.
app = create_app()
