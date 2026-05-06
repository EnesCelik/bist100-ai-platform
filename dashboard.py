import json
import math
from datetime import datetime, timedelta
from urllib import error, parse, request

import altair as alt
import pandas as pd
import streamlit as st


API_DEFAULT = "http://127.0.0.1:8000/api/v1"


def format_tr_number(value: float | int | None, decimals: int = 2) -> str:
    if value is None:
        return "-"
    formatted = f"{float(value):,.{decimals}f}"
    return formatted.replace(",", "_").replace(".", ",").replace("_", ".")


def format_tr_int(value: float | int | None) -> str:
    if value is None:
        return "-"
    return f"{int(round(float(value))):,}".replace(",", ".")


def humanize_slug(value: str | None) -> str:
    if not value:
        return "-"
    mapping = {
        "confirmed_breakout_up": "Yukari Kirilim Teyidi",
        "breakout_watch_up": "Yukari Kirilim Izleme",
        "confirmed_breakout_down": "Asagi Kirilim Teyidi",
        "breakout_watch_down": "Asagi Kirilim Izleme",
        "support_test": "Destek Testi",
        "resistance_test": "Direnc Testi",
        "range": "Yatay Bolge",
        "near_support": "Destege Yakin",
        "near_resistance": "Dirence Yakin",
        "mid_range": "Band Ortasi",
        "compressed_between_levels": "Sikisan Alan",
        "bullish": "Pozitif",
        "bearish": "Negatif",
        "neutral": "Dengeli",
        "higher_highs_and_higher_lows": "Yukselen Tepe ve Dipler",
        "lower_highs_near_support": "Dusuk Tepe ve Destek Baskisi",
        "mixed_stack": "Karisik Ortalama Dizilimi",
        "bullish_stack": "Pozitif Ortalama Dizilimi",
        "moderate": "Orta",
        "strong": "Guclu",
        "weak": "Zayif",
        "pullback_buy": "Destekten Alim",
        "trend_follow": "Trend Takibi",
        "breakout_watch": "Kirilim Izleme",
        "range_trade": "Bant Ici Islem",
        "sell_rally": "Tepki Satisi",
        "breakdown_watch": "Asagi Kirilim Izleme",
    }
    if value in mapping:
        return mapping[value]
    return value.replace("_", " ").title()




def build_readable_source(raw: str | None) -> str:
    if not raw:
        return "-"
    mapping = {
        "yahoo_delayed_market_data": "Yahoo Gecikmeli",
        "yahoo_delayed_market_data_cache": "Yahoo Cache",
        "mock_market_data_tool": "Mock Veri",
        "yahoo_delayed_ohlcv": "Yahoo OHLCV",
        "yahoo_delayed_ohlcv_cache": "Yahoo OHLCV Cache",
    }
    return mapping.get(raw, raw.replace("_", " ").title())


def build_runtime_status_label(value: str | None) -> str:
    mapping = {
        None: "-",
        "ok": "Hazir",
        "running": "Calisiyor",
        "error": "Hata",
    }
    return mapping.get(value, value or "-")


def summarize_mapping(values: dict | None, limit: int = 3) -> str:
    if not values:
        return "-"
    items = sorted(values.items(), key=lambda item: (-item[1], item[0]))[:limit]
    return " · ".join([f"{key}: {value}" for key, value in items])


def build_readable_technical_summary(raw: str | None) -> str:
    if not raw:
        return "-"
    parts = [part.strip() for part in raw.split("·")]
    if not parts:
        return raw
    normalized = []
    for part in parts:
        lower = part.lower()
        if lower.startswith("rsi"):
            normalized.append(part.upper().replace(" ", " "))
        else:
            normalized.append(humanize_slug(lower))
    return " · ".join(normalized)


