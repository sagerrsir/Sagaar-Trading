import streamlit as st
import pandas as pd
import numpy as np
import pyotp
import re
import time
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from SmartApi import SmartConnect
import plotly.graph_objects as go

st.set_page_config(page_title="SAGAR AI PRO - TRADINGVIEW", layout="wide")
st.title("🤖 SAGAR AI PRO - TRADINGVIEW CHART")

INSTRUMENT = st.selectbox("Instrument:", ["NIFTY", "CRUDEOIL MINI", "GOLD MINI"])
CONFIG = {
    "NIFTY": {"exchange": "NSE", "strike_step": 50, "qty": 25, "opt_exchange": "NFO", "prefix": "NIFTY", "news_q": "Nifty 50 stock market India"},
    "CRUDEOIL MINI": {"exchange": "MCX", "strike_step": 50, "qty": 10, "opt_exchange": "MCX", "prefix": "CRUDEOILM", "news_q": "Crude Oil price OPEC"},
    "GOLD MINI": {"exchange": "MCX", "strike_step": 100, "qty": 1, "opt_exchange": "MCX", "prefix": "GOLDM", "news_q": "Gold price today"},
}
cfg = CONFIG[INSTRUMENT]

st.sidebar.header("⚠️ RISK CONTROL")
LIVE_MODE = st.sidebar.toggle("🔴 LIVE TRADING ON", value=False)
QTY = cfg["qty"]
SL_POINTS = st.sidebar.number_input("SL Points", value=30)
TARGET_POINTS = st.sidebar.number_input("Target Points", value=50)
MAX_TRADES = st.sidebar.number_input("Max Trades / Day", value=2)
if 'trades' not in st.session_state: st.session_state['trades'] = 0
if 'killed' not in st.session_state: st.session_state['killed'] = False
if 'cached_ai' not in st.session_state: st.session_state['cached_ai'] = None
if 'last_study' not in st.session_state: st.session_state['last_study'] = 0
if 'live_hist' not in st.session_state: st.session_state['live_hist'] = []
if st.sidebar.button("🛑 KILL SWITCH"): st.session_state['killed'] = True
if st.session_state['killed']:
    st.error("KILL SWITCH ON"); st.stop()

now_ist = datetime.now(timezone(timedelta(hours=5, minutes=30)))

@st.cache_resource
def get_connection():
    smart = SmartConnect(api_key=st.secrets["ANGEL_API_KEY"])
    totp = pyotp.TOTP(st.secrets["ANGEL_TOTP"]).now()
    data = smart.generateSession(st.secrets["ANGEL_CLIENT_ID"], st.secrets["ANGEL_PIN"], totp)
    return smart if data.get('status') else None

def get_underlying(smart):
    if INSTRUMENT == "NIFTY": return "26000", "NIFTY"
    term = "CRUDEOIL" if "CRUDE" in INSTRUMENT else "GOLD"
    res = smart.searchScrip(cfg["exchange"], term)
    best, best_days, best_sym = None, 9999, ""
    for item in res['data']:
        sym = item.get('tradingsymbol','')
        if 'FUT' not in sym: continue
        if 'MINI' in sym or sym.startswith("CRUDEOILM") or sym.startswith("GOLDM"): continue
        m = re.search(r'(\d{2}[A-Z]{3}\d{2})', sym)
        if not m: continue
        exp = datetime.strptime(m.group(1), "%d%b%y")
        days = (exp - now_ist.replace(tzinfo=None)).days
        if 0 <= days < best_days and days < 60:
            best_days, best, best_sym = days, item['symboltoken'], sym
    return best, best_sym

def get_news(query):
    try:
        url = f"https://news.google.com/rss/search?q={query}&hl=en-IN&gl=IN&ceid=IN:en"
        r = requests.get(url, timeout=3)
        root = ET.fromstring(r.content)
        return [item.find("title").text for item in root.findall(".//item")[:5]]
    except: return []

def news_sentiment(news_list):
    bull = ["rise","up","gain","surge","rally","high","bull","jump","positive","hike","strong","record"]
    bear = ["fall","down","drop","decline","crash","low","bear","slump","negative","cut","weak"]
    s=0
    for t in news_list:
        tl=t.lower()
        for w in bull:
            if w in tl: s+=1
        for w in bear:
            if w in tl: s-=1
    return s

