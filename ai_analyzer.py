import os
import json
import requests
import time

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

def call_gemini_api(prompt):
    """ Fast & Resilient Gemini API Call with Auto-Retry & Backoff """
    if not GEMINI_API_KEY:
        print("⚠️ GEMINI_API_KEY missing in Secrets!")
        return None

    api_configs = [
        ("v1beta", "gemini-2.0-flash"),
        ("v1beta", "gemini-2.5-flash"),
        ("v1beta", "gemini-1.5-flash")
    ]

    for api_version, model in api_configs:
        for attempt in range(2):  # Model එකකට දෙපාරක් Try කරයි
            try:
                url = f"https://generativelanguage.googleapis.com/{api_version}/models/{model}:generateContent?key={GEMINI_API_KEY}"
                headers = {'Content-Type': 'application/json'}
                payload = {"contents": [{"parts": [{"text": prompt}]}]}
                
                # Timeout එක තත්පර 25 දක්වා වැඩි කළා
                response = requests.post(url, json=payload, headers=headers, timeout=25)
                
                if response.status_code == 200:
                    res_data = response.json()
                    return res_data['candidates'][0]['content']['parts'][0]['text']
                elif response.status_code == 429:
                    print(f"⚠️ [{model}] Rate limit (429). Retrying in 6s (Attempt {attempt+1}/2)...")
                    time.sleep(6)  # 429 එකට තත්පර 6ක් Pause වෙලා Retry කරයි
                else:
                    print(f"⚠️ [{model}] Error ({response.status_code}): {response.text[:100]}")
                    break
            except requests.exceptions.Timeout:
                print(f"⌛ [{model}] Timeout on attempt {attempt+1}. Retrying...")
                time.sleep(2)
            except Exception as e:
                print(f"❌ Exception [{model}]: {e}")
                break

    print("❌ All Gemini API configs failed. Free API quota might be temporarily busy.")
    return None

def ai_evaluate_market_candidates(candidates_data):
    """ Ultra-Fast Evaluation Prompt """
    prompt = f"""
    You are a Crypto Quant AI. Analyze these top 3 pre-filtered candidates:
    {json.dumps(candidates_data, indent=2)}

    Rules:
    1. NEVER LONG a crashing coin (-10%+ drop).
    2. Pick ONE best setup (>80% win prob) aligned with tv_rating/rsi.
    3. If no setup, reply: "NO_TRADE".
    4. Return ONLY raw JSON (no markdown):
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
    You are a Crypto VIP Assistant AI. Analyze active trade:
    - Pair: {signal['symbol']} | Side: {side} | Entry: {entry} | Current: {current_price} | PnL: {pnl_pct:.2f}%
    - TP1: {signal['tp1']} | TP4: {signal['tp4']} | SL: {signal['sl']} | RSI: {rsi:.1f}

    Generate short Telegram VIP update in English with emojis.
    Provide Recommendation (🟢 HOLD & WAIT, 🎯 MOVE SL TO ENTRY, 💰 TAKE PARTIAL PROFIT, 🔴 CLOSE POSITION NOW) + 1 sentence reason.
    """
    return call_gemini_api(prompt)
