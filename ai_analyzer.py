import os
import json
import requests

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

def call_gemini_api(prompt):
    """ Google Gemini API Call කිරීම සඳහා වන Common Function එක """
    if not GEMINI_API_KEY:
        print("⚠️ Gemini API Key missing!")
        return None

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
            
            response = requests.post(url, json=payload, headers=headers, timeout=12)
            if response.status_code == 200:
                res_data = response.json()
                return res_data['candidates'][0]['content']['parts'][0]['text']
        except Exception as e:
            continue

    print("❌ All Gemini AI models failed.")
    return None

def ai_evaluate_market_candidates(candidates_data):
    """ Market එකේ Candidates අතරින් හොදම High-Winrate Trade Setup එක AI එකෙන් සොයා ගැනීම """
    prompt = f"""
    You are an Expert Crypto Quant Trader and Market Analyst AI.
    Analyze these top crypto candidates gathered from 15m timeframe data:

    {json.dumps(candidates_data, indent=2)}

    Task:
    1. Select ONLY ONE best high-probability trade candidate (LONG or SHORT) with a win probability > 80%.
    2. If no candidate has a strong setup, explicitly respond with: "NO_TRADE".
    3. If a solid setup is found, return ONLY a strict JSON object (no markdown, no extra explanation) in this exact format:

    {{
        "symbol": "BTC/USDT",
        "side": "LONG 🟢" or "SHORT 🔴",
        "reason": "1 short sentence why this is a high conviction setup based on EMA/RSI/Volume",
        "confidence": 85
    }}
    """
    return call_gemini_api(prompt)

def get_ai_trade_decision(signal, current_price, rsi, ema_fast, ema_slow):
    """ Active Trade එක AI එක හරහා Monitor කර Decision එකක් ගැනීම """
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
    return call_gemini_api(prompt)