def do_full_study(smart, token):
    to_date = datetime.now(); from_date = to_date - timedelta(days=3)
    hist = smart.getCandleData({"exchange": cfg["exchange"], "symboltoken": token, "interval": "FIFTEEN_MINUTE", "fromdate": from_date.strftime("%Y-%m-%d %H:%M"), "todate": to_date.strftime("%Y-%m-%d %H:%M")})
    df = pd.DataFrame(hist['data'], columns=['datetime','open','high','low','close','volume'])
    df['datetime'] = pd.to_datetime(df['datetime'])
    df['ema9']=df['close'].ewm(span=9, adjust=False).mean()
    df['ema21']=df['close'].ewm(span=21, adjust=False).mean()
    e12=df['close'].ewm(span=12, adjust=False).mean(); e26=df['close'].ewm(span=26, adjust=False).mean()
    df['macd']=e12-e26; df['macd_sig']=df['macd'].ewm(span=9, adjust=False).mean()
    d=df['close'].diff(); gain=d.clip(lower=0).ewm(alpha=1/14, adjust=False).mean(); loss=-d.clip(upper=0).ewm(alpha=1/14, adjust=False).mean()
    df['rsi']=100-(100/(1+gain/loss.replace(0, np.nan)))
    df['vwap']=(df['close']*df['volume']).cumsum()/df['volume'].cumsum()
    last=df.iloc[-1]
    news=get_news(cfg["news_q"]); n_score=news_sentiment(news)
    score=50; reasons=[]
    if last['ema9']>last['ema21']: score+=10; reasons.append("✅ EMA9 > EMA21 - Trend UP")
    else: score-=10; reasons.append("❌ EMA9 < EMA21 - Trend DOWN")
    if last['close']>last['vwap']: score+=10; reasons.append("✅ Price > VWAP - Buyers Strong")
    else: score-=10; reasons.append("❌ Price < VWAP - Sellers Strong")
    if last['macd']>last['macd_sig']: score+=10; reasons.append("✅ MACD Bullish")
    else: score-=10; reasons.append("❌ MACD Bearish")
    if 50<last['rsi']<70: score+=10; reasons.append(f"✅ RSI {last['rsi']:.1f} - Momentum UP")
    elif 30<last['rsi']<50: score-=10; reasons.append(f"❌ RSI {last['rsi']:.1f} - Momentum DOWN")
    else: reasons.append(f"⚠️ RSI {last['rsi']:.1f}")
    if n_score>0: score+=10; reasons.append(f"✅ NEWS Bullish (+{n_score})")
    elif n_score<0: score-=10; reasons.append(f"❌ NEWS Bearish ({n_score})")
    else: reasons.append("➖ NEWS Neutral")
    if score>=70: final="BUY"
    elif score<=30: final="SELL"
    else: final="WAIT"
    return {"score":score,"final":final,"reasons":reasons,"news":news,"n_score":n_score,"df":df,"last":last,"sup":df['low'].tail(20).min(),"resi":df['high'].tail(20).max()}

def make_tradingview_chart(df, live_price=None):
    # TradingView sarkha - Kala background, Lal/Hirvya Candles
    fig = go.Figure()
    # Candles
    fig.add_trace(go.Candlestick(
        x=df['datetime'], open=df['open'], high=df['high'], low=df['low'], close=df['close'],
        increasing_line_color='#26A69A', increasing_fillcolor='#26A69A',
        decreasing_line_color='#EF5350', decreasing_fillcolor='#EF5350',
        name='Candles'
    ))
    # EMA 9 - Pivla
    fig.add_trace(go.Scatter(x=df['datetime'], y=df['ema9'], line=dict(color='#FFD700', width=1.5), name='EMA 9'))
    # EMA 21 - Nila
    fig.add_trace(go.Scatter(x=df['datetime'], y=df['ema21'], line=dict(color='#2962FF', width=1.5), name='EMA 21'))
    # VWAP - Pandhra dotted
    fig.add_trace(go.Scatter(x=df['datetime'], y=df['vwap'], line=dict(color='white', width=1, dash='dot'), name='VWAP'))
    # Volume - Khali
    colors = ['#26A69A' if c >= o else '#EF5350' for c,o in zip(df['close'], df['open'])]
    fig.add_trace(go.Bar(x=df['datetime'], y=df['volume'], marker_color=colors, opacity=0.5, name='Volume', yaxis='y2'))
    fig.update_layout(
        template='plotly_dark',
        paper_bgcolor='#131722', plot_bgcolor='#131722',
        font=dict(color='white'),
        xaxis=dict(gridcolor='#1E222D', rangeslider=dict(visible=False)),
        yaxis=dict(gridcolor='#1E222D', side='right'),
        yaxis2=dict(overlaying='y', side='left', showgrid=False, position=0),
        height=500,
        margin=dict(l=0, r=50, t=10, b=0),
        legend=dict(orientation='h', y=1.02, x=0),
        hovermode='x unified'
    )
    return fig

