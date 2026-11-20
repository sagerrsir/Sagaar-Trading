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

st.set_page_config(page_title="SAGAR AI PRO - AI VERSION", layout="wide")
st.title("🤖 SAGAR AI PRO - NIFTY | BANKNIFTY | CRUDE | EQUITY - AI SALLA SObat")

CONFIG = {
    "NIFTY": {"exchange": "NSE", "strike_step": 50, "qty": 25, "opt_exchange": "NFO", "prefix": "NIFTY", "news_q": "Nifty 50 stock market India", "token": "26000", "sym": "NIFTY", "fut_exchange": "NFO", "fut_search": "NIFTY"},
    "BANKNIFTY": {"exchange": "NSE", "strike_step": 100, "qty": 15, "opt_exchange": "NFO", "prefix": "BANKNIFTY", "news_q": "Bank Nifty today HDFC ICICI", "token": "26009", "sym": "BANKNIFTY", "fut_exchange": "NFO", "fut_search": "BANKNIFTY"},
    "CRUDEOIL MINI": {"exchange": "MCX", "strike_step": 50, "qty": 10, "opt_exchange": "MCX", "prefix": "CRUDEOILM", "news_q": "Crude Oil price OPEC", "token": None, "sym": None, "fut_exchange": "MCX", "fut_search": "CRUDEOIL"},
}
INSTRUMENTS = ["NIFTY", "BANKNIFTY", "CRUDEOIL MINI"]

# --- SIDEBAR ---
st.sidebar.header("🤖 AI CONTROL")
st.sidebar.success("AI ON - Fakt Pakke Trade")
LIVE_MODE = st.sidebar.toggle("🔴 LIVE TRADING ON", value=False)
if LIVE_MODE:
    st.sidebar.warning("⚠️ LIVE ON AAHE - Khara paisa lagel!")
SL_POINTS = st.sidebar.number_input("SL Points", value=30)
TARGET_POINTS = st.sidebar.number_input("Target Points", value=60)
MAX_TRADES = st.sidebar.number_input("Max Trades / Day", value=1)
MAX_LOSS = st.sidebar.number_input("Max Loss / Day (Rs)", value=1000)

if 'trades' not in st.session_state: st.session_state['trades'] = 0
if 'killed' not in st.session_state: st.session_state['killed'] = False
if 'cached_all' not in st.session_state: st.session_state['cached_all'] = {}
if 'last_study' not in st.session_state: st.session_state['last_study'] = 0
if 'selected_trade' not in st.session_state: st.session_state['selected_trade'] = None
if 'smart_obj' not in st.session_state: st.session_state['smart_obj'] = None
if 'login_time' not in st.session_state: st.session_state['login_time'] = 0
if 'fut_cache' not in st.session_state: st.session_state['fut_cache'] = {}
if 'eq_df' not in st.session_state: st.session_state['eq_df'] = None
if 'news_cache' not in st.session_state: st.session_state['news_cache'] = {}
if 'day_pnl' not in st.session_state: st.session_state['day_pnl'] = 0
if 'ai_memory' not in st.session_state: st.session_state['ai_memory'] = []

if st.sidebar.button("🛑 KILL SWITCH"): st.session_state['killed'] = True
if st.sidebar.button("✅ KILL OFF KAR"): st.session_state['killed'] = False
if st.session_state['killed']:
    st.error("🛑 KILL SWITCH ON - Sagla Trade Band"); st.stop()
if st.sidebar.button("🔄 Navin Login Kar"):
    st.session_state['smart_obj'] = None; st.session_state['login_time'] = 0
    st.session_state['cached_all'] = {}; st.session_state['last_study'] = 0; st.session_state['fut_cache'] = {}
    st.rerun()

# AI - Daily Loss Lock
if st.session_state['day_pnl'] <= -MAX_LOSS:
    st.error(f"🛑 AI RISK LOCK - Aajcha Loss ₹{st.session_state['day_pnl']} zala. Aaj parat trade nahi. Udya navin.")
    st.stop()

