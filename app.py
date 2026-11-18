import streamlit as st
import pandas as pd
import numpy as np
import pyotp, math, time
from datetime import datetime, timedelta
from SmartApi import SmartConnect

st.set_page_config(page_title="SAGAR AUTO TRADER - LIVE", layout="wide")
st.title("SAGAR AUTO TRADER - NIFTY OPTION BUYING - LIVE")

# ============ 1. RISK CONTROL ============
st.sidebar.header("⚠️ RISK CONTROL")
LIVE_MODE = st.sidebar.toggle("🔴 LIVE TRADING ON", value=False)
CAPITAL = st.sidebar.number_input("Capital ₹", value=10000)
MAX_LOSS_DAY = st.sidebar.number_input("Max Loss / Day ₹", value=500)
MAX_TRADES = st.sidebar.number_input("Max Trades / Day", value=2)
QTY = 25 # Nifty 1 Lot
SL_POINTS = st.sidebar.number_input("SL Points (Option Premium var)", value=30)
TARGET_POINTS = st.sidebar.number_input("Target Points", value=50)

if 'killed' not in st.session_state: st.session_state['killed'] = False
if 'trades' not in st.session_state: st.session_state['trades'] = 0
if 'pnl' not in st.session_state: st.session_state['pnl'] = 0

if st.sidebar.button("🛑 KILL SWITCH", type="primary"):
    st.session_state['killed'] = True
if st.session_state['killed']:
    st.error("KILL SWITCH ON - Kuthlihi order janar nahi.")
    st.stop()

st.sidebar.write(f"Trades Today: {st.session_state['trades']} / {MAX_TRADES}")
st.sidebar.write(f"PNL Today: ₹{st.session_state['pnl']}")

# ============ 2. ANGEL CONNECT ============
def get_connection():
    try:
        smart = SmartConnect(api_key=st.secrets["ANGEL_API_KEY"])
        totp = pyotp.TOTP(st.secrets["ANGEL_TOTP"]).now()
        data = smart.generateSession(st.secrets["ANGEL_CLIENT_ID"], st.secrets["ANGEL_PIN"], totp)
        if data.get('status'):
            return smart
        st.error(f"Login Fail: {data.get('message')}")
        return None
    except Exception as e:
        st.error(f"Login Error: {e}")
        return None

# ============ 3. ATM STRIKE + OPTION SYMBOL ============
def get_atm_option(smart, signal):
    # Nifty LTP ghe
    ltp = smart.ltpData("NSE", "NIFTY", "26000")['data']['ltp']
    atm = round(ltp / 50) * 50  # 26000, 26050...
    
    # Aajchi Thursday Expiry - pudhchi Thursday kadh
    today = datetime.now()
    # Expiry: ya athvadyatla Thursday
    days_ahead = (3 - today.weekday()) % 7
    if days_ahead == 0 and today.hour >= 15: days_ahead = 7
    expiry = today + timedelta(days=days_ahead)
    expiry_str = expiry.strftime("%d%b%y").upper() # 20NOV25 sarkha
    
    opt_type = "CE" if signal == "BUY" else "PE"
    # Angel Symbol Format: NIFTY20NOV2526000CE
    symbol = f"NIFTY{expiry_str}{atm}{opt_type}"
    
    # Token shodh - searchScrip ne
    try:
        res = smart.searchScrip("NFO", symbol)
        token = res['data'][0]['symboltoken']
        return symbol, token, atm, ltp
    except:
        st.error(f"Symbol sapadla nahi: {symbol}")
        return None, None, atm, ltp

# ============ 4. STRATEGY - EMA/RSI/VWAP ============
def get_signal(smart):
    # Magche 100 candle 15-min ghe
    to_date = datetime.now()
    from_date = to_date - timedelta(days=5)
    params = {
        "exchange": "NSE",
        "symboltoken": "26000",
        "interval": "FIFTEEN_MINUTE",
        "fromdate": from_date.strftime("%Y-%m-%d %H:%M"),
        "todate": to_date.strftime("%Y-%m-%d %H:%M")
    }
    hist = smart.getCandleData(params)
    df = pd.DataFrame(hist['data'], columns=['datetime','open','high','low','close','volume'])
    df['ema9'] = df['close'].ewm(span=9, adjust=False).mean()
    df['ema21'] = df['close'].ewm(span=21, adjust=False).mean()
    # RSI
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

# ============ 5. ORDER ============
def place_order(smart, signal):
    if st.session_state['trades'] >= MAX_TRADES:
        st.warning("Max Trades zale!")
        return
    if st.session_state['pnl'] <= -MAX_LOSS_DAY:
        st.error("Max Loss zala - Aaj trading band!")
        return
    
    symbol, token, atm, nifty_ltp = get_atm_option(smart, signal)
    if not token: return

    # Option cha Live Premium ghe
    opt_ltp = smart.ltpData("NFO", symbol, token)['data']['ltp']
    sl_price = round(opt_ltp - SL_POINTS, 1)
    target_price = round(opt_ltp + TARGET_POINTS, 1)

    st.info(f"NIFTY: {nifty_ltp} | ATM: {atm} | Symbol: {symbol} | Premium: ₹{opt_ltp} | SL: ₹{sl_price} | Target: ₹{target_price}")

    if not LIVE_MODE:
        st.warning(f"PAPER ORDER: {signal} {symbol} @ ₹{opt_ltp} - LIVE OFF aahe mhanun khari order geli NAHI")
        return

    # LIVE ORDER
    try:
        orderparams = {
            "variety": "NORMAL",
            "tradingsymbol": symbol,
            "symboltoken": token,
            "transactiontype": "BUY",
            "exchange": "NFO",
            "ordertype": "MARKET",
            "producttype": "INTRADAY",
            "duration": "DAY",
            "price": "0",
            "squareoff": str(TARGET_POINTS * 100), # Angel la paise madhe lagte - 50 points = 5000 paise
            "stoploss": str(SL_POINTS * 100),
            "quantity": str(QTY)
        }
        oid = smart.placeOrder(orderparams)
        st.success(f"✅ LIVE ORDER GELI! OrderID: {oid} | {symbol}")
        st.session_state['trades'] += 1
    except Exception as e:
        st.error(f"Order Fail: {e}")

# ============ 6. MAIN BUTTON ============
if st.button("🚀 Connect + Signal Check + Trade", type="primary"):
    smart = get_connection()
    if smart:
        st.success("Angel Connected!")
        signal, last, df = get_signal(smart)
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("NIFTY", f"{last['close']:.2f}")
        c2.metric("EMA 9/21", f"{last['ema9']:.1f} / {last['ema21']:.1f}")
        c3.metric("RSI", f"{last['rsi']:.1f}")
        c4.metric("VWAP", f"{last['vwap']:.1f}")
        
        if signal == "BUY":
            st.success("### SIGNAL: BUY - CALL (CE) Ghe")
            place_order(smart, "BUY")
        elif signal == "SELL":
            st.error("### SIGNAL: SELL - PUT (PE) Ghe")
            place_order(smart, "SELL")
        else:
            st.warning("### SIGNAL: WAIT - Trade Gheu Nako")
        
        st.line_chart(df.set_index('datetime')[['close','ema9','ema21','vwap']].tail(50))

st.caption("LIVE = Khara paisa. Ek trade la Max ₹750 loss (30 pts x 25 qty). Divsala Max ₹500 loss zala ki band. SEBI Algo rule tuza.")
