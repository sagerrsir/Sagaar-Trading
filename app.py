import streamlit as st
import time
import pandas as pd
from datetime import datetime
from angel_data import get_connection, get_nifty_price, get_banknifty_price, get_sensex_price
import plotly.graph_objects as go

st.set_page_config(page_title="SAGAR AI TRADER", layout="wide")
st.title("🤖 SAGAR AI TRADER - Paper Trading")

# --- AI MEMORY ---
if "history" not in st.session_state:
    st.session_state.history = []
if "trades" not in st.session_state:
    st.session_state.trades = []
if "day_pnl" not in st.session_state:
    st.session_state.day_pnl = 0
if "ai_on" not in st.session_state:
    st.session_state.ai_on = False

# --- SIDEBAR - AI CONTROL ---
st.sidebar.header("🧠 AI Control")
st.session_state.ai_on = st.sidebar.toggle("AI AUTO MODE ON / OFF", value=st.session_state.ai_on)
max_loss = st.sidebar.number_input("Divasacha Max Tota (Rs)", value=1000)
target_per_trade = st.sidebar.number_input("Ek Trade cha Target (Points)", value=30)
stoploss_per_trade = st.sidebar.number_input("Ek Trade cha Stoploss (Points)", value=15)

if st.sidebar.button("Reset Day"):
    st.session_state.day_pnl = 0
    st.session_state.trades = []
    st.session_state.history = []
    st.rerun()

# --- LOGIN ---
smart = get_connection()
if not smart:
    st.error("Login Fail - .env tapas")
    st.stop()

# --- LIVE PRICE ---
nifty = get_nifty_price(smart)
bank = get_banknifty_price(smart)
sensex = get_sensex_price(smart)

c1, c2, c3 = st.columns(3)
c1.metric("NIFTY", nifty)
c2.metric("BANKNIFTY", bank)
c3.metric("SENSEX", sensex)

# History madhe tak
if nifty:
    st.session_state.history.append({"time": datetime.now(), "nifty": nifty, "bank": bank, "sensex": sensex})
    st.session_state.history = st.session_state.history[-50:]

# --- 🚥 SIGNAL CHART - NAVIN ---
st.subheader("🚥 Signal Chart - Nifty + Levels")

# Level Signal Logic
level_signal = "🟡 WAIT - 25200 te 25300 madhye"
level_color = "orange"
if nifty and nifty < 25200:
    level_signal = "🔴 PUT SIGNAL - 25200 chya KHALI - 25200 PE BUY"
    level_color = "red"
elif nifty and nifty > 25300:
    level_signal = "🟢 NO TRADE - 25300 chya VAR - Breakdown Fail"
    level_color = "green"

st.markdown(f"<h3 style='color:{level_color}'>{level_signal}</h3>", unsafe_allow_html=True)

if st.session_state.history:
    df = pd.DataFrame(st.session_state.history)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df["time"], y=df["nifty"], mode='lines+markers', name='Nifty', line=dict(color='blue', width=3)))
    # Levels
    fig.add_hline(y=25300, line_dash="dash", line_color="red", annotation_text="Resistance 25300")
    fig.add_hline(y=25200, line_dash="dash", line_color="green", annotation_text="Support 25200")
    # Aajcha tuzha profit level
    fig.add_hline(y=25226, line_dash="dot", line_color="purple", annotation_text="Tuza Exit 25226")
    fig.update_layout(title="Nifty Live + Levels", yaxis_title="Price", height=400)
    st.plotly_chart(fig, use_container_width=True)
else:
    st.write("Chart sathi thoda data yevu de, Refresh dab.")

# --- AI DECISION LOGIC ---
signal = "WAIT - NO TRADE"
reason = ""
color = "gray"

if len(st.session_state.history) >= 3 and st.session_state.ai_on:
    prev = st.session_state.history[-3]["nifty"]
    curr = st.session_state.history[-1]["nifty"]
    prev_bank = st.session_state.history[-3]["bank"]
    curr_bank = st.session_state.history[-1]["bank"]

    nifty_up = curr > prev
    bank_up = curr_bank > prev_bank

    if st.session_state.day_pnl <= -max_loss:
        signal = "🛑 AI STOPPED - Aajcha Tota Limit Sampala"
        reason = f"Day PNL {st.session_state.day_pnl} - Aata trade nahi"
        color = "red"
    elif nifty_up and bank_up:
        signal = "🟢 AI SAYS: BUY NIFTY"
        reason = f"NIFTY {prev} -> {curr} var, BANKNIFTY pan var. Tighe trend var aahe."
        color = "green"
    elif not nifty_up and not bank_up:
        signal = "🔴 AI SAYS: SELL NIFTY"
        reason = f"NIFTY {prev} -> {curr} khali, BANKNIFTY pan khali. Trend khali aahe."
        color = "red"
    else:
        signal = "🟡 AI SAYS: WAIT"
        reason = "NIFTY aani BANKNIFTY vegveglya dishene - Confusion aahe, trade nako"
        color = "orange"
elif not st.session_state.ai_on:
    signal = "AI BAND AAHE - ON kara"
    reason = "Sidebar madhun AI AUTO MODE ON kara"

st.markdown(f"### :{color}[{signal}]")
st.write(reason)

# --- PAPER TRADE BUTTON ---
if st.session_state.ai_on and "BUY" in signal:
    if st.button("✅ AI Signal var PAPER BUY ghe (Khara paisa nahi)"):
        entry = nifty
        st.session_state.trades.append({"time": datetime.now().strftime("%H:%M:%S"), "type": "BUY", "entry": entry, "target": entry + target_per_trade, "stoploss": entry - stoploss_per_trade, "status": "OPEN"})
        st.success(f"Paper BUY ghetla @ {entry} | Target {entry+target_per_trade} | SL {entry-stoploss_per_trade}")

if st.session_state.ai_on and "SELL" in signal:
    if st.button("✅ AI Signal var PAPER SELL ghe (Khara paisa nahi)"):
        entry = nifty
        st.session_state.trades.append({"time": datetime.now().strftime("%H:%M:%S"), "type": "SELL", "entry": entry, "target": entry - target_per_trade, "stoploss": entry + stoploss_per_trade, "status": "OPEN"})
        st.success(f"Paper SELL ghetla @ {entry} | Target {entry-target_per_trade} | SL {entry+stoploss_per_trade}")

# --- TRADES TABLE ---
st.subheader("📒 Aajche Paper Trades")
if st.session_state.trades:
    st.table(pd.DataFrame(st.session_state.trades))
    st.write(f"**Day PNL (Paper): Rs {st.session_state.day_pnl}**")
else:
    st.write("Ajun kuthla trade nahi.")

st.caption("⚠️ He fakt shiknyasathi Paper Trading aahe. Khara paisa lavnyapurvi 7 divas AI la bagh. Market madhe tota hou shakto.")
st.button("🔄 Refresh")
