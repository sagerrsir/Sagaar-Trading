import streamlit as st
import pandas as pd
import numpy as np
import pyotp
from datetime import datetime, timedelta
from SmartApi import SmartConnect

st.set_page_config(page_title="SAGAR AUTO TRADER - MULTI", layout="wide")
st.title("SAGAR AUTO TRADER - NIFTY + CRUDE + GOLD")

INSTRUMENT = st.selectbox("Instrument Nivad:", ["NIFTY", "CRUDEOIL MINI", "GOLD MINI"])

CONFIG = {
    "NIFTY": {"exchange": "NSE", "search": "NIFTY", "strike_step": 50, "qty": 25, "opt_exchange": "NFO", "symbol_prefix": "NIFTY"},
    "CRUDEOIL MINI": {"exchange": "MCX", "search": "CRUDEOILM", "strike_step": 50, "qty": 10, "opt_exchange": "MCX", "symbol_prefix": "CRUDEOILM"},
    "GOLD MINI": {"exchange": "MCX", "search": "GOLDM", "strike_step": 100, "qty": 1, "opt_exchange": "MCX", "symbol_prefix": "GOLDM"},
}
cfg = CONFIG[INSTRUMENT]

st.sidebar.header("⚠️ RISK CONTROL")
LIVE_MODE = st.sidebar.toggle("🔴 LIVE TRADING ON", value=False)
MAX_LOSS_DAY = st.sidebar.number_input("Max Loss / Day ₹", value=500)
MAX_TRADES = st.sidebar.number_input("Max Trades / Day", value=2)
SL_POINTS = st.sidebar.number_input("SL Points", value=30)
TARGET_POINTS = st.sidebar.number_input("Target Points", value=50)
QTY = cfg["qty"]
st.sidebar.write(f"Instrument: {INSTRUMENT} | Qty: {QTY}")

if 'killed' not in st.session_state: st.session_state['killed'] = False
if 'trades' not in st.session_state: st.session_state['trades'] = 0
if 'pnl' not in st.session_state: st.session_state['pnl'] = 0
if st.sidebar.button("🛑 KILL SWITCH", type="primary"):
    st.session_state['killed'] = True
if st.session_state['killed']:
    st.error("KILL SWITCH ON")
    st.stop()

def get_connection():
    try:
        smart = SmartConnect(api_key=st.secrets["ANGEL_API_KEY"])
        totp = pyotp.TOTP(st.secrets["ANGEL_TOTP"]).now()
        data = smart.generateSession(st.secrets["ANGEL_CLIENT_ID"], st.secrets["ANGEL_PIN"], totp)
        if data.get('status'): return smart
        st.error(f"Login Fail: {data.get('message')}")
        return None
    except Exception as e:
        st.error(f"Login Error: {e}")
        return None

# --- NAVIN FIX: Token search karun ghe ---
def get_underlying_token(smart):
    if INSTRUMENT == "NIFTY":
        return "26000", "NIFTY"
    # MCX sathi FUTCOM shodh
    try:
        res = smart.searchScrip(cfg["exchange"], cfg["search"])
        # res['data'] madhe sagle contracts yetat, FUTCOM / FUTCOM wala ghe
        for item in res['data']:
            sym = item.get('tradingsymbol','')
            # CRUDEOILM + date sarkha - FUTURE, CE/PE naslela
            if sym.startswith(cfg["search"]) and 'CE' not in sym and 'PE' not in sym:
                # Expiry javalchi ghe - pahila milala to ghe
                st.info(f"Underlying milala: {sym} Token: {item['symboltoken']}")
                return item['symboltoken'], sym
        # Jar varcha nahi milala tar pahila item ghe
        if res['data']:
            return res['data'][0]['symboltoken'], res['data'][0]['tradingsymbol']
    except Exception as e:
        st.error(f"Token search fail: {e}")
    return None, None

def get_atm_option(smart, signal, underlying_ltp):
    ltp = underlying_ltp
    atm = round(ltp / cfg["strike_step"]) * cfg["strike_step"]
    today = datetime.now()
    if INSTRUMENT == "NIFTY":
        days_ahead = (3 - today.weekday()) % 7
        if days_ahead == 0 and today.hour >= 15: days_ahead = 7
        expiry = today + timedelta(days=days_ahead)
    else:
        expiry = today + timedelta(days=20)
    expiry_str = expiry.strftime("%d%b%y").upper()
    opt_type = "CE" if signal == "BUY" else "PE"
    symbol_try = f"{cfg['symbol_prefix']}{expiry_str}{atm}{opt_type}"
    try:
        res = smart.searchScrip(cfg["opt_exchange"], symbol_try)
        if res['data']:
            return symbol_try, res['data'][0]['symboltoken'], atm, ltp
    except: pass
    # Fallback - javalchi expiry shodh
    try:
        res2 = smart.searchScrip(cfg["opt_exchange"], cfg['symbol_prefix'])
        for item in res2['data']:
            if str(atm) in item['tradingsymbol'] and opt_type in item['tradingsymbol']:
                return item['tradingsymbol'], item['symboltoken'], atm, ltp
    except Exception as e:
        st.error(f"Symbol shodh fail: {e}")
    st.error(f"Symbol sapadla nahi: {symbol_try}")
    return None, None, atm, ltp

