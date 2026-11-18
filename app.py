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

# --- 1 SEC LIVE REFRESH ---
st.markdown("<meta http-equiv='refresh' content='1'>", unsafe_allow_html=True)

st.title("🤖 SAGAR AI PRO - 1 SEC LIVE")

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
if 'last_study_time' not in st.session_state: st.session_state['last_study_time'] = 0
if 'cached_ai' not in st.session_state: st.session_state['cached_ai'] = None
if st.sidebar.button("🛑 KILL SWITCH"): st.session_state['killed'] = True
if st.session_state['killed']:
    st.error("KILL SWITCH ON"); st.stop()

now_ist = datetime.now(timezone(timedelta(hours=5, minutes=30)))
st.info(f"📅 **{now_ist.strftime('%d %b %Y, %A')}** | 🕒 **IST: {now_ist.strftime('%H:%M:%S')}** | ⚡ **LIVE 1 SEC**")

def market_status():
    h = now_ist.hour + now_ist.minute/60
    if INSTRUMENT == "NIFTY":
        if 9.25 <= h <= 15.5: return "🟢 NIFTY OPEN", f"Band: 3:30 PM - {(15.5-h)*60:.0f} min baki"
        else: return "🔴 NIFTY BAND", "Ughdel: 9:15 AM"
    else:
        if 9 <= h <= 23.5: return "🟢 MCX OPEN", f"Band: 11:30 PM - {(23.5-h)*60:.0f} min baki"
        else: return "🔴 MCX BAND", "Ughdel: 9:00 AM"
