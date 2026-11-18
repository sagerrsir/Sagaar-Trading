import streamlit as st
import pandas as pd
import numpy as np
import os, pyotp
from SmartApi import SmartConnect

st.set_page_config(page_title="SAGAR AUTO TRADER - LIVE", layout="wide")
st.title("SAGAR AUTO TRADER - LIVE")

# --- SAFETY SETTINGS ---
st.sidebar.header("⚠️ RISK CONTROL - Ha badlu nakos")
LIVE_MODE = st.sidebar.toggle("LIVE TRADING ON", value=False, help="OFF asel tar fakt Paper signal yeil, order janar nahi")
CAPITAL = st.sidebar.number_input("Capital ₹", value=10000)
MAX_LOSS_PER_DAY = st.sidebar.number_input("Max Loss / Day ₹", value=500)
MAX_TRADES = st.sidebar.number_input("Max Trades / Day", value=2)
QTY = st.sidebar.number_input("Qty (Lot)", value=25) # Nifty 1 Lot = 25
KILL_SWITCH = st.sidebar.button("🛑 KILL SWITCH - Sagla Band Kar", type="primary")

if KILL_SWITCH:
    st.session_state['killed'] = True
if 'killed' in st.session_state and st.session_state['killed']:
    st.error("KILL SWITCH ON aahe - Kuthlihi order janar nahi.")
    st.stop()

if 'trades_today' not in st.session_state:
    st.session_state['trades_today'] = 0
if 'pnl_today' not in st.session_state:
    st.session_state['pnl_today'] = 0

# --- ANGEL LOGIN ---
def get_connection():
    try:
        api_key = st.secrets["ANGEL_API_KEY"]
        client = st.secrets["ANGEL_CLIENT_ID"]
        pin = st.secrets["ANGEL_PIN"]
        totp_secret = st.secrets["ANGEL_TOTP"]
        smart = SmartConnect(api_key=api_key)
        totp = pyotp.TOTP(totp_secret).now()
        data = smart.generateSession(client, pin, totp)
        if data.get('status'):
            return smart
        else:
            st.error(f"Login Fail: {data.get('message')}")
            return None
    except Exception as e:
        st.error(f"Login Error: {e}")
        return None

def place_live_order(smart, signal, price):
    # Risk Check
    if st.session_state['trades_today'] >= MAX_TRADES:
        st.warning("Max Trades zale - Aajun order nahi")
        return None
    if st.session_state['pnl_today'] <= -MAX_LOSS_PER_DAY:
        st.error("Max Loss zala - Trading band")
        return None

    if not LIVE_MODE:
        st.info(f"PAPER ORDER: {signal} @ {price} - Khari order geli NAHI (LIVE OFF aahe)")
        return "PAPER"

    # --- KHARI ORDER ITHE JATE ---
    try:
        orderparams = {
            "variety": "NORMAL",
            "tradingsymbol": "NIFTY", # Option sathi ithe Symbol badlel - उदा. NIFTY26NOV26000CE
            "symboltoken": "26000",
            "transactiontype": "BUY" if signal=="BUY" else "SELL",
            "exchange": "NFO",
            "ordertype": "MARKET",
            "producttype": "INTRADAY",
            "duration": "DAY",
            "price": "0",
            "squareoff": "0",
            "stoploss": "0",
            "quantity": str(QTY)
        }
        order_id = smart.placeOrder(orderparams)
        st.success(f"LIVE ORDER GELI! OrderID: {order_id}")
        st.session_state['trades_today'] += 1
        return order_id
    except Exception as e:
        st.error(f"Order Fail: {e}")
        return None

# --- MAIN ---
if st.button("Connect Angel + Signal Check Kar"):
    smart = get_connection()
    if smart:
        st.success("Angel Connected!")
        # Live LTP
        ltp_data = smart.ltpData("NSE", "NIFTY", "26000")
        ltp = ltp_data['data']['ltp']
        st.metric("NIFTY LTP", ltp)

        # Ithe tuzi EMA/RSI/VWAP strategy yeil - aata sample sathi
        # CSV varun ki Live Candle varun signal kadhaycha
        signal = "WAIT" # Tuza strategy ithe call kar
        st.write(f"Signal: {signal}")

        if signal in ["BUY", "SELL"]:
            place_live_order(smart, signal, ltp)

st.caption("LIVE = Khara paisa. SEBI / Exchange cha Algo rule palan karne tuzi jababdari aahe. ₹10,000 madhe loss hou shakto.")