now_ist = datetime.now(timezone(timedelta(hours=5, minutes=30)))
now_ist_naive = now_ist.replace(tzinfo=None)

missing = [k for k in ["ANGEL_API_KEY","ANGEL_TOTP","ANGEL_CLIENT_ID","ANGEL_PIN"] if k not in st.secrets]
if missing:
    st.error(f"❌ Secrets madhe he nahi: {', '.join(missing)}")
    st.info("Streamlit Cloud > Manage app > Settings > Secrets madhe tak"); st.stop()

def get_connection():
    if st.session_state['smart_obj'] is not None and (time.time() - st.session_state['login_time'] < 1800):
        return st.session_state['smart_obj']
    try:
        smart = SmartConnect(api_key=st.secrets["ANGEL_API_KEY"])
        totp = pyotp.TOTP(st.secrets["ANGEL_TOTP"]).now()
        data = smart.generateSession(st.secrets["ANGEL_CLIENT_ID"], st.secrets["ANGEL_PIN"], totp)
        if data.get('status'):
            st.session_state['smart_obj'] = smart; st.session_state['login_time'] = time.time()
            st.success("✅ Angel Login Zala"); return smart
        else:
            st.error(f"Login Fail: {data.get('message', data)}"); return None
    except Exception as e:
        st.error(f"Login Error: {e}"); return None

def safe_candle(smart, exchange, token):
    to_date = now_ist_naive; from_date = to_date - timedelta(days=3)
    for attempt in range(2):
        try:
            time.sleep(0.2)
            hist = smart.getCandleData({"exchange": exchange, "symboltoken": token, "interval": "FIFTEEN_MINUTE", "fromdate": from_date.strftime("%Y-%m-%d %H:%M"), "todate": to_date.strftime("%Y-%m-%d %H:%M")})
            if hist and hist.get('data'): return hist
            if attempt == 0:
                time.sleep(0.3)
                hist2 = smart.getCandleData({"exchange": exchange, "symboltoken": token, "interval": "ONE_HOUR", "fromdate": from_date.strftime("%Y-%m-%d %H:%M"), "todate": to_date.strftime("%Y-%m-%d %H:%M")})
                if hist2 and hist2.get('data'): return hist2
            return hist
        except Exception as e:
            if "exceeding" in str(e) or "Access denied" in str(e): time.sleep(1.0); continue
            break
    return {"error": "No data"}

def get_underlying(smart, inst):
    if inst in st.session_state['fut_cache']: return st.session_state['fut_cache'][inst]
    cfg = CONFIG[inst]
    try:
        time.sleep(0.2)
        res = smart.searchScrip(cfg["fut_exchange"], cfg["fut_search"])
        if not res or not isinstance(res, dict): return None, None, None
        data_list = res.get('data') or []
        best, best_days, best_sym = None, 9999, ""; best_exch = cfg["fut_exchange"]
        for item in data_list:
            sym = item.get('tradingsymbol','').strip()
            if inst == "NIFTY":
                if not re.match(r'^NIFTY\d{2}[A-Z]{3}\d{2}FUT$', sym): continue
            elif inst == "BANKNIFTY":
                if not re.match(r'^BANKNIFTY\d{2}[A-Z]{3}\d{2}FUT$', sym): continue
            elif inst == "CRUDEOIL MINI":
                if not re.match(r'^CRUDEOIL\d{2}[A-Z]{3}\d{2}FUT$', sym): continue
            m = re.search(r'(\d{2}[A-Z]{3}\d{2})', sym)
            if not m: continue
            try: exp = datetime.strptime(m.group(1), "%d%b%y")
            except: continue
            days = (exp - now_ist_naive).days
            if 0 <= days < best_days and days < 60:
                best_days, best, best_sym = days, item.get('symboltoken'), sym
                best_exch = item.get('exchange', cfg["fut_exchange"])
        if best:
            result = (best, best_sym, best_exch); st.session_state['fut_cache'][inst] = result; return result
        return None, None, None
    except: return None, None, None

