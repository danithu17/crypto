import os
import json
import requests
import time

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

def call_gemini_api(prompt):
    """ Google Gemini API Call කිරීම (Error Logging + Rate Limit Delay සහිතව) """
    if not GEMINI_API_KEY:
        print("⚠️ Gemini API Key missing!")
        return None

    models_to_try = [
        "gemini-1.5-flash",
        "gemini-1.5-pro",
        "gemini-2.0-flash-exp"
    ]

    for model in models_to_try:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}"
            headers = {'Content-Type': 'application/json'}
            payload = {"contents": [{"parts": [{"text": prompt}]}]}
            
            response = requests.post(url, json=payload, headers=headers, timeout=12)
            
            if response.status_code == 200:
                res_data = response.json()
                time.sleep(2)  # Rate Limit වැළැක්වීමට තත්පර 2ක Delay එකක්
                return res_data['candidates'][0]['content']['parts'][0]['text']
            else:
                print(f"⚠️ Model {model} Error ({response.status_code}): {response.text[:100]}")
        except Exception as e:
            print(f"❌ Exception with {model}: {e}")

    print("❌ All Gemini AI models failed.")
    return None

def ai_evaluate_market_candidates(candidates_data):
    """ Market Candidate Analysis """
    prompt = f"""
    You are an Expert Crypto Quant Trader AI.
    Analyze these market candidates:

    {json.dumps(candidates_data, indent=2)}

    Select ONLY ONE best setup (>80% win probability). If none, respond with "NO_TRADE".
    If valid, return ONLY JSON:
    {{
        "symbol": "BTC/USDT",
        "side": "LONG 🟢" or "SHORT 🔴",
        "reason": "1 short sentence explanation",
        "confidence": 85
    }}
    """
    return call_gemini_api(prompt)

def get_ai_trade_decision(signal, current_price, rsi, ema_fast, ema_slow):
    """ Active Trade Live Analysis """
    side = signal['side']
    entry = signal['entry']
    pnl_pct = ((current_price - entry) / entry) * 100 if "LONG" in side else ((entry - current_price) / entry) * 100
    
    prompt = f"""
    You are a professional Crypto VIP Trading Assistant AI. Analyze this active trade:

    - Pair: {signal['symbol']}
    - Position Side: {side}
    - Entry Price: {entry}
    - Current Live Price: {current_price}
    - Current PnL Percentage: {pnl_pct:.2f}%
    - TP1: {signal['tp1']} | TP2: {signal['tp2']} | TP3: {signal['tp3']} | TP4: {signal['tp4']}
    - Stop Loss: {signal['sl']}
    - Current 15m RSI: {rsi:.2f}
    - EMA 9: {ema_fast:.4f} | EMA 21: {ema_slow:.4f}

    Generate a short, attractive Telegram VIP update with emojis.
    Provide Action Recommendation (🟢 HOLD & WAIT, 🎯 MOVE SL TO ENTRY, 💰 TAKE PARTIAL PROFIT, 🔴 CLOSE POSITION NOW) and 1 sentence reason.
    """
    return call_gemini_api(prompt)
