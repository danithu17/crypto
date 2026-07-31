import os
import json
import requests
import time

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

def call_gemini_api(prompt):
    """ Google Gemini API Call කිරීම (Rate Limit Guard + 30s Timeout) """
    if not GEMINI_API_KEY:
        print("⚠️ GEMINI_API_KEY is missing in GitHub Workflow Secrets!")
        return None

    # Active and Valid Models Only
    api_configs = [
        ("v1beta", "gemini-2.5-flash"),
        ("v1beta", "gemini-2.0-flash")
    ]

    for api_version, model in api_configs:
        try:
            url = f"https://generativelanguage.googleapis.com/{api_version}/models/{model}:generateContent?key={GEMINI_API_KEY}"
            headers = {'Content-Type': 'application/json'}
            payload = {"contents": [{"parts": [{"text": prompt}]}]}
            
            # Timeout 30 seconds
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            
            if response.status_code == 200:
                res_data = response.json()
                time.sleep(1) # Small pause
                return res_data['candidates'][0]['content']['parts'][0]['text']
            elif response.status_code == 429:
                print(f"⚠️ [{model}] 429 Rate limit hit. Waiting 5s before fallback...")
                time.sleep(5)
            else:
                print(f"⚠️ [{model}] Response ({response.status_code}): {response.text[:120]}")
        except Exception as e:
            print(f"❌ Exception [{model}]: {e}")

    print("❌ All Gemini API configs failed. Free API quota might be temporarily exhausted. Please wait 5 mins.")
    return None

def ai_evaluate_market_candidates(candidates_data):
    """ Market Candidate Analysis """
    prompt = f"""
    You are an Expert Crypto Quant Trader AI.
    Analyze these highly pre-filtered market candidates (15m timeframe data + TradingView technicals):

    {json.dumps(candidates_data, indent=2)}

    Task:
    1. Select ONLY ONE best high-probability trade candidate (LONG or SHORT) with a win probability > 80%.
    2. Give strong preference if TradingView recommendation is 'STRONG_BUY' (for LONG) or 'STRONG_SELL' (for SHORT).
    3. If no candidate has a strong setup, explicitly respond with: "NO_TRADE".
    4. If a solid setup is found, return ONLY a valid JSON object in this exact format (no markdown):

    {{
        "symbol": "BTC/USDT",
        "side": "LONG 🟢" or "SHORT 🔴",
        "reason": "1 short sentence explanation referencing TradingView rating and momentum",
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

    Instructions:
    Generate a short, attractive, professional Telegram VIP update message in English with emojis.
    Determine Action Recommendation: (🟢 HOLD & WAIT, 🎯 MOVE SL TO ENTRY, 💰 TAKE PARTIAL PROFIT, 🔴 CLOSE POSITION NOW).
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
