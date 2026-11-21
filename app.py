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

st.set_page_config(page_title="SAGAR AI PRO - FINAL FIXED", layout="wide")
st.title("🤖 SAGAR AI PRO - PRE-MARKET + KA PADTOY + KA VADHTOY + INVESTMENT + COURT + GOVT + QUIZ + BHAVISHYA + ASK AI - FIXED")

CONFIG = {
    "NIFTY": {"exchange": "NSE", "strike_step": 50, "qty": 25, "opt_exchange": "NFO", "prefix": "NIFTY", "news_q": "Nifty 50 stock market India", "token": "26000", "sym": "NIFTY", "fut_exchange": "NFO", "fut_search": "NIFTY"},
    "BANKNIFTY": {"exchange": "NSE", "strike_step": 100, "qty": 15, "opt_exchange": "NFO", "prefix": "BANKNIFTY", "news_q": "Bank Nifty today HDFC ICICI", "token": "26009", "sym": "BANKNIFTY", "fut_exchange": "NFO", "fut_search": "BANKNIFTY"},
    "CRUDEOIL MINI": {"exchange": "MCX", "strike_step": 50, "qty": 10, "opt_exchange": "MCX", "prefix": "CRUDEOILM", "news_q": "Crude Oil price OPEC", "token": None, "sym": None, "fut_exchange": "MCX", "fut_search": "CRUDEOILM"},
}
INSTRUMENTS = ["NIFTY", "BANKNIFTY", "CRUDEOIL MINI"]
st.sidebar.header("🤖 SUPER AI CONTROL")
CAPITAL_MODE = st.sidebar.selectbox("Capital", ["₹10,000 - CRUDE MINI", "₹1 Lakh - FULL"])
IS_10K = "10,000" in CAPITAL_MODE
if IS_10K:
    SL_POINTS=8; TARGET_POINTS=12; MAX_TRADES=1; MAX_LOSS=800
    st.sidebar.info("🛢️ ₹10,000 MODE: SL 8 | Target 12 | Max Loss ₹800 | Fakt BUY")
else:
    SL_POINTS = st.sidebar.number_input("SL Points", value=30)
    TARGET_POINTS = st.sidebar.number_input("Target Points", value=60)
    MAX_TRADES = st.sidebar.number_input("Max Trades / Day", value=1)
    MAX_LOSS = st.sidebar.number_input("Max Loss / Day (Rs)", value=1000)
LIVE_MODE = st.sidebar.toggle("🔴 LIVE TRADING ON", value=False)
if LIVE_MODE: st.sidebar.warning("⚠️ LIVE ON AAHE - Khara paisa lagel!")
for k,v in [('trades',0),('killed',False),('cached_all',{}),('last_study',0),('selected_trade',None),('smart_obj',None),('login_time',0),('fut_cache',{}),('news_cache',{}),('day_pnl',0),('global_cache',{}),('global_time',0),('funds_cache',{}),('funds_time',0),('why_cache',{}),('why_time',0),('rise_cache',None),('rise_time',0),('pre_cache',None),('pre_time',0),('inv_cache',None),('inv_time',0),('court_cache',None),('court_time',0),('govt_cache',None),('govt_time',0),('quiz_answered',False),('quiz_selected',None)]:
    if k not in st.session_state: st.session_state[k]=v
if st.sidebar.button("🛑 KILL SWITCH"): st.session_state['killed']=True
if st.sidebar.button("✅ KILL OFF KAR"): st.session_state['killed']=False
if st.session_state['killed']:
    st.error("🛑 KILL SWITCH ON"); st.stop()
if st.sidebar.button("🔄 Navin Login Kar"):
    st.session_state['smart_obj']=None; st.session_state['login_time']=0; st.session_state['cached_all']={}; st.session_state['last_study']=0; st.session_state['fut_cache']={}; st.rerun()
if st.session_state['day_pnl'] <= -MAX_LOSS:
    st.error(f"🛑 AI RISK LOCK - Loss ₹{st.session_state['day_pnl']}"); st.stop()
if IS_10K and st.session_state['day_pnl'] >= 300:
    st.success(f"🎉 PROFIT ₹{st.session_state['day_pnl']} zala. AAJ BAS!"); st.stop()
now_ist = datetime.now(timezone(timedelta(hours=5, minutes=30)))
now_ist_naive = now_ist.replace(tzinfo=None)
now_hm = now_ist.hour*60 + now_ist.minute
is_pre_market = now_hm < 555
is_open = 555 <= now_hm <= 930
# FIX 3 - Pudcha Trading Divas - Saturday/Sunday skip
def next_trading_day(d):
    nd = d + timedelta(days=1)
    while nd.weekday() >= 5:
        nd += timedelta(days=1)
    return nd
missing = [k for k in ["ANGEL_API_KEY","ANGEL_TOTP","ANGEL_CLIENT_ID","ANGEL_PIN"] if k not in st.secrets]
if missing:
    st.error(f"❌ Secrets madhe he nahi: {', '.join(missing)}"); st.stop()
def get_connection():
    if st.session_state['smart_obj'] is not None and (time.time() - st.session_state['login_time'] < 1800):
        return st.session_state['smart_obj']
    try:
        smart = SmartConnect(api_key=st.secrets["ANGEL_API_KEY"])
        totp = pyotp.TOTP(st.secrets["ANGEL_TOTP"]).now()
        data = smart.generateSession(st.secrets["ANGEL_CLIENT_ID"], st.secrets["ANGEL_PIN"], totp)
        if data.get('status'):
            st.session_state['smart_obj']=smart; st.session_state['login_time']=time.time(); return smart
        else: st.error(f"Login Fail: {data.get('message', data)}"); return None
    except Exception as e: st.error(f"Login Error: {e}"); return None
def safe_candle(smart, exchange, token, interval="FIFTEEN_MINUTE", days=3):
    to_date = now_ist_naive; from_date = to_date - timedelta(days=days)
    for attempt in range(2):
        try:
            time.sleep(0.15)
            hist = smart.getCandleData({"exchange": exchange, "symboltoken": token, "interval": interval, "fromdate": from_date.strftime("%Y-%m-%d %H:%M"), "todate": to_date.strftime("%Y-%m-%d %H:%M")})
            if hist and hist.get('data'): return hist
            return hist
        except Exception as e:
            if "exceeding" in str(e) or "Access denied" in str(e): time.sleep(1.0); continue
            break
    return {"error": "No data"}
def get_underlying(smart, inst):
    if inst in st.session_state['fut_cache']: return st.session_state['fut_cache'][inst]
    cfg = CONFIG[inst]
    try:
        time.sleep(0.2); res = smart.searchScrip(cfg["fut_exchange"], cfg["fut_search"])
        if not res or not isinstance(res, dict): return None, None, None
        data_list = res.get('data') or []; best, best_days, best_sym = None, 9999, ""; best_exch = cfg["fut_exchange"]
        for item in data_list:
            sym = item.get('tradingsymbol','').strip()
            if inst == "NIFTY":
                if not re.match(r'^NIFTY\d{2}[A-Z]{3}\d{2}FUT$', sym): continue
            elif inst == "BANKNIFTY":
                if not re.match(r'^BANKNIFTY\d{2}[A-Z]{3}\d{2}FUT$', sym): continue
            elif inst == "CRUDEOIL MINI":
                if not re.match(r'^CRUDEOILM\d{2}[A-Z]{3}\d{2}FUT$', sym): continue
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
        r = requests.get(url, timeout=3); root = ET.fromstring(r.content)
        val = [item.find("title").text for item in root.findall(".//item")[:5]]
    except: val = []
    st.session_state['news_cache'][query] = (time.time(), val); return val
def news_sentiment(news_list):
    bull = ["rise","up","gain","surge","rally","high","bull","jump","positive","hike","strong","record","growth","buy","contract","order","wins","bags","award"]
    bear = ["fall","down","drop","decline","crash","low","bear","slump","negative","cut","weak","loss","sell","war","sanction","cancel","ban"]
    s=0
    for t in news_list:
        tl=t.lower()
        for w in bull:
            if w in tl: s+=1
        for w in bear:
            if w in tl: s-=1
    return s
def get_global_study():
    if time.time() - st.session_state['global_time'] < 300 and st.session_state['global_cache']:
        return st.session_state['global_cache']
    g={"wti":"-", "usdinr":"-", "bias":0, "text":"Global Neutral"}
    try:
        for sym, key in [("CL=F","wti"), ("USDINR=X","usdinr"), ("^GSPC","us_market")]:
            try:
                r=requests.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?interval=1d&range=2d", timeout=3, headers={"User-Agent":"Mozilla/5.0"})
                j=r.json(); closes=j['chart']['result'][0]['indicators']['quote'][0]['close']
                closes=[c for c in closes if c is not None]
                if len(closes)>=2:
                    chg=(closes[-1]-closes[-2])/closes[-2]*100
                    g[key]=f"{closes[-1]:.2f} ({chg:+.2f}%)"
                    if key=="wti": g['wti_chg']=chg
                    if key=="usdinr": g['usdinr_chg']=chg
                    if key=="us_market": g['us_chg']=chg
            except: pass
        bias=0; txt=[]
        if g.get('wti_chg',0) > 0.5: bias+=1; txt.append("WTI UP")
        elif g.get('wti_chg',0) < -0.5: bias-=1; txt.append("WTI DOWN")
        if g.get('us_chg',0) < -1: bias-=1; txt.append("US MARKET KHUP PADLA - Pan India vegla chalu shakto")
        elif g.get('us_chg',0) > 1: bias+=1; txt.append("US MARKET VADHLA")
        g['bias']=bias; g['text']=" | ".join(txt) if txt else "Global Neutral"
    except: pass
    st.session_state['global_cache']=g; st.session_state['global_time']=time.time()
    return g