def get_news(query):
    if query in st.session_state['news_cache']:
        t, val = st.session_state['news_cache'][query]
        if time.time() - t < 300: return val
    try:
        url = f"https://news.google.com/rss/search?q={query}&hl=en-IN&gl=IN&ceid=IN:en"
        r = requests.get(url, timeout=2); root = ET.fromstring(r.content)
        val = [item.find("title").text for item in root.findall(".//item")[:3]]
    except: val = []
    st.session_state['news_cache'][query] = (time.time(), val); return val

def news_sentiment(news_list):
    bull = ["rise","up","gain","surge","rally","high","bull","jump","positive","hike","strong","record","growth"]
    bear = ["fall","down","drop","decline","crash","low","bear","slump","negative","cut","weak","loss"]
    s=0
    for t in news_list:
        tl=t.lower()
        for w in bull:
            if w in tl: s+=1
        for w in bear:
            if w in tl: s-=1
    return s

# ================= AI BRAIN =================
def ai_brain(df, inst):
    # AI Pattern + Prediction + Fake Move Detector
    last = df.iloc[-1]; prev = df.iloc[-2]; prev2 = df.iloc[-3]
    # 1. Volatility - Aaj sarkha fake move?
    df['range'] = df['high'] - df['low']
    avg_range = df['range'].tail(20).mean()
    last_range = last['range']
    volatility = "HIGH" if last_range > avg_range*1.8 else "NORMAL" if last_range > avg_range*0.8 else "LOW"
    # 2. Fake Move Check - Lambi wick = trap
    body = abs(last['close'] - last['open'])
    upper_wick = last['high'] - max(last['close'], last['open'])
    lower_wick = min(last['close'], last['open']) - last['low']
    fake_up = upper_wick > body*2 and last['close'] < last['open']
    fake_down = lower_wick > body*2 and last['close'] > last['open']
    # 3. Momentum - 3 candle trend
    up_candles = sum(1 for i in [-1,-2,-3] if df.iloc[i]['close'] > df.iloc[i]['open'])
    down_candles = 3 - up_candles
    # 4. Breakout Check
    resi = df['high'].tail(20).max(); sup = df['low'].tail(20).min()
    breakout_up = last['close'] > resi*0.998
    breakdown_down = last['close'] < sup*1.002
    # 5. AI Prediction %
    ai_up = 50
    if last['ema9'] > last['ema21'] > last['ema50']: ai_up += 20
    elif last['ema9'] < last['ema21'] < last['ema50']: ai_up -= 20
    if last['close'] > last['vwap']: ai_up += 10
    else: ai_up -= 10
    if last['macd'] > last['macd_sig']: ai_up += 10
    else: ai_up -= 10
    if up_candles == 3: ai_up += 10
    elif down_candles == 3: ai_up -= 10
    if fake_up: ai_up -= 15
    if fake_down: ai_up += 15
    ai_up = max(5, min(95, ai_up))
    ai_down = 100 - ai_up
    # 6. AI Salah - Sopya bhashet
    if fake_up or fake_down:
        pattern = "⚠️ AI: FAKE MOVE / TRAP - Lambi Wick - Fasvu naka!"
        salah = "🛑 THAMBA - Ha move khota vatatoy, 1 candle vaat bagha"
        risk = "HIGH"
    elif breakout_up:
        pattern = "🚀 AI: BREAKOUT - Resistance todla!"
        salah = "✅ GHEU SHAKTA - Breakout confirm, pan SL theva"
        risk = "LOW"
    elif breakdown_down:
        pattern = "📉 AI: BREAKDOWN - Support todla!"
        salah = "✅ SELL / PUT bagha - Khali janar"
        risk = "LOW"
    elif volatility == "HIGH":
        pattern = "🌪️ AI: HIGH VOLATILITY - Market khup haltoy"
        salah = "🛑 THAMBA - Halchal jast aahe, chukicha entry hoil"
        risk = "HIGH"
    elif ai_up >= 70:
        pattern = "📈 AI: STRONG UPTREND - 3 candle var"
        salah = "✅ BUY / CALL bagha"
        risk = "LOW"
    elif ai_up <= 30:
        pattern = "📉 AI: STRONG DOWNTREND"
        salah = "✅ SELL / PUT bagha"
        risk = "LOW"
    else:
        pattern = "➖ AI: SIDEWAYS - Kahi kalat nahi"
        salah = "🛑 TRADE NAKO - Sideways madhe paisa jato"
        risk = "MEDIUM"
    return {"ai_up": ai_up, "ai_down": ai_down, "pattern": pattern, "salah": salah, "risk": risk, "volatility": volatility, "fake_up": fake_up, "fake_down": fake_down, "breakout_up": breakout_up, "breakdown_down": breakdown_down}