ms, ms_detail = market_status()
st.success(f"{ms} | {ms_detail}")

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
        news = []
        for item in root.findall(".//item")[:5]:
            news.append(item.find("title").text)
        return news
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
try:
    smart = get_connection()
    if not smart: st.error("Login Fail"); st.stop()
    token, sym_name = get_underlying(smart)

    # 1 SEC - FAKT LTP - Halka call, Rate Limit nahi yenar
    try:
        live_ltp = smart.ltpData(cfg["exchange"], sym_name if INSTRUMENT!="NIFTY" else "NIFTY", token)['data']['ltp']
    except:
        live_ltp = 0

    # 30 SEC LA EKDA FULL STUDY - Purna abhyas
    now_ts = time.time()
    need_study = (now_ts - st.session_state['last_study_time'] > 30) or (st.session_state['cached_ai'] is None)

    if need_study:
        st.session_state['last_study_time'] = now_ts
        to_date = datetime.now(); from_date = to_date - timedelta(days=10)
        hist = smart.getCandleData({"exchange": cfg["exchange"], "symboltoken": token, "interval": "FIFTEEN_MINUTE", "fromdate": from_date.strftime("%Y-%m-%d %H:%M"), "todate": to_date.strftime("%Y-%m-%d %H:%M")})
        df = pd.DataFrame(hist['data'], columns=['datetime','open','high','low','close','volume'])
        df['ema9']=df['close'].ewm(span=9, adjust=False).mean()
        df['ema21']=df['close'].ewm(span=21, adjust=False).mean()
        df['ema50']=df['close'].ewm(span=50, adjust=False).mean()
        e12=df['close'].ewm(span=12, adjust=False).mean(); e26=df['close'].ewm(span=26, adjust=False).mean()
        df['macd']=e12-e26; df['macd_sig']=df['macd'].ewm(span=9, adjust=False).mean()
        d=df['close'].diff(); gain=d.clip(lower=0).ewm(alpha=1/14, adjust=False).mean(); loss=-d.clip(upper=0).ewm(alpha=1/14, adjust=False).mean()
        df['rsi']=100-(100/(1+gain/loss.replace(0, np.nan)))
        df['vwap']=(df['close']*df['volume']).cumsum()/df['volume'].cumsum()
        last=df.iloc[-1]; prev=df.iloc[-2]
        sup=df['low'].tail(20).min(); resi=df['high'].tail(20).max()
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
        else: reasons.append(f"⚠️ RSI {last['rsi']:.1f} - Overbought/Oversold")
        if last['volume']>df['volume'].tail(20).mean(): score+=5; reasons.append("✅ Volume High")
        if n_score>0: score+=10; reasons.append(f"✅ NEWS Bullish (+{n_score})")
        elif n_score<0: score-=10; reasons.append(f"❌ NEWS Bearish ({n_score})")
        else: reasons.append("➖ NEWS Neutral")
        if "BAND" in ms: score=50; reasons.append("⚠️ Market Band")
        if score>=70: final="BUY"
        elif score<=30: final="SELL"
        else: final="WAIT"
        st.session_state['cached_ai'] = {"score":score,"final":final,"reasons":reasons,"news":news,"n_score":n_score,"df":df,"last":last,"prev":prev,"sup":sup,"resi":resi}
        st.toast("🧠 Purna Study Zala - AI Update!")
    else:
        st.caption(f"🧠 AI Study: {30 - int(now_ts - st.session_state['last_study_time'])} sec madhe parat honar | Price matra 1 sec la live aahe")

    ai = st.session_state['cached_ai']
    df=ai['df']; last=ai['last']; prev=ai['prev']

    c1,c2,c3,c4,c5 = st.columns(5)
    c1.metric(f"{INSTRUMENT} LIVE ⚡", f"₹{live_ltp:.2f}", f"{live_ltp - prev['close']:.2f}")
    c2.metric("AI SCORE", f"{ai['score']}/100", ai['final'])
    c3.metric("RSI", f"{last['rsi']:.1f}")
    c4.metric("Support", f"₹{ai['sup']:.2f}")
    c5.metric("Resistance", f"₹{ai['resi']:.2f}")

    st.subheader(f"🤖 AI DECISION: {ai['final']}")
    if ai['final']=="BUY": st.success(f"### 🟢 BUY CALL (CE) - Score {ai['score']}/100")
    elif ai['final']=="SELL": st.error(f"### 🔴 SELL PUT (PE) - Score {ai['score']}/100")
    else: st.warning(f"### 🟡 WAIT - Score {ai['score']}/100 - No Clear Trend")

    col1,col2 = st.columns(2)
    with col1:
        st.write("**🧠 AI Kasa Decide Kela (Purna Study):**")
        for r in ai['reasons']: st.write(r)
    with col2:
        st.write("**📰 LIVE NEWS:**")
        for n in ai['news']: st.write(f"- {n}")
        st.write(f"Sentiment: {ai['n_score']}")

    st.line_chart(df.set_index('datetime')[['close','ema9','ema21','vwap']].tail(60))

    st.divider()
    if ai['final']!="WAIT" and "BAND" not in ms:
        if st.button(f"🚀 TRADE GHE - {ai['final']} - {INSTRUMENT}", type="primary"):
            if st.session_state['trades']>=MAX_TRADES: st.warning("Max Trades zale!")
            else:
                sym,tok,atm=get_atm_option(smart, ai['final'], live_ltp)
                if tok:
                    opt_ltp=smart.ltpData(cfg["opt_exchange"], sym, tok)['data']['ltp']
                    st.info(f"Option: {sym} | ATM {atm} | Premium ₹{opt_ltp} | Qty {QTY}")
                    if not LIVE_MODE: st.warning(f"PAPER ORDER: {ai['final']} {sym} @ ₹{opt_ltp}")
                    else:
                        oid=smart.placeOrder({"variety":"NORMAL","tradingsymbol":sym,"symboltoken":tok,"transactiontype":"BUY","exchange":cfg["opt_exchange"],"ordertype":"MARKET","producttype":"INTRADAY","duration":"DAY","price":"0","squareoff":str(int(TARGET_POINTS*100)),"stoploss":str(int(SL_POINTS*100)),"quantity":str(QTY)})
                        st.success(f"✅ LIVE ORDER GELI! {oid}"); st.session_state['trades']+=1
                else: st.error("Option sapadla nahi")
    if st.button("📊 Live Positions Bagha"):
        pos=smart.position()
        if pos['data']: st.dataframe(pd.DataFrame(pos['data']))
        else: st.write("Kutlihi Position nahi")

except Exception as e:
    st.error(f"Error: {e}")
    st.write("1 sec madhe parat try hoil")

st.caption(f"Last Price Update: {now_ist.strftime('%H:%M:%S')} IST | Price: 1 SEC LIVE | Full AI Study: 30 SEC")