def why_market_falling():
    if time.time() - st.session_state['why_time'] < 300 and st.session_state['why_cache']:
        return st.session_state['why_cache']
    SCAN_QUERIES = {"WAR": "war Israel Iran Russia Ukraine attack","FED": "US Fed interest rate Powell inflation","FII": "FII selling foreign investors India outflow","OIL": "OPEC crude oil price rise cut","CHINA": "China economy slowdown Taiwan","RESULT": "Nifty company quarterly results profit loss India","USD": "dollar rupee fall dollar index India","TRUMP": "Trump tariff trade war India"}
    reasons=[]; danger=0; all_news={}
    for key, q in SCAN_QUERIES.items():
        news = get_news(q); all_news[key]=news; s = news_sentiment(news)
        if s <= -2:
            danger+=1
            if key=="WAR": reasons.append("🪖 WAR / ATTACK - Market ghabartoy")
            elif key=="FED": reasons.append("🏦 US FED - Vyaj vadhavnar - US padla mhanun India padtoy")
            elif key=="FII": reasons.append("💸 FII VIKRI - Paradeshi paisa kadhun ghetayat")
            elif key=="OIL": reasons.append("🛢️ CRUDE VADHLA - India la nuksan")
            elif key=="CHINA": reasons.append("🇨🇳 CHINA - China padla")
            elif key=="RESULT": reasons.append("📉 RESULT KHARAB")
            elif key=="USD": reasons.append("💵 DOLLAR VADHLA - Rupee padla")
            elif key=="TRUMP": reasons.append("🇺🇸 TARIFF / TRADE WAR")
    glob = get_global_study()
    if danger >= 4: verdict=f"🚨 MARKET PADNYACHA KHARA KARAN - {danger} goshti bighadlya!"; action="🛑 AAJ TRADE NAKO"; trade_allow=False
    elif danger == 3: verdict=f"⚠️ 3 KARAN SAPADLE - Pan India Strong asel tar Trade karu shakta"; action="⚠️ SAVDHAN PAN TRADE CHALEL"; trade_allow=True
    elif danger == 2: verdict=f"⚠️ 2 KARAN SAPADLE"; action="⚠️ SAVDHAN"; trade_allow=True
    elif danger == 1: verdict=f"⚠️ 1 KARAN SAPADLA"; action="⚠️ SAVDHAN"; trade_allow=True
    else: verdict="✅ JAGAT KAHI BIGHADLE NAHI"; action="✅ GHABRU NAKA"; trade_allow=True
    out={"reasons":reasons,"danger":danger,"verdict":verdict,"action":action,"trade_allow":trade_allow,"all_news":all_news,"global":glob}
    st.session_state['why_cache']=out; st.session_state['why_time']=time.time(); return out
def why_market_rising():
    if time.time() - st.session_state['rise_time'] < 300 and st.session_state['rise_cache']:
        return st.session_state['rise_cache']
    SCAN = {"FII BUY": "FII buying foreign investors India inflow","GOOD RESULT": "Nifty company quarterly results profit growth record India","GOVT CONTRACT": "government contract wins company order crore India","RBI": "RBI interest rate cut repo rate India","US UP": "US market rally Dow Jones Nasdaq up","OIL DOWN": "crude oil price fall down","GST / TAX": "GST cut tax relief government India","MONSOON": "monsoon good rain India agriculture"}
    reasons=[]; power=0; all_rise_news={}
    for key, q in SCAN.items():
        news = get_news(q); all_rise_news[key]=news; s = news_sentiment(news)
        if s >= 2:
            power+=1
            if key=="FII BUY": reasons.append("💰 FII GHETAYET - Paradeshi lok paisa takta yet - Market vadhnar")
            elif key=="GOOD RESULT": reasons.append("📈 RESULT CHANGLA - Mothya company cha profit vadhla - Market vadhnar")
            elif key=="GOVT CONTRACT": reasons.append("🏛️ GOVT CONTRACT MILALA - Company la motha kaam milala - Share vadhnar")
            elif key=="RBI": reasons.append("🏦 RBI NE VYAJ KAMI KELA - Loan swast - Market vadhnar")
            elif key=="US UP": reasons.append("🇺🇸 US MARKET VADHLA - Ratri US vadhla mhanun India vadhnar")
            elif key=="OIL DOWN": reasons.append("🛢️ CRUDE PADLA - Tel swast - India la fayda - Market vadhnar")
            elif key=="GST / TAX": reasons.append("💸 GST / TAX KAMI - Govt ne tax kami kela - Market vadhnar")
            elif key=="MONSOON": reasons.append("🌧️ MONSOON CHANGLA - Paus changla - Market vadhnar")
    if power >= 3: verdict=f"🚀 MARKET VADHNYACHA KHARA KARAN SAPADLA - {power} goshti changlya aahet!"; action="BUY"; salla="Aaj BUY CE ghe - Market var janar"
    elif power == 2: verdict=f"🟢 2 KARAN SAPADLE - Market var jaychi shakyata jast"; action="BUY"; salla="Thoda var jail - CE gheu shakta"
    elif power == 1: verdict=f"🟡 1 KARAN SAPADLA - Thoda var jail"; action="WAIT"; salla="Fakt 1 karan aahe - Motha move nahi yenar"
    else: verdict="➖ VADHNYACHA KONTAHI KARAN NAHI"; action="WAIT"; salla="Market vadhnar nahi - Sideways rahil"
    out={"reasons":reasons,"power":power,"verdict":verdict,"action":action,"salla":salla,"all_news":all_rise_news}
    st.session_state['rise_cache']=out; st.session_state['rise_time']=time.time(); return out
def investment_flow_study():
    if time.time() - st.session_state['inv_time'] < 300 and st.session_state['inv_cache']:
        return st.session_state['inv_cache']
    score=0; reasons=[]; hot_stocks=[]
    for q, label in [("FII DII buying selling yesterday NSE India","FII/DII"),("FII bought shares bulk deal today India","BULK DEAL"),("foreign investment India company stake buy","FOREIGN INVEST"),("mutual fund buying stocks India SIP","MF BUYING"),("promoter buying shares open market India","PROMOTER BUY")]:
        news = get_news(q); s = news_sentiment(news)
        if s >= 2:
            score+=2; reasons.append(f"💰 {label} - Paisa YETOY - {news[0] if news else ''}")
            for n in news[:2]:
                for comp in ["RELIANCE","HDFC","ICICI","INFY","TCS","ADANI","TATA","VEDANTA","VODAFONE","JIO","SBIN","ITC","LT","TITAN","HAL","BEL"]:
                    if comp in n.upper(): hot_stocks.append(f"{comp} - {n[:80]}")
        elif s <= -2: score-=2; reasons.append(f"💸 {label} - Paisa BAHER JATOY - {news[0] if news else ''}")
    for sec, q in [("DEFENCE","defence stocks order government India"),("PSU BANK","PSU bank profit government India"),("GREEN ENERGY","green energy solar investment India"),("IT","IT stocks US deal Infosys TCS India"),("PHARMA","pharma stocks USFDA approval India")]:
        news = get_news(q); s = news_sentiment(news)
        if s >= 2: reasons.append(f"🔥 {sec} SECTOR HOT - {news[0] if news else ''}"); hot_stocks.append(f"{sec} SECTOR - HOT")
        elif s <= -2: reasons.append(f"❄️ {sec} SECTOR COLD")
    if score >= 4: verdict="💰 PAISA YETOY - FII / MF / Promoter gheta yet - Market vadhnar"; action="BUY"
    elif score <= -4: verdict="💸 PAISA BAHER JATOY - FII vikta yet - Market padnar"; action="SELL"
    else: verdict="➖ PAISA NEUTRAL"; action="WAIT"
    out={"score":score,"verdict":verdict,"action":action,"reasons":reasons,"hot_stocks":list(set(hot_stocks))}
    st.session_state['inv_cache']=out; st.session_state['inv_time']=time.time(); return out
def court_verdict_study():
    if time.time() - st.session_state['court_time'] < 300 and st.session_state['court_cache']:
        return st.session_state['court_cache']
    danger=0; reasons=[]; affected=[]
    # FIX 1 - Fakt India cha Court - UK/US cha news nako - GOVT ORDER ani TAX kadhle
    SCAN = {"SUPREME COURT":"Supreme Court India verdict company shares","HIGH COURT":"High Court India order company stock","SEBI":"SEBI action fine company shares India","ADANI":"Adani court case verdict India","VODAFONE":"Vodafone Idea AGR court verdict India","VEDANTA":"Vedanta court case mining India"}
    for key, q in SCAN.items():
        news = get_news(q); s = news_sentiment(news)
        # Fakt India cha news ghe - UK / GOV.UK asel tar sodun de
        news_india = [n for n in news if "GOV.UK" not in n and "Atherton" not in n and "UK " not in n]
        if not news_india: continue
        if s <= -2: danger+=1; reasons.append(f"⚖️ {key} - COURT / SEBI NEGATIVE - {news_india[0] if news_india else ''}"); affected.append(f"{key} - NEGATIVE - {news_india[0][:100] if news_india else ''}")
        elif s >= 2: reasons.append(f"✅ {key} - COURT POSITIVE - {news_india[0] if news_india else ''}"); affected.append(f"{key} - POSITIVE - {news_india[0][:100] if news_india else ''}")
    if danger >= 2: verdict=f"🚨 COURT CHA MOTHHA NIKAL - {danger} company var parinam"; trade_allow=False
    elif danger == 1: verdict="⚠️ 1 COURT NIKAL AALA - Tya company pasun lamb raha - Pan NIFTY la farak nahi"; trade_allow=True
    else: verdict="✅ AAJ COURT CHA KONTAHI MOTHHA NIKAL NAHI - India Court Clear"; trade_allow=True
    out={"danger":danger,"verdict":verdict,"trade_allow":trade_allow,"reasons":reasons,"affected":affected}
    st.session_state['court_cache']=out; st.session_state['court_time']=time.time(); return out
