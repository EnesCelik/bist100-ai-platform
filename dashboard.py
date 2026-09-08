import streamlit as st

from dashboard_ui.api_client import (
    API_DEFAULT,
    api_post,
    halt_trading_safety,
    load_all_time_paper_trade_report,
    load_llm_trace_summary,
    load_market_debug,
    load_ohlcv_series,
    load_runtime_health,
    load_scan,
    load_scan_history,
    load_ticker_bundle,
    load_trading_safety_status,
    resume_trading_safety,
)
from dashboard_ui.components import (
    apply_table_filters,
    build_scan_dataframe,
    render_ask_detail,
    render_chart_feature_visual,
    render_factor_group,
    render_focused_candlestick_chart,
    render_market_data_health,
    render_performance_and_llmops_panel,
    render_runtime_health_sidebar,
    render_scan_cards,
    render_trading_safety_badge,
    summary_pick,
)
from dashboard_ui.formatting import (
    build_readable_technical_summary,
    build_runtime_status_label,
    format_tr_int,
    format_tr_number,
    humanize_slug,
    summarize_mapping,
)
from dashboard_ui.styles import inject_styles


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

        with st.expander("Trading Safety (Kill-Switch)", expanded=False):
            safety_status = load_trading_safety_status(base_url)
            render_trading_safety_badge(safety_status)
            is_halted = isinstance(safety_status, dict) and safety_status.get("halted")
            safety_cols = st.columns(2)
            with safety_cols[0]:
                if st.button("Durdur", use_container_width=True, disabled=bool(is_halted)):
                    halt_trading_safety(base_url, "Dashboard uzerinden manuel durdurma")
                    st.rerun()
            with safety_cols[1]:
                if st.button("Devam Ettir", use_container_width=True, disabled=not is_halted):
                    resume_trading_safety(base_url)
                    st.rerun()

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

    paper_report = load_all_time_paper_trade_report(base_url)
    llm_summary = load_llm_trace_summary(base_url)
    render_performance_and_llmops_panel(paper_report, llm_summary)

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
