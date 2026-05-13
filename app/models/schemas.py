from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field(description="Application health status", examples=["ok"])


class RuntimeHealthResponse(BaseModel):
    status: str = Field(description="Scheduler/runtime health status", examples=["ok"])
    scheduler_enabled: bool = Field(description="Whether background scheduler is enabled", examples=[True])
    cleanup_enabled: bool = Field(description="Whether cleanup job is enabled", examples=[True])
    prefetch_enabled: bool = Field(description="Whether prefetch job is enabled", examples=[True])
    paper_log_enabled: bool = Field(description="Whether automatic paper-log capture is enabled", examples=[True])
    last_cleanup_started_at: str | None = Field(default=None, description="Cleanup job last start time")
    last_cleanup_completed_at: str | None = Field(default=None, description="Cleanup job last completion time")
    last_cleanup_status: str | None = Field(default=None, description="Cleanup job last status")
    last_cleanup_message: str | None = Field(default=None, description="Cleanup job last summary message")
    last_prefetch_started_at: str | None = Field(default=None, description="Prefetch job last start time")
    last_prefetch_completed_at: str | None = Field(default=None, description="Prefetch job last completion time")
    last_prefetch_status: str | None = Field(default=None, description="Prefetch job last status")
    last_prefetch_message: str | None = Field(default=None, description="Prefetch job last summary message")
    last_paper_log_started_at: str | None = Field(default=None, description="Paper-log job last start time")
    last_paper_log_completed_at: str | None = Field(default=None, description="Paper-log job last completion time")
    last_paper_log_status: str | None = Field(default=None, description="Paper-log job last status")
    last_paper_log_message: str | None = Field(default=None, description="Paper-log job last summary message")


class DatabaseHealthResponse(BaseModel):
    status: str = Field(description="Database health status", examples=["ok"])
    database: str = Field(description="Database reachability detail", examples=["reachable"])


class DatabaseInitResponse(BaseModel):
    status: str = Field(description="Database initialization result", examples=["initialized"])


class CompanyResponse(BaseModel):
    ticker: str = Field(description="BIST ticker code", examples=["GARAN"])
    name: str = Field(description="Company name", examples=["Garanti BBVA"])
    sector: str = Field(description="Sector name", examples=["Banking"])
    signal_enabled: bool = Field(
        description="Whether signal engine is enabled for this company",
        examples=[False],
    )
    source: str | None = Field(default=None, description="Universe source", examples=["manual_seed"])


class CompanyListResponse(BaseModel):
    total: int = Field(description="Number of returned companies", examples=[4])
    universe_code: str | None = Field(default=None, description="Optional universe filter", examples=["bist100"])
    items: list[CompanyResponse] = Field(description="Returned companies")


class CompanyProfileEnrichmentResponse(BaseModel):
    ticker: str = Field(description="BIST ticker code", examples=["ASTOR"])
    resolved_name: str | None = Field(default=None, description="Resolved company name after enrichment")
    resolved_sector: str | None = Field(default=None, description="Resolved normalized sector after enrichment")
    raw_name: str | None = Field(default=None, description="Raw company name returned by the enrichment provider")
    raw_sector: str | None = Field(default=None, description="Raw sector returned by the enrichment provider")
    raw_industry: str | None = Field(default=None, description="Raw industry returned by the enrichment provider")
    provider: str | None = Field(default=None, description="Underlying enrichment provider", examples=["yahoo_quote_summary"])
    source: str | None = Field(default=None, description="Stored enrichment source label")
    updated_at: str | None = Field(default=None, description="Last enrichment timestamp")
    status: str = Field(description="Enrichment lookup result", examples=["cached"])


class CompanyProfileUniverseRefreshResponse(BaseModel):
    universe_code: str = Field(description="Universe code used for the refresh", examples=["bist100"])
    total_requested: int = Field(description="Number of tickers attempted", examples=[10])
    refreshed_count: int = Field(description="Number of tickers successfully refreshed", examples=[8])
    tickers: list[str] = Field(description="Successfully refreshed tickers")
    status: str = Field(description="Refresh result", examples=["refreshed"])


class UniverseCompanyUpsertItem(BaseModel):
    ticker: str = Field(description="BIST ticker code", examples=["THYAO"])
    name: str = Field(description="Company name")
    sector: str = Field(description="Sector name")
    signal_enabled: bool = Field(default=False, description="Whether signal engine is enabled")
    is_active: bool = Field(default=True, description="Whether company is active in master universe")


class UniverseUpsertRequest(BaseModel):
    universe_code: str = Field(description="Universe code", examples=["bist100"])
    universe_name: str = Field(description="Universe display name", examples=["BIST 100"])
    source: str = Field(default="manual_seed", description="Source label for the upsert")
    items: list[UniverseCompanyUpsertItem] = Field(description="Companies to upsert into the universe")


class UniverseUpsertResponse(BaseModel):
    universe_code: str = Field(description="Universe code", examples=["bist100"])
    total_items: int = Field(description="Number of submitted companies", examples=[4])
    company_upserted: int = Field(description="Number of company master records upserted", examples=[4])
    membership_upserted: int = Field(description="Number of universe memberships upserted", examples=[4])
    source: str = Field(description="Source label used during upsert", examples=["manual_seed"])
    status: str = Field(description="Upsert result", examples=["saved"])


class CompanyMigrationResponse(BaseModel):
    total_seed_records: int = Field(description="Number of seed records inspected", examples=[4])
    company_upserted: int = Field(description="Number of company records upserted", examples=[4])
    membership_upserted: int = Field(description="Number of universe memberships upserted", examples=[4])
    universe_code: str = Field(description="Universe code populated by the migration", examples=["demo_core"])
    status: str = Field(description="Migration result", examples=["migrated"])
    source: str = Field(description="Migration source label", examples=["mock_company_seed"])
    note: str | None = Field(default=None, description="Additional migration note")


class UniverseSeedInfo(BaseModel):
    seed_name: str = Field(description="Seed file name", examples=["bist100_seed.template"])
    path: str = Field(description="Absolute seed file path")
    item_count: int = Field(description="Number of companies found in the seed file", examples=[100])
    universe_code: str | None = Field(default=None, description="Universe code declared in the seed file")
    source: str | None = Field(default=None, description="Seed source label")


class UniverseSeedListResponse(BaseModel):
    total: int = Field(description="Number of discovered seed files", examples=[1])
    items: list[UniverseSeedInfo] = Field(description="Available universe seed files")


class UniverseSeedLoadResponse(BaseModel):
    seed_name: str = Field(description="Loaded seed file name", examples=["bist100_seed.template"])
    universe_code: str = Field(description="Universe code", examples=["bist100"])
    total_items: int = Field(description="Number of submitted companies", examples=[100])
    company_upserted: int = Field(description="Number of company records upserted", examples=[100])
    membership_upserted: int = Field(description="Number of universe memberships upserted", examples=[100])
    source: str = Field(description="Source label used during import", examples=["manual_seed"])
    status: str = Field(description="Seed load result", examples=["loaded"])
    note: str | None = Field(default=None, description="Additional import note")


class NewsImpactArticleResponse(BaseModel):
    headline: str = Field(description="Article headline")
    published_at: str = Field(description="Article publish timestamp")
    source: str | None = Field(default=None, description="Publisher/source name")
    url: str | None = Field(default=None, description="Source URL")
    sentiment_score: float | None = Field(default=None, description="Entity sentiment score for the ticker")
    match_score: float | None = Field(default=None, description="Entity match score for the ticker")