def do_study(smart, inst, fut_info):
    cfg = CONFIG[inst]; token, fut_sym, fut_exch = fut_info
    hist = safe_candle(smart, fut_exch, token)
    if not hist or 'data' not in hist or not hist['data']: return None
    df = pd.DataFrame(hist['data'], columns=['datetime','open','high','low','close','volume'])
    if len(df) < 20: return None
    df['datetime'] = pd.to_datetime(df['datetime'])
    df['ema9']=df['close'].ewm(span=9, adjust=False).mean()
    df['ema21']=df['close'].ewm(span=21, adjust=False).mean()
    df['ema50']=df['close'].ewm(span=50, adjust=False).mean()
    e12=df['close'].ewm(span=12, adjust=False).mean(); e26=df['close'].ewm(span=26, adjust=False).mean()
    df['macd']=e12-e26; df['macd_sig']=df['macd'].ewm(span=9, adjust=False).mean()
    d=df['close'].diff(); gain=d.clip(lower=0).ewm(alpha=1/14, adjust=False).mean(); loss=-d.clip(upper=0).ewm(alpha=1/14, adjust=False).mean()
    df['rsi']=100-(100/(1+gain/loss.replace(0, np.nan)))
    df['vwap']=(df['close']*df['volume']).cumsum()/df['volume'].cumsum()
    last=df.iloc[-1]; prev=df.iloc[-2]
    news=get_news(cfg["news_q"]); n_score=news_sentiment(news)
    # AI CALL
    ai = ai_brain(df, inst)
    score=50; reasons=[]; confirm=0
    if last['ema9']>last['ema21']>last['ema50']: score+=15; confirm+=1; reasons.append("✅ EMA 9>21>50 - Pakka UPTREND")
    elif last['ema9']<last['ema21']<last['ema50']: score-=15; confirm+=1; reasons.append("✅ EMA 9<21<50 - Pakka DOWNTREND")
    else: reasons.append("❌ EMA Guntale - Sideways")
    if last['close']>last['vwap']: score+=10; reasons.append("✅ Price > VWAP")
    else: score-=10; reasons.append("❌ Price < VWAP")
    if last['macd']>last['macd_sig'] and prev['macd']>prev['macd_sig']: score+=10; confirm+=1; reasons.append("✅ MACD 2 Candle Bullish")
    elif last['macd']<last['macd_sig'] and prev['macd']<prev['macd_sig']: score-=10; confirm+=1; reasons.append("✅ MACD 2 Candle Bearish")
    else: reasons.append("❌ MACD Confused")
    if 52<last['rsi']<65: score+=10; reasons.append(f"✅ RSI {last['rsi']:.1f} - UP")
    elif 35<last['rsi']<48: score-=10; reasons.append(f"✅ RSI {last['rsi']:.1f} - DOWN")
    elif last['rsi']>=70 or last['rsi']<=30: reasons.append(f"🛑 RSI {last['rsi']:.1f} - Over - NO TRADE"); score=50
    else: reasons.append(f"⚠️ RSI {last['rsi']:.1f} - Madhe")
    avg_vol = df['volume'].tail(20).mean()
    if last['volume'] > avg_vol*1.2: score+=10; confirm+=1; reasons.append("✅ Volume HIGH - Confirm")
    else: reasons.append("❌ Volume KAMI - Fake asu shakto")
    if n_score>0: score+=5; reasons.append(f"✅ NEWS Bullish (+{n_score})")
    elif n_score<0: score-=5; reasons.append(f"❌ NEWS Bearish ({n_score})")
    else: reasons.append("➖ NEWS Neutral")
    # AI BONUS
    reasons.append(f"🤖 {ai['pattern']}")
    reasons.append(f"🤖 AI Prediction: Var {ai['ai_up']}% | Khali {ai['ai_down']}%")
    reasons.append(f"🤖 AI Salah: {ai['salah']}")
    reasons.append(f"🤖 Volatility: {ai['volatility']} | Risk: {ai['risk']}")
    reasons.append(f"📊 Data: {fut_sym} FUT varun")
    blocked=""
    if inst in ["NIFTY","BANKNIFTY"] and now_ist.hour==10 and now_ist.minute<15: blocked="⏰ AI: 10:15 aadhi NO TRADE - Sakalcha fake move"
    if inst=="CRUDEOIL MINI" and now_ist.hour==9 and now_ist.minute<30: blocked="⏰ 9:30 aadhi NO TRADE"
    if inst in ["NIFTY","BANKNIFTY"] and now_ist.hour==15: blocked="⏰ Market Off la 30 min baki - NO TRADE"
    if inst=="CRUDEOIL MINI" and now_ist.hour==23: blocked="⏰ Market Off javal - NO TRADE"
    # AI Risk Block - Fake move asel tar trade band
    if ai['risk']=="HIGH" and (ai['fake_up'] or ai['fake_down']):
        blocked="🛑 AI: FAKE MOVE - Trade Band"
    if blocked: final="WAIT"; reasons.append(f"🛑 {blocked}")
    elif score>=90 and confirm>=3 and ai['risk']!="HIGH": final="BUY"; reasons.append(f"🎯 {confirm}/3 FILTER + AI PASS - PAKKA BUY")
    elif score<=10 and confirm>=3 and ai['risk']!="HIGH": final="SELL"; reasons.append(f"🎯 {confirm}/3 FILTER + AI PASS - PAKKA SELL")
    else: final="WAIT"; reasons.append(f"⏳ Score {score} - 90 pahije - WAIT")
    try:
        if inst in ["NIFTY","BANKNIFTY"]:
            ltp = smart.ltpData(cfg["exchange"], cfg["sym"], cfg["token"])['data']['ltp']
        else:
            ltp = smart.ltpData(fut_exch, fut_sym, token)['data']['ltp']
    except: ltp = float(last['close'])
    return {"score":score,"final":final,"reasons":reasons,"news":news,"df":df,"last":last,"ltp":ltp,"sup":df['low'].tail(20).min(),"resi":df['high'].tail(20).max(),"instrument":inst,"confirm":confirm,"token":token,"sym_name":fut_sym,"fut_sym":fut_sym,"ai":ai}

