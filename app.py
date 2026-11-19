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

st.set_page_config(page_title="SAGAR AI PRO - ALL IN ONE", layout="wide")
st.title("🎯 SAGAR AI PRO - NIFTY | BANKNIFTY | CRUDE | EQUITY - EKA PAGE VAR")

CONFIG = {
    "NIFTY": {"exchange": "NSE", "strike_step": 50, "qty": 25, "opt_exchange": "NFO", "prefix": "NIFTY", "news_q": "Nifty 50 stock market India", "token": "26000", "sym": "NIFTY"},
    "BANKNIFTY": {"exchange": "NSE", "strike_step": 100, "qty": 15, "opt_exchange": "NFO", "prefix": "BANKNIFTY", "news_q": "Bank Nifty today HDFC ICICI", "token": "26009", "sym": "BANKNIFTY"},
    "CRUDEOIL MINI": {"exchange": "MCX", "strike_step": 50, "qty": 10, "opt_exchange": "MCX", "prefix": "CRUDEOILM", "news_q": "Crude Oil price OPEC", "token": None, "sym": None},
}
INSTRUMENTS = ["NIFTY", "BANKNIFTY", "CRUDEOIL MINI"]

st.sidebar.header("🎯 ACCURACY MODE")
st.sidebar.success("FAKT PAKKE TRADE - Score 85+")
LIVE_MODE = st.sidebar.toggle("🔴 LIVE TRADING ON", value=False)
SL_POINTS = st.sidebar.number_input("SL Points", value=30)
TARGET_POINTS = st.sidebar.number_input("Target Points", value=60)
MAX_TRADES = st.sidebar.number_input("Max Trades / Day", value=1)
if 'trades' not in st.session_state: st.session_state['trades'] = 0
if 'killed' not in st.session_state: st.session_state['killed'] = False
if 'cached_all' not in st.session_state: st.session_state['cached_all'] = {}
if 'last_study' not in st.session_state: st.session_state['last_study'] = 0
if 'selected_trade' not in st.session_state: st.session_state['selected_trade'] = None
if 'watchlist' not in st.session_state: st.session_state['watchlist'] = []
if 'smart_obj' not in st.session_state: st.session_state['smart_obj'] = None
if 'login_time' not in st.session_state: st.session_state['login_time'] = 0
if st.sidebar.button("🛑 KILL SWITCH"): st.session_state['killed'] = True
if st.session_state['killed']:
    st.error("KILL SWITCH ON"); st.stop()
if st.sidebar.button("🔄 Navin Login Kar (Token Expire zala tar)"):
    st.session_state['smart_obj'] = None
    st.session_state['login_time'] = 0
    st.session_state['cached_all'] = {}
    st.session_state['last_study'] = 0
    st.rerun()

now_ist = datetime.now(timezone(timedelta(hours=5, minutes=30)))

# ===== FIX: CACHE NAKO - PRATYEK VELI NAVIN LOGIN / 30 MIN NANTAR PARAT LOGIN =====
def get_connection():
    # Jar login 30 min peksha juna asel tar parat login kar - nahi tar Invalid Token yeto
    if st.session_state['smart_obj'] is not None and (time.time() - st.session_state['login_time'] < 1800):
        return st.session_state['smart_obj']
    try:
        smart = SmartConnect(api_key=st.secrets["ANGEL_API_KEY"])
        totp = pyotp.TOTP(st.secrets["ANGEL_TOTP"]).now()
        data = smart.generateSession(st.secrets["ANGEL_CLIENT_ID"], st.secrets["ANGEL_PIN"], totp)
        if data.get('status'):
            st.session_state['smart_obj'] = smart
            st.session_state['login_time'] = time.time()
            return smart
        else:
            st.error(f"Login Fail: {data}")
            return None
    except Exception as e:
        st.error(f"Login Error: {e}")
        return None

def get_underlying(smart, inst):
    cfg = CONFIG[inst]
    if cfg["token"]:
        return cfg["token"], cfg["sym"]
    try:
        res = smart.searchScrip(cfg["exchange"], "CRUDEOIL")
        if not res or not isinstance(res, dict):
            return None, None
        data_list = res.get('data') or []
        if not data_list:
            return None, None
        best, best_days, best_sym = None, 9999, ""
        for item in data_list:
            sym = item.get('tradingsymbol','')
            if 'FUT' not in sym: continue
            if 'MINI' in sym or sym.startswith("CRUDEOILM"): continue
            m = re.search(r'(\d{2}[A-Z]{3}\d{2})', sym)
            if not m: continue
            try:
                exp = datetime.strptime(m.group(1), "%d%b%y")
            except:
                continue
            days = (exp - now_ist.replace(tzinfo=None)).days
            if 0 <= days < best_days and days < 60:
                best_days, best, best_sym = days, item.get('symboltoken'), sym
        return best, best_sym
    except:
        return None, None