class NewsImpactResponse(BaseModel):
    ticker: str = Field(description="BIST ticker code", examples=["THYAO"])
    provider: str = Field(description="News impact provider", examples=["marketaux_news_impact"])
    total_articles: int = Field(description="Number of returned articles", examples=[5])
    average_sentiment: float | None = Field(default=None, description="Average sentiment across returned articles")
    latest_published_at: str | None = Field(default=None, description="Latest article timestamp")
    items: list[NewsImpactArticleResponse] = Field(description="Ticker-filtered news impact items")


class MarketDataResponse(BaseModel):
    ticker: str = Field(description="BIST ticker code", examples=["GARAN"])
    last_price: float = Field(description="Latest traded price", examples=[128.4])
    change_percent: float = Field(description="Daily percentage change", examples=[1.85])
    volume: int = Field(description="Daily traded volume", examples=[15420000])
    best_bid: float = Field(description="Best bid price", examples=[128.35])
    best_ask: float = Field(description="Best ask price", examples=[128.45])
    source: str = Field(description="Data source name", examples=["mock_market_data_tool"])


class OrderBookLevel(BaseModel):
    price: float = Field(description="Order book level price", examples=[128.4])
    quantity: int = Field(description="Order book level quantity", examples=[125000])


class OrderBookPressureResponse(BaseModel):
    ticker: str = Field(description="BIST ticker code", examples=["GARAN"])
    available: bool = Field(description="Whether real order book/depth data was available", examples=[True])
    bid_total_quantity: int = Field(description="Total visible bid quantity across returned levels", examples=[2500000])
    ask_total_quantity: int = Field(description="Total visible ask quantity across returned levels", examples=[1200000])
    bid_ask_imbalance: float | None = Field(default=None, description="Bid quantity divided by ask quantity")
    pressure_bucket: str = Field(description="Order book pressure bucket", examples=["strong_bid_pressure"])
    top_bid_price: float | None = Field(default=None, description="Best visible bid price")
    top_ask_price: float | None = Field(default=None, description="Best visible ask price")
    top_bid_quantity: int | None = Field(default=None, description="Best visible bid quantity")
    top_ask_quantity: int | None = Field(default=None, description="Best visible ask quantity")
    bid_levels: list[OrderBookLevel] = Field(default_factory=list, description="Visible bid levels")
    ask_levels: list[OrderBookLevel] = Field(default_factory=list, description="Visible ask levels")
    source: str = Field(description="Order book data source", examples=["matriks_depth"])
    message: str | None = Field(default=None, description="Availability or parsing note")


class OHLCVBar(BaseModel):
    timestamp: str = Field(description="Bar timestamp in ISO format", examples=["2026-04-21T10:00:00+03:00"])
    open: float = Field(description="Open price", examples=[322.5])
    high: float = Field(description="High price", examples=[325.0])
    low: float = Field(description="Low price", examples=[320.75])
    close: float = Field(description="Close price", examples=[324.25])
    volume: int = Field(description="Bar volume", examples=[12450000])


class OHLCVResponse(BaseModel):
    ticker: str = Field(description="BIST ticker code", examples=["THYAO"])
    timeframe: str = Field(description="Requested dashboard timeframe", examples=["1G"])
    bars: int = Field(description="Requested bar count", examples=[40])
    candles: list[OHLCVBar] = Field(description="Ordered OHLCV bars")
    source: str = Field(description="OHLCV source name", examples=["yahoo_delayed_ohlcv"])


class MarketDataDebugResponse(BaseModel):
    ticker: str = Field(description="BIST ticker code", examples=["THYAO"])
    snapshot_available: bool = Field(description="Whether a current market snapshot exists in cache", examples=[True])
    snapshot_source: str | None = Field(default=None, description="Source stored for the current snapshot")
    snapshot_updated_at: str | None = Field(default=None, description="Last snapshot update timestamp")
    snapshot_source_family: str | None = Field(default=None, description="Normalized source family for the current snapshot", examples=["matriks"])
    snapshot_is_matriks: bool = Field(description="Whether the current snapshot source is Matriks-based", examples=[True])
    ohlcv_timeframe: str = Field(description="Requested OHLCV timeframe", examples=["1G"])
    ohlcv_cached_bars: int = Field(description="Number of cached bars found for the requested timeframe", examples=[40])
    ohlcv_latest_timestamp: str | None = Field(default=None, description="Latest cached OHLCV timestamp")
    ohlcv_source: str | None = Field(default=None, description="Source stored for cached OHLCV bars")
    ohlcv_source_family: str | None = Field(default=None, description="Normalized source family for cached OHLCV bars", examples=["matriks"])
    ohlcv_is_matriks: bool = Field(description="Whether the cached OHLCV source is Matriks-based", examples=[True])
    ohlcv_cache_sources: list[str] = Field(description="Distinct cached OHLCV sources found for the requested timeframe")
    ohlcv_has_matriks_cache: bool = Field(description="Whether any Matriks OHLCV cache rows exist for the requested timeframe", examples=[True])
    ohlcv_has_yahoo_cache: bool = Field(description="Whether any Yahoo OHLCV cache rows exist for the requested timeframe", examples=[False])


class GarantiSsoStartResponse(BaseModel):
    status: str = Field(description="SSO bootstrap status", examples=["pending_approval"])
    client_state: str = Field(description="Generated Garanti SSO client_state value")
    login_url: str = Field(description="Garanti SSO login URL to open in the browser")
    next_step: str = Field(description="What the user should do next")


class GarantiSsoCompleteRequest(BaseModel):
    client_state: str = Field(description="Previously generated Garanti SSO client_state")
    wait_seconds: int = Field(default=60, ge=0, le=300, description="How long to poll the Garanti SSO hashkey service")
    poll_interval_seconds: float = Field(default=2.0, ge=0.5, le=10.0, description="Polling interval for hashkey checks")


class GarantiSsoCompleteResponse(BaseModel):
    status: str = Field(description="Finalize result", examples=["token_acquired"])
    token_acquired: bool = Field(description="Whether a fresh MarketDataToken was acquired", examples=[True])
    expires_at: str | None = Field(default=None, description="Decoded JWT expiry when available")
    message: str = Field(description="Short outcome message")


class GarantiBrowserBootstrapRequest(BaseModel):
    market_data_token: str = Field(description="MarketDataToken value copied from Garanti Integration.aspx response")
    session_key: str | None = Field(default=None, description="Optional SessionKey copied from the same response")
    customer_id: str | None = Field(default=None, description="Optional CustomerID copied from the same response")
    account_id: str | None = Field(default=None, description="Optional DefaultAccount or account id copied from the same response")


class GarantiBrowserBootstrapResponse(BaseModel):
    status: str = Field(description="Bootstrap result", examples=["token_loaded"])
    token_loaded: bool = Field(description="Whether the provided token was accepted", examples=[True])
    expires_at: str | None = Field(default=None, description="Decoded JWT expiry when available")
    message: str = Field(description="Short bootstrap outcome message")


class MarketDataCleanupResponse(BaseModel):
    status: str = Field(description="Cleanup operation result", examples=["cleaned"])
    snapshot_deleted: int = Field(description="Number of deleted snapshot rows", examples=[0])
    ohlcv_deleted: int = Field(description="Number of deleted OHLCV rows", examples=[12])
    ticker_filter: str | None = Field(default=None, description="Optional ticker filter used during cleanup")
    timeframe_filter: str | None = Field(default=None, description="Optional timeframe filter used during cleanup")


