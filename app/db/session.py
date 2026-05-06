import threading

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.db.base import Base


engine = create_engine(settings.database_url, echo=settings.database_echo, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)
_schema_lock = threading.Lock()
_schema_initialized = False


def ensure_runtime_schema() -> None:
    global _schema_initialized

    if _schema_initialized:
        return

    with _schema_lock:
        if _schema_initialized:
            return

        import app.db.models  # noqa: F401

        Base.metadata.create_all(bind=engine)
        with engine.begin() as connection:
            connection.execute(
                text(
                    "ALTER TABLE analysis_runs ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
                )
            )
            connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_analysis_runs_created_at ON analysis_runs (created_at)"
                )
            )
            connection.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS ux_ohlcv_bar_cache_key ON ohlcv_bar_cache (ticker, timeframe, timestamp)"
                )
            )
            connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_market_snapshot_current_updated_at ON market_snapshot_current (updated_at)"
                )
            )
            connection.execute(
                text(
                    "ALTER TABLE scan_snapshots ADD COLUMN IF NOT EXISTS market_data_source_summary JSON DEFAULT '{}'::json"
                )
            )
            connection.execute(
                text(
                    "ALTER TABLE scan_snapshots ADD COLUMN IF NOT EXISTS used_source_summary JSON DEFAULT '{}'::json"
                )
            )
            connection.execute(
                text(
                    "ALTER TABLE scan_snapshots ADD COLUMN IF NOT EXISTS runtime_health_summary JSON DEFAULT '{}'::json"
                )
            )
            connection.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS ux_universe_membership_key ON universe_membership (ticker, universe_code)"
                )
            )
            connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_company_master_is_active ON company_master (is_active)"
                )
            )
            connection.execute(
                text(
                    "ALTER TABLE market_snapshot_current ALTER COLUMN volume TYPE BIGINT"
                )
            )
            connection.execute(
                text(
                    "ALTER TABLE ohlcv_bar_cache ALTER COLUMN volume TYPE BIGINT"
                )
            )
            connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_paper_decision_logs_created_at ON paper_decision_logs (created_at)"
                )
            )
            connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_paper_decision_logs_ticker_created_at ON paper_decision_logs (ticker, created_at)"
                )
            )
            connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_paper_decision_logs_source_mode ON paper_decision_logs (source_mode)"
                )
            )
            connection.execute(
                text(
                    "ALTER TABLE paper_decision_logs ADD COLUMN IF NOT EXISTS capture_batch_id VARCHAR(64)"
                )
            )
            connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_paper_decision_logs_capture_batch_id ON paper_decision_logs (capture_batch_id)"
                )
            )

        _schema_initialized = True


def init_database() -> None:
    ensure_runtime_schema()


def check_database_connection() -> bool:
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    return True
