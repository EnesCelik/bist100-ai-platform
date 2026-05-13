from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_env: str = "local"
    app_name: str = "BIST100 AI Platform"
    api_v1_prefix: str = "/api/v1"
    signal_enabled: bool = False
    paper_trade_enabled: bool = False

    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/bist100_ai"
    database_echo: bool = False
    market_data_provider: str = "mock"
    yahoo_timeout_seconds: float = 8.0
    market_snapshot_max_age_minutes: int = 2
    ohlcv_cache_max_age_minutes_1h: int = 45
    ohlcv_cache_max_age_minutes_4h: int = 90
    ohlcv_cache_max_age_minutes_1g: int = 360
    ohlcv_cache_max_age_minutes_1w: int = 1440
    fmp_api_key: str = ""
    fmp_base_url: str = "https://financialmodelingprep.com/stable"
    fmp_timeout_seconds: float = 8.0
    eodhd_api_token: str = ""
    eodhd_base_url: str = "https://eodhd.com/api"
    eodhd_timeout_seconds: float = 8.0
    kap_sectors_url: str = "https://www.kap.org.tr/en/Sektorler"
    kap_timeout_seconds: float = 10.0
    news_impact_provider: str = "marketaux"
    marketaux_api_token: str = ""
    marketaux_base_url: str = "https://api.marketaux.com/v1"
    marketaux_language: str = "en"
    marketaux_countries: str = "tr"
    marketaux_timeout_seconds: float = 8.0
    market_snapshot_retention_days: int = 14
    ohlcv_retention_days_1h: int = 45
    ohlcv_retention_days_4h: int = 180
    ohlcv_retention_days_1g: int = 1825
    ohlcv_retention_days_1w: int = 3650
    scheduler_enabled: bool = True
    scheduler_cleanup_interval_minutes: int = 360
    scheduler_prefetch_enabled: bool = True
    scheduler_prefetch_interval_minutes: int = 60
    scheduler_prefetch_bars: int = 120
    scheduler_prefetch_timeframes: str = "1H,4H,1G"
    scheduler_prefetch_tickers: str = ""
    scheduler_prefetch_initial_delay_minutes: int = 0
    scheduler_paper_log_enabled: bool = True
    scheduler_paper_log_interval_minutes: int = 1440
    scheduler_paper_log_limit: int = 10
    scheduler_paper_log_stance: str = "bullish"
    scheduler_paper_log_stances: str = ""
    scheduler_paper_log_initial_delay_minutes: int = 5
    scheduler_paper_log_wait_for_prefetch: bool = True

    # Live Garanti / Matriks snapshot ayarlari.
    matriks_base_url: str = "https://api.matriksdata.com"
    matriks_market_data_token: str = ""
    matriks_integration_url: str = "https://etrader.garantibbvayatirim.com.tr/0172_v3_trader/Integration.aspx"
    matriks_snapshot_path: str = "/dumrul/v1/snapshot-market-real"
    matriks_bar_path: str = "/dumrul/v1/tick/bar"
    matriks_depth_path: str = ""
    matriks_sso_login_service: str = "https://ssomatriks.garantibbvayatirim.com.tr/9984_sso_etrader/Integration.aspx"
    matriks_sso_hashkey_service: str = "https://ssomatriks.garantibbvayatirim.com.tr/9984_sso_etrader/SSOCheckState.aspx"
    matriks_sso_date_service: str = "https://ssomatriks.garantibbvayatirim.com.tr/9984_sso_etrader/UTCDate.aspx"
    matriks_sso_tid: str = "prodTr"
    matriks_source_id: str = "40"
    matriks_exchange_id: str = "4"
    matriks_client_ip: str = "127.0.0.1"
    matriks_platform: str = "D"
    matriks_language: str = "tr"
    matriks_version: str = "20250804.20250915.20240520.20241017"
    matriks_customer_no: str = ""
    matriks_account_id: str = ""
    matriks_session_key: str = ""
    matriks_login_action: str = ""
    matriks_login_otp: str = ""
    matriks_symbol_suffix: str = ""
    matriks_bar_period_1h: str = ""
    matriks_bar_period_4h: str = ""
    matriks_bar_period_1g: str = ""
    matriks_bar_period_1w: str = ""
    matriks_timeout_seconds: float = 5.0
    matriks_verify_ssl: bool = True

    # Legacy alanlari geriye donuk uyumluluk icin koruyoruz.
    matriks_username: str = ""
    matriks_password: str = ""
    matriks_terminal_id: str = ""


settings = Settings()