def get_news(query):
    try:
        url = f"https://news.google.com/rss/search?q={query}&hl=en-IN&gl=IN&ceid=IN:en"
        r = requests.get(url, timeout=3)
        root = ET.fromstring(r.content)
        return [item.find("title").text for item in root.findall(".//item")[:3]]
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

def do_study(smart, inst, token):
    cfg = CONFIG[inst]
    to_date = datetime.now(); from_date = to_date - timedelta(days=2)
    try:
        hist = smart.getCandleData({"exchange": cfg["exchange"], "symboltoken": token, "interval": "FIFTEEN_MINUTE", "fromdate": from_date.strftime("%Y-%m-%d %H:%M"), "todate": to_date.strftime("%Y-%m-%d %H:%M")})
    except Exception as e:
        st.warning(f"{inst} Candle Error: {e}")
        return None
    if not hist or 'data' not in hist or not hist['data']:
        # Invalid Token aala tar login parat karayla sang
        if hist and 'Invalid Token' in str(hist):
            st.error(f"⚠️ {inst} - Token Expire zala! Sidebar madhe 'Navin Login Kar' dab.")
            st.session_state['smart_obj'] = None
        else:
            st.warning(f"{inst} - Angel ne data dila nahi: {hist}")
        return None
    df = pd.DataFrame(hist['data'], columns=['datetime','open','high','low','close','volume'])
    if len(df) < 20:
        st.warning(f"{inst} - Fakt {len(df)} candle aale, 20 pahije")
        return None
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
    blocked=""
    if inst in ["NIFTY","BANKNIFTY"] and now_ist.hour==9 and now_ist.minute<45: blocked="⏰ 9:45 aadhi NO TRADE"
    if inst=="CRUDEOIL MINI" and now_ist.hour==9 and now_ist.minute<30: blocked="⏰ 9:30 aadhi NO TRADE"
    if inst in ["NIFTY","BANKNIFTY"] and now_ist.hour==15 and now_ist.minute>=0: blocked="⏰ Market Off la 30 min baki - NO TRADE"
    if inst=="CRUDEOIL MINI" and now_ist.hour==23 and now_ist.minute>=0: blocked="⏰ Market Off javal - NO TRADE"
    if blocked: final="WAIT"; reasons.append(f"🛑 {blocked}")
    elif score>=85 and confirm>=3: final="BUY"; reasons.append(f"🎯 {confirm}/3 FILTER PASS - PAKKA BUY")
    elif score<=15 and confirm>=3: final="SELL"; reasons.append(f"🎯 {confirm}/3 FILTER PASS - PAKKA SELL")
    else: final="WAIT"; reasons.append(f"⏳ Score {score} - 85 pahije - WAIT")
    try:
        if inst == "CRUDEOIL MINI":
            _, sym_name = get_underlying(smart, inst)
            ltp = smart.ltpData(cfg["exchange"], sym_name, token)['data']['ltp']
        else:
            ltp = smart.ltpData(cfg["exchange"], CONFIG[inst]["sym"], token)['data']['ltp']
    except: ltp = float(last['close'])
    try:
        _, sym_name2 = get_underlying(smart, inst) if inst=="CRUDEOIL MINI" else (None, CONFIG[inst]["sym"])
    except:
        sym_name2 = CONFIG[inst]["sym"] if inst!="CRUDEOIL MINI" else ""
    return {"score":score,"final":final,"reasons":reasons,"news":news,"df":df,"last":last,"ltp":ltp,"sup":df['low'].tail(20).min(),"resi":df['high'].tail(20).max(),"instrument":inst,"confirm":confirm,"token":token,"sym_name":sym_name2}