def get_atm_option(smart, signal, ltp):
    atm = round(ltp / cfg["strike_step"]) * cfg["strike_step"]
    otype = "CE" if signal=="BUY" else "PE"
    res = smart.searchScrip(cfg["opt_exchange"], cfg["prefix"])
    cands=[]
    for item in res['data']:
        sym=item.get('tradingsymbol','')
        if 'FUT' in sym: continue
        if otype not in sym: continue
        if str(atm) not in sym: continue
        cands.append(item)
    def get_exp(s):
        m=re.search(r'(\d{2}[A-Z]{3}\d{2})', s.get('tradingsymbol',''))
        if m:
            try: return datetime.strptime(m.group(1), "%d%b%y")
            except: return datetime(2030,1,1)
        return datetime(2030,1,1)
    cands.sort(key=get_exp)
    if cands: return cands[0]['tradingsymbol'], cands[0]['symboltoken'], atm
    return None,None,atm

# --- MAIN ---
smart = get_connection()
if not smart:
    st.error("Login Fail"); st.stop()
token, sym_name = get_underlying(smart)

if time.time() - st.session_state['last_study'] > 30 or st.session_state['cached_ai'] is None:
    try:
        st.session_state['cached_ai'] = do_full_study(smart, token)
        st.session_state['last_study'] = time.time()
    except Exception as e: st.warning(f"Study Error: {e}")

ai = st.session_state['cached_ai']
if ai:
    st.info(f"📅 {now_ist.strftime('%d %b %Y, %A')} | 🕒 {now_ist.strftime('%H:%M:%S')} IST | 🧠 AI 30 sec la update")
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("AI SCORE", f"{ai['score']}/100", ai['final'])
    c2.metric("RSI", f"{ai['last']['rsi']:.1f}")
    c3.metric("Support", f"₹{ai['sup']:.2f}")
    c4.metric("Resistance", f"₹{ai['resi']:.2f}")
    if ai['final']=="BUY": st.success(f"### 🟢 BUY CALL (CE) - Score {ai['score']}/100")
    elif ai['final']=="SELL": st.error(f"### 🔴 SELL PUT (PE) - Score {ai['score']}/100")
    else: st.warning(f"### 🟡 WAIT - Score {ai['score']}/100")
    col1,col2 = st.columns(2)
    with col1:
        st.write("**🧠 AI Reason:**")
        for r in ai['reasons']: st.write(r)
    with col2:
        st.write("**📰 NEWS:**")
        for n in ai['news']: st.write(f"- {n}")

# --- TRADINGVIEW CHART + 1 SEC LIVE - Fakt ha bhag halel ---
@st.fragment(run_every=1)
def live_chart_box():
    try:
        s = get_connection()
        ltp = s.ltpData(cfg["exchange"], sym_name if INSTRUMENT!="NIFTY" else "NIFTY", token)['data']['ltp']
        # Live candle update - shevatchi candle live halav
        df = ai['df'].copy() if ai else pd.DataFrame()
        if not df.empty:
            # Shevatchi candle cha close = live price
            df.loc[df.index[-1], 'close'] = ltp
            df.loc[df.index[-1], 'high'] = max(df.loc[df.index[-1], 'high'], ltp)
            df.loc[df.index[-1], 'low'] = min(df.loc[df.index[-1], 'low'], ltp)
        c1,c2 = st.columns([1,3])
        with c1:
            st.metric(f"{INSTRUMENT} LIVE ⚡", f"₹{ltp:.2f}")
            st.caption(f"Update: {datetime.now().strftime('%H:%M:%S')} - Page refresh nahi")
        with c2:
            st.write(f"**{INSTRUMENT} · {cfg['exchange']} · 15m**")
        if not df.empty:
            fig = make_tradingview_chart(df.tail(60), ltp)
            st.plotly_chart(fig, use_container_width=True, key=f"tv_{datetime.now().strftime('%H%M%S')}")
    except Exception as e:
        st.write(f"Chart load hotoy... {e}")

