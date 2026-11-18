import os
import pyotp
from dotenv import load_dotenv
from SmartApi import SmartConnect

load_dotenv()

def get_connection():
    try:
        # Donhi naav chaltil - CODE kinva ID
        client_id = os.getenv("ANGEL_CLIENT_ID") or os.getenv("ANGEL_CLIENT_CODE")
        totp_secret = os.getenv("ANGEL_TOTP") or os.getenv("ANGEL_TOTP_SECRET")
        
        if totp_secret and len(totp_secret) > 6:
            totp_code = pyotp.TOTP(totp_secret).now()
        else:
            totp_code = totp_secret

        smart = SmartConnect(api_key=os.getenv("ANGEL_API_KEY"))
        data = smart.generateSession(client_id, os.getenv("ANGEL_PIN"), totp_code)
        print("Login Success!")
        return smart
    except Exception as e:
        print(f"Login Fail: {e}")
        return None

def get_nifty_price(smart):
    try:
        ltp = smart.ltpData("NSE", "NIFTY", "26000")
        return ltp['data']['ltp']
    except: return None

def get_banknifty_price(smart):
    try:
        ltp = smart.ltpData("NSE", "NIFTY BANK", "26009")
        return ltp['data']['ltp']
    except: return None

def get_sensex_price(smart):
    try:
        ltp = smart.ltpData("BSE", "SENSEX", "1")
        return ltp['data']['ltp']
    except: return None