class ChartFeatureResponse(BaseModel):
    ticker: str = Field(description="BIST ticker code", examples=["THYAO"])
    current_price: float = Field(description="Current reference price used by the chart engine", examples=[322.75])
    trend: str = Field(description="Detected trend bias", examples=["bullish"])
    ema20: float = Field(description="EMA20 value", examples=[322.4])
    ema50: float = Field(description="EMA50 value", examples=[318.9])
    ema200: float = Field(description="EMA200 value", examples=[301.2])
    ema_alignment: str = Field(description="EMA stack state", examples=["bullish_stack"])
    rsi14: float = Field(description="RSI(14) value", examples=[61.5])
    current_volume: int = Field(description="Current traded volume", examples=[8450000])
    avg_volume: int = Field(description="Reference average volume", examples=[9400000])
    volume_ratio: float = Field(description="Current volume divided by average volume", examples=[1.12])
    breakout_state: str = Field(description="Breakout state with confirmation context", examples=["confirmed_breakout_up"])
    breakout_score: int = Field(description="Numeric breakout contribution to the technical score", examples=[2])
    nearest_support: float = Field(description="Nearest support level", examples=[318.0])
    nearest_resistance: float = Field(description="Nearest resistance level", examples=[327.0])
    support_gap_percent: float = Field(description="Distance to support as percentage of price", examples=[1.47])
    resistance_gap_percent: float = Field(description="Distance to resistance as percentage of price", examples=[1.32])
    price_position_percent: float = Field(description="Price position within the support-resistance range", examples=[63.4])
    level_status: str = Field(description="Whether price is near support, resistance or mid-range", examples=["near_support"])
    trend_reference_level: float = Field(description="Primary trend reference level derived from support and moving averages", examples=[323.4])
    entry_zone_low: float = Field(description="Lower bound of the preferred technical reaction zone", examples=[319.8])
    entry_zone_high: float = Field(description="Upper bound of the preferred technical reaction zone", examples=[323.9])
    breakout_buy_trigger: float = Field(description="Level that strengthens upside continuation if exceeded", examples=[327.8])
    breakdown_sell_trigger: float = Field(description="Level that strengthens downside pressure if broken", examples=[317.1])
    take_profit_level: float = Field(description="Nearest technical take-profit reference", examples=[327.0])
    stop_loss_level: float = Field(description="Nearest technical invalidation or stop level", examples=[317.4])
    trade_setup: str = Field(description="Dominant technical setup label", examples=["pullback_buy"])
    risk_reward_ratio: float = Field(description="Approximate risk-reward ratio based on the derived levels", examples=[1.65])
    level_commentary: str = Field(description="Short trade-level commentary built from trend and support-resistance logic")
    trade_level_positive_factors: list[str] = Field(description="Positive trade-level factors built from entry, stop, breakout and risk-reward logic")
    trade_level_negative_factors: list[str] = Field(description="Negative trade-level factors built from entry, stop, breakout and risk-reward logic")
    atr_percent: float = Field(description="ATR-like volatility as percentage", examples=[2.7])
    volatility_regime: str = Field(description="Volatility regime", examples=["normal"])
    market_structure: str = Field(description="Market structure label", examples=["higher_highs_and_higher_lows"])
    structure_bias: str = Field(description="Bullish/bearish interpretation of market structure", examples=["bullish"])
    signal_bias: str = Field(description="Technical signal bias derived from the features", examples=["bullish"])
    signal_strength: str = Field(description="Technical signal strength", examples=["moderate"])
    signal_score: int = Field(description="Aggregated technical score before policy translation", examples=[4])
    positive_factors: list[str] = Field(description="Positive chart feature highlights")
    negative_factors: list[str] = Field(description="Negative chart feature highlights")
    source: str = Field(description="Chart feature source", examples=["mock_chart_feature_engine"])


class MarketScanItem(BaseModel):
    ticker: str = Field(description="BIST ticker code", examples=["THYAO"])
    company_name: str = Field(description="Company name", examples=["Turkish Airlines"])
    sector: str = Field(description="Sector name", examples=["Airlines"])
    stance: str = Field(description="Recommendation stance", examples=["bearish"])
    action: str = Field(description="Suggested action", examples=["reduce"])
    confidence: float = Field(description="Scan confidence score", examples=[0.78])
    score: int = Field(description="Net evidence score", examples=[-2])
    weighted_score: float = Field(description="Weighted evidence score", examples=[-3.0])
    last_price: float | None = Field(default=None, description="Latest traded price")
    change_percent: float | None = Field(default=None, description="Daily percentage change")
    volume: int | None = Field(default=None, description="Daily traded volume")
    market_data_source: str | None = Field(default=None, description="Source used for the latest market snapshot")
    technical_summary: str | None = Field(default=None, description="Short technical overview built from chart features")
    news_impact_summary: str | None = Field(default=None, description="Optional short news-impact overview")
    used_sources: list[str] = Field(description="Sources used in the scan item")
    summary: str = Field(description="Short summary of the scan decision")
    top_positive_factors: list[str] = Field(description="Top positive factors shown in the scan")
    top_negative_factors: list[str] = Field(description="Top negative factors shown in the scan")


class MarketScanResponse(BaseModel):
    generated_at: str = Field(description="Scan generation timestamp", examples=["2026-04-20T12:00:00"])
    universe_size: int = Field(description="Number of companies scanned", examples=[4])
    total: int = Field(description="Number of returned scan items", examples=[4])
    items: list[MarketScanItem] = Field(description="Ranked market scan items")


class LimitUpCandidateItem(BaseModel):
    ticker: str = Field(description="BIST ticker code", examples=["PETKM"])
    company_name: str = Field(description="Company name")
    sector: str = Field(description="Sector name")
    limit_up_score: float = Field(description="0-100 limit-up candidate score", examples=[76.5])
    probability_bucket: str = Field(description="Qualitative probability bucket", examples=["high"])
    last_price: float | None = Field(default=None, description="Latest traded price")
    change_percent: float | None = Field(default=None, description="Daily percentage change")
    distance_to_limit_percent: float | None = Field(default=None, description="Approximate remaining distance to +10% limit")
    volume: int | None = Field(default=None, description="Daily traded volume")
    daily_volume_ratio: float | None = Field(default=None, description="Current volume divided by 20-day average volume")
    expected_volume_ratio: float | None = Field(default=None, description="Time-adjusted current volume divided by expected volume")
    intraday_volume_ratio_1h: float | None = Field(default=None, description="1H current volume divided by 1H average volume")
    volume_momentum_bucket: str | None = Field(default=None, description="Volume momentum bucket after time adjustment")
    technical_bias: str | None = Field(default=None, description="Daily technical bias")
    intraday_bias_1h: str | None = Field(default=None, description="1H technical bias")
    breakout_state_1h: str | None = Field(default=None, description="1H breakout state")
    spread_percent: float | None = Field(default=None, description="Best ask/bid spread percentage when available")
    order_flow_proxy: str = Field(description="Order-flow proxy derived from best bid/ask and spread", examples=["healthy_spread"])
    order_book_pressure: str | None = Field(default=None, description="Depth/order book pressure bucket when available")
    bid_ask_imbalance: float | None = Field(default=None, description="Visible bid/ask quantity imbalance when available")
    entry_trigger: float | None = Field(default=None, description="Level that confirms upside continuation")
    invalidation_level: float | None = Field(default=None, description="Level that weakens the setup")
    reasons: list[str] = Field(description="Positive reasons for the limit-up candidate ranking")
    risks: list[str] = Field(description="Risks or invalidation notes")


class LimitUpCandidateResponse(BaseModel):
    generated_at: str = Field(description="Scan generation timestamp", examples=["2026-05-12T12:00:00"])
    universe_size: int = Field(description="Number of companies scanned", examples=[85])
    total: int = Field(description="Number of returned candidates", examples=[10])
    excluded_already_limit_count: int = Field(description="Number of symbols excluded because they were already near limit-up")
    items: list[LimitUpCandidateItem] = Field(description="Ranked limit-up candidate items")


