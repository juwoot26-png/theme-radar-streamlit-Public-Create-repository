import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import feedparser
from datetime import datetime, timedelta
from functools import lru_cache

st.set_page_config(page_title="Theme Radar (US Stocks)", page_icon="📈", layout="wide")

# ---------- Settings ----------
HOT_THEMES = ["AI", "Data Center", "Optical (CPO)", "Power Grid", "GLP-1"]
THEME_MAP = {
    "AI": ["NVDA","AMD","MSFT","SMCI","GOOGL","AMZN"],
    "Data Center": ["NVDA","AMD","MSFT","SMCI","GOOGL","AMZN","AVGO"],
    "Optical (CPO)": ["CIEN","AAOI","AVGO","LITE"],
    "Power Grid": ["NEE","AEP","DUK","PCG","ETN"],
    "GLP-1": ["LLY","NVO","PFE","ABT"],
}
SECTOR_ETFS = {
    "Semis (SOXX)": "SOXX",
    "Utilities (XLU)": "XLU",
    "Industrials (XLI)": "XLI",
    "Energy (XLE)": "XLE",
    "Financials (XLF)": "XLF",
    "Health Care (XLV)": "XLV",
    "Consumer Discr (XLY)": "XLY",
    "Consumer Staples (XLP)": "XLP",
    "Materials (XLB)": "XLB",
    "Communication (XLC)": "XLC",
    "Transportation (IYT)": "IYT",
}

# ---------- Utils ----------
def _zscore(vals):
    s = pd.Series(vals, dtype=float)
    if s.std(ddof=0) == 0: return s*0
    return (s - s.mean()) / s.std(ddof=0)

@lru_cache(maxsize=256)
def dl_daily(symbol: str, period="6mo"):
    return yf.download(symbol, period=period, interval="1d", progress=False)

def volume_ratio(df: pd.DataFrame, short=5, long=60):
    if df is None or "Volume" not in df or len(df) < long: return None
    short_avg = df["Volume"].tail(short).mean()
    long_avg = df["Volume"].tail(long).mean()
    if long_avg == 0 or pd.isna(long_avg): return None
    return float(short_avg / long_avg)

def momentum(df_close: pd.Series):
    if df_close is None or len(df_close) < 22: return None
    ret_1w = (df_close.iloc[-1]/df_close.iloc[-5]) - 1 if len(df_close) >= 5 else 0
    ret_1m = (df_close.iloc[-1]/df_close.iloc[-22]) - 1 if len(df_close) >= 22 else 0
    return float(ret_1w + 0.5*ret_1m)

def google_news_count(query: str, days=7, limit=100):
    url = f"[news.google.com](https://news.google.com/rss/search?q={query.replace()' ', '+')}+stock&hl=en-US&gl=US&ceid=US:en"
    feed = feedparser.parse(url)
    cutoff = datetime.utcnow() - timedelta(days=days)
    cnt = 0
    for e in feed.entries[:limit]:
        try:
            # published_parsed may not exist on all items
            if hasattr(e, "published_parsed"):
                published = datetime(*e.published_parsed[:6])
                if published > cutoff: cnt += 1
        except Exception:
            continue
    return cnt

@st.cache_data(ttl=60*30)
def theme_scores():
    counts = {t: google_news_count(t, 7) for t in HOT_THEMES}
    zs = _zscore(list(counts.values()))
    out = []
    for i, t in enumerate(HOT_THEMES):
        out.append({"theme": t, "news_7d": counts[t], "score": float(zs.iloc[i])})
    out = sorted(out, key=lambda x: x["score"], reverse=True)
    return pd.DataFrame(out)

@st.cache_data(ttl=60*30)
def rank_theme_stocks(theme: str):
    tickers = THEME_MAP.get(theme, [])
    rows = []
    for t in tickers:
        df = dl_daily(t)
        if df is None or len(df)==0: 
            continue
        vr = volume_ratio(df) or 0.0
        mo = momentum(df["Close"]) or 0.0
        score = 0.45*vr + 0.35*mo + 0.2*1.0
        rows.append({"ticker": t, "vol_x": round(vr,2), "mom": round(mo,3), "score": round(score,3)})
    df = pd.DataFrame(rows).sort_values("score", ascending=False).reset_index(drop=True)
    return df