def make_chart(df):
    fig = go.Figure()
    fig.add_trace(go.Candlestick(x=df['datetime'], open=df['open'], high=df['high'], low=df['low'], close=df['close'], increasing_line_color='#26A69A', increasing_fillcolor='#26A69A', decreasing_line_color='#EF5350', decreasing_fillcolor='#EF5350', name='Candles'))
    fig.add_trace(go.Scatter(x=df['datetime'], y=df['ema9'], line=dict(color='#FFD700', width=1.5), name='EMA 9'))
    fig.add_trace(go.Scatter(x=df['datetime'], y=df['ema21'], line=dict(color='#2962FF', width=1.5), name='EMA 21'))
    fig.add_trace(go.Scatter(x=df['datetime'], y=df['ema50'], line=dict(color='#FF6D00', width=1.2, dash='dash'), name='EMA 50'))
    fig.add_trace(go.Scatter(x=df['datetime'], y=df['vwap'], line=dict(color='white', width=1, dash='dot'), name='VWAP'))
    colors = ['#26A69A' if c >= o else '#EF5350' for c,o in zip(df['close'], df['open'])]
    fig.add_trace(go.Bar(x=df['datetime'], y=df['volume'], marker_color=colors, opacity=0.5, name='Volume', yaxis='y2'))
    fig.update_layout(template='plotly_dark', paper_bgcolor='#131722', plot_bgcolor='#131722', font=dict(color='white'), xaxis=dict(gridcolor='#1E222D', rangeslider=dict(visible=False)), yaxis=dict(gridcolor='#1E222D', side='right'), yaxis2=dict(overlaying='y', side='left', showgrid=False), height=420, margin=dict(l=0, r=50, t=10, b=0), legend=dict(orientation='h', y=1.02, x=0), hovermode='x unified')
    return fig

def get_atm_option(smart, inst, signal, ltp):
    try:
        cfg = CONFIG[inst]
        atm = round(ltp / cfg["strike_step"]) * cfg["strike_step"]
        otype = "CE" if signal=="BUY" else "PE"
        res = smart.searchScrip(cfg["opt_exchange"], cfg["prefix"])
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
    except:
        return None,None,0

# --- MAIN ---
smart = get_connection()
if not smart:
    st.error("Login Fail - API Key / TOTP / PIN check kar"); st.stop()
if time.time() - st.session_state['last_study'] > 30 or not st.session_state['cached_all']:
    new_cache = {}
    for inst in INSTRUMENTS:
        try:
            tok, sym = get_underlying(smart, inst)
            if not tok:
                st.warning(f"{inst} - Token milala nahi (CRUDE search fail asel)")
                continue
            res = do_study(smart, inst, tok)
            if res: new_cache[inst] = res
        except Exception as e:
            st.warning(f"{inst} skip: {e}")
            continue
    st.session_state['cached_all'] = new_cache
    st.session_state['last_study'] = time.time()
all_data = st.session_state['cached_all']
st.info(f"📅 {now_ist.strftime('%d %b %Y, %A')} | 🕒 {now_ist.strftime('%H:%M:%S')} IST | 🎯 ACCURACY MODE | 30 sec la update")

# ===== TOP DASHBOARD =====
c1,c2,c3 = st.columns(3)
for col, inst in zip([c1,c2,c3], INSTRUMENTS):
    with col:
        d = all_data.get(inst)
        if d:
            emoji = "🟢" if d['final']=="BUY" else "🔴" if d['final']=="SELL" else "🟡"
            st.markdown(f"### {emoji} {inst}")
            st.metric(f"{inst} LIVE", f"₹{d['ltp']:.2f}", f"Score {d['score']}/100 - {d['final']}")
            st.write(f"RSI {d['last']['rsi']:.1f} | Sup ₹{d['sup']:.0f} | Res ₹{d['resi']:.0f}")
            st.progress(min(max(d['score'],0),100)/100)
            if d['final']=="BUY": st.success("🎯 PAKKA BUY")
            elif d['final']=="SELL": st.error("🎯 PAKKA SELL")
            else: st.warning("WAIT")
            if st.button(f"Trade Ghe - {inst}", key=f"btn_{inst}"):
                st.session_state['selected_trade'] = inst
        else:
            st.warning(f"{inst} - Data yetoy / Market Band / Thodya velane yeil")
st.divider()