class OpeningCandidateItem(BaseModel):
    ticker: str = Field(description="BIST ticker code", examples=["GARAN"])
    company_name: str = Field(description="Company name")
    sector: str = Field(description="Sector name")
    opening_score: float = Field(description="0-100 next-session opening strength score", examples=[74.2])
    probability_bucket: str = Field(description="Qualitative probability bucket", examples=["high"])
    last_price: float | None = Field(default=None, description="Latest traded price")
    change_percent: float | None = Field(default=None, description="Latest daily percentage change")
    volume: int | None = Field(default=None, description="Latest daily traded volume")
    daily_volume_ratio: float | None = Field(default=None, description="Latest volume divided by daily average volume")
    expected_volume_ratio: float | None = Field(default=None, description="Time-adjusted latest volume divided by expected volume")
    volume_momentum_bucket: str | None = Field(default=None, description="Volume momentum bucket after time adjustment")
    closing_strength_proxy: float | None = Field(default=None, description="0-100 proxy for close/position strength")
    technical_bias: str | None = Field(default=None, description="Daily technical bias")
    intraday_bias_1h: str | None = Field(default=None, description="1H technical bias")
    intraday_bias_4h: str | None = Field(default=None, description="4H technical bias")
    breakout_state_1h: str | None = Field(default=None, description="1H breakout state")
    breakout_state_4h: str | None = Field(default=None, description="4H breakout state")
    opening_trigger: float | None = Field(default=None, description="Level that strengthens opening continuation")
    invalidation_level: float | None = Field(default=None, description="Level that weakens the opening setup")
    spread_percent: float | None = Field(default=None, description="Best ask/bid spread percentage when available")
    order_flow_proxy: str = Field(description="Order-flow proxy derived from best bid/ask and spread", examples=["healthy_spread"])
    order_book_pressure: str | None = Field(default=None, description="Depth/order book pressure bucket when available")
    bid_ask_imbalance: float | None = Field(default=None, description="Visible bid/ask quantity imbalance when available")
    gap_risk: str = Field(description="Qualitative gap/chase risk", examples=["medium"])
    reasons: list[str] = Field(description="Positive reasons for the opening candidate ranking")
    risks: list[str] = Field(description="Risks or invalidation notes")


class OpeningCandidateResponse(BaseModel):
    generated_at: str = Field(description="Scan generation timestamp", examples=["2026-05-12T18:15:00"])
    universe_size: int = Field(description="Number of companies scanned", examples=[85])
    total: int = Field(description="Number of returned candidates", examples=[10])
    excluded_already_limit_count: int = Field(description="Number of symbols excluded because they were already near limit-up")
    items: list[OpeningCandidateItem] = Field(description="Ranked next-session opening candidate items")


class OpportunityScanItem(BaseModel):
    ticker: str = Field(description="BIST ticker code", examples=["MGROS"])
    company_name: str = Field(description="Company name")
    sector: str = Field(description="Sector name")
    scenario: str = Field(description="Detected opportunity scenario", examples=["intraday_gain_candidate"])
    opportunity_score: float = Field(description="0-100 scenario-aware opportunity score", examples=[78.5])
    confidence: float = Field(description="0-1 confidence score", examples=[0.68])
    target_move: str = Field(description="Expected move style", examples=["2-3% intraday"])
    last_price: float | None = Field(default=None, description="Latest traded price")
    change_percent: float | None = Field(default=None, description="Daily percentage change")
    distance_to_limit_percent: float | None = Field(default=None, description="Approximate remaining distance to +10% limit")
    volume: int | None = Field(default=None, description="Latest traded volume")
    daily_volume_ratio: float | None = Field(default=None, description="Current volume divided by average daily volume")
    expected_volume_ratio: float | None = Field(default=None, description="Time-adjusted current volume divided by expected volume")
    volume_momentum_bucket: str | None = Field(default=None, description="Time-adjusted volume momentum bucket")
    technical_bias: str | None = Field(default=None, description="Daily technical bias")
    intraday_bias_1h: str | None = Field(default=None, description="1H technical bias")
    intraday_bias_4h: str | None = Field(default=None, description="4H technical bias")
    breakout_state_1h: str | None = Field(default=None, description="1H breakout state")
    breakout_state_4h: str | None = Field(default=None, description="4H breakout state")
    spread_percent: float | None = Field(default=None, description="Best ask/bid spread percentage when available")
    order_flow_proxy: str | None = Field(default=None, description="Spread-derived order flow proxy")
    order_book_pressure: str | None = Field(default=None, description="Depth/order book pressure bucket when available")
    bid_ask_imbalance: float | None = Field(default=None, description="Visible bid/ask quantity imbalance when available")
    trigger_price: float | None = Field(default=None, description="Price level that confirms the scenario")
    invalidation_price: float | None = Field(default=None, description="Price level that weakens or invalidates the scenario")
    why_now: list[str] = Field(description="Reasons supporting the scenario")
    risks: list[str] = Field(description="Risks or invalidation notes")
    data_quality: str = Field(description="Freshness/source quality label", examples=["fresh_matriks"])


class OpportunityScanResponse(BaseModel):
    generated_at: str = Field(description="Scan generation timestamp", examples=["2026-05-13T14:15:00"])
    universe_size: int = Field(description="Number of companies scanned", examples=[85])
    total: int = Field(description="Number of returned opportunities", examples=[10])
    scenario_counts: dict[str, int] = Field(description="Returned scenario distribution")
    items: list[OpportunityScanItem] = Field(description="Ranked opportunity scan items")


class AskRequest(BaseModel):
    question: str = Field(
        description="User question for the assistant",
        examples=["GARAN son fiyat nedir?"],
    )


class AskResponse(BaseModel):
    question: str = Field(description="Original user question")
    route_type: str = Field(
        description="Detected route type",
        examples=["tool_query", "rag_query", "hybrid_query"],
    )
    answer: str = Field(description="Assistant answer")
    used_sources: list[str] = Field(
        description="Sources or subsystems used to build the answer",
        examples=[["mock_market_data_tool"]],
    )
    confidence: float = Field(description="Confidence score for the answer", examples=[0.86])
    reasoning_summary: str = Field(
        description="Short explanation of why this route and answer were produced",
        examples=["Question matched KAP intent and recent KAP documents were prioritized."],
    )
    recommendation: "RecommendationPolicyResult | None" = Field(
        default=None,
        description="Optional recommendation policy output",
    )
    analysis_evidence: list["AnalysisEvidence"] = Field(
        default_factory=list,
        description="Structured evidence items used in analysis-style answers",
    )
    citations: list["Citation"] = Field(
        default_factory=list,
        description="Document citations used in the answer",
    )


class RetrievedDocument(BaseModel):
    ticker: str = Field(description="BIST ticker code", examples=["GARAN"])
    document_title: str = Field(description="Document title")
    document_type: str = Field(description="Document type", examples=["kap"])
    published_at: str = Field(description="Publish date", examples=["2026-03-11"])
    excerpt: str = Field(description="Relevant excerpt from the document")
    source: str = Field(description="Retriever source name", examples=["mock_rag_retriever"])


class Citation(BaseModel):
    ticker: str = Field(description="BIST ticker code", examples=["GARAN"])
    document_title: str = Field(description="Document title")
    document_type: str = Field(description="Document type", examples=["kap"])
    published_at: str = Field(description="Publish date", examples=["2026-03-11"])
    source: str = Field(description="Citation source", examples=["mock_rag_retriever"])


class IngestDocumentRequest(BaseModel):
    ticker: str = Field(description="BIST ticker code", examples=["GARAN"])
    document_title: str = Field(description="Document title")
    document_type: str = Field(description="Document type", examples=["kap"])
    published_at: str = Field(description="Publish date", examples=["2026-04-16"])
    content: str = Field(description="Markdown document content")