def make_chart(df):
    fig = go.Figure()
    fig.add_trace(go.Candlestick(x=df['datetime'], open=df['open'], high=df['high'], low=df['low'], close=df['close'], increasing_line_color='#26A69A', increasing_fillcolor='#26A69A', decreasing_line_color='#EF5350', decreasing_fillcolor='#EF5350', name='Candles'))
    fig.add_trace(go.Scatter(x=df['datetime'], y=df['ema9'], line=dict(color='#FFD700', width=1.5), name='EMA 9'))
    fig.add_trace(go.Scatter(x=df['datetime'], y=df['ema21'], line=dict(color='#2962FF', width=1.5), name='EMA 21'))
    fig.add_trace(go.Scatter(x=df['datetime'], y=df['ema50'], line=dict(color='#FF6D00', width=1.2, dash='dash'), name='EMA 50'))
    fig.add_trace(go.Scatter(x=df['datetime'], y=df['vwap'], line=dict(color='white', width=1, dash='dot'), name='VWAP'))
    colors = ['#26A69A' if c >= o else '#EF5350' for c,o in zip(df['close'], df['open'])]
    fig.add_trace(go.Bar(x=df['datetime'], y=df['volume'], marker_color=colors, opacity=0.5, name='Volume', yaxis='y2'))
    fig.update_layout(template='plotly_dark', paper_bgcolor='#131722', plot_bgcolor='#131722', font=dict(color='white'), xaxis=dict(gridcolor='#1E222D', rangeslider=dict(visible=False)), yaxis=dict(gridcolor='#1E222D', side='right'), yaxis2=dict(overlaying='y', side='left', showgrid=False), height=380, margin=dict(l=0, r=50, t=10, b=0), legend=dict(orientation='h', y=1.02, x=0), hovermode='x unified')
    return fig