def api_get(base_url: str, path: str, params: dict | None = None) -> dict:
    query = f"?{parse.urlencode(params)}" if params else ""
    url = f"{base_url}{path}{query}"
    try:
        with request.urlopen(url) as response:
            return json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8")
        raise RuntimeError(f"GET {path} failed: {detail}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"API baglantisi kurulamadi: {exc.reason}") from exc


def api_post(base_url: str, path: str, payload: dict) -> dict:
    url = f"{base_url}{path}"
    data = json.dumps(payload).encode("utf-8")
    req = request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with request.urlopen(req) as response:
            return json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8")
        raise RuntimeError(f"POST {path} failed: {detail}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"API baglantisi kurulamadi: {exc.reason}") from exc


def load_scan(base_url: str, stance: str | None = None, limit: int = 100) -> dict:
    params = {"limit": limit}
    if stance:
        params["stance"] = stance
    return api_get(base_url, "/scan/market", params)


def load_ticker_bundle(base_url: str, ticker: str, timeframe: str = "1G") -> dict:
    bundle: dict[str, dict | str] = {}
    for name, path in [
        ("company", f"/companies/{ticker}"),
        ("chart", f"/chart-features/{ticker}"),
        ("news", f"/news/history/{ticker}"),
        ("macro", f"/macro-events/history/{ticker}"),
        ("runs", f"/analysis-runs?ticker={ticker}&limit=5"),
    ]:
        try:
            if name == "runs":
                bundle[name] = api_get(base_url, "/analysis-runs", {"ticker": ticker, "limit": 5})
            elif name == "chart":
                bundle[name] = api_get(base_url, path, {"timeframe": timeframe})
            else:
                bundle[name] = api_get(base_url, path)
        except RuntimeError as exc:
            bundle[name] = str(exc)
    return bundle


def load_scan_history(base_url: str, limit: int = 5) -> dict | str:
    try:
        return api_get(base_url, "/scan/history", {"limit": limit})
    except RuntimeError as exc:
        return str(exc)


def load_runtime_health(base_url: str) -> dict | str:
    try:
        return api_get(base_url, "/health/runtime")
    except RuntimeError as exc:
        return str(exc)


def load_ohlcv_series(base_url: str, ticker: str, timeframe: str, bars: int) -> dict | str:
    try:
        return api_get(base_url, f"/market-data/{ticker}/ohlcv", {"timeframe": timeframe, "bars": bars})
    except RuntimeError as exc:
        return str(exc)


def load_market_debug(base_url: str, ticker: str, timeframe: str = "1G") -> dict | str:
    try:
        return api_get(base_url, f"/market-data/{ticker}/debug", {"timeframe": timeframe})
    except RuntimeError as exc:
        return str(exc)


def inject_styles() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;700&family=IBM+Plex+Serif:wght@500;600&display=swap');
        :root {
            --bg: #f6f0e6;
            --card: #fffaf2;
            --ink: #1f2a24;
            --muted: #68756d;
            --line: #d8cdbf;
            --bull: #2f7d57;
            --bear: #a2452d;
            --accent: #b88a44;
        }
        .stApp {
            background: radial-gradient(circle at top left, #fff9ef 0%, var(--bg) 55%, #efe4d3 100%);
            color: var(--ink);
        }
        html, body, [class*="css"] {
            font-family: 'Space Grotesk', sans-serif;
        }
        h1, h2, h3 {
            font-family: 'IBM Plex Serif', serif !important;
            letter-spacing: -0.02em;
            color: var(--ink);
        }
        .block-container {
            padding-top: 2rem;
            padding-bottom: 2rem;
            max-width: 1320px;
        }
        .hero {
            background: linear-gradient(135deg, rgba(31,42,36,0.98), rgba(49,74,61,0.96));
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 24px;
            padding: 1.4rem 1.4rem 1.1rem 1.4rem;
            color: #f7f3ec;
            box-shadow: 0 18px 45px rgba(31,42,36,0.16);
            margin-bottom: 1rem;
        }
        .hero p { color: rgba(247,243,236,0.86); }
        .chip-row {
            display: flex;
            gap: .6rem;
            flex-wrap: wrap;
            margin-top: .9rem;
        }
        .chip {
            border-radius: 999px;
            padding: .4rem .8rem;
            font-size: .86rem;
            border: 1px solid rgba(255,255,255,0.15);
            background: rgba(255,255,255,0.08);
        }
        .metric-card, .panel-card, .scan-card {
            background: var(--card);
            border: 1px solid var(--line);
            border-radius: 22px;
            padding: 1rem 1rem .95rem 1rem;
            box-shadow: 0 10px 25px rgba(88,66,44,0.06);
        }
        .metric-value {
            font-size: 1.55rem;
            font-weight: 700;
            margin-top: .15rem;
        }
        .label {
            text-transform: uppercase;
            letter-spacing: .08em;
            font-size: .73rem;
            color: var(--muted);
        }
        .headline-strip {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: .8rem;
            margin: 1rem 0 1rem 0;
        }
        .headline-box {
            background: rgba(255,250,242,0.8);
            border: 1px solid var(--line);
            border-radius: 18px;
            padding: .95rem 1rem;
            box-shadow: 0 10px 20px rgba(88,66,44,0.05);
        }
        .scan-card {
            margin-bottom: .85rem;
            padding-bottom: .8rem;
        }
        .scan-top {
            display: flex;
            justify-content: space-between;
            align-items: baseline;
            gap: 1rem;
        }
        .ticker {
            font-weight: 700;
            font-size: 1.15rem;
        }
        .sector {
            color: var(--muted);
            font-size: .88rem;
        }
        .stance-bullish, .stance-bearish, .stance-neutral {
            font-size: .78rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: .08em;
            border-radius: 999px;
            padding: .38rem .62rem;
            display: inline-block;
        }
        .stance-bullish { background: rgba(47,125,87,0.14); color: var(--bull); }
        .stance-bearish { background: rgba(162,69,45,0.12); color: var(--bear); }
        .stance-neutral { background: rgba(104,117,109,0.12); color: var(--muted); }
        .factor-pill {
            display: inline-block;
            margin: .2rem .28rem .15rem 0;
            padding: .3rem .55rem;
            border-radius: 999px;
            font-size: .78rem;
            background: #f1e7da;
            color: #4a534d;
        }
        .factor-pos { background: rgba(47,125,87,0.11); color: var(--bull); }
        .factor-neg { background: rgba(162,69,45,0.10); color: var(--bear); }
        .detail-title {
            font-weight: 700;
            font-size: 1rem;
            margin-bottom: .5rem;
        }
        .mini-divider {
            height: 1px;
            background: var(--line);
            margin: .75rem 0;
        }
        .meter-wrap {
            margin: .5rem 0 .85rem 0;
        }
        .meter-label {
            font-size: .8rem;
            color: var(--muted);
            margin-bottom: .2rem;
        }
        .meter-track {
            width: 100%;
            height: 10px;
            border-radius: 999px;
            background: #eadfce;
            overflow: hidden;
        }
        .meter-fill-bull, .meter-fill-bear, .meter-fill-neutral {
            height: 100%;
            border-radius: 999px;
        }
        .meter-fill-bull { background: linear-gradient(90deg, #6fc196, #2f7d57); }
        .meter-fill-bear { background: linear-gradient(90deg, #d98a72, #a2452d); }
        .meter-fill-neutral { background: linear-gradient(90deg, #b9b1a3, #7f867f); }
        .mini-grid {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: .45rem;
            margin: .9rem 0 .55rem 0;
        }
        .mini-stat {
            border: 1px solid var(--line);
            border-radius: 14px;
            padding: .65rem .75rem;
            background: rgba(255,250,242,0.7);
        }
        .mini-stat .k {
            font-size: .72rem;
            color: var(--muted);
            text-transform: uppercase;
            letter-spacing: .08em;
        }
        .mini-stat .v {
            font-size: .98rem;
            font-weight: 700;
            color: var(--ink);
            margin-top: .15rem;
        }
        .source-badge {
            display: inline-block;
            margin: .35rem 0 .5rem 0;
            padding: .34rem .65rem;
            border-radius: 999px;
            font-size: .77rem;
            font-weight: 700;
            letter-spacing: .04em;
            border: 1px solid var(--line);
        }
        .source-live {
            background: rgba(47,125,87,0.11);
            color: var(--bull);
        }
        .source-fallback {
            background: rgba(184,138,68,0.13);
            color: #8a6428;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_scan_cards(items: list[dict], empty_message: str, key_prefix: str) -> None:
    if not items:
        st.info(empty_message)
        return

    for item in items:
        stance_class = f"stance-{item['stance'].lower()}"
        st.markdown(
            f"""
            <div class="scan-card">
                <div class="scan-top">
                    <div>
                        <div class="ticker">{item['ticker']}</div>
                        <div class="sector">{item['company_name']} · {item['sector']}</div>
                    </div>
                    <div class="{stance_class}">{item['stance']} · {item['action']}</div>
                </div>
                <div class="chip-row">
                    <span class="chip">Confidence {item['confidence']}</span>
                    <span class="chip">Weighted {item['weighted_score']}</span>
                    <span class="chip">Price {format_tr_number(item['last_price']) if item['last_price'] is not None else '-'}</span>
                    <span class="chip">Vol {format_tr_int(item['volume']) if item['volume'] is not None else '-'}</span>
                </div>
                <p style="margin-top:.9rem; color:#435048;">{item['summary']}</p>
                <p style="margin-top:.45rem; color:#68756d; font-size:.9rem;">Teknik: {build_readable_technical_summary(item.get('technical_summary'))} </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button(f"{item['ticker']} detayini ac", key=f"{key_prefix}_{item['ticker']}", use_container_width=True):
            st.session_state["selected_ticker"] = item["ticker"]
            st.rerun()


def _meter_variant(kind: str) -> str:
    if kind == "bullish":
        return "meter-fill-bull"
    if kind == "bearish":
        return "meter-fill-bear"
    return "meter-fill-neutral"


def render_meter(title: str, value: float, variant: str, right_label: str) -> None:
    clipped = max(0.0, min(value, 100.0))
    st.markdown(
        f"""
        <div class='meter-wrap'>
            <div class='meter-label'>{title} · {right_label}</div>
            <div class='meter-track'>
                <div class='{_meter_variant(variant)}' style='width:{clipped}%;'></div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_chart_feature_visual(chart: dict) -> None:
    level_rows = [
        {"Seviye": "Support", "Deger": chart["nearest_support"], "Tur": "support"},
        {"Seviye": "EMA200", "Deger": chart["ema200"], "Tur": "ema"},
        {"Seviye": "EMA50", "Deger": chart["ema50"], "Tur": "ema"},
        {"Seviye": "EMA20", "Deger": chart["ema20"], "Tur": "ema"},
        {"Seviye": "Price", "Deger": chart.get("current_price", chart.get("last_price", 0)) or 0, "Tur": "price"},
        {"Seviye": "Resistance", "Deger": chart["nearest_resistance"], "Tur": "resistance"},
    ]
    levels_df = pd.DataFrame(level_rows)

    level_chart = (
        alt.Chart(levels_df)
        .mark_bar(cornerRadius=6)
        .encode(
            x=alt.X("Deger:Q", title="Seviye"),
            y=alt.Y("Seviye:N", sort=["Support", "EMA200", "EMA50", "EMA20", "Price", "Resistance"], title=""),
            color=alt.Color(
                "Tur:N",
                scale=alt.Scale(
                    domain=["support", "ema", "price", "resistance"],
                    range=["#2f7d57", "#b88a44", "#1f2a24", "#a2452d"],
                ),
                legend=None,
            ),
            tooltip=["Seviye:N", alt.Tooltip("Deger:Q", format=".2f")],
        )
        .properties(height=220)
    )
    st.altair_chart(level_chart, use_container_width=True)

    meter_cols = st.columns(3)
    with meter_cols[0]:
        render_meter("RSI", float(chart["rsi14"]), "neutral", f"{chart['rsi14']}")
    with meter_cols[1]:
        render_meter("Price Position", float(chart["price_position_percent"]), chart["signal_bias"] if chart["signal_bias"] in {"bullish", "bearish"} else "neutral", f"{chart['price_position_percent']}%")
    with meter_cols[2]:
        render_meter("Volume Ratio", min(float(chart["volume_ratio"]) * 50, 100), chart["signal_bias"] if chart["signal_bias"] in {"bullish", "bearish"} else "neutral", f"{chart['volume_ratio']}x")


def build_mock_candles(chart: dict, ticker: str, bars: int = 42, timeframe: str = "1G") -> pd.DataFrame:
    current_price = float(chart.get("current_price", chart["nearest_support"]))
    support = float(chart["nearest_support"])
    resistance = float(chart["nearest_resistance"])
    price_range = max(resistance - support, max(current_price * 0.08, 1.0))
    midpoint = support + price_range / 2

    drift_map = {"bullish": 0.34, "neutral": 0.08, "bearish": -0.30}
    volatility_map = {"1H": 0.18, "4H": 0.14, "1G": 0.11, "1W": 0.07}
    step_map = {"1H": timedelta(hours=1), "4H": timedelta(hours=4), "1G": timedelta(days=1), "1W": timedelta(weeks=1)}

    drift = drift_map.get(chart.get("signal_bias", "neutral"), 0.0)
    volatility = volatility_map.get(timeframe, 0.11)
    start_price = midpoint - (drift * price_range)
    base_date = datetime.utcnow() - (step_map.get(timeframe, timedelta(days=1)) * bars)
    base_volume = max(float(chart.get("avg_volume", 1) or 1), 1.0)
    rows: list[dict] = []

    prev_close = start_price
    for i in range(bars):
        phase = i / max(bars - 1, 1)
        primary_wave = math.sin(i / 2.4) * price_range * volatility
        secondary_wave = math.cos(i / 4.7) * price_range * (volatility * 0.65)
        pulse = math.sin(i / 1.25) * price_range * (volatility * 0.18)
        target = start_price + (current_price - start_price) * phase + primary_wave + secondary_wave + pulse
        open_price = prev_close
        close_price = (open_price * 0.34) + (target * 0.66)
        wick = max(price_range * (0.055 + (0.02 * abs(math.sin(i / 1.3)))), current_price * 0.005)
        high_price = max(open_price, close_price) + wick
        low_price = min(open_price, close_price) - wick
        swing_boost = 1 + abs(close_price - open_price) / max(price_range * 0.08, 0.1)
        volume = base_volume * (0.45 + 0.55 * abs(math.sin(i / 2.1))) * swing_boost
        if i == bars - 1:
            volume *= 1.2
        rows.append({
            "date": (base_date + (step_map.get(timeframe, timedelta(days=1)) * i)).isoformat(),
            "open": round(open_price, 2),
            "high": round(high_price, 2),
            "low": round(low_price, 2),
            "close": round(close_price, 2),
            "volume": int(volume),
            "ticker": ticker,
        })
        prev_close = close_price

    if rows:
        rows[-1]["close"] = round(current_price, 2)
        rows[-1]["high"] = round(max(rows[-1]["open"], rows[-1]["close"], rows[-1]["high"]), 2)
        rows[-1]["low"] = round(min(rows[-1]["open"], rows[-1]["close"], rows[-1]["low"]), 2)

    return pd.DataFrame(rows)



def render_focused_candlestick_chart(ticker: str, chart: dict, timeframe: str, bars: int, ohlcv_payload: dict | None = None) -> dict | None:
    candles = pd.DataFrame()
    if isinstance(ohlcv_payload, dict) and ohlcv_payload.get("candles"):
        candles = pd.DataFrame(ohlcv_payload["candles"])
        if "timestamp" in candles.columns and "date" not in candles.columns:
            candles["date"] = candles["timestamp"]
    if candles.empty:
        candles = build_mock_candles(chart, ticker, bars=bars, timeframe=timeframe)
    if candles.empty:
        st.caption("Grafik verisi olusturulamadi.")
        return None

    last_candle = candles.iloc[-1].to_dict()
    price_min = float(candles["low"].min())
    price_max = float(candles["high"].max())
    price_pad = max((price_max - price_min) * 0.08, 0.6)
    color_condition = alt.condition("datum.open <= datum.close", alt.value("#0f9d8a"), alt.value("#e24646"))

    bar_count = len(candles)
    if bar_count >= 80:
        tick_count = 8
    elif bar_count >= 50:
        tick_count = 10
    else:
        tick_count = 12

    base = alt.Chart(candles).encode(
        x=alt.X(
            "date:T",
            title="Tarih",
            axis=alt.Axis(labelAngle=0, format="%d %b", tickCount=tick_count, labelLimit=90),
        )
    )
    wick = base.mark_rule(strokeWidth=1.4).encode(
        y=alt.Y("low:Q", title="Fiyat", scale=alt.Scale(domain=[price_min - price_pad, price_max + price_pad])),
        y2="high:Q",
        color=color_condition,
        tooltip=[
            alt.Tooltip("date:T", title="Tarih"),
            alt.Tooltip("open:Q", title="Acilis", format=".2f"),
            alt.Tooltip("high:Q", title="Yuksek", format=".2f"),
            alt.Tooltip("low:Q", title="Dusuk", format=".2f"),
            alt.Tooltip("close:Q", title="Kapanis", format=".2f"),
            alt.Tooltip("volume:Q", title="Hacim", format=",")
        ],
    )
    body = base.mark_bar(size=10).encode(
        y=alt.Y("open:Q", scale=alt.Scale(domain=[price_min - price_pad, price_max + price_pad])),
        y2="close:Q",
        color=color_condition,
    )
    support_rule = alt.Chart(pd.DataFrame([{"level": chart["nearest_support"], "label": "Support"}])).mark_rule(strokeDash=[4, 4], color="#2f7d57").encode(y="level:Q")
    resistance_rule = alt.Chart(pd.DataFrame([{"level": chart["nearest_resistance"], "label": "Resistance"}])).mark_rule(strokeDash=[4, 4], color="#a2452d").encode(y="level:Q")
    price_rule = alt.Chart(pd.DataFrame([{"level": chart["current_price"], "label": "Price"}])).mark_rule(strokeDash=[2, 2], color="#f0b04d").encode(y="level:Q")
    price_layer = (wick + body + support_rule + resistance_rule + price_rule).properties(height=340)

    volume_chart = base.mark_bar(opacity=0.45, size=10).encode(
        y=alt.Y("volume:Q", title="Hacim"),
        color=color_condition,
        tooltip=[alt.Tooltip("date:T", title="Tarih"), alt.Tooltip("volume:Q", title="Hacim", format=",")],
    ).properties(height=110)

    combined = alt.vconcat(price_layer, volume_chart, spacing=10).resolve_scale(x="shared").configure_axis(labelPadding=8, titlePadding=14)
    st.altair_chart(combined, use_container_width=True)
    return last_candle


def render_runtime_health_sidebar(runtime_health: dict | str | None) -> None:
    with st.expander("Sistem Durumu", expanded=False):
        if not isinstance(runtime_health, dict):
            st.caption(str(runtime_health) if runtime_health else "Runtime health verisi alinamadi.")
            return

        cleanup_status = build_runtime_status_label(runtime_health.get("last_cleanup_status"))
        prefetch_status = build_runtime_status_label(runtime_health.get("last_prefetch_status"))
        cleanup_message = runtime_health.get("last_cleanup_message") or "-"
        prefetch_message = runtime_health.get("last_prefetch_message") or "-"

        st.caption(
            f"Scheduler {'Acik' if runtime_health.get('scheduler_enabled') else 'Kapali'} · "
            f"Cleanup {cleanup_status} · Prefetch {prefetch_status}"
        )
        st.markdown(
            f"""
            <div class='mini-grid'>
                <div class='mini-stat'><div class='k'>Son Cleanup</div><div class='v'>{runtime_health.get('last_cleanup_completed_at') or '-'}</div></div>
                <div class='mini-stat'><div class='k'>Son Prefetch</div><div class='v'>{runtime_health.get('last_prefetch_completed_at') or '-'}</div></div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.caption(f"Cleanup: {cleanup_message}")
        st.caption(f"Prefetch: {prefetch_message}")


def render_market_data_health(debug_payload: dict | str | None, timeframe: str, title: str = "Veri Sagligi") -> None:
    st.markdown(f"<div class='detail-title'>{title}</div>", unsafe_allow_html=True)
    if not isinstance(debug_payload, dict):
        st.caption(str(debug_payload) if debug_payload else "Debug verisi alinamadi.")
        return

    snapshot_state = "Canli/Cache Hazir" if debug_payload.get("snapshot_available") else "Snapshot Yok"
    snapshot_source = build_readable_source(debug_payload.get("snapshot_source"))
    ohlcv_source = build_readable_source(debug_payload.get("ohlcv_source"))
    snapshot_updated = debug_payload.get("snapshot_updated_at") or "-"
    ohlcv_latest = debug_payload.get("ohlcv_latest_timestamp") or "-"
    cached_bars = debug_payload.get("ohlcv_cached_bars", 0)

    st.markdown(
        f"""
        <div class='mini-grid'>
            <div class='mini-stat'><div class='k'>Snapshot</div><div class='v'>{snapshot_state}</div></div>
            <div class='mini-stat'><div class='k'>Snapshot Kaynagi</div><div class='v'>{snapshot_source}</div></div>
            <div class='mini-stat'><div class='k'>OHLCV Timeframe</div><div class='v'>{timeframe}</div></div>
            <div class='mini-stat'><div class='k'>Cache Bar</div><div class='v'>{cached_bars}</div></div>
            <div class='mini-stat'><div class='k'>OHLCV Kaynagi</div><div class='v'>{ohlcv_source}</div></div>
            <div class='mini-stat'><div class='k'>Son OHLCV</div><div class='v'>{ohlcv_latest}</div></div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption(f"Snapshot guncelleme: {snapshot_updated}")


def render_factor_group(title: str, factors: list[str], css_class: str) -> None:
    st.markdown(f"<div class='detail-title'>{title}</div>", unsafe_allow_html=True)
    if not factors:
        st.caption("Veri yok")
        return
    html = "".join([f"<span class='factor-pill {css_class}'>{factor}</span>" for factor in factors])
    st.markdown(html, unsafe_allow_html=True)


def build_scan_dataframe(items: list[dict]) -> pd.DataFrame:
    rows = []
    for item in items:
        badge = {
            "bullish": "🟢 bullish",
            "bearish": "🔴 bearish",
            "neutral": "🟡 neutral",
        }.get(item["stance"].lower(), item["stance"])
        rows.append(
            {
                "Ticker": item["ticker"],
                "Sirket": item["company_name"],
                "Sektor": item["sector"],
                "Stance": badge,
                "Action": item["action"],
                "Confidence": item["confidence"],
                "Weighted": item["weighted_score"],
                "Skor": item["score"],
                "Degisim": item["change_percent"],
                "Hacim": item["volume"],
                "Fiyat": item["last_price"],
                "Veri": build_readable_source(item.get("market_data_source")),
                "Teknik": item.get("technical_summary"),
                "Ozet": item["summary"],
                "_stance_raw": item["stance"],
            }
        )
    return pd.DataFrame(rows)


def apply_table_filters(df: pd.DataFrame, stance_filter: str, sector_filter: list[str], min_confidence: float, search: str, sort_by: str) -> pd.DataFrame:
    filtered = df.copy()

    if stance_filter != "All":
        filtered = filtered[filtered["_stance_raw"].str.lower() == stance_filter.lower()]
    if sector_filter:
        filtered = filtered[filtered["Sektor"].isin(sector_filter)]
    filtered = filtered[filtered["Confidence"] >= min_confidence]
    if search:
        lowered = search.lower()
        filtered = filtered[
            filtered["Ticker"].str.lower().str.contains(lowered)
            | filtered["Sirket"].str.lower().str.contains(lowered)
        ]

    sort_map = {
        "Weighted Score": ["Weighted", "Confidence", "Hacim"],
        "Confidence": ["Confidence", "Weighted", "Hacim"],
        "Volume": ["Hacim", "Weighted", "Confidence"],
        "Daily Change": ["Degisim", "Weighted", "Confidence"],
        "Ticker": ["Ticker"],
    }
    columns = sort_map[sort_by]
    ascending = sort_by == "Ticker"
    filtered = filtered.sort_values(by=columns, ascending=ascending)
    return filtered.reset_index(drop=True)


def render_ask_detail(answer: dict | None) -> None:
    st.markdown("### Ask Detail")
    if isinstance(answer, dict):
        st.markdown("<div class='panel-card'>", unsafe_allow_html=True)
        st.markdown(f"**Question:** {answer['question']}")
        st.markdown(f"**Route:** {answer['route_type']}")
        chip_cols = st.columns(3)
        with chip_cols[0]:
            st.markdown(f"<div class='stance-neutral'>confidence {answer['confidence']}</div>", unsafe_allow_html=True)
        if answer.get('recommendation'):
            rec = answer['recommendation']
            stance_class = f"stance-{rec['stance'].lower()}"
            with chip_cols[1]:
                st.markdown(f"<div class='{stance_class}'>{rec['stance']} · {rec['action']}</div>", unsafe_allow_html=True)
            with chip_cols[2]:
                st.markdown(f"<div class='stance-neutral'>weighted {rec['weighted_score']}</div>", unsafe_allow_html=True)
        st.write(answer['answer'])
        st.caption(answer['reasoning_summary'])
        if answer.get('used_sources'):
            st.markdown("**Used Sources**")
            sources_html = "".join([f"<span class='factor-pill'>{source}</span>" for source in answer['used_sources']])
            st.markdown(sources_html, unsafe_allow_html=True)
        evidence = answer.get('analysis_evidence', [])
        if evidence:
            st.markdown("**Analysis Evidence**")
            evidence_rows = [
                {
                    "Kategori": item.get("category"),
                    "Etki": item.get("impact"),
                    "Detay": item.get("detail"),
                    "Kaynak": item.get("source"),
                }
                for item in evidence
            ]
            st.dataframe(pd.DataFrame(evidence_rows), hide_index=True, use_container_width=True)
        with st.expander("Ham API cevabi"):
            st.json(answer)
        st.markdown("</div>", unsafe_allow_html=True)
    else:
        st.info("Secili hisse icin daha derin bir soru sormak istersen soldaki kutudan calistirabilirsin.")


def summary_pick(scan_items: list[dict], key: str, reverse: bool = True) -> dict | None:
    valid = [item for item in scan_items if item.get(key) is not None]
    if not valid:
        return None
    return sorted(valid, key=lambda item: item[key], reverse=reverse)[0]


def main() -> None:
    st.set_page_config(page_title="BIST100 Market Scan", page_icon="▣", layout="wide")
    inject_styles()

    st.session_state.setdefault("selected_ticker", "THYAO")
    st.session_state.setdefault("last_ask_response", None)

    with st.sidebar:
        st.markdown("## Ayarlar")
        base_url = st.text_input("API Base URL", value=API_DEFAULT)
        card_limit = st.slider("Kart Limiti", min_value=1, max_value=12, value=6)
        selected_ticker_input = st.text_input("Detay Ticker", value=st.session_state["selected_ticker"]).upper().strip() or "THYAO"
        st.session_state["selected_ticker"] = selected_ticker_input
        ask_question = st.text_area(
            "Ask Panel",
            value=f"{selected_ticker_input} hangi kosullarda artar ve hangi kosullarda duser?",
            height=120,
        )
        ask_trigger = st.button("Soruyu Calistir", use_container_width=True)

    if ask_trigger:
        try:
            st.session_state["last_ask_response"] = api_post(base_url, "/ask", {"question": ask_question})
        except RuntimeError as exc:
            st.error(str(exc))

    try:
        all_scan = load_scan(base_url, limit=100)
        bullish_scan = load_scan(base_url, stance="bullish", limit=card_limit)
        bearish_scan = load_scan(base_url, stance="bearish", limit=card_limit)
        scan_history = load_scan_history(base_url, limit=5)
        runtime_health = load_runtime_health(base_url)
    except RuntimeError as exc:
        st.error(str(exc))
        return

    scan_items = all_scan.get("items", [])
    scan_df = build_scan_dataframe(scan_items)
    if scan_df.empty:
        st.error("Market scan verisi bulunamadi.")
        return

    st.markdown(
        f"""
        <div class="hero">
            <h1 style="margin-bottom:.2rem;">BIST100 Market Scan Desk</h1>
            <p>Gunluk tarama, hisse bazli detay ve soru-cevap akislarini tek yerde toplar. Ana ekran chat degil, piyasadaki adaylari gorecegin tarama yuzudur.</p>
            <div class="chip-row">
                <span class="chip">Tarama zamani: {all_scan['generated_at']}</span>
                <span class="chip">Evren: {all_scan['universe_size']} hisse</span>
                <span class="chip">Secili ticker: {st.session_state['selected_ticker']}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    metric_cols = st.columns(4)
    metrics = [
        ("Toplam Taranan", all_scan["universe_size"]),
        ("Bullish Aday", bullish_scan["total"]),
        ("Bearish Aday", bearish_scan["total"]),
        ("Secili Hisse", st.session_state["selected_ticker"]),
    ]
    for col, (label, value) in zip(metric_cols, metrics):
        with col:
            st.markdown(
                f"<div class='metric-card'><div class='label'>{label}</div><div class='metric-value'>{value}</div></div>",
                unsafe_allow_html=True,
            )

    top_riser = summary_pick(scan_items, "change_percent", reverse=True)
    top_faller = summary_pick(scan_items, "change_percent", reverse=False)
    highest_conf = summary_pick(scan_items, "confidence", reverse=True)
    strips = st.columns(3)
    strip_payload = [
        ("Top Riser", top_riser),
        ("Top Faller", top_faller),
        ("Highest Confidence", highest_conf),
    ]
    for col, (label, item) in zip(strips, strip_payload):
        with col:
            if item is None:
                st.markdown(f"<div class='headline-box'><div class='label'>{label}</div><div class='metric-value'>-</div></div>", unsafe_allow_html=True)
            else:
                value = item['ticker']
                extra = f"{item['stance']} · {item['weighted_score']}"
                if label != "Highest Confidence":
                    extra = f"{item.get('change_percent', '-') }% · {item['stance']}"
                st.markdown(
                    f"<div class='headline-box'><div class='label'>{label}</div><div class='metric-value'>{value}</div><div style='margin-top:.25rem; color:#68756d;'>{extra}</div></div>",
                    unsafe_allow_html=True,
                )

    with st.sidebar:
        render_runtime_health_sidebar(runtime_health)

    render_ask_detail(st.session_state.get("last_ask_response"))

    st.markdown("### Market Scan Table")
    filter_cols = st.columns([1.1, 1.2, 1.1, 1.2, 1.4])
    with filter_cols[0]:
        stance_filter = st.selectbox("Stance", ["All", "bullish", "neutral", "bearish"], index=0)
    with filter_cols[1]:
        sector_filter = st.multiselect("Sector", options=sorted(scan_df["Sektor"].unique().tolist()))
    with filter_cols[2]:
        min_confidence = st.slider("Min Confidence", min_value=0.0, max_value=1.0, value=0.0, step=0.01)
    with filter_cols[3]:
        search = st.text_input("Focused Ticker Search", value="")
    with filter_cols[4]:
        sort_by = st.selectbox("Sort By", ["Weighted Score", "Confidence", "Volume", "Daily Change", "Ticker"])

    filtered_df = apply_table_filters(scan_df, stance_filter, sector_filter, min_confidence, "", sort_by)
    st.caption(f"Filtre sonrasi {len(filtered_df)} hisse gorunuyor. Satira tiklayip detay panelini guncelleyebilirsin.")

    focus_query = search.strip().upper()
    focus_df = scan_df.iloc[0:0].copy()
    if focus_query:
        focus_df = scan_df[(scan_df["Ticker"].str.upper().str.contains(focus_query)) | (scan_df["Sirket"].str.upper().str.contains(focus_query))].reset_index(drop=True)
        if len(focus_df) == 1:
            st.session_state["selected_ticker"] = focus_df.iloc[0]["Ticker"]

    selection_event = st.dataframe(
        filtered_df.drop(columns=["_stance_raw"]),
        hide_index=True,
        use_container_width=True,
        on_select="rerun",
        selection_mode="single-row",
        column_config={
            "Confidence": st.column_config.NumberColumn(format="%.2f"),
            "Weighted": st.column_config.NumberColumn(format="%.2f"),
            "Degisim": st.column_config.NumberColumn(format="%.2f"),
            "Hacim": st.column_config.NumberColumn(format="%d"),
            "Fiyat": st.column_config.NumberColumn(format="%.2f"),
            "Veri": st.column_config.TextColumn(width="medium"),
            "Ozet": st.column_config.TextColumn(width="large"),
        },
    )

    selected_rows = selection_event.selection.rows if selection_event is not None else []
    if selected_rows:
        st.session_state["selected_ticker"] = filtered_df.iloc[selected_rows[0]]["Ticker"]
        st.rerun()

    focused_bundle = None
    if focus_query:
        st.markdown("### Focused Technical Chart")
        if focus_df.empty:
            st.info("Arama ile eslesen ticker bulunamadi.")
        else:
            focus_ticker = focus_df.iloc[0]["Ticker"]
            st.session_state["selected_ticker"] = focus_ticker
            focus_info = focus_df.iloc[0].to_dict()
            st.markdown(
                f"""
                <div class='panel-card' style='margin-bottom: .9rem;'>
                    <div class='scan-top'>
                        <div>
                            <div class='ticker'>{focus_info['Ticker']}</div>
                            <div class='sector'>{focus_info['Sirket']} · {focus_info['Sektor']}</div>
                        </div>
                        <div class='stance-{focus_info['_stance_raw']}'>{focus_info['_stance_raw']} · {focus_info['Action']}</div>
                    </div>
                    <div class='chip-row'>
                        <span class='chip'>Confidence {focus_info['Confidence']:.2f}</span>
                        <span class='chip'>Weighted {format_tr_number(focus_info['Weighted'])}</span>
                        <span class='chip'>Veri {focus_info.get('Veri') or "-"}</span>
                        <span class='chip'>Teknik {build_readable_technical_summary(focus_info.get('Teknik'))}</span>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            control_cols = st.columns([1.1, 1.1, 2.2])
            with control_cols[0]:
                focus_timeframe = st.selectbox(
                    "Timeframe",
                    ["1H", "4H", "1G", "1W"],
                    index=2,
                    key="focused_chart_timeframe",
                )
            with control_cols[1]:
                focus_bars = st.select_slider(
                    "Mum Sayisi",
                    options=[20, 30, 40, 60, 90],
                    value=40,
                    key="focused_chart_bars",
                )
            with control_cols[2]:
                st.caption("Search sadece focus alanini besliyor; ana market tarama tablosu ayni kalir. Buradaki grafik mock candle + hacim barlari ile teknik akisi daha okunur gosterir.")

            try:
                focused_bundle = load_ticker_bundle(base_url, focus_ticker, timeframe=focus_timeframe)
            except RuntimeError as exc:
                st.caption(str(exc))
                focused_bundle = None

            focused_debug = load_market_debug(base_url, focus_ticker, timeframe=focus_timeframe)

            if isinstance(focused_bundle, dict):
                focused_chart = focused_bundle.get("chart")
                if isinstance(focused_chart, dict):
                    st.caption(f"Search ile odaklanan grafik: {focus_ticker} · {focus_timeframe} · {focus_bars} mum")
                    ohlcv_payload = load_ohlcv_series(base_url, focus_ticker, focus_timeframe, int(focus_bars))
                    if isinstance(ohlcv_payload, str):
                        st.markdown("<div class='source-badge source-fallback'>Fallback Grafik · Mock Candle</div>", unsafe_allow_html=True)
                        st.caption(f"Gercek OHLCV alinamadi, mock grafik kullaniliyor: {ohlcv_payload}")
                        ohlcv_payload = None
                    else:
                        st.markdown(f"<div class='source-badge source-live'>Grafik Kaynagi · {ohlcv_payload.get('source', 'bilinmiyor')}</div>", unsafe_allow_html=True)
                    candle = render_focused_candlestick_chart(focus_ticker, focused_chart, focus_timeframe, int(focus_bars), ohlcv_payload)
                    if candle is not None:
                        st.markdown(
                            f"""
                            <div class='mini-grid'>
                                <div class='mini-stat'><div class='k'>Acilis</div><div class='v'>{format_tr_number(candle['open'])}</div></div>
                                <div class='mini-stat'><div class='k'>Yuksek</div><div class='v'>{format_tr_number(candle['high'])}</div></div>
                                <div class='mini-stat'><div class='k'>Dusuk</div><div class='v'>{format_tr_number(candle['low'])}</div></div>
                                <div class='mini-stat'><div class='k'>Kapanis</div><div class='v'>{format_tr_number(candle['close'])}</div></div>
                                <div class='mini-stat'><div class='k'>Hacim</div><div class='v'>{format_tr_int(candle['volume'])}</div></div>
                                <div class='mini-stat'><div class='k'>Kirim Durumu</div><div class='v'>{humanize_slug(focused_chart['breakout_state'])}</div></div>
                            </div>
                            <div class='mini-grid' style='margin-top:.7rem;'>
                                <div class='mini-stat'><div class='k'>Trade Setup</div><div class='v'>{humanize_slug(focused_chart['trade_setup'])}</div></div>
                                <div class='mini-stat'><div class='k'>Trend Referansi</div><div class='v'>{format_tr_number(focused_chart['trend_reference_level'])}</div></div>
                                <div class='mini-stat'><div class='k'>Entry Zone</div><div class='v'>{format_tr_number(focused_chart['entry_zone_low'])} - {format_tr_number(focused_chart['entry_zone_high'])}</div></div>
                                <div class='mini-stat'><div class='k'>Breakout Up</div><div class='v'>{format_tr_number(focused_chart['breakout_buy_trigger'])}</div></div>
                                <div class='mini-stat'><div class='k'>Breakdown</div><div class='v'>{format_tr_number(focused_chart['breakdown_sell_trigger'])}</div></div>
                                <div class='mini-stat'><div class='k'>R/R</div><div class='v'>{format_tr_number(focused_chart['risk_reward_ratio'])}</div></div>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )
                        st.caption(focused_chart['level_commentary'])
                    render_market_data_health(focused_debug, focus_timeframe, title="Focused Live / Cache Health")
                else:
                    st.caption(str(focused_chart))

    left, right = st.columns([1.05, 1.05])
    with left:
        st.markdown("### Bullish Candidates")
        render_scan_cards(bullish_scan["items"], "Bullish aday bulunamadi.", "bull")
    with right:
        st.markdown("### Bearish Candidates")
        render_scan_cards(bearish_scan["items"], "Bearish aday bulunamadi.", "bear")

    selected_ticker = st.session_state["selected_ticker"]
    try:
        ticker_bundle = load_ticker_bundle(base_url, selected_ticker, timeframe="1G")
    except RuntimeError as exc:
        st.error(str(exc))
        return
    selected_debug = load_market_debug(base_url, selected_ticker, timeframe="1G")

    st.markdown("### Scan Snapshot History")
    if isinstance(scan_history, dict):
        history_cols = st.columns(min(max(scan_history.get("total", 0), 1), 5))
        items = scan_history.get("items", [])[:5]
        if items:
            for col, item in zip(history_cols, items):
                with col:
                    market_source_summary = summarize_mapping(item.get("market_data_source_summary"))
                    used_source_summary = summarize_mapping(item.get("used_source_summary"))
                    runtime_health = item.get("runtime_health_summary") or {}
                    cleanup_status = build_runtime_status_label(runtime_health.get("last_cleanup_status"))
                    prefetch_status = build_runtime_status_label(runtime_health.get("last_prefetch_status"))
                    st.markdown(
                        f"""
                        <div class='panel-card'>
                            <div class='label'>Snapshot #{item['id']}</div>
                            <div class='metric-value' style='font-size:1.1rem;'>{item['stance_filter']}</div>
                            <div style='color:#68756d; margin-top:.35rem;'>Provider {item['provider']}</div>
                            <div style='color:#68756d;'>Returned {item['total_returned']} / {item['universe_size']}</div>
                            <div style='color:#68756d;'>Limit {item['limit_requested']}</div>
                            <div style='color:#68756d; margin-top:.45rem; font-size:.82rem;'>{item['created_at']}</div>
                            <div class='mini-divider'></div>
                            <div style='color:#68756d; font-size:.82rem;'><strong>Piyasa Veri:</strong> {market_source_summary}</div>
                            <div style='color:#68756d; font-size:.82rem; margin-top:.25rem;'><strong>Analiz Kaynaklari:</strong> {used_source_summary}</div>
                            <div style='color:#68756d; font-size:.82rem; margin-top:.25rem;'><strong>Cleanup:</strong> {cleanup_status}</div>
                            <div style='color:#68756d; font-size:.82rem; margin-top:.1rem;'><strong>Prefetch:</strong> {prefetch_status}</div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
        else:
            st.info("Snapshot history bulunamadi.")
    else:
        st.caption(str(scan_history))

    st.markdown("### Ticker Detail")
    detail_left, detail_mid, detail_right = st.columns([1.1, 1.1, 0.9])

    company = ticker_bundle.get("company")
    chart = ticker_bundle.get("chart")
    news = ticker_bundle.get("news")
    macro = ticker_bundle.get("macro")
    runs = ticker_bundle.get("runs")

    with detail_left:
        st.markdown("<div class='panel-card'>", unsafe_allow_html=True)
        st.markdown(f"#### {selected_ticker}")
        if isinstance(company, dict):
            st.caption(f"{company['name']} · {company['sector']}")
        st.markdown("<div class='mini-divider'></div>", unsafe_allow_html=True)
        st.markdown("<div class='detail-title'>Technical Chart</div>", unsafe_allow_html=True)
        if isinstance(chart, dict):
            st.markdown(
                f"""
                <div class='chip-row'>
                    <span class='chip'>Trend {humanize_slug(chart['trend'])}</span>
                    <span class='chip'>Bias {humanize_slug(chart['signal_bias'])}</span>
                    <span class='chip'>Strength {humanize_slug(chart['signal_strength'])}</span>
                    <span class='chip'>Structure {humanize_slug(chart['structure_bias'])}</span>
                    <span class='chip'>{humanize_slug(chart['breakout_state'])}</span>
                    <span class='chip'>{humanize_slug(chart['level_status'])}</span>
                </div>
                """,
                unsafe_allow_html=True,
            )
            render_chart_feature_visual(chart)
            st.markdown(
                f"""
                <div class='mini-grid'>
                    <div class='mini-stat'><div class='k'>Support Gap</div><div class='v'>{format_tr_number(chart['support_gap_percent'])}%</div></div>
                    <div class='mini-stat'><div class='k'>Resistance Gap</div><div class='v'>{format_tr_number(chart['resistance_gap_percent'])}%</div></div>
                    <div class='mini-stat'><div class='k'>Signal Score</div><div class='v'>{chart['signal_score']}</div></div>
                    <div class='mini-stat'><div class='k'>Volatility</div><div class='v'>{humanize_slug(chart['volatility_regime'])} · ATR %{format_tr_number(chart['atr_percent'])}</div></div>
                </div>
                <div class='mini-grid' style='margin-top:.7rem;'>
                    <div class='mini-stat'><div class='k'>Trade Setup</div><div class='v'>{humanize_slug(chart['trade_setup'])}</div></div>
                    <div class='mini-stat'><div class='k'>Trend Ref</div><div class='v'>{format_tr_number(chart['trend_reference_level'])}</div></div>
                    <div class='mini-stat'><div class='k'>Entry Zone</div><div class='v'>{format_tr_number(chart['entry_zone_low'])} - {format_tr_number(chart['entry_zone_high'])}</div></div>
                    <div class='mini-stat'><div class='k'>Take Profit</div><div class='v'>{format_tr_number(chart['take_profit_level'])}</div></div>
                    <div class='mini-stat'><div class='k'>Stop Loss</div><div class='v'>{format_tr_number(chart['stop_loss_level'])}</div></div>
                    <div class='mini-stat'><div class='k'>R/R</div><div class='v'>{format_tr_number(chart['risk_reward_ratio'])}</div></div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.caption(chart['level_commentary'])
        else:
            st.caption(str(chart))
        st.markdown("<div class='mini-divider'></div>", unsafe_allow_html=True)
        render_market_data_health(selected_debug, "1G", title="Selected Ticker Data Health")
        st.markdown("<div class='mini-divider'></div>", unsafe_allow_html=True)
        if isinstance(news, dict):
            st.markdown("<div class='detail-title'>Latest News</div>", unsafe_allow_html=True)
            for item in news.get("items", [])[:3]:
                st.markdown(f"**{item['headline']}**")
                st.caption(f"{item['published_at']} · {item['publisher']}")
                st.write(item['summary'])
        else:
            st.caption(str(news))
        st.markdown("</div>", unsafe_allow_html=True)

    with detail_mid:
        st.markdown("<div class='panel-card'>", unsafe_allow_html=True)
        st.markdown("#### Macro Event Timeline")
        if isinstance(macro, dict):
            for item in macro.get("items", [])[:3]:
                st.markdown(f"**{item['latest_macro_event']}**")
                st.caption(f"{item['published_at']} · {item['event_category']} · {item['region']}")
                render_factor_group("Positive", item.get("positive_impacts", [])[:3], "factor-pos")
                render_factor_group("Negative", item.get("negative_impacts", [])[:3], "factor-neg")
                st.markdown("<div class='mini-divider'></div>", unsafe_allow_html=True)
        else:
            st.caption(str(macro))
        st.markdown("</div>", unsafe_allow_html=True)

    with detail_right:
        st.markdown("<div class='panel-card'>", unsafe_allow_html=True)
        st.markdown("#### Analysis History")
        if isinstance(runs, dict):
            for item in runs.get("items", [])[:5]:
                stance_class = f"stance-{item['stance'].lower()}"
                st.markdown(
                    f"<div class='{stance_class}' style='margin-bottom:.35rem;'>{item['stance']} · {item['action']}</div>",
                    unsafe_allow_html=True,
                )
                st.caption(item.get("created_at") or "timestamp yok")
                st.write(item["recommendation_summary"])
                st.markdown("<div class='mini-divider'></div>", unsafe_allow_html=True)
        else:
            st.caption(str(runs))
        st.markdown("</div>", unsafe_allow_html=True)

if __name__ == "__main__":
    main()