class IngestDocumentResponse(BaseModel):
    ticker: str = Field(description="BIST ticker code", examples=["GARAN"])
    document_title: str = Field(description="Document title")
    file_path: str = Field(description="Saved file name", examples=["garan_new_doc.md"])
    status: str = Field(description="Ingest result", examples=["saved"])


class SignalResponse(BaseModel):
    ticker: str = Field(description="BIST ticker code", examples=["GARAN"])
    direction: str = Field(description="Signal direction", examples=["bullish"])
    strength: str = Field(description="Signal strength", examples=["moderate"])
    positive_factors: list[str] = Field(description="Positive signal factors")
    negative_factors: list[str] = Field(description="Negative signal factors")
    source: str = Field(description="Signal source", examples=["mock_signal_service"])


class FundamentalResponse(BaseModel):
    ticker: str = Field(description="BIST ticker code", examples=["GARAN"])
    summary: str = Field(description="Fundamental summary")
    positive_factors: list[str] = Field(description="Positive fundamental factors")
    risk_factors: list[str] = Field(description="Fundamental risk factors")
    source: str = Field(description="Fundamental source", examples=["mock_fundamental_service"])


class EventResponse(BaseModel):
    ticker: str = Field(description="BIST ticker code", examples=["GARAN"])
    latest_event: str = Field(description="Latest notable event")
    supportive_events: list[str] = Field(description="Events that may support the stock")
    pressure_events: list[str] = Field(description="Events that may pressure the stock")
    source: str = Field(description="Event source", examples=["mock_event_service"])


class MacroEventResponse(BaseModel):
    ticker: str = Field(description="BIST ticker code", examples=["THYAO"])
    latest_macro_event: str = Field(description="Latest macro event title")
    positive_impacts: list[str] = Field(description="Positive macro impacts")
    negative_impacts: list[str] = Field(description="Negative macro impacts")
    source: str = Field(description="Macro event source", examples=["json_macro_event_store"])


class MacroEventHistoryItem(BaseModel):
    ticker: str = Field(description="BIST ticker code", examples=["THYAO"])
    latest_macro_event: str = Field(description="Macro event title")
    event_category: str = Field(description="Macro event category", examples=["geopolitics"])
    region: str = Field(description="Macro event region", examples=["middle_east"])
    published_at: str = Field(description="Publish date", examples=["2026-04-17"])
    positive_impacts: list[str] = Field(description="Positive impacts after rule mapping")
    negative_impacts: list[str] = Field(description="Negative impacts after rule mapping")
    source: str = Field(description="Macro event source", examples=["json_macro_event_store"])


class MacroEventHistoryResponse(BaseModel):
    ticker: str = Field(description="BIST ticker code", examples=["THYAO"])
    total: int = Field(description="Number of returned history items", examples=[3])
    items: list[MacroEventHistoryItem] = Field(description="Historical macro events for the ticker")


class InstitutionalFlowResponse(BaseModel):
    ticker: str = Field(description="BIST ticker code", examples=["GARAN"])
    latest_view: str = Field(description="Latest institutional flow summary")
    positive_factors: list[str] = Field(description="Positive institutional flow factors")
    negative_factors: list[str] = Field(description="Negative institutional flow factors")
    source: str = Field(description="Institutional flow source", examples=["mock_institutional_flow_service"])


class IngestMacroEventRequest(BaseModel):
    ticker: str = Field(description="BIST ticker code", examples=["THYAO"])
    latest_macro_event: str = Field(description="Macro event title")
    positive_impacts: list[str] = Field(description="Positive macro impacts")
    negative_impacts: list[str] = Field(description="Negative macro impacts")
    event_category: str = Field(description="Macro event category", examples=["energy"])
    region: str = Field(description="Region impacted by the event", examples=["middle_east"])
    published_at: str = Field(description="Publish date", examples=["2026-04-17"])


class IngestMacroEventBulkRequest(BaseModel):
    tickers: list[str] = Field(description="Affected BIST tickers", examples=[["THYAO", "ASELS", "GARAN"]])
    latest_macro_event: str = Field(description="Macro event title")
    base_positive_impacts: list[str] = Field(
        description="Ticker-agnostic positive impacts shared across all affected tickers",
        examples=[["Kuresel guvenlik gundemi risk algisini degistirebilir"]],
    )
    base_negative_impacts: list[str] = Field(
        description="Ticker-agnostic negative impacts shared across all affected tickers",
        examples=[["Enerji ve lojistik maliyetleri yukselebilir"]],
    )
    event_category: str = Field(description="Macro event category", examples=["geopolitics"])
    region: str = Field(description="Region impacted by the event", examples=["middle_east"])
    published_at: str = Field(description="Publish date", examples=["2026-04-17"])


class IngestMacroEventResponse(BaseModel):
    ticker: str = Field(description="BIST ticker code", examples=["THYAO"])
    latest_macro_event: str = Field(description="Saved macro event title")
    published_at: str = Field(description="Saved macro event date", examples=["2026-04-17"])
    status: str = Field(description="Ingest result", examples=["saved"])


class IngestMacroEventBulkResponse(BaseModel):
    tickers: list[str] = Field(description="Saved BIST tickers", examples=[["THYAO", "ASELS", "GARAN"]])
    latest_macro_event: str = Field(description="Saved macro event title")
    published_at: str = Field(description="Saved macro event date", examples=["2026-04-17"])
    status: str = Field(description="Bulk ingest result", examples=["saved"])


class GlobalEventSourceItem(BaseModel):
    source_id: str = Field(description="Stable source identifier", examples=["gdelt"])
    name: str = Field(description="Display name of the source", examples=["GDELT 2.0"])
    category: str = Field(description="Source category", examples=["global_events"])
    access_mode: str = Field(description="How the source is accessed", examples=["api"])
    coverage: str = Field(description="Short explanation of what the source covers")
    notes: str = Field(description="Implementation or operational note")


class GlobalEventSourceCatalogResponse(BaseModel):
    total: int = Field(description="Number of configured source entries", examples=[5])
    items: list[GlobalEventSourceItem] = Field(description="Configured global event source catalog")


class SectorImpactOverride(BaseModel):
    sectors: list[str] = Field(default_factory=list, description="Sectors that should receive the override impacts")
    positive_impacts: list[str] = Field(default_factory=list, description="Sector-specific positive impacts")
    negative_impacts: list[str] = Field(default_factory=list, description="Sector-specific negative impacts")


class PreviewGlobalEventRequest(BaseModel):
    headline: str = Field(description="Global event headline or title")
    event_category: str = Field(description="Normalized macro category", examples=["geopolitics"])
    region: str = Field(description="Affected region", examples=["middle_east"])
    published_at: str = Field(description="Publish date of the event", examples=["2026-04-27"])
    source_name: str = Field(description="Originating feed or manual source label", examples=["manual_editor"])
    affected_sectors: list[str] = Field(default_factory=list, description="Directly affected sectors in the BIST universe")
    affected_tickers: list[str] = Field(default_factory=list, description="Optional explicit ticker overrides")
    base_positive_impacts: list[str] = Field(default_factory=list, description="Shared positive event impacts")
    base_negative_impacts: list[str] = Field(default_factory=list, description="Shared negative event impacts")
    sector_impact_overrides: list[SectorImpactOverride] = Field(default_factory=list, description="Optional sector-specific impact overrides")


class PreviewGlobalEventResponse(BaseModel):
    headline: str = Field(description="Global event headline or title")
    event_category: str = Field(description="Normalized macro category", examples=["geopolitics"])
    region: str = Field(description="Affected region", examples=["middle_east"])
    published_at: str = Field(description="Publish date of the event", examples=["2026-04-27"])
    source_name: str = Field(description="Originating feed or manual source label", examples=["manual_editor"])
    affected_sectors: list[str] = Field(description="Normalized affected sectors")
    derived_tickers: list[str] = Field(description="Tickers that would be affected by this event")
    sector_count: int = Field(description="Count of matched sectors", examples=[2])
    ticker_count: int = Field(description="Count of derived tickers", examples=[8])
    status: str = Field(description="Preview result", examples=["previewed"])