# ===== TABS - INDEX =====
tab1, tab2, tab3 = st.tabs(["📈 NIFTY", "🏦 BANKNIFTY", "🛢️ CRUDEOIL MINI"])
for tab, inst in zip([tab1, tab2, tab3], INSTRUMENTS):
    with tab:
        d = all_data.get(inst)
        if not d:
            st.warning(f"{inst} - Market Band aahe / Data yet nahi / Search fail - Thodya velane parat yeil."); continue
        st.subheader(f"{inst} - Score {d['score']} - {d['final']} - LIVE ₹{d['ltp']:.2f}")
        col1, col2 = st.columns(2)
        with col1:
            st.write("**🧠 AI Reason:**")
            for r in d['reasons']: st.write(r)
        with col2:
            st.write("**📰 NEWS:**")
            for n in d['news']: st.write(f"- {n}")
            if inst in ["NIFTY","BANKNIFTY"]:
                close_t = now_ist.replace(hour=15, minute=30, second=0); open_t = now_ist.replace(hour=9, minute=15, second=0)
            else:
                close_t = now_ist.replace(hour=23, minute=30, second=0); open_t = now_ist.replace(hour=9, minute=0, second=0)
            if now_ist < open_t: st.warning(f"🔴 Ajun ughadla nahi - {open_t.strftime('%I:%M %p')} - Pan kalcha chart khali disel")
            elif now_ist > close_t: st.error(f"🔴 BAND zala")
            else:
                left = (close_t - now_ist).total_seconds()/60
                st.success(f"🟢 CHALU - Band hoyla {int(left//60)} taas {int(left%60)} min baki")
                st.progress(int(((now_ist-open_t).total_seconds()/(close_t-open_t).total_seconds())*100)/100)
        fig = make_chart(d['df'].tail(60))
        st.plotly_chart(fig, use_container_width=True, key=f"chart_{inst}")
        last20 = d['df'].tail(20)
        avg_vol = last20['volume'].mean(); curr_vol = last20['volume'].iloc[-1]
        st.write(f"**👥 Crowd:** Volume {int(curr_vol):,} | Avg {int(avg_vol):,} | {'🔥 Lok aale' if curr_vol>avg_vol else '📉 Lok kami'}")
        fig_c = go.Figure()
        fig_c.add_trace(go.Bar(x=last20['datetime'], y=last20['volume'], marker_color=['#26A69A' if c>=o else '#EF5350' for c,o in zip(last20['close'], last20['open'])]))
        fig_c.update_layout(template='plotly_dark', paper_bgcolor='#131722', plot_bgcolor='#131722', title='Crowd - Bar unch = Lok jasta', height=200, margin=dict(l=0,r=10,t=30,b=0))
        st.plotly_chart(fig_c, use_container_width=True, key=f"crowd_{inst}")

# ===== EQUITY SCANNER =====
st.divider()
st.subheader("🏆 EQUITY SCANNER - PURN MARKET MADHUN KONTA VADHANAR?")
st.caption("NIFTY 50 madhle 20 mothe stocks scan kartoy - Konta vadhanar, tyat profit aahe ka?")

EQUITY_LIST = [
    ("RELIANCE", "2885"), ("HDFCBANK", "1330"), ("ICICIBANK", "3045"), ("INFY", "1802"),
    ("TCS", "3046"), ("SBIN", "3047"), ("TATAMOTORS", "3048"), ("TATASTEEL", "3049"),
    ("LT", "3007"), ("TITAN", "3050"), ("ADANIENT", "6401"), ("ITC", "1660"),
    ("HINDUNILVR", "1394"), ("AXISBANK", "5900"), ("KOTAKBANK", "1929"),
    ("BAJFINANCE", "317"), ("MARUTI", "10999"), ("SUNPHARMA", "3351"),
    ("ONGC", "2475"), ("NTPC", "11630"),
]

def scan_equity():
    results = []
    for name, tok in EQUITY_LIST:
        try:
            hist = smart.getCandleData({"exchange": "NSE", "symboltoken": tok, "interval": "FIFTEEN_MINUTE", "fromdate": (datetime.now()-timedelta(days=2)).strftime("%Y-%m-%d %H:%M"), "todate": datetime.now().strftime("%Y-%m-%d %H:%M")})
            if not hist or 'data' not in hist or not hist['data']: continue
            df = pd.DataFrame(hist['data'], columns=['datetime','open','high','low','close','volume'])
            if len(df) < 30: continue
            df['ema9']=df['close'].ewm(span=9, adjust=False).mean()
            df['ema21']=df['close'].ewm(span=21, adjust=False).mean()
            df['vwap']=(df['close']*df['volume']).cumsum()/df['volume'].cumsum()
            d=df['close'].diff(); gain=d.clip(lower=0).ewm(alpha=1/14, adjust=False).mean(); loss=-d.clip(upper=0).ewm(alpha=1/14, adjust=False).mean()
            rsi=100-(100/(1+gain/loss.replace(0, np.nan)))
            last=df.iloc[-1]
            avg_vol=df['volume'].tail(20).mean()
            score=50
            if last['ema9']>last['ema21']: score+=15
            else: score-=15
            if last['close']>last['vwap']: score+=15
            else: score-=15
            if 52<rsi.iloc[-1]<68: score+=10
            elif rsi.iloc[-1]>=70: score=50
            if last['volume']>avg_vol*1.3: score+=15
            resi = df['high'].tail(20).max()
            sup = df['low'].tail(20).min()
            breakout = "🚀 BREAKOUT" if last['close'] > resi*0.998 else "➖ Range madhe" if last['close']>sup else "⚠️ BREAKDOWN"
            if last['close'] > resi*0.998: score+=10
            profit_pct = ((resi - last['close'])/last['close']*100) if last['close']<resi else ((last['close']-sup)/last['close']*100)
            try: ltp = smart.ltpData("NSE", name, tok)['data']['ltp']
            except: ltp = float(last['close'])
            results.append({"Stock": name, "LTP": round(float(ltp),2), "Score": score, "RSI": round(float(rsi.iloc[-1]),1), "Signal": "🟢 BUY" if score>=75 else "🔴 SELL" if score<=25 else "🟡 WAIT", "Breakout": breakout, "Support": round(float(sup),2), "Resistance": round(float(resi),2), "Volume": f"{int(last['volume']):,}", "Profit Chance": f"{profit_pct:.2f}%"})
        except: continue
    return pd.DataFrame(results)

