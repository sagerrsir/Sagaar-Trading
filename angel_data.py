import os
import pyotp
import streamlit as st
from dotenv import load_dotenv
from SmartApi import SmartConnect

load_dotenv()

def get_val(*names):
    # 1. Streamlit Secrets, 2. .env
    for n in names:
        try:
            if n in st.secrets:
                return st.secrets[n]
        except:
            pass
        v = os.getenv(n)
        if v:
            return v
    return None

def get_connection():
    api_key = get_val("ANGEL_API_KEY", "API_KEY")
    client_id = get_val("ANGEL_CLIENT_ID", "ANGEL_CLIENT_CODE", "CLIENT_CODE")
    pin = get_val("ANGEL_PIN", "ANGEL_MPIN", "MPIN")
    totp_secret = get_val("ANGEL_TOTP", "ANGEL_TOTP_SECRET", "TOTP_KEY")

    if not all([api_key, client_id, pin, totp_secret]):
        print(f"Missing: API={bool(api_key)} ID={bool(client_id)} PIN={bool(pin)} TOTP={bool(totp_secret)}")
        return None

    try:
        # Secret 16+ char asel tar TOTP banav, nahi tar direct code samaj
        totp_code = pyotp.TOTP(totp_secret).now() if len(totp_secret) > 6 else totp_secret

        smart = SmartConnect(api_key=api_key)
        data = smart.generateSession(client_id, pin, totp_code)

        if data and data.get('status') == True:
            print("Login Success!")
            return smart
        else:
            print(f"Login Fail: {data.get('message') if data else 'No response'}")
            return None
    except Exception as e:
        print(f"Login Fail: {e}")
        return None

def get_price(smart, exchange, symbol, token):
    try:
        ltp = smart.ltpData(exchange, symbol, token)
        if ltp and ltp.get('status'):
            return ltp['data']['ltp']
    except:
        pass
    return None

# Vapar:
# smart = get_connection()
# if smart:
#     print("NIFTY:", get_price(smart, "NSE", "NIFTY", "26000"))
#     print("BANKNIFTY:", get_price(smart, "NSE", "BANKNIFTY", "26009")) # NIFTY BANK NAHI
#     print("SENSEX:", get_price(smart, "BSE", "SENSEX", "1"))