class IngestGlobalEventRequest(BaseModel):
    headline: str = Field(description="Global event headline or title")
    event_category: str = Field(description="Normalized macro category", examples=["geopolitics"])
    region: str = Field(description="Affected region", examples=["middle_east"])
    published_at: str = Field(description="Publish date of the event", examples=["2026-04-27"])
    source_name: str = Field(description="Originating feed or manual source label", examples=["manual_editor"])
    affected_sectors: list[str] = Field(default_factory=list, description="Directly affected sectors in the BIST universe")
    affected_tickers: list[str] = Field(default_factory=list, description="Optional explicit ticker overrides")
    base_positive_impacts: list[str] = Field(default_factory=list, description="Shared positive event impacts")
    base_negative_impacts: list[str] = Field(default_factory=list, description="Shared negative event impacts")
    sector_impact_overrides: list[SectorImpactOverride] = Field(default_factory=list, description="Optional sector-specific impact overrides")


class IngestGlobalEventResponse(BaseModel):
    headline: str = Field(description="Saved global event headline")
    event_category: str = Field(description="Saved macro category", examples=["geopolitics"])
    region: str = Field(description="Saved region", examples=["middle_east"])
    published_at: str = Field(description="Saved event date", examples=["2026-04-27"])
    source_name: str = Field(description="Originating feed or manual source label", examples=["manual_editor"])
    affected_sectors: list[str] = Field(description="Normalized affected sectors")
    tickers: list[str] = Field(description="Affected tickers saved into macro event store")
    ticker_count: int = Field(description="Count of saved tickers", examples=[8])
    status: str = Field(description="Ingest result", examples=["saved"])


class NewsItemResponse(BaseModel):
    ticker: str = Field(description="BIST ticker code", examples=["THYAO"])
    headline: str = Field(description="News headline")
    summary: str = Field(description="News summary")
    source_url: str = Field(description="Source URL")
    publisher: str = Field(description="News publisher", examples=["mock_news_feed"])
    published_at: str = Field(description="Publish date", examples=["2026-04-18"])
    tags: list[str] = Field(description="News tags")
    source: str = Field(description="News source", examples=["json_news_store"])


class NewsHistoryResponse(BaseModel):
    ticker: str = Field(description="BIST ticker code", examples=["THYAO"])
    total: int = Field(description="Number of returned news items", examples=[2])
    items: list[NewsItemResponse] = Field(description="Historical news items for the ticker")


class IngestNewsRequest(BaseModel):
    ticker: str = Field(description="BIST ticker code", examples=["THYAO"])
    headline: str = Field(description="News headline")
    summary: str = Field(description="News summary")
    source_url: str = Field(description="Source URL")
    publisher: str = Field(description="News publisher", examples=["manual_news_seed"])
    published_at: str = Field(description="Publish date", examples=["2026-04-19"])
    tags: list[str] = Field(description="News tags")


class IngestNewsResponse(BaseModel):
    ticker: str = Field(description="BIST ticker code", examples=["THYAO"])
    headline: str = Field(description="Saved news headline")
    published_at: str = Field(description="Saved news date", examples=["2026-04-19"])
    status: str = Field(description="Ingest result", examples=["saved", "skipped"])


class ConvertNewsToMacroRequest(BaseModel):
    ticker: str = Field(description="BIST ticker code", examples=["THYAO"])
    headline: str = Field(description="News headline to convert")
    published_at: str = Field(description="Publish date of the news item", examples=["2026-04-19"])


class ConvertNewsToMacroResponse(BaseModel):
    ticker: str = Field(description="BIST ticker code", examples=["THYAO"])
    latest_macro_event: str = Field(description="Derived macro event title")
    event_category: str = Field(description="Derived macro event category", examples=["energy"])
    region: str = Field(description="Derived macro event region", examples=["middle_east"])
    published_at: str = Field(description="Converted macro event date", examples=["2026-04-19"])
    status: str = Field(description="Conversion result", examples=["saved", "skipped"])


class NewsCleanupResponse(BaseModel):
    removed_count: int = Field(description="Number of removed duplicate news records", examples=[1])
    status: str = Field(description="Cleanup result", examples=["cleaned"])


class NewsMigrationResponse(BaseModel):
    total_json_records: int = Field(description="Number of JSON news records inspected", examples=[3])
    migrated_count: int = Field(description="Number of records moved into PostgreSQL", examples=[2])
    skipped_count: int = Field(description="Number of records skipped because they already existed", examples=[1])
    status: str = Field(description="Migration result", examples=["migrated", "no_changes"])


class MacroEventCleanupResponse(BaseModel):
    updated_count: int = Field(description="Number of normalized legacy macro event records", examples=[3])
    status: str = Field(description="Cleanup result", examples=["cleaned"])


class MacroEventMigrationResponse(BaseModel):
    total_json_records: int = Field(description="Number of JSON macro event records inspected", examples=[4])
    migrated_count: int = Field(description="Number of macro event records moved into PostgreSQL", examples=[4])
    skipped_count: int = Field(description="Number of macro event records skipped because they already existed", examples=[0])
    status: str = Field(description="Migration result", examples=["migrated", "no_changes"])


class ScanSnapshotCreateResponse(BaseModel):
    snapshot_id: int = Field(description="Database id for the saved snapshot", examples=[1])
    created_at: str = Field(description="Snapshot creation timestamp", examples=["2026-04-20T12:30:00"])
    stance_filter: str = Field(description="Applied stance filter for the snapshot", examples=["all"])
    total_returned: int = Field(description="Number of returned scan rows inside the snapshot", examples=[4])
    provider: str = Field(description="Market data provider used during the snapshot", examples=["mock"])
    market_data_source_summary: dict[str, int] = Field(default_factory=dict, description="Summary of market snapshot sources used in the scan")
    used_source_summary: dict[str, int] = Field(default_factory=dict, description="Summary of analysis sources used across the scan items")
    runtime_health_summary: dict = Field(default_factory=dict, description="Runtime scheduler health summary captured when the snapshot was saved")
    status: str = Field(description="Snapshot save result", examples=["saved"])


class ScanSnapshotHistoryItem(BaseModel):
    id: int = Field(description="Database id for the snapshot", examples=[1])
    created_at: str = Field(description="Snapshot creation timestamp", examples=["2026-04-20T12:30:00"])
    stance_filter: str = Field(description="Applied stance filter", examples=["all"])
    limit_requested: int = Field(description="Requested item limit", examples=[20])
    universe_size: int = Field(description="Scanned universe size", examples=[4])
    total_returned: int = Field(description="Number of returned items", examples=[4])
    provider: str = Field(description="Market data provider used during the snapshot", examples=["mock"])
    market_data_source_summary: dict[str, int] = Field(default_factory=dict, description="Summary of market snapshot sources used in the scan")
    used_source_summary: dict[str, int] = Field(default_factory=dict, description="Summary of analysis sources used across the scan items")
    runtime_health_summary: dict = Field(default_factory=dict, description="Runtime scheduler health summary captured when the snapshot was saved")


class ScanSnapshotHistoryResponse(BaseModel):
    total: int = Field(description="Number of returned snapshots", examples=[2])
    items: list[ScanSnapshotHistoryItem] = Field(description="Scan snapshot history items")