def govt_contract_study():
    if time.time() - st.session_state['govt_time'] < 300 and st.session_state['govt_cache']:
        return st.session_state['govt_cache']
    score=0; reasons=[]; contract_stocks=[]
    SCAN = {"DEFENCE CONTRACT": "defence contract HAL BEL Mazagon government order India","RAILWAY CONTRACT": "railway contract RVNL IRCON L&T order wins India","ROAD CONTRACT": "NHAI road highway contract company wins order India","POWER CONTRACT": "power contract NTPC Power Grid solar order wins India","GOVT TENDER": "government tender wins company bags order crore India","MAKE IN INDIA": "Make in India government order defence India"}
    for key, q in SCAN.items():
        news = get_news(q); s = news_sentiment(news)
        if s >= 2:
            score+=2; reasons.append(f"🏛️ {key} - GOVT CONTRACT MILALA - {news[0] if news else ''}")
            for n in news[:3]:
                for comp in ["HAL","BEL","MAZAGON","L&T","RVNL","IRCON","NTPC","POWER GRID","BHEL","COCHIN","GRSE","BEML","NBCC","HUDCO","IRFC"]:
                    if comp in n.upper(): contract_stocks.append(f"{comp} - Govt Contract - {n[:90]}")
                if not any(c in n.upper() for c in ["HAL","BEL","MAZAGON","L&T","RVNL","IRCON","NTPC"]):
                    contract_stocks.append(f"{key} - {n[:90]}")
        elif s <= -2: score-=1; reasons.append(f"❌ {key} - CONTRACT CANCEL - {news[0] if news else ''}")
    if score >= 4: verdict="🏛️ GOVT CONTRACT FLOOD - Khup company la contract milale - Market vadhnar"; action="BUY"
    elif score >= 2: verdict="🏛️ 1-2 GOVT CONTRACT MILALE - Tya company cha share vadhnar"; action="BUY"
    elif score <= -2: verdict="❌ GOVT CONTRACT CANCEL - Tya company cha share padnar"; action="SELL"
    else: verdict="➖ AAJ KONALA MOTHHA GOVT CONTRACT NAHI"; action="WAIT"
    out={"score":score,"verdict":verdict,"action":action,"reasons":reasons,"contract_stocks":list(set(contract_stocks))}
    st.session_state['govt_cache']=out; st.session_state['govt_time']=time.time(); return out
def pre_market_study(why_data, rise_data):
    if time.time() - st.session_state['pre_time'] < 300 and st.session_state['pre_cache']:
        return st.session_state['pre_cache']
    score=50; reasons=[]; danger=0
    for sym, name in [("^GSPC","US S&P 500"), ("^IXIC","US Nasdaq"), ("^N225","Japan Nikkei"), ("^HSI","Hong Kong")]:
        try:
            r=requests.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?interval=1d&range=2d", timeout=4, headers={"User-Agent":"Mozilla/5.0"})
            j=r.json(); closes=j['chart']['result'][0]['indicators']['quote'][0]['close']; closes=[c for c in closes if c is not None]
            if len(closes)>=2:
                chg=(closes[-1]-closes[-2])/closes[-2]*100
                if name in ["US S&P 500","US Nasdaq"]:
                    # FIX 4 - US la kami vajan - India US peksha vegla chaltoy
                    if chg < -1: reasons.append(f"🇺🇸 {name} RATRI KHUP PADLA {chg:+.2f}% - Pan India vegla chalu shakto, FII bagh"); score-=5; danger+=1
                    elif chg < -0.3: reasons.append(f"🇺🇸 {name} Thoda padla {chg:+.2f}%"); score-=2
                    elif chg > 1: reasons.append(f"🇺🇸 {name} KHUP VADHLA {chg:+.2f}%"); score+=5
                    elif chg > 0.3: reasons.append(f"🇺🇸 {name} Thoda vadhla {chg:+.2f}%"); score+=2
                if name in ["Japan Nikkei","Hong Kong"]:
                    if chg < -1: reasons.append(f"🌏 {name} SAKALI PADLA {chg:+.2f}%"); score-=4; danger+=1
                    elif chg > 1: reasons.append(f"🌏 {name} SAKALI VADHLA {chg:+.2f}%"); score+=4
        except: pass
    for sym, name in [("CL=F","Crude Oil"), ("GC=F","Gold"), ("USDINR=X","USD/INR")]:
        try:
            r=requests.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?interval=1d&range=2d", timeout=3, headers={"User-Agent":"Mozilla/5.0"})
            j=r.json(); closes=j['chart']['result'][0]['indicators']['quote'][0]['close']; closes=[c for c in closes if c is not None]
            if len(closes)>=2:
                chg=(closes[-1]-closes[-2])/closes[-2]*100
                if name=="Crude Oil" and chg > 1.5: reasons.append(f"🛢️ CRUDE RATRI KHUP VADHLA {chg:+.2f}%"); score-=4; danger+=1
                elif name=="Crude Oil" and chg < -1.5: reasons.append(f"🛢️ CRUDE PADLA {chg:+.2f}%"); score+=4
                if name=="Gold" and chg > 1: reasons.append(f"🥇 GOLD VADHLA {chg:+.2f}%"); score-=2; danger+=1
                if name=="USD/INR" and chg > 0.3: reasons.append(f"💵 DOLLAR VADHLA {chg:+.2f}%"); score-=2
        except: pass
    if not why_data.get('trade_allow', True): danger+=2; reasons.append(f"🚨 RATRI BIGHADLAY - {why_data['verdict']}")
    else: reasons.append(f"✅ RATRI JAGAT KAHI BIGHADLE NAHI - Kinva India Strong Aahe")
    if rise_data and rise_data['power']>=3: score+=10; reasons.append(f"🚀 VADHNYACHA KARAN STRONG - {rise_data['verdict']}")
    elif rise_data and rise_data['power']>=2: score+=5; reasons.append(f"🟢 VADHNYACHA KARAN - {rise_data['verdict']}")
    if why_data.get('danger',0)>=4: score-=10
    score=max(5,min(95,score))
    if score >= 70: plan="🟢 AAJ VAR JANAR - 9:15 la BUY CE chi tayari kar"; action="BUY"; plan_detail="US + Asia + Crude + Ka Vadhtoy sagla changla. 9:15 la lagech BUY CE ghe."
    elif score <= 30: plan="🔴 AAJ KHALI JANAR - 9:15 la BUY PE chi tayari kar"; action="SELL"; plan_detail="US padla / War / Crude vadhla / Ka Padtoy strong. 9:15 la lagech BUY PE ghe."
    elif danger >= 3 and rise_data['power'] < 2: plan="🛑 AAJ TRADE NAKO - JAGAT BIGHADLAY"; action="WAIT"; plan_detail="Ratri 3+ goshti bighadlya ani Vadhtoy kamkuvat. 10:15 paryant vaat bagha."
    else: plan="🟡 AAJ SIDEWAYS / BREAKOUT - 9:15 la WAIT - Level todla ki ghe"; action="WAIT"; plan_detail="Vadhtoy = Padtoy - Donhi sarkhe. Var gela tar CE, Khali gela tar PE. Level todla ki ghe."
    out={"score":score,"plan":plan,"action":action,"plan_detail":plan_detail,"reasons":reasons,"danger":danger,"why":why_data,"rise":rise_data}
    st.session_state['pre_cache']=out; st.session_state['pre_time']=time.time(); return out
def get_funds_and_margin(smart):
    if time.time() - st.session_state['funds_time'] < 30 and st.session_state['funds_cache']:
        return st.session_state['funds_cache']
    try:
        f=smart.rmsLimit(); d=f.get('data', {}) if isinstance(f, dict) else {}
        avail=float(d.get('availablecash',0) or 0); used=float(d.get('utilisedmargin',0) or 0)
        if avail==0:
            try: avail=float(d.get('net',0) or 0)
            except: pass
        out=(avail,used,d); st.session_state['funds_cache']=out; st.session_state['funds_time']=time.time(); return out
    except: return 0,0,{}
def check_margin_before_trade(smart, inst, opt_ltp, is_sell=False):
    cfg=CONFIG[inst]
    need=(opt_ltp*cfg['qty']*3+500) if is_sell else (opt_ltp*cfg['qty']+100)
    avail, used, _ = get_funds_and_margin(smart)
    if avail < need: return False, f"❌ MARGIN KAMI! Pahije ₹{need:.0f} | Aahe ₹{avail:.0f}", avail, need
    return True, f"✅ MARGIN OK - Pahije ₹{need:.0f} | Aahe ₹{avail:.0f} | Urdla ₹{avail-need:.0f}", avail, need