@st.cache_data(ttl=60*30)
def sector_trend():
    rows = []
    for name, sym in SECTOR_ETFS.items():
        df = dl_daily(sym, period="1y")
        if df is None or len(df)==0: 
            continue
        close = df["Close"]
        vratio = volume_ratio(df) or 0.0
        r1w = (close.iloc[-1]/close.iloc[-5]-1) if len(close)>=5 else np.nan
        r1m = (close.iloc[-1]/close.iloc[-22]-1) if len(close)>=22 else np.nan
        rows.append({"sector": name, "etf": sym, "ret_1w": r1w, "ret_1m": r1m, "vol_x": vratio})
    df = pd.DataFrame(rows)
    df["score"] = 0.4*df["vol_x"].fillna(0) + 0.3*df["ret_1w"].fillna(0) + 0.3*df["ret_1m"].fillna(0)
    return df.sort_values("score", ascending=False).reset_index(drop=True)

@st.cache_data(ttl=60*30)
def company_overview(ticker: str):
    tk = yf.Ticker(ticker)
    info = tk.info or {}
    summary = info.get("longBusinessSummary") or info.get("summary") or ""
    name = info.get("shortName") or info.get("longName") or ticker
    sector = info.get("sector")
    mcap = info.get("marketCap")
    hist = tk.history(period="6mo", interval="1d")
    price = float(hist["Close"].iloc[-1]) if len(hist) else None
    fin = {"revenue_ttm": info.get("totalRevenue"), "profit_margin": info.get("profitMargins")}
    return {"ticker": ticker, "name": name, "sector": sector, "marketCap": mcap, "price": price,
            "summary": summary, "financials": fin}

@st.cache_data(ttl=60*30)
def company_news(ticker: str, limit=10):
    url = f"[news.google.com](https://news.google.com/rss/search?q={ticker}+stock&hl=en-US&gl=US&ceid=US:en)"
    feed = feedparser.parse(url)
    items = []
    for e in feed.entries[:limit]:
        items.append({
            "title": getattr(e, "title", ""),
            "link": getattr(e, "link", ""),
            "published": getattr(e, "published", "")
        })
    sec = f"[sec.gov](https://www.sec.gov/edgar/search/#/entityName={ticker})"
    return items, sec

# ---------- UI ----------
st.title("📈 Theme Radar — US Stocks (Daily Flow)")

colA, colB = st.columns([2,1])
with colA:
    st.subheader("오늘 돈이 몰리는 섹터 Top")
    sec_df = sector_trend()
    st.dataframe(
        sec_df.assign(
            ret_1w=lambda d: (d["ret_1w"]*100).round(2),
            ret_1m=lambda d: (d["ret_1m"]*100).round(2),
            vol_x=lambda d: d["vol_x"].round(2),
            score=lambda d: d["score"].round(3),
        )[["sector","etf","ret_1w","ret_1m","vol_x","score"]],
        use_container_width=True,
        hide_index=True
    )

with colB:
    st.subheader("오늘의 테마 랭킹")
    th_df = theme_scores()
    st.dataframe(th_df[["theme","news_7d","score"]], use_container_width=True, hide_index=True)

st.markdown("---")
st.subheader("테마별 상위 종목")
theme = st.segmented_control("테마 선택", HOT_THEMES, default=HOT_THEMES[0])
rank_df = rank_theme_stocks(theme)
st.dataframe(rank_df, use_container_width=True, hide_index=True)

st.markdown("---")
st.subheader("종목 상세")
ticker_input = st.text_input("티커 입력 (예: NVDA, SMCI, LLY)", value=rank_df["ticker"].iloc[0] if len(rank_df)>0 else "NVDA")
if ticker_input:
    ov = company_overview(ticker_input.upper())
    with st.container(border=True):
        st.markdown(f"**{ov['name']} ({ov['ticker']})**")
        st.caption(f"Sector: {ov.get('sector','-')}  |  Mkt Cap: {ov.get('marketCap','-')}  |  Price: {ov.get('price','-')}")
        st.write(ov["summary"] or "회사 개요 정보를 준비 중입니다.")
        fin = ov["financials"] or {}
        st.metric("Revenue (TTM)", f"{fin.get('revenue_ttm', '-')}")
        st.metric("Profit Margin", f"{round(fin.get('profit_margin',0)*100,2)}%" if fin.get('profit_margin') else "-")

    st.write("뉴스/공시")
    news, sec_url = company_news(ticker_input.upper())
    for n in news:
        st.markdown(f"- [{n['title']}]({n['link']}) · {n['published']}")
    st.markdown(f"[SEC EDGAR 바로가기]({sec_url})")

st.markdown("---")
st.caption("Data may be delayed. For information only — not investment advice.")