class ReplayCalibrationResponse(BaseModel):
    ticker: str = Field(description="BIST ticker code", examples=["THYAO"])
    timeframe: str = Field(description="Replay timeframe", examples=["1G"])
    horizon_bars: int = Field(description="Forward bars used in each replay sample", examples=[10])
    sample_size: int = Field(description="Number of replay samples included in calibration", examples=[12])
    entry_touch_rate: float = Field(description="Share of samples where entry zone was touched", examples=[0.42])
    take_profit_rate: float = Field(description="Share of samples where take-profit level was reached", examples=[0.58])
    stop_loss_rate: float = Field(description="Share of samples where stop-loss level was reached", examples=[0.25])
    positive_close_rate: float = Field(description="Share of samples closing positive over the evaluation horizon", examples=[0.67])
    average_close_return_percent: float = Field(description="Average close return across samples", examples=[2.18])
    average_max_upside_percent: float = Field(description="Average maximum upside excursion across samples", examples=[4.86])
    average_max_drawdown_percent: float = Field(description="Average maximum drawdown across samples", examples=[-2.11])
    calibration_bias: str = Field(description="Directional calibration label derived from replay samples", examples=["supportive"])
    calibration_summary: str = Field(description="Short summary of replay calibration quality")



class ReplayScorecardItem(BaseModel):
    ticker: str = Field(description="BIST ticker code", examples=["THYAO"])
    company_name: str = Field(description="Company name", examples=["Turkish Airlines"])
    sector: str = Field(description="Sector name", examples=["Airlines"])
    calibration_bias: str = Field(description="Replay calibration quality label", examples=["mixed"])
    scorecard_score: float = Field(description="Composite replay quality score used for ranking", examples=[18.4])
    entry_touch_rate: float = Field(description="Share of samples where entry zone was touched", examples=[0.62])
    take_profit_rate: float = Field(description="Share of samples where take-profit was reached", examples=[0.25])
    stop_loss_rate: float = Field(description="Share of samples where stop-loss was reached", examples=[0.5])
    positive_close_rate: float = Field(description="Share of samples closing positive over the evaluation horizon", examples=[0.38])
    average_close_return_percent: float = Field(description="Average close return across replay samples", examples=[-2.7])
    average_max_upside_percent: float = Field(description="Average maximum upside excursion across replay samples", examples=[6.38])
    average_max_drawdown_percent: float = Field(description="Average maximum drawdown across replay samples", examples=[-10.92])
    calibration_summary: str = Field(description="Short human-readable replay summary for the ticker")


class ReplayScorecardResponse(BaseModel):
    universe_code: str = Field(description="Universe used for the replay scorecard", examples=["bist100"])
    timeframe: str = Field(description="Replay timeframe", examples=["1G"])
    horizon_bars: int = Field(description="Forward bars used in each replay sample", examples=[10])
    sample_size: int = Field(description="Replay samples requested per ticker", examples=[8])
    total_universe: int = Field(description="Number of companies considered before replay filtering", examples=[83])
    evaluated_count: int = Field(description="Number of companies successfully evaluated", examples=[20])
    skipped_count: int = Field(description="Number of companies skipped because replay data or calibration was unavailable", examples=[4])
    items: list[ReplayScorecardItem] = Field(description="Ranked replay calibration scorecard items")


class ReplayEvaluationResponse(BaseModel):
    ticker: str = Field(description="BIST ticker code", examples=["THYAO"])
    timeframe: str = Field(description="Replay timeframe", examples=["1G"])
    as_of_timestamp: str = Field(description="Historical anchor timestamp used for the replay")
    horizon_bars: int = Field(description="Number of forward bars inspected after the anchor", examples=[10])
    evaluated_bars: int = Field(description="Number of bars that were actually available for evaluation", examples=[10])
    chart_feature: ChartFeatureResponse = Field(description="Historical chart feature snapshot at the anchor timestamp")
    entry_zone_touched: bool = Field(description="Whether the entry zone was touched in forward bars", examples=[True])
    breakout_buy_trigger_hit: bool = Field(description="Whether upside continuation trigger was hit", examples=[False])
    breakdown_sell_trigger_hit: bool = Field(description="Whether downside pressure trigger was hit", examples=[False])
    take_profit_hit: bool = Field(description="Whether take-profit level was reached", examples=[True])
    stop_loss_hit: bool = Field(description="Whether stop-loss level was reached", examples=[False])
    first_material_event: str | None = Field(default=None, description="First important event reached by price")
    close_return_percent: float = Field(description="Return from anchor close to evaluation close", examples=[4.25])
    max_upside_percent: float = Field(description="Maximum upside excursion during the evaluation window", examples=[6.8])
    max_drawdown_percent: float = Field(description="Maximum downside excursion during the evaluation window", examples=[-2.4])
    evaluation_summary: str = Field(description="Short summary of how the setup evolved")


class AnalysisRunHistoryItem(BaseModel):
    id: int = Field(description="Database id for the analysis run", examples=[1])
    ticker: str = Field(description="BIST ticker code", examples=["THYAO"])
    question: str = Field(description="Original user question")
    route_type: str = Field(description="Detected route type", examples=["analysis_query"])
    stance: str = Field(description="Recommendation stance for the run", examples=["bearish"])
    action: str = Field(description="Suggested action for the run", examples=["reduce"])
    confidence: float = Field(description="Confidence score recorded for the run", examples=[0.78])
    used_sources: list[str] = Field(description="Sources used during the run")
    recommendation_summary: str = Field(description="Stored recommendation or reasoning summary")
    created_at: str | None = Field(default=None, description="Creation timestamp for the analysis run", examples=["2026-04-20T10:15:00"])


class PaperDecisionLogCreateResponse(BaseModel):
    saved_count: int = Field(description="Number of saved paper decision records", examples=[1])
    source_mode: str = Field(description="Decision creation mode", examples=["ask"])
    tickers: list[str] = Field(description="Tickers captured in the save operation", examples=[["THYAO"]])
    stances: list[str] = Field(default_factory=list, description="Stance filters used during the save operation", examples=[["bullish", "neutral"]])
    batch_id: str | None = Field(default=None, description="Batch identifier for grouped scan captures", examples=["scan_20260427T083336Z_ab12cd34"])
    status: str = Field(description="Save result", examples=["saved"])


class PaperDecisionLogItem(BaseModel):
    id: int = Field(description="Database id for the paper decision log", examples=[1])
    ticker: str = Field(description="BIST ticker code", examples=["THYAO"])
    source_mode: str = Field(description="Whether the decision came from ask or scan capture", examples=["ask"])
    question: str = Field(description="Original question when available")
    stance: str = Field(description="Recorded stance", examples=["neutral"])
    action: str = Field(description="Recorded action", examples=["hold"])
    confidence: float = Field(description="Recorded confidence score", examples=[0.81])
    weighted_score: float = Field(description="Recorded weighted recommendation score", examples=[-0.55])
    decision_price: float = Field(description="Market price at the time of decision capture", examples=[322.75])
    current_price: float | None = Field(default=None, description="Latest available price when history is requested")
    current_return_percent: float | None = Field(default=None, description="Return from decision price to latest available price")
    market_data_source: str | None = Field(default=None, description="Source of the captured market price")
    batch_id: str | None = Field(default=None, description="Batch identifier when the log belongs to a grouped capture")
    trade_setup: str | None = Field(default=None, description="Captured trade setup label", examples=["trend_follow"])
    trend_reference_level: float | None = Field(default=None, description="Captured trend reference level")
    entry_zone_low: float | None = Field(default=None, description="Captured entry zone lower bound")
    entry_zone_high: float | None = Field(default=None, description="Captured entry zone upper bound")
    breakout_buy_trigger: float | None = Field(default=None, description="Captured breakout trigger")
    stop_loss_level: float | None = Field(default=None, description="Captured stop-loss level")
    take_profit_level: float | None = Field(default=None, description="Captured take-profit level")
    calibration_bias: str | None = Field(default=None, description="Replay calibration bias at capture time", examples=["mixed"])
    recommendation_summary: str = Field(description="Stored recommendation summary")
    used_sources: list[str] = Field(description="Sources used when the decision was captured")
    created_at: str | None = Field(default=None, description="Creation timestamp")


