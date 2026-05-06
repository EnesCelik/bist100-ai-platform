from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd
from fastapi import HTTPException

from app.data_sources.company_data.provider import list_company_records
from app.data_sources.market_data.provider import get_market_ohlcv
from app.models.schemas import ReplayCalibrationResponse, ReplayEvaluationResponse, ReplayScorecardItem, ReplayScorecardResponse
from app.services.chart_feature_service import fetch_chart_feature_summary


_calibration_cache: dict[tuple[str, str, int, int, int], tuple[datetime, ReplayCalibrationResponse]] = {}
_CALIBRATION_TTL = timedelta(hours=6)


def get_trade_calibration_cached(
    ticker: str,
    timeframe: str = "1G",
    horizon_bars: int = 10,
    sample_size: int = 8,
    step_bars: int = 5,
    use_cache_only: bool = False,
) -> ReplayCalibrationResponse | None:
    key = (ticker.upper().strip(), timeframe.upper().strip() or "1G", horizon_bars, sample_size, step_bars)
    cached = _calibration_cache.get(key)
    if cached is not None:
        cached_at, payload = cached
        if datetime.utcnow() - cached_at <= _CALIBRATION_TTL:
            return payload

    if use_cache_only:
        return None

    payload = evaluate_trade_calibration(
        ticker=ticker,
        timeframe=timeframe,
        horizon_bars=horizon_bars,
        sample_size=sample_size,
        step_bars=step_bars,
    )
    _calibration_cache[key] = (datetime.utcnow(), payload)
    return payload


def build_trade_calibration_signals(calibration: ReplayCalibrationResponse | None) -> tuple[list[str], list[str]]:
    if calibration is None:
        return [], []

    positives: list[str] = []
    negatives: list[str] = []

    if calibration.calibration_bias == "supportive":
        positives.append("Replay kalibrasyonu son donemde teknik seviye planinin destekleyici calistigini gosteriyor")
        if calibration.take_profit_rate >= 0.6 and calibration.stop_loss_rate <= 0.2:
            positives.append("Take-profit orani stop-loss oraninin belirgin uzerinde kalarak teknik setup'i teyit ediyor")
        elif calibration.positive_close_rate >= 0.75 and calibration.average_close_return_percent > 0:
            positives.append("Pozitif kapanis orani yuksek kalarak teknik seviyelerin tasinabilirligini destekliyor")
        return positives, negatives

    if calibration.calibration_bias == "fragile":
        negatives.append("Replay kalibrasyonu teknik seviyelerin son donemde kirilgan calistigini gosteriyor")
        if calibration.stop_loss_rate >= calibration.take_profit_rate:
            negatives.append("Stop-loss orani take-profit oraninin uzerinde kalarak teknik setup guvenini zayiflatiyor")
        if calibration.positive_close_rate <= 0.45 or calibration.average_close_return_percent < 0:
            negatives.append("Pozitif kapanis kalitesi zayif kalarak ortalama getiriyi baski altinda birakiyor")
        return positives, negatives

    negatives.append("Replay kalibrasyonu teknik seviye performansinin karisik kaldigini gosteriyor")
    if calibration.average_close_return_percent <= 0:
        negatives.append("Ortalama kapanis getirisi sifirin altinda kalarak teknik avantajin netlesmedigine isaret ediyor")
    elif calibration.stop_loss_rate > calibration.take_profit_rate:
        negatives.append("Stop-loss orani take-profit oranini asarak teknik planin istikrarini zayiflatiyor")
    return positives, negatives


def _load_replay_dataframe(ticker: str, timeframe: str, bars: int) -> pd.DataFrame:
    payload = get_market_ohlcv(ticker, timeframe=timeframe, bars=bars)
    if payload is None or not payload.candles:
        raise HTTPException(status_code=404, detail=f"Replay verisi ticker '{ticker.upper()}' icin bulunamadi.")

    df = pd.DataFrame([bar.model_dump() for bar in payload.candles])
    if df.empty:
        raise HTTPException(status_code=404, detail=f"Replay verisi ticker '{ticker.upper()}' icin bulunamadi.")

    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    return df.sort_values("timestamp").reset_index(drop=True)