def get_atm_option(smart, inst, signal, ltp):
    try:
        cfg = CONFIG[inst]; atm = round(ltp / cfg["strike_step"]) * cfg["strike_step"]
        otype = "CE" if signal=="BUY" else "PE"
        time.sleep(0.2); res = smart.searchScrip(cfg["opt_exchange"], cfg["prefix"])
        data_list = res.get('data') or [] if isinstance(res, dict) else []
        cands=[]
        for item in data_list:
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
    except: return None,None,0

# --- MAIN ---
smart = get_connection()
if not smart:
    st.warning("⚠️ Login zala nahi - 'Navin Login Kar' dab"); st.stop()

if time.time() - st.session_state['last_study'] > 120 or not st.session_state['cached_all']:
    new_cache = {}
    with st.spinner("🤖 AI Study kartoy... 10 sec thamb"):
        for inst in INSTRUMENTS:
            try:
                fut_info = get_underlying(smart, inst)
                if not fut_info or not fut_info[0]: continue
                res = do_study(smart, inst, fut_info)
                if res: new_cache[inst] = res
            except: continue
    st.session_state['cached_all'] = new_cache; st.session_state['last_study'] = time.time()

all_data = st.session_state['cached_all']
if not all_data:
    st.error("❌ Data aala nahi - Angel Future Token / Internet check kar")
    if st.button("🔄 Parat Try Kar"): st.session_state['last_study']=0; st.rerun()
    st.stop()

st.info(f"📅 {now_ist.strftime('%d %b %Y, %A')} | 🕒 {now_ist.strftime('%H:%M:%S')} IST | 🤖 AI ON | Aajcha P&L ₹{st.session_state['day_pnl']}")

# AI TOP BOX
st.subheader("🤖 AI CHA AAJCHA SALLA")
for inst in INSTRUMENTS:
    d = all_data.get(inst)
    if d:
        ai = d['ai']
        if ai['risk']=="HIGH":
            st.error(f"**{inst}**: {ai['pattern']} | {ai['salah']}")
        elif d['final'] in ["BUY","SELL"]:
            st.success(f"**{inst}**: {ai['pattern']} | Var {ai['ai_up']}% | {ai['salah']}")
        else:
            st.warning(f"**{inst}**: {ai['pattern']} | Var {ai['ai_up']}% | {ai['salah']}")

c1,c2,c3 = st.columns(3)
for col, inst in zip([c1,c2,c3], INSTRUMENTS):
    with col:
        d = all_data.get(inst)
        if d:
            ai = d['ai']
            emoji = "🟢" if d['final']=="BUY" else "🔴" if d['final']=="SELL" else "🟡"
            st.markdown(f"### {emoji} {inst}")
            st.metric(f"{inst} LIVE", f"₹{d['ltp']:.2f}", f"Score {d['score']}/100 - {d['final']}")
            st.write(f"🤖 AI: Var {ai['ai_up']}% | Khali {ai['ai_down']}% | Risk {ai['risk']}")
            st.write(f"RSI {d['last']['rsi']:.1f} | Sup ₹{d['sup']:.0f} | Res ₹{d['resi']:.0f}")
            st.write(f"FUT: {d.get('fut_sym','')}")
            st.progress(min(max(d['score'],0),100)/100)
            if d['final']=="BUY": st.success("🎯 PAKKA BUY")
            elif d['final']=="SELL": st.error("🎯 PAKKA SELL")
            else: st.warning("WAIT")
            if st.button(f"Trade Ghe - {inst}", key=f"btn_{inst}"): st.session_state['selected_trade'] = inst
        else: st.warning(f"{inst} - Data yetoy")