def add_indicators(df):
    df=df.copy()
    df['ema9']=df['close'].ewm(span=9, adjust=False).mean(); df['ema21']=df['close'].ewm(span=21, adjust=False).mean(); df['ema50']=df['close'].ewm(span=50, adjust=False).mean()
    e12=df['close'].ewm(span=12, adjust=False).mean(); e26=df['close'].ewm(span=26, adjust=False).mean()
    df['macd']=e12-e26; df['macd_sig']=df['macd'].ewm(span=9, adjust=False).mean()
    d=df['close'].diff(); gain=d.clip(lower=0).ewm(alpha=1/14, adjust=False).mean(); loss=-d.clip(upper=0).ewm(alpha=1/14, adjust=False).mean()
    df['rsi']=100-(100/(1+gain/loss.replace(0, np.nan)))
    df['vwap']=(df['close']*df['volume']).cumsum()/df['volume'].cumsum()
    df['bb_mid']=df['close'].rolling(20).mean(); df['bb_std']=df['close'].rolling(20).std()
    df['bb_up']=df['bb_mid']+2*df['bb_std']; df['bb_low']=df['bb_mid']-2*df['bb_std']
    df['tr']=np.maximum(df['high']-df['low'], np.maximum(abs(df['high']-df['close'].shift(1)), abs(df['low']-df['close'].shift(1))))
    df['atr']=df['tr'].rolling(10).mean(); df['st_low']=(df['high']+df['low'])/2 - 2*df['atr']
    df['super_bull']=df['close'] > df['st_low']
    return df
def timeframe_signal(df):
    if df is None or len(df)<30: return 0, "No Data"
    last=df.iloc[-1]; s=0; why=[]
    if last['ema9']>last['ema21']>last['ema50']: s+=2; why.append("EMA UP")
    elif last['ema9']<last['ema21']<last['ema50']: s-=2; why.append("EMA DOWN")
    if last['close']>last['vwap']: s+=1; why.append("VWAP UP")
    else: s-=1; why.append("VWAP DOWN")
    if last['macd']>last['macd_sig']: s+=1; why.append("MACD UP")
    else: s-=1; why.append("MACD DOWN")
    if last['super_bull']: s+=1; why.append("Supertrend UP")
    else: s-=1; why.append("Supertrend DOWN")
    if last['close']>last['bb_up']: s-=1; why.append("Bollinger Over")
    elif last['close']<last['bb_low']: s+=1; why.append("Bollinger Oversold")
    if last['rsi']>=70: s-=1; why.append("RSI Over")
    elif last['rsi']<=30: s+=1; why.append("RSI Oversold")
    return s, ", ".join(why)
def super_ai_brain(df15, df5, df60, inst, news_score, global_data, why_data, rise_data, pre_data, inv_data, court_data, govt_data):
    s15, w15 = timeframe_signal(df15); s5, w5 = timeframe_signal(df5); s60, w60 = timeframe_signal(df60)
    total = s15*2 + s5*1 + s60*2 + news_score + (global_data.get('bias',0)*1 if inst=="CRUDEOIL MINI" else 0)
    if pre_data:
        if pre_data['action']=="BUY": total+=3
        elif pre_data['action']=="SELL": total-=3
    if inv_data:
        if inv_data['action']=="BUY": total+=3
        elif inv_data['action']=="SELL": total-=3
    if govt_data:
        if govt_data['action']=="BUY": total+=3
        elif govt_data['action']=="SELL": total-=3
    if rise_data and rise_data['power']>=3: total+=3
    elif rise_data and rise_data['power']>=2: total+=1
    # FIX 2 - BLOCK nako, fakt kami kar - India Strong asel tar Trade chalel
    if not why_data.get('trade_allow', True): total-=3
    if not court_data.get('trade_allow', True): total-=3
    signals=[np.sign(s15), np.sign(s5), np.sign(s60)]
    agree=len(set([x for x in signals if x!=0]))==1 if any(x!=0 for x in signals) else False
    ai_up=max(5,min(95,50+total*5))
    if total>=9 and agree and s15>0 and s60>0:
        final="BUY"; pattern="🚀 SUPER AI: 3 TIMEFRAME BUY"; salah="✅ PAKKA BUY"; risk="LOW"
    elif total<=-9 and agree and s15<0 and s60<0:
        final="SELL"; pattern="📉 SUPER AI: 3 TIMEFRAME SELL"; salah="✅ PAKKA SELL"; risk="LOW"
    elif not why_data.get('trade_allow', True) and rise_data and rise_data['power']>=3:
        final="BUY"; pattern="⚠️ JAGAT BIGHADLA PAN INDIA STRONG - BUY"; salah="✅ SAVDHAN PAN BUY"; risk="MEDIUM"
    elif not why_data.get('trade_allow', True) and court_data.get('danger',0)>=2:
        final="WAIT"; pattern="🚨 JAGAT + COURT DONHI BIGHADLE"; salah="🛑 TRADE NAKO"; risk="HIGH"
    elif not agree:
        final="WAIT"; pattern="⚠️ TIMEFRAME CONFUSED - Level todla ki ghe"; salah="🛑 THAMBA - Level bagh"; risk="MEDIUM"
    else:
        final="WAIT"; pattern="⏳ HALF SIGNAL - Level todla ki ghe"; salah="🛑 THAMBA - Level bagh"; risk="MEDIUM"
    return {"ai_up":ai_up,"ai_down":100-ai_up,"pattern":pattern,"salah":salah,"risk":risk,"s15":s15,"s5":s5,"s60":s60,"total":total,"agree":agree,"w15":w15,"w5":w5,"w60":w60,"final":final}
def do_study(smart, inst, fut_info, why_data, rise_data, pre_data, inv_data, court_data, govt_data):
    cfg=CONFIG[inst]; token, fut_sym, fut_exch = fut_info
    h15=safe_candle(smart, fut_exch, token, "FIFTEEN_MINUTE", 3)
    h5=safe_candle(smart, fut_exch, token, "FIVE_MINUTE", 2)
    h60=safe_candle(smart, fut_exch, token, "ONE_HOUR", 5)
    if not h15 or 'data' not in h15 or not h15['data']: return None
    df15=pd.DataFrame(h15['data'], columns=['datetime','open','high','low','close','volume']); df15['datetime']=pd.to_datetime(df15['datetime']); df15=add_indicators(df15)
    df5=None
    if h5 and 'data' in h5 and h5['data']:
        df5=pd.DataFrame(h5['data'], columns=['datetime','open','high','low','close','volume']); df5['datetime']=pd.to_datetime(df5['datetime']); df5=add_indicators(df5)
    df60=None
    if h60 and 'data' in h60 and h60['data']:
        df60=pd.DataFrame(h60['data'], columns=['datetime','open','high','low','close','volume']); df60['datetime']=pd.to_datetime(df60['datetime']); df60=add_indicators(df60)
    if df5 is None: df5=df15
    if df60 is None: df60=df15
    last=df15.iloc[-1]
    news=get_news(cfg["news_q"]); n_score=news_sentiment(news)
    glob=get_global_study()
    ai=super_ai_brain(df15, df5, df60, inst, n_score, glob, why_data, rise_data, pre_data, inv_data, court_data, govt_data)
    score=ai['ai_up']
    reasons=[]
    reasons.append(f"🕐 5 MIN: {ai['s5']} - {ai['w5']}")
    reasons.append(f"🕐 15 MIN: {ai['s15']} - {ai['w15']}")
    reasons.append(f"🕐 1 HOUR: {ai['s60']} - {ai['w60']}")
    reasons.append(f"🌍 GLOBAL: {glob.get('text','')}")
    reasons.append(f"🌅 PRE-MARKET: {pre_data['plan'] if pre_data else '-'}")
    reasons.append(f"🔴 KA PADTOY: {why_data['verdict'] if why_data else '-'}")
    reasons.append(f"🟢 KA VADHTOY: {rise_data['verdict'] if rise_data else '-'}")
    reasons.append(f"💰 INVESTMENT: {inv_data['verdict'] if inv_data else '-'}")
    reasons.append(f"⚖️ COURT: {court_data['verdict'] if court_data else '-'}")
    reasons.append(f"🏛️ GOVT CONTRACT: {govt_data['verdict'] if govt_data else '-'}")
    reasons.append(f"🤖 SUPER AI Total {ai['total']} | Var {ai['ai_up']}% | {ai['pattern']}")
    reasons.append(f"📊 RSI {last['rsi']:.1f} | Sup {df15['low'].tail(20).min():.0f} | Res {df15['high'].tail(20).max():.0f}")
    blocked=""
    if inst in ["NIFTY","BANKNIFTY"] and now_ist.hour==10 and now_ist.minute<15: blocked="⏰ 10:15 aadhi NO TRADE"
    if inst in ["NIFTY","BANKNIFTY"] and now_ist.hour==15: blocked="⏰ Market Off javal"
    if inst=="CRUDEOIL MINI" and (now_ist.hour < 14 or now_ist.hour >= 16): blocked="⏰ CRUDE: Fakt Dupari 2-4"
    if ai['risk']=="HIGH": blocked=f"🛑 {ai['salah']}"
    if blocked: final="WAIT"; reasons.append(f"🛑 {blocked}")
    else: final=ai['final']; reasons.append(f"🎯 FINAL: {final} - Level todla ki ghe")
    try:
        if inst in ["NIFTY","BANKNIFTY"]: ltp=smart.ltpData(cfg["exchange"], cfg["sym"], cfg["token"])['data']['ltp']
        else: ltp=smart.ltpData(fut_exch, fut_sym, token)['data']['ltp']
    except: ltp=float(last['close'])
    return {"score":score,"final":final,"reasons":reasons,"news":news,"df":df15,"last":last,"ltp":ltp,"sup":df15['low'].tail(20).min(),"resi":df15['high'].tail(20).max(),"instrument":inst,"token":token,"fut_sym":fut_sym,"ai":ai,"global":glob}
