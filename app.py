import streamlit as st
import pandas as pd
import numpy as np

st.set_page_config(page_title="SAGAR AUTO TRADER - Paper", layout="wide")
st.title("SAGAR AUTO TRADER - PAPER TRADING")

# --- Strategy Functions ---
def ema(s, n):
    return s.ewm(span=n, adjust=False).mean()

def rsi(s, n=14):
    d = s.diff()
    gain = d.clip(lower=0).ewm(alpha=1/n, adjust=False).mean()
    loss = -d.clip(upper=0).ewm(alpha=1/n, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))

def get_signal(df):
    df = df.copy()
    df['ema9'] = ema(df['close'], 9)
    df['ema21'] = ema(df['close'], 21)
    df['rsi'] = rsi(df['close'], 14)
    df['vwap'] = (df['close'] * df['volume']).cumsum() / df['volume'].cumsum()
    
    last = df.iloc[-1]
    prev = df.iloc[-2]
    
    # BUY: EMA9 > EMA21, Price > VWAP, RSI 50-70
    if last['ema9'] > last['ema21'] and last['close'] > last['vwap'] and 50 < last['rsi'] < 70:
        return "BUY", last
    # SELL: EMA9 < EMA21, Price < VWAP, RSI 30-50
    elif last['ema9'] < last['ema21'] and last['close'] < last['vwap'] and 30 < last['rsi'] < 50:
        return "SELL", last
    else:
        return "WAIT", last

# --- UI ---
uploaded = st.file_uploader("CSV upload kar: datetime,open,high,low,close,volume", type="csv")

if uploaded:
    df = pd.read_csv(uploaded)
    df['datetime'] = pd.to_datetime(df['datetime'])
    signal, last = get_signal(df)
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("LTP", f"{last['close']:.2f}")
    c2.metric("EMA 9 / 21", f"{last['ema9']:.2f} / {last['ema21']:.2f}")
    c3.metric("RSI 14", f"{last['rsi']:.1f}")
    c4.metric("VWAP", f"{last['vwap']:.2f}")

    if signal == "BUY":
        st.success(f"### SIGNAL: BUY @ {last['close']:.2f} - PAPER ONLY")
    elif signal == "SELL":
        st.error(f"### SIGNAL: SELL @ {last['close']:.2f} - PAPER ONLY")
    else:
        st.warning(f"### SIGNAL: WAIT - No Trade")

    st.line_chart(df.set_index('datetime')[['close','ema9','ema21','vwap']].tail(100))
    st.dataframe(df.tail(20))
else:
    st.info("Aadhi CSV upload kar. Sample sathi Nifty cha 15-min data ghe.")

st.divider()
st.caption("PAPER TRADING ONLY - Angel One la login nahi, khari order jat nahi. ₹10,000 capital madhe pan loss hou shakto.")