st.divider()
st.subheader(f"📈 {INSTRUMENT} - TRADINGVIEW CHART - 15m - LIVE 1 SEC")
live_chart_box()

# --- TRADE BUTTONS - Tuzya screenshot sarkhe ---
st.divider()
if ai and ai['final']!="WAIT":
    col_buy, col_put = st.columns(2)
    with col_buy:
        if st.button("⬆️ BUY CALL", type="primary", use_container_width=True):
            st.session_state['manual_signal'] = "BUY"
    with col_put:
        if st.button("⬇️ BUY PUT", type="primary", use_container_width=True):
            st.session_state['manual_signal'] = "SELL"
    sig = st.session_state.get('manual_signal', ai['final'])
    if st.button(f"🚀 TRADE GHE - {sig} - {INSTRUMENT}", type="primary"):
        if st.session_state['trades']>=MAX_TRADES: st.warning("Max Trades zale!")
        else:
            live_ltp = smart.ltpData(cfg["exchange"], sym_name if INSTRUMENT!="NIFTY" else "NIFTY", token)['data']['ltp']
            sym,tok,atm=get_atm_option(smart, sig, live_ltp)
            if tok:
                opt_ltp=smart.ltpData(cfg["opt_exchange"], sym, tok)['data']['ltp']
                st.info(f"Option: {sym} | ATM {atm} | Premium ₹{opt_ltp} | Qty {QTY}")
                if not LIVE_MODE: st.warning(f"PAPER ORDER: {sig} {sym} @ ₹{opt_ltp}")
                else:
                    oid=smart.placeOrder({"variety":"NORMAL","tradingsymbol":sym,"symboltoken":tok,"transactiontype":"BUY","exchange":cfg["opt_exchange"],"ordertype":"MARKET","producttype":"INTRADAY","duration":"DAY","price":"0","squareoff":str(int(TARGET_POINTS*100)),"stoploss":str(int(SL_POINTS*100)),"quantity":str(QTY)})
                    st.success(f"✅ LIVE ORDER GELI! {oid}"); st.session_state['trades']+=1
            else: st.error("Option sapadla nahi")
else:
    st.info("WAIT aahe - AI la clear signal nahi")
    if st.button("⬆️ BUY CALL", use_container_width=True): st.session_state['manual_signal']="BUY"
    if st.button("⬇️ BUY PUT", use_container_width=True): st.session_state['manual_signal']="SELL"

if st.button("📊 Live Positions Bagha"):
    pos=smart.position()
    if pos['data']: st.dataframe(pd.DataFrame(pos['data']))
    else: st.write("Kutlihi Position nahi")
if st.button("🔄 Study Aatach Parat Kar"):
    st.session_state['last_study']=0; st.rerun()
# --- MARKET OFF + INTRADAY CROWD CHART ---
import streamlit as st
import plotly.graph_objects as go
from datetime import datetime, timedelta, timezone

st.divider()
st.subheader("👥 INTRADAY CROWD + ⏰ MARKET OFF COUNTDOWN")

now_ist = datetime.now(timezone(timedelta(hours=5, minutes=30)))

# 1. MARKET OFF COUNTDOWN
if INSTRUMENT == "NIFTY":
    close_time = now_ist.replace(hour=15, minute=30, second=0)
    open_time = now_ist.replace(hour=9, minute=15, second=0)
    market_name = "NIFTY"
else:
    close_time = now_ist.replace(hour=23, minute=30, second=0)
    open_time = now_ist.replace(hour=9, minute=0, second=0)
    market_name = "MCX"

if now_ist < open_time:
    st.warning(f"🔴 {market_name} ajun ughadla nahi - Ughdel: {open_time.strftime('%I:%M %p')}")
    progress = 0
    remaining_str = f"Ughdayla {int((open_time - now_ist).total_seconds()/60)} min baki"
elif now_ist > close_time:
    st.error(f"🔴 {market_name} BAND zala - Udhya {open_time.strftime('%I:%M %p')} la ughdel")
    progress = 100
    remaining_str = "Market Band - Udhya baghu"
