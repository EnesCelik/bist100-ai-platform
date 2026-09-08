import streamlit as st


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


