import os
import requests

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

def get_ai_trade_decision(signal, current_price, rsi, ema_fast, ema_slow):
    """ Google Gemini AI Model එක හරහා Live Trade Analysis එකක් ලබා ගැනීම """
    if not GEMINI_API_KEY:
        print("⚠️ Gemini API Key missing!")
        return None

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

    Instructions:
    Generate a short, attractive, professional Telegram VIP update message in English with emojis.
    Determine the primary AI Recommendation Action: (Options: 🟢 HOLD & WAIT, 🎯 MOVE SL TO ENTRY, 💰 TAKE PARTIAL PROFIT, 🔴 CLOSE POSITION NOW).
    Provide 1 sentence reason explaining WHY based on RSI/Price movement.

    Output format:
    🤖 **AI TRADE MANAGEMENT UPDATE** 🤖

    📌 **Pair:** #{signal['symbol'].replace('/', '')}
    📊 **Status:** [Action Recommendation]
    📈 **Current PnL:** {pnl_pct:+.2f}%

    💡 **AI Analysis:** [1 sentence explanation]
    🛡️ **Action Plan:** [Clear instructions for members]
    """

    models_to_try = [
        "gemini-2.5-flash",
        "gemini-1.5-flash",
        "gemini-2.0-flash"
    ]

    for model in models_to_try:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}"
            headers = {'Content-Type': 'application/json'}
            payload = {"contents": [{"parts": [{"text": prompt}]}]}
            
            response = requests.post(url, json=payload, headers=headers, timeout=10)
            if response.status_code == 200:
                res_data = response.json()
                return res_data['candidates'][0]['content']['parts'][0]['text']
        except Exception as e:
            continue

    print("❌ All Gemini AI models failed.")
    return None
