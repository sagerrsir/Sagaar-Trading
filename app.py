import streamlit as st
import os
import pyotp
from SmartApi import SmartConnect

def get_secret(name):
    try:
        if name in st.secrets:
            return st.secrets[name]
    except:
        pass
    return os.getenv(name)

API_KEY = get_secret("API_KEY") or get_secret("ANGEL_API_KEY")
CLIENT_CODE = get_secret("CLIENT_CODE") or get_secret("ANGEL_CLIENT_CODE")
MPIN = get_secret("MPIN")
TOTP_KEY = get_secret("TOTP_KEY")

def get_connection():
    if not API_KEY or not CLIENT_CODE or not MPIN or not TOTP_KEY:
        st.error(f"Key missing - API:{bool(API_KEY)} Client:{bool(CLIENT_CODE)} MPIN:{bool(MPIN)} TOTP:{bool(TOTP_KEY)}")
        return None
    
    try:
        smart = SmartConnect(api_key=API_KEY)
        totp = pyotp.TOTP(TOTP_KEY).now()
        data = smart.generateSession(CLIENT_CODE, MPIN, totp)
        
        # Hach khara check aahe
        if data and data.get('status') == True:
            return smart
        else:
            st.error(f"Login Failed: {data.get('message') if data else 'No response'}")
            return None
    except Exception as e:
        st.error(f"Login Error: {e}")
        return None

def get_price(smart, exchange, symbol, token):
    try:
        data = smart.ltpData(exchange, symbol, token)
        if data and data.get('status'):
            return data['data']['ltp']
    except Exception as e:
        st.warning(f"{symbol} error: {e}")
    return None

# Vapar asa kar:
# smart = get_connection()
# if smart:
#     nifty = get_price(smart, "NSE", "NIFTY", "26000")
#     banknifty = get_price(smart, "NSE", "BANKNIFTY", "26009")
#     sensex = get_price(smart, "BSE", "SENSEX", "1")
#     st.write(nifty, banknifty, sensex)