def make_chart(df):
    fig=go.Figure()
    fig.add_trace(go.Candlestick(x=df['datetime'], open=df['open'], high=df['high'], low=df['low'], close=df['close'], increasing_line_color='#26A69A', increasing_fillcolor='#26A69A', decreasing_line_color='#EF5350', decreasing_fillcolor='#EF5350', name='Candles'))
    fig.add_trace(go.Scatter(x=df['datetime'], y=df['ema9'], line=dict(color='#FFD700', width=1.5), name='EMA 9'))
    fig.add_trace(go.Scatter(x=df['datetime'], y=df['ema21'], line=dict(color='#2962FF', width=1.5), name='EMA 21'))
    fig.add_trace(go.Scatter(x=df['datetime'], y=df['ema50'], line=dict(color='#FF6D00', width=1.2, dash='dash'), name='EMA 50'))
    fig.add_trace(go.Scatter(x=df['datetime'], y=df['vwap'], line=dict(color='white', width=1, dash='dot'), name='VWAP'))
    colors=['#26A69A' if c>=o else '#EF5350' for c,o in zip(df['close'], df['open'])]
    fig.add_trace(go.Bar(x=df['datetime'], y=df['volume'], marker_color=colors, opacity=0.5, name='Volume', yaxis='y2'))
    fig.update_layout(template='plotly_dark', paper_bgcolor='#131722', plot_bgcolor='#131722', font=dict(color='white'), xaxis=dict(gridcolor='#1E222D', rangeslider=dict(visible=False)), yaxis=dict(gridcolor='#1E222D', side='right'), yaxis2=dict(overlaying='y', side='left', showgrid=False), height=380, margin=dict(l=0, r=50, t=10, b=0), legend=dict(orientation='h', y=1.02, x=0), hovermode='x unified')
    return fig
def get_atm_option(smart, inst, signal, ltp):
    try:
        cfg=CONFIG[inst]; atm=round(ltp/cfg["strike_step"])*cfg["strike_step"]
        otype="CE" if signal=="BUY" else "PE"
        time.sleep(0.2); res=smart.searchScrip(cfg["opt_exchange"], cfg["prefix"])
        data_list=res.get('data') or [] if isinstance(res, dict) else []
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
def get_both_orders(smart, sel, d):
    cfg=CONFIG[sel]; ltp=d['ltp']
    ce_sym, ce_tok, atm = get_atm_option(smart, sel, "BUY", ltp)
    pe_sym, pe_tok, _ = get_atm_option(smart, sel, "SELL", ltp)
    ce_ltp=0; pe_ltp=0
    try:
        if ce_tok: ce_ltp=float(smart.ltpData(cfg["opt_exchange"], ce_sym, ce_tok)['data']['ltp'])
    except: pass
    try:
        if pe_tok: pe_ltp=float(smart.ltpData(cfg["opt_exchange"], pe_sym, pe_tok)['data']['ltp'])
    except: pass
    return {"atm":atm,"ltp":ltp,"ce":{"sym":ce_sym,"tok":ce_tok,"ltp":ce_ltp},"pe":{"sym":pe_sym,"tok":pe_tok,"ltp":pe_ltp}}
def bhavishya_ai_predict(df15, ai_data, pre_data, inv_data, govt_data, court_data, why_data, rise_data):
    if df15 is None or len(df15) < 30: return None
    last = df15.iloc[-1]
    close = float(last['close'])
    ema_trend = 0
    if last['ema9'] > last['ema21'] > last['ema50']: ema_trend = 2
    elif last['ema9'] < last['ema21'] < last['ema50']: ema_trend = -2
    mom = (df15['close'].iloc[-1] - df15['close'].iloc[-10]) / df15['close'].iloc[-10] * 100
    atr = float(last['atr']) if 'atr' in last else close*0.005
    fund_score = 0
    if pre_data and pre_data['action']=="BUY": fund_score+=2
    elif pre_data and pre_data['action']=="SELL": fund_score-=2
    if inv_data and inv_data['action']=="BUY": fund_score+=2
    elif inv_data and inv_data['action']=="SELL": fund_score-=2
    if govt_data and govt_data['action']=="BUY": fund_score+=2
    elif govt_data and govt_data['action']=="SELL": fund_score-=2
    if rise_data and rise_data['power']>=3: fund_score+=2
    elif rise_data and rise_data['power']>=1: fund_score+=1
    if court_data and not court_data.get('trade_allow', True): fund_score-=3
    if why_data and not why_data.get('trade_allow', True): fund_score-=1
    total_score = ema_trend*2 + fund_score + (1 if mom>0 else -1 if mom<0 else 0)
    if total_score >= 5:
        udya = "🟢 PUDHCHA DIVAS VAR JANAR"; udya_conf = 75 + min(20, total_score*2); udya_move = atr*1.2
        udya_target = close + udya_move; udya_sl = close - atr*0.5
        udya_salla = "Pudhcha trading divshi BUY CE chi tayari kar - Sakali 9:15 la CE ghe"
    elif total_score <= -5:
        udya = "🔴 PUDHCHA DIVAS KHALI JANAR"; udya_conf = 75 + min(20, abs(total_score)*2); udya_move = atr*1.2
        udya_target = close - udya_move; udya_sl = close + atr*0.5
        udya_salla = "Pudhcha trading divshi BUY PE chi tayari kar - Sakali 9:15 la PE ghe"
    elif total_score >= 2:
        udya = "🟡 PUDHCHA DIVAS THODA VAR JANAR"; udya_conf = 60; udya_move = atr*0.6
        udya_target = close + udya_move; udya_sl = close - atr*0.5
        udya_salla = "Pudhcha divas thoda var jail - Ardha qty ghe"
    elif total_score <= -2:
        udya = "🟡 PUDHCHA DIVAS THODA KHALI JANAR"; udya_conf = 60; udya_move = atr*0.6
        udya_target = close - udya_move; udya_sl = close + atr*0.5
        udya_salla = "Pudhcha divas thoda khali jail - Ardha qty ghe"
    else:
        udya = "⚪ PUDHCHA DIVAS SIDEWAYS RAHNAR"; udya_conf = 55; udya_move = atr*0.3
        udya_target = close; udya_sl = close - atr
        udya_salla = "Pudhcha divas sideways rahil - Trade gheu naka - Level todla tarach ghe"
    if abs(total_score) >= 5:
        teen_divas = f"Trend STRONG aahe - Pudhe 3 divas hech disha rahil - {udya} cha trend tiknar"
        athvada = f"Pudcha athvada pan {udya} dishene janar - Motha trend suru zala aahe"
    elif abs(total_score) >= 2:
        teen_divas = "Trend MEDIUM aahe - 2 divas tikal, mag badlu shakto"
        athvada = "Athvada Sideways rahil - Motha trend nahi"
    else:
        teen_divas = "Trend NAHI - Roj badalnar - Roj sakali Pre-Market baghunach trade ghe"
        athvada = "Athvada Sideways - Motha paisa nahi bananar"
    sup = df15['low'].tail(30).min()
    res = df15['high'].tail(30).max()
    fut_sup = sup - atr
    fut_res = res + atr
    return {"close": close, "total_score": total_score, "mom": mom, "atr": atr,"udya": udya, "udya_conf": udya_conf, "udya_target": udya_target, "udya_sl": udya_sl, "udya_salla": udya_salla,"teen_divas": teen_divas, "athvada": athvada,"sup": sup, "res": res, "fut_sup": fut_sup, "fut_res": fut_res,"ema_trend": ema_trend, "fund_score": fund_score}
def get_daily_quiz():
    quizzes = [
        {"q": "Govt ne HAL la ₹10,000 Cr Defence Contract dila - Kay hoil?", "options": ["HAL cha share padel", "HAL cha share vadhel", "Kahi honar nahi", "Market band hoil"], "ans": 1, "exp": "✅ Barobar - Govt Contract milala ki company la paisa + kaam milto - Mhanun share vadhto."},
        {"q": "FII lok India madhun paisa kadhun ghetayat - Market kay karel?", "options": ["Market vadhel", "Market padel", "Kahi honar nahi", "Rupee vadhel"], "ans": 1, "exp": "✅ Barobar - FII vikle ki market padto. FII ne kal ₹2000 Cr vikle tar dusrya divshi market padnar."},
        {"q": "Supreme Court ne company viruddha nikal dila - Kay karaycha?", "options": ["Tya company cha CE ghe", "Tya company pasun lamb raha", "Double qty ghe", "Kahi nahi"], "ans": 1, "exp": "✅ Barobar - Court nikal aalyavar share 10-20% halto - Tya divshi tya company cha Option gheu naka."},
        {"q": "US Market ratri 2% padla - Aaj NIFTY kay karel?", "options": ["NIFTY khup vadhel", "NIFTY padnyachi shakyata jast", "NIFTY band rahil", "Crude vadhel"], "ans": 1, "exp": "✅ Barobar - US padla ki India pan padto. Pan aata India US peksha vegla chaltoy - FII baghaycha."},
        {"q": "Crude Oil khup vadhla - Konala fayda / nuksan?", "options": ["India la fayda", "India la nuksan - Tel mahag", "Kahi honar nahi", "Bank la fayda"], "ans": 1, "exp": "✅ Barobar - India tel baherun anto. Crude vadhla ki India la nuksan - Market padto."},
        {"q": "9:15 la trade ghyaycha - Aadhi kay baghaycha?", "options": ["Fakt Chart", "Pre-Market + Jag + Investment + Court + Govt Contract", "Kahi nahi", "Fakt News"], "ans": 1, "exp": "✅ Barobar - Fakt Chart baghun trade gheu naka. 8:00-9:15 madhe sagla study kar - Mag 9:15 la trade ghe."},
        {"q": "₹10,000 madhe SELL Option ka karu naka?", "options": ["Margin kami aahe", "SELL la 3x Margin lagto", "Donhi barobar", "Kahi nahi"], "ans": 2, "exp": "✅ Barobar - Donhi barobar - ₹10,000 madhe SELL la margin purat nahi. SELL la 3x margin lagto."},
    ]
    return quizzes[now_ist.day % len(quizzes)]