st.divider()

tab1, tab2, tab3 = st.tabs(["📈 NIFTY", "🏦 BANKNIFTY", "🛢️ CRUDEOIL MINI"])
for tab, inst in zip([tab1, tab2, tab3], INSTRUMENTS):
    with tab:
        d = all_data.get(inst)
        if not d: st.warning(f"{inst} - Data yet nahi"); continue
        st.subheader(f"{inst} - Score {d['score']} - {d['final']} - LIVE ₹{d['ltp']:.2f}")
        col1, col2 = st.columns(2)
        with col1:
            st.write("**🧠 AI + Reason:**")
            for r in d['reasons']: st.write(r)
        with col2:
            st.write("**📰 NEWS:**")
            for n in d['news']: st.write(f"- {n}")
        fig = make_chart(d['df'].tail(50)); st.plotly_chart(fig, use_container_width=True, key=f"chart_{inst}")

st.divider()
st.subheader("🏆 EQUITY SCANNER - AI SObat")
if st.button("🔍 EQUITY SCAN KAR - TOP 10 STOCKS", type="primary"):
    EQUITY_LIST = [("RELIANCE", "2885"), ("HDFCBANK", "1330"), ("ICICIBANK", "3045"), ("INFY", "1802"), ("TCS", "3046"), ("SBIN", "3047"), ("LT", "3007"), ("ITC", "1660"), ("AXISBANK", "5900"), ("BAJFINANCE", "317")]
    results = []; prog = st.progress(0)
    for i, (name, tok) in enumerate(EQUITY_LIST):
        try:
            prog.progress((i+1)/len(EQUITY_LIST))
            hist = safe_candle(smart, "NSE", tok)
            if not hist or 'data' not in hist or not hist['data']: continue
            df = pd.DataFrame(hist['data'], columns=['datetime','open','high','low','close','volume'])
            if len(df) < 30: continue
            df['ema9']=df['close'].ewm(span=9, adjust=False).mean(); df['ema21']=df['close'].ewm(span=21, adjust=False).mean()
            df['vwap']=(df['close']*df['volume']).cumsum()/df['volume'].cumsum()
            d=df['close'].diff(); gain=d.clip(lower=0).ewm(alpha=1/14, adjust=False).mean(); loss=-d.clip(upper=0).ewm(alpha=1/14, adjust=False).mean()
            rsi=100-(100/(1+gain/loss.replace(0, np.nan))); last=df.iloc[-1]; avg_vol=df['volume'].tail(20).mean()
            score=50
            if last['ema9']>last['ema21']: score+=15
            else: score-=15
            if last['close']>last['vwap']: score+=15
            else: score-=15
            if 52<rsi.iloc[-1]<68: score+=10
            elif rsi.iloc[-1]>=70: score=50
            if last['volume']>avg_vol*1.3: score+=15
            resi = df['high'].tail(20).max(); sup = df['low'].tail(20).min()
            breakout = "🚀 BREAKOUT" if last['close'] > resi*0.998 else "➖ Range madhe" if last['close']>sup else "⚠️ BREAKDOWN"
            if last['close'] > resi*0.998: score+=10
            profit_pct = ((resi - last['close'])/last['close']*100) if last['close']<resi else ((last['close']-sup)/last['close']*100)
            try: ltp = smart.ltpData("NSE", name, tok)['data']['ltp']
            except: ltp = float(last['close'])
            results.append({"Stock": name, "LTP": round(float(ltp),2), "Score": score, "RSI": round(float(rsi.iloc[-1]),1), "Signal": "🟢 BUY" if score>=75 else "🔴 SELL" if score<=25 else "🟡 WAIT", "Breakout": breakout, "Support": round(float(sup),2), "Resistance": round(float(resi),2), "Profit Chance": f"{profit_pct:.2f}%"})
        except: continue
    st.session_state['eq_df'] = pd.DataFrame(results) if results else None

