from datetime import datetime

from sqlalchemy import BIGINT, JSON, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class NewsItem(Base):
    __tablename__ = "news_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(16), index=True)
    headline: Mapped[str] = mapped_column(String(512), index=True)
    summary: Mapped[str] = mapped_column(Text)
    source_url: Mapped[str] = mapped_column(String(1024))
    publisher: Mapped[str] = mapped_column(String(128))
    published_at: Mapped[str] = mapped_column(String(32), index=True)
    tags: Mapped[list[str]] = mapped_column(JSON)
    source: Mapped[str] = mapped_column(String(64), default="json_news_store")


class MacroEventRecord(Base):
    __tablename__ = "macro_event_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(16), index=True)
    latest_macro_event: Mapped[str] = mapped_column(String(512), index=True)
    event_category: Mapped[str] = mapped_column(String(64), index=True)
    region: Mapped[str] = mapped_column(String(64), index=True)
    published_at: Mapped[str] = mapped_column(String(32), index=True)
    positive_impacts: Mapped[list[str]] = mapped_column(JSON)
    negative_impacts: Mapped[list[str]] = mapped_column(JSON)
    source: Mapped[str] = mapped_column(String(64), default="json_macro_event_store")


class AnalysisRun(Base):
    __tablename__ = "analysis_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(16), index=True)
    question: Mapped[str] = mapped_column(Text)
    route_type: Mapped[str] = mapped_column(String(64), index=True)
    stance: Mapped[str] = mapped_column(String(32), index=True)
    action: Mapped[str] = mapped_column(String(32), index=True)
    confidence: Mapped[str] = mapped_column(String(16))
    used_sources: Mapped[list[str]] = mapped_column(JSON)
    recommendation_summary: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)


class ScanSnapshot(Base):
    __tablename__ = "scan_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    stance_filter: Mapped[str] = mapped_column(String(32), index=True)
    limit_requested: Mapped[int] = mapped_column(Integer)
    universe_size: Mapped[int] = mapped_column(Integer)
    total_returned: Mapped[int] = mapped_column(Integer)
    provider: Mapped[str] = mapped_column(String(64), index=True)
    items: Mapped[list[dict]] = mapped_column(JSON)
    market_data_source_summary: Mapped[dict] = mapped_column(JSON, default=dict)
    used_source_summary: Mapped[dict] = mapped_column(JSON, default=dict)
    runtime_health_summary: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)


class MarketSnapshotCurrent(Base):
    __tablename__ = "market_snapshot_current"

    ticker: Mapped[str] = mapped_column(String(16), primary_key=True)
    last_price: Mapped[float] = mapped_column()
    change_percent: Mapped[float] = mapped_column()
    volume: Mapped[int] = mapped_column(BIGINT)
    best_bid: Mapped[float] = mapped_column()
    best_ask: Mapped[float] = mapped_column()
    source: Mapped[str] = mapped_column(String(64), default="yahoo_delayed_market_data")
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), index=True)


class OHLCVBarCache(Base):
    __tablename__ = "ohlcv_bar_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(16), index=True)
    timeframe: Mapped[str] = mapped_column(String(8), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, index=True)
    open: Mapped[float] = mapped_column()
    high: Mapped[float] = mapped_column()
    low: Mapped[float] = mapped_column()
    close: Mapped[float] = mapped_column()
    volume: Mapped[int] = mapped_column(BIGINT)
    source: Mapped[str] = mapped_column(String(64), default="yahoo_delayed_ohlcv")
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), index=True)


class CompanyMaster(Base):
    __tablename__ = "company_master"

    ticker: Mapped[str] = mapped_column(String(16), primary_key=True)
    name: Mapped[str] = mapped_column(String(256), index=True)
    sector: Mapped[str] = mapped_column(String(128), index=True)
    signal_enabled: Mapped[bool] = mapped_column(default=False)
    is_active: Mapped[bool] = mapped_column(default=True, index=True)
    source: Mapped[str] = mapped_column(String(64), default="manual_seed")
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), index=True)


class UniverseMembership(Base):
    __tablename__ = "universe_membership"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(16), index=True)
    universe_code: Mapped[str] = mapped_column(String(64), index=True)
    universe_name: Mapped[str] = mapped_column(String(128), default="")
    is_active: Mapped[bool] = mapped_column(default=True, index=True)
    source: Mapped[str] = mapped_column(String(64), default="manual_seed")
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), index=True)


class PaperDecisionLog(Base):
    __tablename__ = "paper_decision_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(16), index=True)
    source_mode: Mapped[str] = mapped_column(String(32), index=True)
    question: Mapped[str] = mapped_column(Text, default="")
    stance: Mapped[str] = mapped_column(String(32), index=True)
    action: Mapped[str] = mapped_column(String(32), index=True)
    confidence: Mapped[str] = mapped_column(String(16))
    weighted_score: Mapped[str] = mapped_column(String(16))
    decision_price: Mapped[float] = mapped_column()
    market_data_source: Mapped[str] = mapped_column(String(64), default="yahoo_delayed_market_data")
    capture_batch_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    trade_setup: Mapped[str] = mapped_column(String(64), default="")
    trend_reference_level: Mapped[float | None] = mapped_column(nullable=True)
    entry_zone_low: Mapped[float | None] = mapped_column(nullable=True)
    entry_zone_high: Mapped[float | None] = mapped_column(nullable=True)
    breakout_buy_trigger: Mapped[float | None] = mapped_column(nullable=True)
    stop_loss_level: Mapped[float | None] = mapped_column(nullable=True)
    take_profit_level: Mapped[float | None] = mapped_column(nullable=True)
    calibration_bias: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    recommendation_summary: Mapped[str] = mapped_column(Text)
    used_sources: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)