def ai_ask_answer(question, all_data, pre_data, why_data, rise_data, inv_data, court_data, govt_data):
    q = question.lower()
    lines = []
    if any(w in q for w in ["var", "up", "vadh", "vadhel", "ce", "buy ce", "call"]): topic = "VAR JANAR KA?"
    elif any(w in q for w in ["khali", "pad", "down", "pe", "put", "buy pe"]): topic = "KHALI JANAR KA?"
    elif any(w in q for w in ["trade", "gheu", "ghyaycha", "konta", "kay karu"]): topic = "TRADE GHYAYCHA KA?"
    elif any(w in q for w in ["court", "nikal"]): topic = "COURT"
    elif any(w in q for w in ["govt", "contract", "sarkar"]): topic = "GOVT CONTRACT"
    elif any(w in q for w in ["fii", "investment", "paisa"]): topic = "INVESTMENT"
    elif any(w in q for w in ["udya", "tomorrow", "bhavishya", "future"]): topic = "BHAVISHYA"
    else: topic = "GENERAL"
    lines.append(f"**Tuza Question:** {question}")
    lines.append(f"**AI ne olakhla Topic:** {topic}")
    lines.append("---")
    lines.append("**📊 AI cha PURN STUDY:**")
    lines.append(f"🌅 PRE-MARKET: {pre_data['plan']} - Score {pre_data['score']}/100")
    lines.append(f"🔴 KA PADTOY: {why_data['verdict']} - Danger {why_data['danger']}")
    for r in why_data['reasons']: lines.append(f"  - {r}")
    lines.append(f"🟢 KA VADHTOY: {rise_data['verdict']} - Power {rise_data['power']}")
    for r in rise_data['reasons']: lines.append(f"  - {r}")
    lines.append(f"💰 INVESTMENT: {inv_data['verdict']}")
    lines.append(f"⚖️ COURT: {court_data['verdict']}")
    lines.append(f"🏛️ GOVT CONTRACT: {govt_data['verdict']}")
    if govt_data['contract_stocks']:
        for h in govt_data['contract_stocks'][:3]: lines.append(f"  - {h}")
    target_inst = None
    for inst in ["NIFTY", "BANKNIFTY", "CRUDEOIL MINI"]:
        if inst.lower() in q or ("bank" in q and inst=="BANKNIFTY") or (("crude" in q or "oil" in q or "tel" in q) and inst=="CRUDEOIL MINI"):
            target_inst = inst; break
    if not target_inst: target_inst = "NIFTY"
    d = all_data.get(target_inst)
    if d:
        ai = d['ai']
        lines.append(f"---")
        lines.append(f"**🎯 {target_inst} cha SUPER AI:**")
        lines.append(f"  - LIVE: ₹{d['ltp']:.2f} | Var {ai['ai_up']}% | Khali {ai['ai_down']}%")
        lines.append(f"  - 5m {ai['s5']} | 15m {ai['s15']} | 1h {ai['s60']} | {ai['pattern']}")
        lines.append(f"  - Support ₹{d['sup']:.0f} | Resistance ₹{d['resi']:.0f} | RSI {d['last']['rsi']:.1f}")
        fut = bhavishya_ai_predict(d['df'], d['ai'], pre_data, inv_data, govt_data, court_data, why_data, rise_data)
        if fut: lines.append(f"  - 🔮 BHAVISHYA: {fut['udya']} - Pudhcha Target ₹{fut['udya_target']:.2f} - Confidence {fut['udya_conf']}%")
    lines.append("---")
    lines.append("**🤖 AI CHA FINAL UTTAR:**")
    if topic == "VAR JANAR KA?":
        if rise_data['power'] >= 2 and d and d['ai']['ai_up'] >= 60: lines.append(f"✅ HO - {target_inst} VAR JANAR - Karan: {rise_data['verdict']} + SUPER AI Var {d['ai']['ai_up']}% - Resistance ₹{d['resi']:.0f} todla ki BUY CE ghe.")
        elif rise_data['power'] > why_data['danger']: lines.append(f"🟢 HO, THODA VAR JANAR - Vadhtoy Power {rise_data['power']} > Padtoy {why_data['danger']} - Ardha qty ne CE ghe.")
        else: lines.append(f"❌ NAHI - {target_inst} var janar nahi - Karan: {why_data['verdict']} - Padtoy jor jast aahe - CE gheu naka.")
    elif topic == "KHALI JANAR KA?":
        if why_data['danger'] >= 3 and d and d['ai']['ai_down'] >= 60: lines.append(f"✅ HO - {target_inst} KHALI JANAR - Karan: {why_data['verdict']} + SUPER AI Khali {d['ai']['ai_down']}% - Support ₹{d['sup']:.0f} todla ki BUY PE ghe.")
        elif why_data['danger'] > rise_data['power']: lines.append(f"🔴 HO, THODA KHALI JANAR - Padtoy {why_data['danger']} > Vadhtoy {rise_data['power']} - PE gheu shakta.")
        else: lines.append(f"❌ NAHI - {target_inst} khali janar nahi - Karan: {rise_data['verdict']} - Vadhtoy jor jast aahe.")
    elif topic == "TRADE GHYAYCHA KA?":
        if d and d['ai']['ai_up'] >= 70: lines.append(f"✅ HO - AAJ TRADE GHE - {target_inst} Var {d['ai']['ai_up']}% - Resistance ₹{d['resi']:.0f} todla ki BUY CE ghe - SL + Target pakka thev.")
        elif d and d['ai']['ai_down'] >= 70: lines.append(f"✅ HO - AAJ TRADE GHE - {target_inst} Khali {d['ai']['ai_down']}% - Support ₹{d['sup']:.0f} todla ki BUY PE ghe.")
        elif d and d['ai']['risk']=="HIGH": lines.append(f"🛑 NAKO - JAGAT + COURT DONHI BIGHADLE - Aaj trade gheu naka.")
        else: lines.append(f"⏳ WAIT - Var {d['ai']['ai_up'] if d else '-'}% / Khali {d['ai']['ai_down'] if d else '-'}% - Level todla ki ghe - Resistance ₹{d['resi']:.0f} / Support ₹{d['sup']:.0f}")
    elif topic == "COURT": lines.append(f"{court_data['verdict']} - " + (" | ".join(court_data['reasons']) if court_data['reasons'] else "Aaj India Court cha motha nikal nahi - Trade karu shakta."))
    elif topic == "GOVT CONTRACT": lines.append(f"{govt_data['verdict']} - " + (" | ".join(govt_data['contract_stocks'][:3]) if govt_data['contract_stocks'] else "Aaj konala motha contract nahi."))
    elif topic == "INVESTMENT": lines.append(f"{inv_data['verdict']} - " + (" | ".join(inv_data['reasons'][:2]) if inv_data['reasons'] else ""))
    elif topic == "BHAVISHYA":
        if d:
            fut = bhavishya_ai_predict(d['df'], d['ai'], pre_data, inv_data, govt_data, court_data, why_data, rise_data)
            if fut: lines.append(f"{fut['udya']} - Pudhcha Target ₹{fut['udya_target']:.2f} - {fut['udya_salla']} - 3 Divas: {fut['teen_divas']}")
    else:
        if rise_data['power'] > why_data['danger']: lines.append(f"🟢 AAJ VAR JANYACHA JOR JAST - Vadhtoy {rise_data['power']} vs Padtoy {why_data['danger']} - CE var laksh thev.")
        elif why_data['danger'] > rise_data['power']: lines.append(f"🔴 AAJ KHALI JANYACHA JOR JAST - Padtoy {why_data['danger']} vs Vadhtoy {rise_data['power']} - PE var laksh thev.")
        else: lines.append(f"🟡 AAJ DONHI SARKHE - Vadhtoy {rise_data['power']} = Padtoy {why_data['danger']} - BREAKOUT DAY - Level todla ki ghe.")
    lines.append("")
    lines.append("⚠️ He AI cha andaj aahe - 100% guarantee nahi - SL nehmi thev.")
    return "\n".join(lines)
# --- MAIN ---
smart=get_connection()
if not smart:
    st.warning("⚠️ Login zala nahi"); st.stop()
with st.spinner("🕵️ AI Jag + Vadhtoy + Padtoy + Investment + Court + Govt shodhtoy..."):
    why_data=why_market_falling(); rise_data=why_market_rising(); inv_data=investment_flow_study(); court_data=court_verdict_study(); govt_data=govt_contract_study()
with st.spinner("🌅 AI Pre-Market Study kartoy..."):
    pre_data=pre_market_study(why_data, rise_data)