else:
    total_min = (close_time - open_time).total_seconds()/60
    done_min = (now_ist - open_time).total_seconds()/60
    left_min = (close_time - now_ist).total_seconds()/60
    progress = int((done_min/total_min)*100)
    h = int(left_min//60); m = int(left_min%60)
    remaining_str = f"Market Band hoyla: {h} taas {m} min baki"
    st.success(f"🟢 {market_name} CHALU AAHE | {remaining_str}")

st.progress(progress/100)
st.caption(f"Market Progress: {progress}% sampala | {remaining_str}")

# 2. INTRADAY CROWD - Volume + OI varun
# Angel kade OI milto - Option Chain madhun
try:
    # Option Chain / OI ghe
    # NIFTY sathi NFO, MCX sathi MCX
    oi_data = smart.getOptionChain(cfg["opt_exchange"], sym_name if INSTRUMENT!="NIFTY" else "NIFTY", token) if INSTRUMENT=="NIFTY" else None
    # Jar OI milala nahi tar Volume varun andaz
    df_crowd = ai['df'].copy() if ai else pd.DataFrame()
    if not df_crowd.empty:
        # Shevatchya 20 candles cha Volume
        last20 = df_crowd.tail(20).copy()
        # Crowd Estimate: Volume jasta = lok jasta
        # 1 Lot = 1 jan pakadla (andaz)
        avg_vol = last20['volume'].mean()
        curr_vol = last20['volume'].iloc[-1]
        crowd_trend = "🔥 VADHATAY" if curr_vol > avg_vol else "📉 KAMI HOTAY"
        
        c1,c2,c3 = st.columns(3)
        c1.metric("📊 Aatcha Volume (15m)", f"{int(curr_vol):,}", f"{((curr_vol-avg_vol)/avg_vol*100):.1f}% vs Avg")
        c2.metric("👥 Andaz Intraday Traders", f"~{int(curr_vol/2):,}", crowd_trend)
        c3.metric("⏰ Market Off", remaining_str)

        # Volume Chart - Kiti lok aale, kiti gele
        fig_crowd = go.Figure()
        fig_crowd.add_trace(go.Bar(
            x=last20['datetime'], y=last20['volume'],
            marker_color=['#26A69A' if c>=o else '#EF5350' for c,o in zip(last20['close'], last20['open'])],
            name='Volume = Lok'
        ))
        fig_crowd.add_trace(go.Scatter(
            x=last20['datetime'], y=[avg_vol]*len(last20),
            line=dict(color='yellow', dash='dash'), name='Avg Volume - Sarvasadharan Crowd'
        ))
        fig_crowd.update_layout(
            template='plotly_dark', paper_bgcolor='#131722', plot_bgcolor='#131722',
            title='👥 INTRADAY CROWD CHART - Bar unch = Lok jasta aale, Bar lahan = Lok gele',
            height=280, margin=dict(l=0,r=10,t=40,b=0),
            xaxis=dict(gridcolor='#1E222D'), yaxis=dict(gridcolor='#1E222D')
        )
        st.plotly_chart(fig_crowd, use_container_width=True)
        st.caption("Samaj: Hirva Bar unch = Buying sathi lok aale | Lal Bar unch = Selling sathi lok aale | Pivli line chya khali Bar = Lok kami zale, Market Off javal aala ki lok palatat")
        
        # 3. Market Off javal aalyavar kay hota te sang
        if left_min < 60 if 'left_min' in locals() else False:
            st.warning("⚠️ **Market Off la 1 taas baki - Intraday wale Square Off kartat!** Volume vadhil, pan trend ulta hou shakto. Navin entry nako!")
        elif left_min < 180 if 'left_min' in locals() else False:
            st.info("ℹ️ **Market Off la 3 taas baki - Halu halu lok baher padtil.**")
except Exception as e:
    st.write(f"Crowd Chart load hotoy... {e}")

# 4. PCR - Lok Call ghetay ka Put ghetay?
st.write("**📊 PCR - Lokancha Mood:**")
st.write("- PCR > 1.0 = Lok PUT ghetay (Market padel vatay)")
st.write("- PCR < 0.8 = Lok CALL ghetay (Market vadhil vatay)")
st.write("- PCR 0.8 - 1.0 = Donhi bajula lok aahet, Neutral")