class PaperDecisionOutcomeResponse(BaseModel):
    log_id: int = Field(description="Paper decision log id", examples=[14])
    ticker: str = Field(description="BIST ticker code", examples=["THYAO"])
    source_mode: str = Field(description="Whether the record came from ask or scan", examples=["scan"])
    batch_id: str | None = Field(default=None, description="Batch identifier when the outcome belongs to a grouped capture")
    timeframe: str = Field(description="Evaluation timeframe", examples=["1G"])
    batch_id: str | None = Field(default=None, description="Batch identifier filter applied to the summary")
    horizon_bars: int = Field(description="Maximum number of forward bars inspected", examples=[10])
    evaluated_bars: int = Field(description="Number of forward bars actually available", examples=[4])
    decision_timestamp: str = Field(description="Timestamp when the decision was saved")
    decision_price: float = Field(description="Captured decision price", examples=[322.75])
    latest_close: float | None = Field(default=None, description="Latest close reached inside the evaluated horizon")
    close_return_percent: float | None = Field(default=None, description="Return from decision price to the last evaluated close")
    max_upside_percent: float | None = Field(default=None, description="Best upside excursion after the decision")
    max_drawdown_percent: float | None = Field(default=None, description="Worst downside excursion after the decision")
    entry_zone_touched: bool = Field(description="Whether the stored entry zone was touched after the decision")
    breakout_buy_trigger_hit: bool = Field(description="Whether the stored breakout trigger was reached")
    take_profit_hit: bool = Field(description="Whether the stored take-profit level was reached")
    stop_loss_hit: bool = Field(description="Whether the stored stop-loss level was reached")
    first_material_event: str | None = Field(default=None, description="First important event reached after the decision")
    outcome_label: str = Field(description="Outcome label such as pending, win, loss, mixed or open", examples=["win"])
    outcome_summary: str = Field(description="Short human-readable outcome summary")


class PaperDecisionPerformanceSummaryResponse(BaseModel):
    timeframe: str = Field(description="Evaluation timeframe", examples=["1G"])
    batch_id: str | None = Field(default=None, description="Batch identifier filter applied to the summary")
    horizon_bars: int = Field(description="Forward bars inspected for each outcome", examples=[10])
    total_logs: int = Field(description="Number of paper decision logs included in the summary", examples=[20])
    pending_count: int = Field(description="Logs without enough future bars yet", examples=[12])
    open_count: int = Field(description="Logs with future bars but no TP/SL hit yet", examples=[3])
    win_count: int = Field(description="Logs where TP was hit before SL-only outcome", examples=[4])
    loss_count: int = Field(description="Logs where SL was hit without TP", examples=[1])
    mixed_count: int = Field(description="Logs where both TP and SL were seen inside the horizon", examples=[0])
    resolved_count: int = Field(description="Logs that produced a non-pending outcome", examples=[8])
    bullish_count: int = Field(description="Number of bullish stance logs in the summary window", examples=[12])
    neutral_count: int = Field(description="Number of neutral stance logs in the summary window", examples=[6])
    bearish_count: int = Field(description="Number of bearish stance logs in the summary window", examples=[2])
    source_mode_counts: dict[str, int] = Field(default_factory=dict, description="Source-mode distribution such as ask vs scan")
    calibration_bias_counts: dict[str, int] = Field(default_factory=dict, description="Calibration bias distribution such as supportive, mixed, fragile")
    win_rate: float | None = Field(default=None, description="Share of resolved logs ending in win")
    loss_rate: float | None = Field(default=None, description="Share of resolved logs ending in loss")
    average_close_return_percent: float | None = Field(default=None, description="Average close return across resolved logs")
    average_max_upside_percent: float | None = Field(default=None, description="Average maximum upside across resolved logs")
    average_max_drawdown_percent: float | None = Field(default=None, description="Average maximum drawdown across resolved logs")
    summary: str = Field(description="Human-readable performance summary")


class PaperDecisionResolvedPerformanceSummaryResponse(BaseModel):
    timeframe: str = Field(description="Evaluation timeframe", examples=["1G"])
    batch_id: str | None = Field(default=None, description="Batch identifier filter applied to the resolved summary")
    horizon_bars: int = Field(description="Forward bars inspected for each outcome", examples=[10])
    total_logs: int = Field(description="Number of paper decision logs included in the selected window", examples=[20])
    resolved_count: int = Field(description="Number of non-pending outcomes", examples=[8])
    pending_count: int = Field(description="Number of still-pending outcomes", examples=[12])
    resolution_rate: float | None = Field(default=None, description="Resolved share of total logs")
    win_count: int = Field(description="Resolved outcomes labeled win", examples=[4])
    loss_count: int = Field(description="Resolved outcomes labeled loss", examples=[1])
    mixed_count: int = Field(description="Resolved outcomes labeled mixed", examples=[1])
    open_count: int = Field(description="Resolved outcomes labeled open", examples=[2])
    resolved_win_rate: float | None = Field(default=None, description="Win share among resolved outcomes")
    resolved_loss_rate: float | None = Field(default=None, description="Loss share among resolved outcomes")
    resolved_positive_close_rate: float | None = Field(default=None, description="Share of resolved outcomes with positive close return")
    bullish_resolved_count: int = Field(description="Resolved bullish stance count", examples=[5])
    neutral_resolved_count: int = Field(description="Resolved neutral stance count", examples=[3])
    bearish_resolved_count: int = Field(description="Resolved bearish stance count", examples=[0])
    average_close_return_percent: float | None = Field(default=None, description="Average close return across resolved outcomes")
    average_max_upside_percent: float | None = Field(default=None, description="Average max upside across resolved outcomes")
    average_max_drawdown_percent: float | None = Field(default=None, description="Average max drawdown across resolved outcomes")
    best_ticker: str | None = Field(default=None, description="Ticker with best resolved close return")
    best_close_return_percent: float | None = Field(default=None, description="Best resolved close return")
    worst_ticker: str | None = Field(default=None, description="Ticker with worst resolved close return")
    worst_close_return_percent: float | None = Field(default=None, description="Worst resolved close return")
    summary: str = Field(description="Human-readable resolved performance summary")


class PaperDecisionOutcomeHistoryResponse(BaseModel):
    total: int = Field(description="Number of evaluated paper decision outcomes", examples=[10])
    items: list[PaperDecisionOutcomeResponse] = Field(description="Paper decision outcome rows")


class PaperDecisionLogHistoryResponse(BaseModel):
    total: int = Field(description="Number of returned paper decision logs", examples=[10])
    items: list[PaperDecisionLogItem] = Field(description="Paper decision history rows")


class AnalysisRunHistoryResponse(BaseModel):
    total: int = Field(description="Number of returned analysis runs", examples=[2])
    items: list[AnalysisRunHistoryItem] = Field(description="Analysis run history items")


class AnalysisEvidence(BaseModel):
    category: str = Field(description="Evidence category", examples=["signal"])
    impact: str = Field(description="Whether the evidence supports upside or downside", examples=["positive"])
    detail: str = Field(description="Evidence detail text")
    source: str = Field(description="Evidence source", examples=["mock_signal_service"])


class RecommendationPolicyResult(BaseModel):
    stance: str = Field(description="Recommendation stance", examples=["bullish"])
    action: str = Field(description="Suggested action", examples=["buy"])
    score: int = Field(description="Net evidence score", examples=[3])
    weighted_score: float = Field(description="Weighted net evidence score", examples=[2.5])
    summary: str = Field(description="Short explanation for the recommendation")
