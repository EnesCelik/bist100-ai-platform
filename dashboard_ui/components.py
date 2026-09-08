import math
from datetime import datetime, timedelta

import altair as alt
import pandas as pd
import streamlit as st

from dashboard_ui.formatting import (
    build_readable_source,
    build_readable_technical_summary,
    build_runtime_status_label,
    format_tr_int,
    format_tr_number,
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


def render_trading_safety_badge(safety_status: dict | str | None) -> None:
    if not isinstance(safety_status, dict):
        st.caption(str(safety_status) if safety_status else "Trading safety durumu alinamadi.")
        return
    if safety_status.get("halted"):
        st.error(f"DURDURULDU ({safety_status.get('triggered_by', '-')}): {safety_status.get('reason', '-')}")
    else:
        st.success("Paper trade acilisi aktif (durdurulmadi)")


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


def render_performance_and_llmops_panel(paper_report: dict | str | None, llm_summary: dict | str | None) -> None:
    st.markdown("### Performans & LLM Kullanimi")
    perf_col, llm_col = st.columns([1.2, 1])

    with perf_col, st.container(border=True):
        st.markdown("<div class='detail-title'>Paper Trade - Tum Zamanlar</div>", unsafe_allow_html=True)
        if not isinstance(paper_report, dict):
            st.caption(str(paper_report) if paper_report else "Paper trade ozeti alinamadi.")
        else:
            win_rate = paper_report.get("win_rate")
            win_rate_text = f"%{win_rate * 100:.0f}" if win_rate is not None else "-"
            total_pnl = paper_report.get("total_pnl_try")
            total_pnl_percent = paper_report.get("total_pnl_percent")
            best_ticker = paper_report.get("best_ticker")
            worst_ticker = paper_report.get("worst_ticker")
            best_worst_html = ""
            if best_ticker or worst_ticker:
                best_worst_html = (
                    f"<p style='margin-top:.6rem; color:#68756d; font-size:.85rem;'>"
                    f"En iyi {best_ticker} ({format_tr_number(paper_report.get('best_pnl_try'))} TL) · "
                    f"En zayif {worst_ticker} ({format_tr_number(paper_report.get('worst_pnl_try'))} TL)</p>"
                )
            st.markdown(
                f"""
                <div class='mini-grid'>
                    <div class='mini-stat'><div class='k'>Toplam Islem</div><div class='v'>{paper_report.get('total_trades', '-')}</div></div>
                    <div class='mini-stat'><div class='k'>Acik / Kapali</div><div class='v'>{paper_report.get('open_count', '-')} / {paper_report.get('closed_count', '-')}</div></div>
                    <div class='mini-stat'><div class='k'>Win Rate (kararli)</div><div class='v'>{win_rate_text}</div></div>
                    <div class='mini-stat'><div class='k'>Win / Loss / Neutral</div><div class='v'>{paper_report.get('win_count', '-')} / {paper_report.get('loss_count', '-')} / {paper_report.get('neutral_count', '-')}</div></div>
                    <div class='mini-stat'><div class='k'>Toplam PnL</div><div class='v'>{format_tr_number(total_pnl)} TL</div></div>
                    <div class='mini-stat'><div class='k'>PnL / Sermaye</div><div class='v'>%{format_tr_number(total_pnl_percent)}</div></div>
                </div>
                {best_worst_html}
                """,
                unsafe_allow_html=True,
            )
            st.caption(paper_report.get("summary", ""))

    with llm_col, st.container(border=True):
        st.markdown("<div class='detail-title'>LLM Sentez Kullanimi</div>", unsafe_allow_html=True)
        if not isinstance(llm_summary, dict):
            st.caption(str(llm_summary) if llm_summary else "LLM trace ozeti alinamadi.")
        else:
            avg_latency = llm_summary.get("average_latency_ms")
            avg_latency_text = f"{avg_latency / 1000:.1f}s" if avg_latency is not None else "-"
            st.markdown(
                f"""
                <div class='mini-grid'>
                    <div class='mini-stat'><div class='k'>Toplam Cagri</div><div class='v'>{llm_summary.get('total_calls', '-')}</div></div>
                    <div class='mini-stat'><div class='k'>Basarili / Hatali</div><div class='v'>{llm_summary.get('ok_count', '-')} / {llm_summary.get('error_count', '-')}</div></div>
                    <div class='mini-stat'><div class='k'>Toplam Maliyet</div><div class='v'>${format_tr_number(llm_summary.get('total_estimated_cost_usd'), decimals=4)}</div></div>
                    <div class='mini-stat'><div class='k'>Ort. Gecikme</div><div class='v'>{avg_latency_text}</div></div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            recent_traces = llm_summary.get("recent_traces") or []
            for trace in recent_traces[:5]:
                status_icon = "OK" if trace.get("status") == "ok" else "HATA"
                cost = trace.get("estimated_cost_usd")
                cost_text = f"${cost:.4f}" if cost is not None else "-"
                st.caption(f"{status_icon} · {trace.get('ticker', '-')} · {trace.get('model', '-')} · {cost_text}")


def summary_pick(scan_items: list[dict], key: str, reverse: bool = True) -> dict | None:
    valid = [item for item in scan_items if item.get(key) is not None]
    if not valid:
        return None
    return sorted(valid, key=lambda item: item[key], reverse=reverse)[0]