if st.session_state['eq_df'] is not None and not st.session_state['eq_df'].empty:
    eq_df = st.session_state['eq_df'].sort_values("Score", ascending=False)
    st.success("🏆 **TOP 3:**")
    top3 = eq_df.head(3); tc1, tc2, tc3 = st.columns(3)
    for col, (_, row) in zip([tc1, tc2, tc3], top3.iterrows()):
        with col:
            st.markdown(f"### {row['Stock']}"); st.metric(f"{row['Stock']} - ₹{row['LTP']}", f"Score {row['Score']}", row['Signal'])
            st.write(f"{row['Breakout']} | RSI {row['RSI']}"); st.write(f"Sup ₹{row['Support']} | Res ₹{row['Resistance']} | Profit {row['Profit Chance']}")
    st.dataframe(eq_df, use_container_width=True, hide_index=True)

st.divider()
st.subheader("🚀 TRADE - AI Sallah Baghun Ghe")
sel = st.session_state.get('selected_trade')
if sel and sel in INSTRUMENTS:
    st.info(f"Nivadla: {sel} - {all_data[sel]['final'] if sel in all_data else ''}")
else:
    sel = st.selectbox("Konatya var Trade ghyaycha?", INSTRUMENTS)
if sel in all_data:
    d = all_data[sel]; cfg = CONFIG[sel]; sig = d['final']; ai = d['ai']
    st.info(f"🤖 AI: {ai['pattern']} | {ai['salah']} | Var {ai['ai_up']}%")
    if sig == "WAIT":
        st.warning(f"🟡 {sel} WAIT aahe - AI mhanatoy trade nako.")
        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("⬆️ Tari pan BUY CALL ghe", use_container_width=True): sig="BUY"
        with col_b:
            if st.button("⬇️ Tari pan BUY PUT ghe", use_container_width=True): sig="SELL"
    else:
        st.success(f"🎯 {sel} la {sig} - Score {d['score']}")
    if sig != "WAIT":
        if st.button(f"🚀 TRADE GHE - {sel} - {sig}", type="primary"):
            if st.session_state['trades']>=MAX_TRADES: st.warning("Max Trades zale!")
            else:
                live_ltp = d['ltp']; sym,tok,atm=get_atm_option(smart, sel, sig, live_ltp)
                if tok:
                    opt_ltp=smart.ltpData(cfg["opt_exchange"], sym, tok)['data']['ltp']
                    st.info(f"Option: {sym} | ATM {atm} | Premium ₹{opt_ltp} | Qty {cfg['qty']} | SL {SL_POINTS} | Target {TARGET_POINTS}")
                    if not LIVE_MODE: st.warning(f"PAPER ORDER: {sig} {sym} @ ₹{opt_ltp}")
                    else:
                        oid=smart.placeOrder({"variety":"NORMAL","tradingsymbol":sym,"symboltoken":tok,"transactiontype":"BUY","exchange":cfg["opt_exchange"],"ordertype":"MARKET","producttype":"INTRADAY","duration":"DAY","price":"0","squareoff":str(int(TARGET_POINTS*100)),"stoploss":str(int(SL_POINTS*100)),"quantity":str(cfg['qty'])})
                        st.success(f"✅ LIVE ORDER GELI! {oid}"); st.session_state['trades']+=1
                else: st.error("Option sapadla nahi")
if st.button("📊 Live Positions Bagha"):
    pos=smart.position()
    if pos['data']: st.dataframe(pd.DataFrame(pos['data']))
    else: st.write("Kutlihi Position nahi")
if st.button("🔄 AI Study Aatach Parat Kar"):
    st.session_state['last_study']=0; st.rerun()