st.markdown("## 🌅 PRE-MARKET STUDY - 8:00 to 9:15 - AAJCHA PURN ANDAJ")
if is_pre_market: st.info("⏰ AATA PRE-MARKET AAHE - 9:15 aadhi Trade BAND")
elif is_open: st.success("🟢 MARKET CHALU - 9:15 ZALA - Trade Gheu Shakta")
else: st.info("🌙 MARKET BAND - Pudhcha Trading Divas Monday la bagh")
if pre_data['action']=="BUY": st.success(f"### {pre_data['plan']}"); st.success(f"**Score {pre_data['score']}/100 - {pre_data['plan_detail']}**")
elif pre_data['action']=="SELL": st.error(f"### {pre_data['plan']}"); st.error(f"**Score {pre_data['score']}/100 - {pre_data['plan_detail']}**")
elif pre_data['danger']>=3 and rise_data['power']<2: st.error(f"### {pre_data['plan']}"); st.error(f"**{pre_data['plan_detail']}**")
else: st.warning(f"### {pre_data['plan']}"); st.warning(f"**Score {pre_data['score']}/100 - {pre_data['plan_detail']}**")
for r in pre_data['reasons']: st.write(r)
if is_pre_market: st.warning("⏰ 9:15 AADHI TRADE BUTTON BAND - Fakt Plan bagh")
st.markdown("## 🔴 KA PADTOY? - KHALI JANYACHA KARAN")
if why_data['danger']>=4: st.error(f"### {why_data['verdict']}")
elif why_data['danger']>=1: st.warning(f"### {why_data['verdict']}")
else: st.success(f"### {why_data['verdict']}")
for r in why_data['reasons']: st.write(r)
st.markdown("## 🟢 KA VADHTOY? - VAR JANYACHA KARAN")
if rise_data['power']>=3:
    st.success(f"### {rise_data['verdict']}")
    for r in rise_data['reasons']: st.success(r)
    st.success(f"**🎯 {rise_data['salla']}**")
elif rise_data['power']>=1:
    st.warning(f"### {rise_data['verdict']}")
    for r in rise_data['reasons']: st.warning(r)
    st.warning(f"**🎯 {rise_data['salla']}**")
else:
    st.info(f"### {rise_data['verdict']}")
    st.info("Market vadhnar nahi - Khali / Sideways bagh")
st.markdown("## ⚖️ DONHI EKVATRA - AAJCHA FINAL KARAN")
if rise_data['power'] > why_data['danger']:
    st.success(f"🟢 VADHNYACHA JOR JAST - Vadhtoy Power {rise_data['power']} vs Padtoy Danger {why_data['danger']} - AAJ CE chi shakyata jast")
elif why_data['danger'] > rise_data['power']:
    st.error(f"🔴 PADNYACHA JOR JAST - Padtoy Danger {why_data['danger']} vs Vadhtoy Power {rise_data['power']} - AAJ PE chi shakyata jast")
else:
    st.warning(f"🟡 DONHI SARKHE - Vadhtoy {rise_data['power']} vs Padtoy {why_data['danger']} - BREAKOUT DAY - Level todla ki ghe - CE kinva PE")
st.markdown("## 💰 INVESTMENT STUDY - KONATYA COMPANY MADHE PAISA YETOY?")
if inv_data['action']=="BUY": st.success(f"### {inv_data['verdict']}")
elif inv_data['action']=="SELL": st.error(f"### {inv_data['verdict']}")
else: st.warning(f"### {inv_data['verdict']}")
for r in inv_data['reasons']: st.write(r)
if inv_data['hot_stocks']:
    st.markdown("#### 🔥 HOT STOCKS:")
    for h in inv_data['hot_stocks'][:5]: st.success(f"- {h}")
st.markdown("## ⚖️ COURT / SEBI / GOVT NIKAL - FAKT INDIA")
if court_data['danger']>=2: st.error(f"### {court_data['verdict']}")
elif court_data['danger']==1: st.warning(f"### {court_data['verdict']}")
else: st.success(f"### {court_data['verdict']}")
for r in court_data['reasons']: st.write(r)
for a in court_data['affected']: st.write(f"- {a}")
st.markdown("## 🏛️ GOVT CONTRACT STUDY - KONALA CONTRACT MILALA?")
if govt_data['action']=="BUY": st.success(f"### {govt_data['verdict']}")
elif govt_data['action']=="SELL": st.error(f"### {govt_data['verdict']}")
else: st.warning(f"### {govt_data['verdict']}")
for r in govt_data['reasons']: st.write(r)
if govt_data['contract_stocks']:
    st.markdown("#### 🏛️ AAJ CONTRACT MILALELE COMPANY - Yanche Share Vadhnar:")
    for h in govt_data['contract_stocks'][:6]: st.success(f"- {h}")
    st.info("💡 Salla: Govt Contract milalelya Sector mule NIFTY vadhnar - BUY CE gheu shakta")
if time.time() - st.session_state['last_study'] > 120 or not st.session_state['cached_all']:
    new_cache={}
    with st.spinner("🤖 SUPER AI Study kartoy..."):
        for inst in INSTRUMENTS:
            try:
                fut_info=get_underlying(smart, inst)
                if not fut_info or not fut_info[0]: continue
                res=do_study(smart, inst, fut_info, why_data, rise_data, pre_data, inv_data, court_data, govt_data)
                if res: new_cache[inst]=res
            except: continue
    st.session_state['cached_all']=new_cache; st.session_state['last_study']=time.time()
all_data=st.session_state['cached_all']
if not all_data:
    st.error("❌ Data aala nahi")
    if st.button("🔄 Parat Try Kar"): st.session_state['last_study']=0; st.rerun()
    st.stop()
avail, used, _ = get_funds_and_margin(smart)
m1,m2,m3=st.columns(3)
with m1: st.metric("Available Cash", f"₹{avail:.0f}")
with m2: st.metric("Used Margin", f"₹{used:.0f}")
with m3: st.metric("Aajcha P&L", f"₹{st.session_state['day_pnl']:.0f}")
st.subheader("🤖 SUPER AI SALLA - Sagla Ekatra - FIXED")
for inst in INSTRUMENTS:
    d=all_data.get(inst)
    if d:
        ai=d['ai']
        if ai['risk']=="HIGH": st.error(f"**{inst}**: {ai['pattern']} | {ai['salah']}")
        elif d['final'] in ["BUY","SELL"]: st.success(f"**{inst}**: {ai['pattern']} | Var {ai['ai_up']}%")
        else: st.warning(f"**{inst}**: {ai['pattern']} | Var {ai['ai_up']}% - Level todla ki ghe")
c1,c2,c3=st.columns(3)
for col, inst in zip([c1,c2,c3], INSTRUMENTS):
    with col:
        d=all_data.get(inst)
        if d:
            ai=d['ai']
            st.markdown(f"### {inst} - {d['final']}")
            st.metric(f"{inst} LIVE", f"₹{d['ltp']:.2f}", f"Score {d['score']}/100")
            st.write(f"5m {ai['s5']} | 15m {ai['s15']} | 1h {ai['s60']} | Pre {pre_data['action']} | Vadhtoy {rise_data['power']} | Padtoy {why_data['danger']}")
            st.write(f"RSI {d['last']['rsi']:.1f} | Sup ₹{d['sup']:.0f} | Res ₹{d['resi']:.0f}")
            if st.button(f"Trade Ghe - {inst}", key=f"btn_{inst}"): st.session_state['selected_trade']=inst
st.divider()
st.markdown("## 🔮 BHAVISHYA AI - PUDHCHA TRADING DIVAS KAY HONAR?")
for inst in INSTRUMENTS:
    d = all_data.get(inst)
    if not d: continue
    fut = bhavishya_ai_predict(d['df'], d['ai'], pre_data, inv_data, govt_data, court_data, why_data, rise_data)
    if not fut: continue
    udya_date = next_trading_day(now_ist).strftime('%d %b %Y, %A')
    col_f1, col_f2, col_f3 = st.columns(3)
    with col_f1:
        st.markdown(f"### 🔮 {inst} - BHAVISHYA")
        if "VAR JANAR" in fut['udya'] and "THODA" not in fut['udya']: st.success(f"**{fut['udya']}**")
        elif "KHALI JANAR" in fut['udya'] and "THODA" not in fut['udya']: st.error(f"**{fut['udya']}**")
        else: st.warning(f"**{fut['udya']}**")
        st.write(f"**Pudhcha Trading Divas: {udya_date}**")
        st.write(f"**Aajcha Close:** ₹{fut['close']:.2f}")
        st.write(f"**Pudhcha Target:** ₹{fut['udya_target']:.2f}")
        st.write(f"**Confidence:** {fut['udya_conf']}%")
        st.write(f"**Salla:** {fut['udya_salla']}")
    with col_f2:
        st.markdown("### 📅 3 DIVAS + ATHVADA")
        st.write(f"**3 Divas:** {fut['teen_divas']}")
        st.write(f"**Athvada:** {fut['athvada']}")
        st.write(f"**Momentum (10 Candle):** {fut['mom']:+.2f}%")
        st.write(f"**Trend Power:** {fut['total_score']:+d} / 10")
        st.write(f"**ATR (Roj Halchal):** ₹{fut['atr']:.2f}")
    with col_f3:
        st.markdown("### 🎯 FUTURE LEVELS")
        st.write(f"**Aajcha Support:** ₹{fut['sup']:.0f}")
        st.write(f"**Aajcha Resistance:** ₹{fut['res']:.0f}")
        st.write(f"**Pudhcha Support:** ₹{fut['fut_sup']:.0f}")
        st.write(f"**Pudhcha Resistance:** ₹{fut['fut_res']:.0f}")
        if "VAR JANAR" in fut['udya']: st.success("💡 Pudhcha divshi CE var laksh thev - Resistance todla ki CE ghe")
        elif "KHALI JANAR" in fut['udya']: st.error("💡 Pudhcha divshi PE var laksh thev - Support todla ki PE ghe")
        else: st.warning("💡 Pudhcha divas Sideways - Level todla tarach ghe")
    st.divider()
st.divider()
tab1, tab2, tab3 = st.tabs(["📈 NIFTY", "🏦 BANKNIFTY", "🛢️ CRUDEOIL MINI"])
for tab, inst in zip([tab1, tab2, tab3], INSTRUMENTS):
    with tab:
        d=all_data.get(inst)
        if not d: continue
        st.subheader(f"{inst} - {d['final']} - ₹{d['ltp']:.2f}")
        col1, col2 = st.columns(2)
        with col1:
            for r in d['reasons']: st.write(r)
        with col2:
            for n in d['news']: st.write(f"- {n}")
        fig=make_chart(d['df'].tail(50)); st.plotly_chart(fig, use_container_width=True, key=f"chart_{inst}")