def _pick_anchor_index(df: pd.DataFrame, horizon_bars: int, as_of_timestamp: str | None) -> int:
    max_anchor_index = len(df) - horizon_bars - 1
    if max_anchor_index < 30:
        raise HTTPException(status_code=400, detail="Replay icin yeterli gecmis veya ileri bar yok.")

    if as_of_timestamp is None:
        return max_anchor_index

    cutoff = pd.to_datetime(as_of_timestamp, utc=True)
    eligible = df.index[df["timestamp"] <= cutoff].tolist()
    if not eligible:
        raise HTTPException(status_code=404, detail="Istenen replay zamani icin bar bulunamadi.")

    anchor_index = eligible[-1]
    if anchor_index > max_anchor_index:
        raise HTTPException(status_code=400, detail="Secilen replay zamani sonraki barlar olmadan degerlendirilemez.")
    if anchor_index < 30:
        raise HTTPException(status_code=400, detail="Secilen replay zamani teknik hesap icin yeterli gecmis bar icermiyor.")
    return anchor_index


def _first_material_event(future_df: pd.DataFrame, chart_feature) -> str | None:
    if future_df.empty:
        return None

    bullish_like = chart_feature.trade_setup in {"pullback_buy", "trend_follow", "breakout_watch", "range_trade"}

    for _, row in future_df.iterrows():
        if bullish_like:
            if row["low"] <= chart_feature.stop_loss_level:
                return "stop_loss"
            if row["high"] >= chart_feature.take_profit_level:
                return "take_profit"
            if row["high"] >= chart_feature.breakout_buy_trigger:
                return "breakout_buy_trigger"
            if row["low"] <= chart_feature.entry_zone_high and row["high"] >= chart_feature.entry_zone_low:
                return "entry_zone"
        else:
            if row["high"] >= chart_feature.stop_loss_level:
                return "stop_loss"
            if row["low"] <= chart_feature.take_profit_level:
                return "take_profit"
            if row["low"] <= chart_feature.breakdown_sell_trigger:
                return "breakdown_sell_trigger"
            if row["low"] <= chart_feature.entry_zone_high and row["high"] >= chart_feature.entry_zone_low:
                return "entry_zone"
    return None


def _evaluate_on_anchor(df: pd.DataFrame, normalized_ticker: str, normalized_timeframe: str, anchor_index: int, horizon_bars: int) -> ReplayEvaluationResponse:
    anchor_row = df.iloc[anchor_index]
    anchor_ts = anchor_row["timestamp"].isoformat()

    chart_feature = fetch_chart_feature_summary(
        normalized_ticker,
        timeframe=normalized_timeframe,
        as_of_timestamp=anchor_ts,
    )

    future_df = df.iloc[anchor_index + 1 : anchor_index + 1 + horizon_bars].copy()
    evaluated_bars = len(future_df)
    if evaluated_bars == 0:
        raise HTTPException(status_code=400, detail="Replay icin ileriye donuk degerlendirilecek bar bulunamadi.")

    entry_zone_touched = bool(((future_df["low"] <= chart_feature.entry_zone_high) & (future_df["high"] >= chart_feature.entry_zone_low)).any())
    breakout_buy_trigger_hit = bool((future_df["high"] >= chart_feature.breakout_buy_trigger).any())
    breakdown_sell_trigger_hit = bool((future_df["low"] <= chart_feature.breakdown_sell_trigger).any())

    bullish_like = chart_feature.trade_setup in {"pullback_buy", "trend_follow", "breakout_watch", "range_trade"}
    if bullish_like:
        take_profit_hit = bool((future_df["high"] >= chart_feature.take_profit_level).any())
        stop_loss_hit = bool((future_df["low"] <= chart_feature.stop_loss_level).any())
        max_upside_percent = round(((future_df["high"].max() / chart_feature.current_price) - 1) * 100, 2)
        max_drawdown_percent = round(((future_df["low"].min() / chart_feature.current_price) - 1) * 100, 2)
    else:
        take_profit_hit = bool((future_df["low"] <= chart_feature.take_profit_level).any())
        stop_loss_hit = bool((future_df["high"] >= chart_feature.stop_loss_level).any())
        max_upside_percent = round(((future_df["high"].max() / chart_feature.current_price) - 1) * 100, 2)
        max_drawdown_percent = round(((future_df["low"].min() / chart_feature.current_price) - 1) * 100, 2)

    close_return_percent = round(((float(future_df.iloc[-1]["close"]) / chart_feature.current_price) - 1) * 100, 2)
    first_event = _first_material_event(future_df, chart_feature)

    summary_parts = [
        f"{normalized_ticker} icin {anchor_ts} anindaki {chart_feature.trade_setup} setup'i sonraki {evaluated_bars} barda izlendi",
        f"entry temasi {'geldi' if entry_zone_touched else 'gelmedi'}",
        f"TP {'goruldu' if take_profit_hit else 'gorulmedi'}",
        f"SL {'calisti' if stop_loss_hit else 'calismadi'}",
        f"kapanis getirisi %{close_return_percent}",
    ]
    if first_event is not None:
        summary_parts.append(f"ilk kritik olay {first_event}")

    return ReplayEvaluationResponse(
        ticker=normalized_ticker,
        timeframe=normalized_timeframe,
        as_of_timestamp=anchor_ts,
        horizon_bars=horizon_bars,
        evaluated_bars=evaluated_bars,
        chart_feature=chart_feature,
        entry_zone_touched=entry_zone_touched,
        breakout_buy_trigger_hit=breakout_buy_trigger_hit,
        breakdown_sell_trigger_hit=breakdown_sell_trigger_hit,
        take_profit_hit=take_profit_hit,
        stop_loss_hit=stop_loss_hit,
        first_material_event=first_event,
        close_return_percent=close_return_percent,
        max_upside_percent=max_upside_percent,
        max_drawdown_percent=max_drawdown_percent,
        evaluation_summary=". ".join(summary_parts) + ".",
    )


