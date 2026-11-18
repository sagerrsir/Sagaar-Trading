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

st.set_page_config(page_title="SAGAR AI PRO 1-SEC", layout="wide")
st.title("🤖 SAGAR AI PRO - 1 SEC LIVE - NO PAGE REFRESH")

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
if 'price_history' not in st.session_state: st.session_state['price_history'] = []
if 'cached_ai' not in st.session_state: st.session_state['cached_ai'] = None
if 'last_study' not in st.session_state: st.session_state['last_study'] = 0
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

def do_full_study(smart, token, sym_name):
    # Purna study - 30 sec la ekda
    to_date = datetime.now(); from_date = to_date - timedelta(days=10)
    hist = smart.getCandleData({"exchange": cfg["exchange"], "symboltoken": token, "interval": "FIFTEEN_MINUTE", "fromdate": from_date.strftime("%Y-%m-%d %H:%M"), "todate": to_date.strftime("%Y-%m-%d %H:%M")})
    df = pd.DataFrame(hist['data'], columns=['datetime','open','high','low','close','volume'])
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

# --- MAIN STATIC PART - Ha ekdach load honar, parat nahi halnar ---
smart = get_connection()
if not smart:
    st.error("Login Fail"); st.stop()
token, sym_name = get_underlying(smart)

# Purna Study - Fakt 30 sec la ekda
if time.time() - st.session_state['last_study'] > 30 or st.session_state['cached_ai'] is None:
    try:
        st.session_state['cached_ai'] = do_full_study(smart, token, sym_name)
        st.session_state['last_study'] = time.time()
    except Exception as e:
        st.warning(f"Study Error: {e}")

ai = st.session_state['cached_ai']
if ai:
    st.info(f"📅 {now_ist.strftime('%d %b %Y, %A')} | 🕒 {now_ist.strftime('%H:%M:%S')} | 🧠 AI Study: 30 sec la update")
    c1,c2,c3 = st.columns(3)
    c1.metric("AI SCORE", f"{ai['score']}/100", ai['final'])
    c2.metric("RSI", f"{ai['last']['rsi']:.1f}")
    c3.metric("Support / Resistance", f"{ai['sup']:.0f} / {ai['resi']:.0f}")
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

# --- LIVE 1 SEC FRAGMENT - Fakt ha bhag halel, baki page nahi ---
@st.fragment(run_every=1)
def live_price_box():
    try:
        s = get_connection()
        ltp = s.ltpData(cfg["exchange"], sym_name if INSTRUMENT!="NIFTY" else "NIFTY", token)['data']['ltp']
        # History madhe add kar - chart sathi
        st.session_state['price_history'].append({"time": datetime.now().strftime("%H:%M:%S"), "price": ltp})
        if len(st.session_state['price_history']) > 60:
            st.session_state['price_history'] = st.session_state['price_history'][-60:]
        ph = pd.DataFrame(st.session_state['price_history'])
        c1,c2 = st.columns([1,3])
        with c1:
            st.metric(f"{INSTRUMENT} LIVE ⚡ 1 SEC", f"₹{ltp:.2f}", f"{ltp - ph['price'].iloc[0]:.2f}" if len(ph)>1 else "")
            st.caption(f"Update: {datetime.now().strftime('%H:%M:%S')} - Page refresh nahi hot")
        with c2:
            # LIVE CHART - Fakt ha chart halel
            if len(ph) > 1:
                st.line_chart(ph.set_index("time")["price"], height=180)
            else:
                st.write("Live price yetoy... 1 sec thamb")
    except Exception as e:
        st.write(f"Live price wait... {e}")

st.divider()
st.subheader("📈 LIVE PRICE + CHART - 1 SEC (Page Refresh Nahi Honar)")
live_price_box()

# --- TRADE BUTTON - Static, halnar nahi ---
st.divider()
if ai and ai['final']!="WAIT":
    if st.button(f"🚀 TRADE GHE - {ai['final']} - {INSTRUMENT}", type="primary"):
        if st.session_state['trades']>=MAX_TRADES: st.warning("Max Trades zale!")
        else:
            # Live LTP gheun trade
            live_ltp = smart.ltpData(cfg["exchange"], sym_name if INSTRUMENT!="NIFTY" else "NIFTY", token)['data']['ltp']
            sym,tok,atm=get_atm_option(smart, ai['final'], live_ltp)
            if tok:
                opt_ltp=smart.ltpData(cfg["opt_exchange"], sym, tok)['data']['ltp']
                st.info(f"Option: {sym} | ATM {atm} | Premium ₹{opt_ltp} | Qty {QTY}")
                if not LIVE_MODE: st.warning(f"PAPER ORDER: {ai['final']} {sym} @ ₹{opt_ltp}")
                else:
                    oid=smart.placeOrder({"variety":"NORMAL","tradingsymbol":sym,"symboltoken":tok,"transactiontype":"BUY","exchange":cfg["opt_exchange"],"ordertype":"MARKET","producttype":"INTRADAY","duration":"DAY","price":"0","squareoff":str(int(TARGET_POINTS*100)),"stoploss":str(int(SL_POINTS*100)),"quantity":str(QTY)})
                    st.success(f"✅ LIVE ORDER GELI! {oid}"); st.session_state['trades']+=1
            else: st.error("Option sapadla nahi")
else:
    st.info("WAIT aahe - Trade button nahi")

if st.button("📊 Live Positions Bagha"):
    pos=smart.position()
    if pos['data']: st.dataframe(pd.DataFrame(pos['data']))
    else: st.write("Kutlihi Position nahi")

if st.button("🔄 Purna Study Aatach Parat Kar (30 sec chi vaat nako)"):
    st.session_state['last_study'] = 0
    st.rerun()