with st.spinner("Purn market scan kartoy... 20 stocks..."):
    eq_df = scan_equity()

if not eq_df.empty:
    eq_df = eq_df.sort_values("Score", ascending=False)
    st.success("🏆 **TOP 3 - AATA VADHANAR VATNARI STOCKS:**")
    top3 = eq_df.head(3)
    tc1, tc2, tc3 = st.columns(3)
    for col, (_, row) in zip([tc1, tc2, tc3], top3.iterrows()):
        with col:
            st.markdown(f"### {row['Stock']}")
            st.metric(f"{row['Stock']} - ₹{row['LTP']}", f"Score {row['Score']}", row['Signal'])
            st.write(f"{row['Breakout']} | RSI {row['RSI']}")
            st.write(f"Sup ₹{row['Support']} | Res ₹{row['Resistance']}")
            st.write(f"Profit Chance: {row['Profit Chance']}")
            if st.button(f"👁️ Laksh Thev - {row['Stock']}", key=f"watch_{row['Stock']}"):
                if row['Stock'] not in st.session_state['watchlist']:
                    st.session_state['watchlist'].append(row['Stock'])
                st.success(f"✅ {row['Stock']} var laksh thevlay!")
    if st.session_state['watchlist']:
        st.info(f"👁️ Tuza Watchlist: {', '.join(st.session_state['watchlist'])} - Hya var AI laksh thevtoy")
    st.divider()
    st.write("**📊 SAGLE 20 STOCKS - SCORE NUSAR:**")
    st.dataframe(eq_df, use_container_width=True, hide_index=True)
    best = eq_df.iloc[0]
    if best['Score'] >= 75:
        st.success(f"🎯 **AAJCHA BEST EQUITY TRADE: {best['Stock']} @ ₹{best['LTP']} - Score {best['Score']} - {best['Breakout']} - Target ₹{best['Resistance']} - Profit Chance {best['Profit Chance']}**")
        st.info(f"Strategy: {best['Stock']} Resistance ₹{best['Resistance']} chya var gela ki BUY kar, SL Support ₹{best['Support']} thev.")
    else:
        st.warning(f"🟡 Aata konatahi Equity stock pakka nahi - Best pan {best['Stock']} Score {best['Score']} aahe. Thamb, 75 yeu de.")
else:
    st.write("Equity scan hotoy... Market band asel tar thamb. - Angel ne data dila nahi tar 9:15 la parat yeil.")

# ===== TRADE BOX =====
st.divider()
st.subheader("🚀 TRADE - Khali nivad")
sel = st.session_state.get('selected_trade')
if sel and sel in INSTRUMENTS:
    st.info(f"Nivadla: {sel} - {all_data[sel]['final'] if sel in all_data else ''}")
else:
    sel = st.selectbox("Konatya var Trade ghyaycha?", INSTRUMENTS)
if sel in all_data:
    d = all_data[sel]
    cfg = CONFIG[sel]
    sig = d['final']
    if sig == "WAIT":
        st.warning(f"🟡 {sel} WAIT aahe - Accuracy Mode madhe trade nako. Dusra bagh - NIFTY / BANKNIFTY / CRUDE madhe konata PAKKA aahe ka?")
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
                live_ltp = d['ltp']
                sym,tok,atm=get_atm_option(smart, sel, sig, live_ltp)
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
if st.button("🔄 Saglyancha Study Aatach Parat Kar"):
    st.session_state['last_study']=0; st.rerun()