def evaluate_trade_replay(
    ticker: str,
    timeframe: str = "1G",
    horizon_bars: int = 10,
    as_of_timestamp: str | None = None,
) -> ReplayEvaluationResponse:
    normalized_ticker = ticker.upper().strip()
    normalized_timeframe = timeframe.upper().strip() or "1G"
    bars = max(240, horizon_bars + 180)

    df = _load_replay_dataframe(normalized_ticker, normalized_timeframe, bars=bars)
    anchor_index = _pick_anchor_index(df, horizon_bars, as_of_timestamp)
    return _evaluate_on_anchor(df, normalized_ticker, normalized_timeframe, anchor_index, horizon_bars)


def evaluate_trade_calibration(
    ticker: str,
    timeframe: str = "1G",
    horizon_bars: int = 10,
    sample_size: int = 12,
    step_bars: int = 5,
) -> ReplayCalibrationResponse:
    normalized_ticker = ticker.upper().strip()
    normalized_timeframe = timeframe.upper().strip() or "1G"
    bars = max(360, horizon_bars + (sample_size * step_bars) + 220)

    df = _load_replay_dataframe(normalized_ticker, normalized_timeframe, bars=bars)
    max_anchor_index = len(df) - horizon_bars - 1
    if max_anchor_index < 40:
        raise HTTPException(status_code=400, detail="Kalibrasyon icin yeterli bar yok.")

    anchor_indexes: list[int] = []
    current = max_anchor_index
    min_anchor_index = 30
    while current >= min_anchor_index and len(anchor_indexes) < sample_size:
        anchor_indexes.append(current)
        current -= max(step_bars, 1)

    if not anchor_indexes:
        raise HTTPException(status_code=400, detail="Kalibrasyon icin uygun anchor bulunamadi.")

    results = [_evaluate_on_anchor(df, normalized_ticker, normalized_timeframe, idx, horizon_bars) for idx in anchor_indexes]
    sample_count = len(results)

    entry_touch_rate = round(sum(1 for item in results if item.entry_zone_touched) / sample_count, 2)
    take_profit_rate = round(sum(1 for item in results if item.take_profit_hit) / sample_count, 2)
    stop_loss_rate = round(sum(1 for item in results if item.stop_loss_hit) / sample_count, 2)
    positive_close_rate = round(sum(1 for item in results if item.close_return_percent > 0) / sample_count, 2)
    average_close_return_percent = round(sum(item.close_return_percent for item in results) / sample_count, 2)
    average_max_upside_percent = round(sum(item.max_upside_percent for item in results) / sample_count, 2)
    average_max_drawdown_percent = round(sum(item.max_drawdown_percent for item in results) / sample_count, 2)

    calibration_score = (take_profit_rate * 1.2) + (positive_close_rate * 0.8) - (stop_loss_rate * 1.0)
    if calibration_score >= 0.9:
        calibration_bias = "supportive"
    elif calibration_score <= 0.15:
        calibration_bias = "fragile"
    else:
        calibration_bias = "mixed"

    calibration_summary = (
        f"{normalized_ticker} icin son {sample_count} replay setup'inda TP orani %{round(take_profit_rate * 100, 1)}, "
        f"SL orani %{round(stop_loss_rate * 100, 1)}, pozitif kapanis orani %{round(positive_close_rate * 100, 1)}. "
        f"Ortalama kapanis getirisi %{average_close_return_percent}."
    )

    return ReplayCalibrationResponse(
        ticker=normalized_ticker,
        timeframe=normalized_timeframe,
        horizon_bars=horizon_bars,
        sample_size=sample_count,
        entry_touch_rate=entry_touch_rate,
        take_profit_rate=take_profit_rate,
        stop_loss_rate=stop_loss_rate,
        positive_close_rate=positive_close_rate,
        average_close_return_percent=average_close_return_percent,
        average_max_upside_percent=average_max_upside_percent,
        average_max_drawdown_percent=average_max_drawdown_percent,
        calibration_bias=calibration_bias,
        calibration_summary=calibration_summary,
    )


