import streamlit as st
import os
import pyotp
from SmartApi import SmartConnect

def get_secret(name):
    # 1. Aadhi Streamlit Secrets madhe bagh
    try:
        if name in st.secrets:
            return st.secrets[name]
    except:
        pass
    # 2. Nahi milala tar .env / os.getenv madhe bagh
    return os.getenv(name)

API_KEY = get_secret("API_KEY")
CLIENT_CODE = get_secret("CLIENT_CODE")
MPIN = get_secret("MPIN")
TOTP_KEY = get_secret("TOTP_KEY")

# Jar nav vegle asel tar he pan try kar
if not API_KEY:
    API_KEY = get_secret("ANGEL_API_KEY")
if not CLIENT_CODE:
    CLIENT_CODE = get_secret("ANGEL_CLIENT_CODE")

def get_connection():
    try:
        if not API_KEY or not CLIENT_CODE or not MPIN or not TOTP_KEY:
            print("Key missing:", bool(API_KEY), bool(CLIENT_CODE), bool(MPIN), bool(TOTP_KEY))
            return None
        
        smart = SmartConnect(api_key=API_KEY)
        totp = pyotp.TOTP(TOTP_KEY).now()
        data = smart.generateSession(CLIENT_CODE, MPIN, totp)
        return smart
    except Exception as e:
        print("Login Error:", e)
        return None

def get_nifty_price(smart):
    try:
        data = smart.ltpData("NSE", "NIFTY", "26000")
        return data['data']['ltp']
    except:
        return None

def get_banknifty_price(smart):
    try:
        data = smart.ltpData("NSE", "BANKNIFTY", "26009")
        return data['data']['ltp']
    except:
        return None

def get_sensex_price(smart):
    try:
        data = smart.ltpData("BSE", "SENSEX", "1")
        return data['data']['ltp']
    except:
        return None