st.divider()
st.subheader("🚀 AI DONHI ORDER - BUY + SELL")
sel=st.session_state.get('selected_trade')
if sel and sel in INSTRUMENTS: st.info(f"Nivadla: {sel}")
else: sel=st.selectbox("Konatya var Trade ghyaycha?", INSTRUMENTS)
if sel in all_data:
    d=all_data[sel]; cfg=CONFIG[sel]; sig=d['final']; ai=d['ai']
    st.info(f"🤖 SUPER AI: {ai['pattern']} | Var {ai['ai_up']}% | SAKAL: {pre_data['plan']} | VADHTOY: {rise_data['verdict']} | PADTOY: {why_data['verdict']} | GOVT: {govt_data['verdict']}")
    if ai['risk']=="HIGH":
        st.error(f"🛑 TRADE BAND - Jag + Court donhi bighadle")
    if is_pre_market:
        st.error("🛑 9:15 AADHI TRADE BAND - Fakt Plan bagh.")
    else:
        both=get_both_orders(smart, sel, d); ce=both['ce']; pe=both['pe']; atm=both['atm']
        st.markdown(f"### 🎯 {sel} - LIVE ₹{d['ltp']:.2f} | ATM {atm} | AI Var {ai['ai_up']}% | Khali {ai['ai_down']}%")
        col_buy, col_sell = st.columns(2)
        with col_buy:
            st.markdown("### 🟢 ORDER 1 - BUY CE - VAR GELA TAR")
            st.success(f"**{ce['sym']}**"); st.metric("CE Premium", f"₹{ce['ltp']:.2f}")
            st.write(f"**Kevha Gheu:** ₹{d['resi']:.0f} var gela tar | **Qty:** {cfg['qty']} | **Lagel:** ₹{ce['ltp']*cfg['qty']:.0f}")
            ok_ce, msg_ce, _, _ = check_margin_before_trade(smart, sel, ce['ltp'], False)
            if ok_ce: st.success(msg_ce)
            else: st.error(msg_ce)
            if st.button(f"🟢 BUY CE GHE - {ce['sym']}", key=f"buy_ce_{sel}", use_container_width=True):
                if st.session_state['trades']>=MAX_TRADES: st.warning("Max Trades zale!")
                elif ai['risk']=="HIGH": st.error("🛑 JAG + COURT DONHI BIGHADLE")
                elif not ok_ce: st.error("🛑 MARGIN KAMI")
                elif not LIVE_MODE: st.warning(f"PAPER ORDER: BUY {ce['sym']} @ ₹{ce['ltp']}"); st.session_state['trades']+=1
                else:
                    oid=smart.placeOrder({"variety":"NORMAL","tradingsymbol":ce['sym'],"symboltoken":ce['tok'],"transactiontype":"BUY","exchange":cfg["opt_exchange"],"ordertype":"MARKET","producttype":"INTRADAY","duration":"DAY","price":"0","squareoff":str(int(TARGET_POINTS*100)),"stoploss":str(int(SL_POINTS*100)),"quantity":str(cfg['qty'])})
                    st.success(f"✅ BUY CE ORDER GELI! {oid}"); st.session_state['trades']+=1
        with col_sell:
            st.markdown("### 🔴 ORDER 2 - BUY PE - KHALI GELA TAR")
            st.error(f"**{pe['sym']}**"); st.metric("PE Premium", f"₹{pe['ltp']:.2f}")
            st.write(f"**Kevha Gheu:** ₹{d['sup']:.0f} khali gela tar | **Qty:** {cfg['qty']} | **Lagel:** ₹{pe['ltp']*cfg['qty']:.0f}")
            ok_pe, msg_pe, _, _ = check_margin_before_trade(smart, sel, pe['ltp'], False)
            if ok_pe: st.success(msg_pe)
            else: st.error(msg_pe)
            if st.button(f"🔴 BUY PE GHE - {pe['sym']}", key=f"buy_pe_{sel}", use_container_width=True):
                if st.session_state['trades']>=MAX_TRADES: st.warning("Max Trades zale!")
                elif ai['risk']=="HIGH": st.error("🛑 JAG + COURT DONHI BIGHADLE")
                elif not ok_pe: st.error("🛑 MARGIN KAMI")
                elif not LIVE_MODE: st.warning(f"PAPER ORDER: BUY {pe['sym']} @ ₹{pe['ltp']}"); st.session_state['trades']+=1
                else:
                    oid=smart.placeOrder({"variety":"NORMAL","tradingsymbol":pe['sym'],"symboltoken":pe['tok'],"transactiontype":"BUY","exchange":cfg["opt_exchange"],"ordertype":"MARKET","producttype":"INTRADAY","duration":"DAY","price":"0","squareoff":str(int(TARGET_POINTS*100)),"stoploss":str(int(SL_POINTS*100)),"quantity":str(cfg['qty'])})
                    st.success(f"✅ BUY PE ORDER GELI! {oid}"); st.session_state['trades']+=1
        st.divider()
        st.markdown("### 🤖 AI CHA FINAL DECISION - FIXED")
        if ai['ai_up']>=70:
            st.success(f"🎯 AADHI **BUY CE** GHE - Var {ai['ai_up']}% - Resistance ₹{d['resi']:.0f} todla ki ghe.")
        elif ai['ai_down']>=70:
            st.error(f"🎯 AADHI **BUY PE** GHE - Khali {ai['ai_down']}% - Support ₹{d['sup']:.0f} todla ki ghe.")
        elif ai['risk']=="HIGH":
            st.error(f"🛑 DONHI NAKO - Jag + Court donhi bighadle - Aaj trade nako")
        else:
            st.warning(f"⏳ BREAKOUT DAY - Var {ai['ai_up']}% / Khali {ai['ai_down']}% - Resistance ₹{d['resi']:.0f} var gela tar CE, Support ₹{d['sup']:.0f} khali gela tar PE - Level todla ki ghe.")
st.divider()
st.markdown("## 💬 AI LA VICHAR - TU TYPE KAR, AI PURN STUDY KARUN UTTAR DEIL")
st.info("💡 Udaharan: `Aaj NIFTY var jail ka?` / `Aaj trade gheu ka?` / `Udya kay honar?` / `Court cha kay zala?` / `Konala Govt Contract milala?`")
user_q = st.text_input("✍️ Ithe tuza Question type kar:", placeholder="Ud: Aaj NIFTY var jail ka?", key="ai_ask_input")
col_ask1, col_ask2 = st.columns([1, 3])
with col_ask1:
    ask_btn = st.button("🤖 AI LA VICHAR", key="ai_ask_btn", use_container_width=True)
with col_ask2:
    quick_q = st.selectbox("🚀 Lagich Vichar - Ek dab:", ["", "Aaj NIFTY var jail ka?", "Aaj NIFTY khali jail ka?", "Aaj trade gheu ka?", "Udya kay honar?", "Konala Govt Contract milala?", "Court cha kay zala?", "FII paisa takta yet ka?"], key="ai_quick_q")
final_q = user_q if user_q else quick_q
if ask_btn and final_q:
    with st.spinner("🤖 AI Purn Study kartoy - Pre-Market + Ka Vadhtoy + Ka Padtoy + Investment + Court + Govt + Bhavishya..."):
        ans = ai_ask_answer(final_q, all_data, pre_data, why_data, rise_data, inv_data, court_data, govt_data)
    st.success("### 🤖 AI CHA UTTAR:")
    st.markdown(ans)
    with st.expander("📋 Uttar Copy Karnyasathi - Ithe dakhva"):
        st.text(ans)
elif ask_btn and not final_q:
    st.warning("👆 Aadhi Question type kar kinva varun ek nivad - Mag AI LA VICHAR dab")
st.divider()
st.markdown("## 🎯 DAILY 1 QUIZ - AAJCHA 1 QUESTION - SHIKNAY SATHI")
quiz = get_daily_quiz()
st.info(f"**Q: {quiz['q']}**")
selected = st.radio("Tuza Answer nivad:", quiz['options'], key="quiz_radio")
if st.button("✅ Answer Check Kar", key="quiz_check"):
    st.session_state['quiz_answered'] = True
    st.session_state['quiz_selected'] = selected
if st.session_state['quiz_answered']:
    correct_opt = quiz['options'][quiz['ans']]
    if st.session_state['quiz_selected'] == correct_opt:
        st.success(f"🎉 EK DAM BAROBAR! Tu shiktoy! - {correct_opt}")
    else:
        st.error(f"❌ Chukla - Barobar Answer: **{correct_opt}** - Tu nivadla: {st.session_state['quiz_selected']}")
    st.info(f"📖 **Samjavun Ghe:** {quiz['exp']}")
    if st.button("🔄 Parat Try Kar", key="quiz_reset"):
        st.session_state['quiz_answered'] = False
        st.rerun()
else:
    st.warning("👆 Var Answer nivadun 'Answer Check Kar' dab - Barobar aala ki tula kalel tu shiktoy!")
if st.button("📊 Live Positions Bagha"):
    pos=smart.position()
    if pos['data']: st.dataframe(pd.DataFrame(pos['data']))
    else: st.write("Kutlihi Position nahi")
if st.button("🔄 Sagla Study Parat Kar"):
    st.session_state['last_study']=0; st.session_state['why_time']=0; st.session_state['rise_time']=0; st.session_state['pre_time']=0; st.session_state['inv_time']=0; st.session_state['court_time']=0; st.session_state['govt_time']=0; st.rerun()