def get_signal(smart):
    token, sym_name = get_underlying_token(smart)
    if not token:
        st.error("Underlying Token milala nahi!")
        return "WAIT", None, pd.DataFrame()

    to_date = datetime.now()
    from_date = to_date - timedelta(days=10)
    params = {
        "exchange": cfg["exchange"],
        "symboltoken": token,
        "interval": "FIFTEEN_MINUTE",
        "fromdate": from_date.strftime("%Y-%m-%d %H:%M"),
        "todate": to_date.strftime("%Y-%m-%d %H:%M")
    }
    try:
        hist = smart.getCandleData(params)
    except Exception as e:
        st.error(f"Candle Error: {e}")
        return "WAIT", None, pd.DataFrame()
    if not hist or not hist.get('data') or len(hist['data']) == 0:
        st.error(f"Candle Data rikama! Token: {token} Symbol: {sym_name} Reply: {hist}")
        return "WAIT", None, pd.DataFrame()

    df = pd.DataFrame(hist['data'], columns=['datetime','open','high','low','close','volume'])
    df['ema9'] = df['close'].ewm(span=9, adjust=False).mean()
    df['ema21'] = df['close'].ewm(span=21, adjust=False).mean()
    d = df['close'].diff()
    gain = d.clip(lower=0).ewm(alpha=1/14, adjust=False).mean()
    loss = -d.clip(upper=0).ewm(alpha=1/14, adjust=False).mean()
    df['rsi'] = 100 - (100 / (1 + gain/loss.replace(0, np.nan)))
    df['vwap'] = (df['close']*df['volume']).cumsum() / df['volume'].cumsum()
    last = df.iloc[-1]
    if last['ema9'] > last['ema21'] and last['close'] > last['vwap'] and 50 < last['rsi'] < 70:
        return "BUY", last, df
    elif last['ema9'] < last['ema21'] and last['close'] < last['vwap'] and 30 < last['rsi'] < 50:
        return "SELL", last, df
    else:
        return "WAIT", last, df

def place_order(smart, signal, underlying_ltp):
    if st.session_state['trades'] >= MAX_TRADES:
        st.warning("Max Trades zale!")
        return
    symbol, token, atm, ltp = get_atm_option(smart, signal, underlying_ltp)
    if not token: return
    opt_ltp = smart.ltpData(cfg["opt_exchange"], symbol, token)['data']['ltp']
    st.info(f"{INSTRUMENT} LTP: {ltp} | ATM: {atm} | Symbol: {symbol} | Premium: ₹{opt_ltp} | Qty: {QTY}")
    if not LIVE_MODE:
        st.warning(f"PAPER ORDER: {signal} {symbol} @ ₹{opt_ltp} - LIVE OFF aahe")
        return
    try:
        orderparams = {
            "variety": "NORMAL", "tradingsymbol": symbol, "symboltoken": token,
            "transactiontype": "BUY", "exchange": cfg["opt_exchange"],
            "ordertype": "MARKET", "producttype": "INTRADAY", "duration": "DAY",
            "price": "0",
            "squareoff": str(int(TARGET_POINTS * 100)),
            "stoploss": str(int(SL_POINTS * 100)),
            "quantity": str(QTY)
        }
        oid = smart.placeOrder(orderparams)
        st.success(f"✅ LIVE ORDER GELI! {oid} | {symbol}")
        st.session_state['trades'] += 1
    except Exception as e:
        st.error(f"Order Fail: {e}")

if st.button("🚀 Connect + Signal Check + Trade", type="primary"):
    smart = get_connection()
    if smart:
        st.success("Angel Connected!")
        signal, last, df = get_signal(smart)
        if last is None or df.empty:
            st.stop()
        c1, c2, c3, c4 = st.columns(4)
        c1.metric(f"{INSTRUMENT}", f"{last['close']:.2f}")
        c2.metric("EMA 9/21", f"{last['ema9']:.1f} / {last['ema21']:.1f}")
        c3.metric("RSI", f"{last['rsi']:.1f}")
        c4.metric("VWAP", f"{last['vwap']:.1f}")
        if signal == "BUY":
            st.success(f"### SIGNAL: BUY - CALL (CE) - {INSTRUMENT}")
            place_order(smart, "BUY", last['close'])
        elif signal == "SELL":
            st.error(f"### SIGNAL: SELL - PUT (PE) - {INSTRUMENT}")
            place_order(smart, "SELL", last['close'])
        else:
            st.warning("### SIGNAL: WAIT")
        st.line_chart(df.set_index('datetime')[['close','ema9','ema21','vwap']].tail(50))

st.caption("NIFTY 25 Qty | CRUDE MINI 10 Qty | GOLD MINI 1 Qty.")