def _scorecard_numeric_score(calibration: ReplayCalibrationResponse) -> float:
    bias_bonus_map = {
        "supportive": 18.0,
        "mixed": 8.0,
        "fragile": 0.0,
    }
    score = (
        bias_bonus_map.get(calibration.calibration_bias, 0.0)
        + (calibration.take_profit_rate * 22.0)
        + (calibration.positive_close_rate * 18.0)
        + (calibration.entry_touch_rate * 8.0)
        - (calibration.stop_loss_rate * 20.0)
        + (calibration.average_close_return_percent * 1.6)
        + (calibration.average_max_upside_percent * 0.55)
        + (calibration.average_max_drawdown_percent * 0.35)
    )
    return round(score, 2)


_BIAS_SORT_ORDER = {
    "supportive": 0,
    "mixed": 1,
    "fragile": 2,
}


def evaluate_trade_scorecard(
    universe_code: str = "bist100",
    timeframe: str = "1G",
    horizon_bars: int = 10,
    sample_size: int = 8,
    step_bars: int = 5,
    limit: int = 20,
    cache_only: bool = False,
    tickers: list[str] | None = None,
) -> ReplayScorecardResponse:
    normalized_universe = (universe_code or "bist100").lower().strip() or "bist100"
    normalized_timeframe = timeframe.upper().strip() or "1G"
    companies = list_company_records(universe_code=normalized_universe)
    if tickers:
        allowed = {ticker.upper().strip() for ticker in tickers if ticker and ticker.strip()}
        companies = [company for company in companies if company.ticker in allowed]
    if not companies:
        raise HTTPException(status_code=404, detail="Scorecard icin uygun sirket bulunamadi.")

    items: list[ReplayScorecardItem] = []
    skipped_count = 0
    for company in companies:
        try:
            calibration = get_trade_calibration_cached(
                company.ticker,
                timeframe=normalized_timeframe,
                horizon_bars=horizon_bars,
                sample_size=sample_size,
                step_bars=step_bars,
                use_cache_only=cache_only,
            )
        except HTTPException:
            calibration = None

        if calibration is None:
            skipped_count += 1
            continue

        items.append(
            ReplayScorecardItem(
                ticker=company.ticker,
                company_name=company.name,
                sector=company.sector,
                calibration_bias=calibration.calibration_bias,
                scorecard_score=_scorecard_numeric_score(calibration),
                entry_touch_rate=calibration.entry_touch_rate,
                take_profit_rate=calibration.take_profit_rate,
                stop_loss_rate=calibration.stop_loss_rate,
                positive_close_rate=calibration.positive_close_rate,
                average_close_return_percent=calibration.average_close_return_percent,
                average_max_upside_percent=calibration.average_max_upside_percent,
                average_max_drawdown_percent=calibration.average_max_drawdown_percent,
                calibration_summary=calibration.calibration_summary,
            )
        )

    items.sort(
        key=lambda item: (
            _BIAS_SORT_ORDER.get(item.calibration_bias, 3),
            -item.scorecard_score,
            -item.average_close_return_percent,
            -item.take_profit_rate,
            item.stop_loss_rate,
        )
    )

    return ReplayScorecardResponse(
        universe_code=normalized_universe,
        timeframe=normalized_timeframe,
        horizon_bars=horizon_bars,
        sample_size=sample_size,
        total_universe=len(companies),
        evaluated_count=len(items),
        skipped_count=skipped_count,
        items=items[:limit],
    )

