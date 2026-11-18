# SAGAR AUTO TRADER — प्रारंभिक आवृत्ती

ही आवृत्ती **फक्त PAPER TRADING / संकेत तपासणीसाठी** आहे. यात Angel One ला लॉगिन होत नाही आणि कोणतीही खरी ऑर्डर जात नाही.

## संगणकावर सुरू करण्याची पद्धत

1. Python 3.10 किंवा नवीन आवृत्ती स्थापित करा.
2. ZIP extract करा.
3. त्या फोल्डरमध्ये Terminal / Command Prompt उघडा.
4. खालील कमांड चालवा:

```bash
python -m venv .venv
```

Windows:
```bash
.venv\Scripts\activate
```

Mac/Linux:
```bash
source .venv/bin/activate
```

नंतर:
```bash
pip install -r requirements.txt
streamlit run app.py
```

ब्राउजरमध्ये स्थानिक dashboard उघडेल. मोबाइलवर वापरण्यासाठी पुढील टप्प्यात सुरक्षित hosting आणि login जोडावे लागेल.

## CSV डेटा स्वरूप

CSV मध्ये ही columns असावीत:
`datetime,open,high,low,close,volume`

## सध्याची रणनीती

- EMA 9 / EMA 21 trend
- RSI 14 momentum filter
- VWAP price confirmation
- Signal: BUY / SELL / WAIT

ही प्राथमिक नियमाधारित strategy आहे. AI मॉड्यूल पुढील टप्प्यात signal quality वर्गीकृत करण्यासाठी जोडले जाईल; AI ला risk limits ओलांडण्याची परवानगी नसेल.

## पुढील टप्पे

1. Angel One SmartAPI account/app setup आणि अधिकृत API documentation नुसार authentication.
2. Live market data WebSocket integration.
3. Historical data backtesting, brokerage/slippage समाविष्ट करून.
4. Paper order simulator, order-state reconciliation आणि kill switch.
5. Angel One / exchange च्या लागू algo नियमांची पडताळणी झाल्यावरच live execution.

## सुरक्षा

- API key, PIN, TOTP secret, password किंवा access token कोणालाही पाठवू नका.
- Credentials फक्त स्वतःच्या सुरक्षित मशीन/secret manager मध्ये ठेवा.
- Live trading code या starter मध्ये मुद्दाम समाविष्ट केलेला नाही.
- ₹10,000 भांडवलात नुकसान होऊ शकते; नफा निश्चित नाही.
