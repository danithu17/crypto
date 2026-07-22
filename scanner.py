import os
import json
import requests
import ccxt
import pandas as pd
from ai_analyzer import ai_evaluate_market_candidates

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
CHAT_ID = os.environ.get("CHAT_ID", "")
TOP_COINS_LIMIT = 25 
TIMEFRAME = '15m' 
ACTIVE_SIGNAL_FILE = 'active_signal.json'
MAX_ACTIVE_SIGNALS = 2

exchange = ccxt.mexc({'enableRateLimit': True})

def load_active_signals():
    if os.path.exists(ACTIVE_SIGNAL_FILE):
        try:
            with open(ACTIVE_SIGNAL_FILE, 'r') as f:
                data = json.load(f)
                return data if isinstance(data, list) else [data]
        except Exception as e:
            print(f"Error loading active signals: {e}")
    return []

def save_active_signals(signals):
    try:
        with open(ACTIVE_SIGNAL_FILE, 'w') as f:
            json.dump(signals, f, indent=4)
    except Exception as e:
        print(f"Error saving active signals: {e}")

def calculate_ema(df, length):
    return df['close'].ewm(span=length, adjust=False).mean()

def calculate_rsi(df, length=14):
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1/length, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/length, adjust=False).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def calculate_atr(df, length=14):
    high_low = df['high'] - df['low']
    high_close = (df['high'] - df['close'].shift()).abs()
    low_close = (df['low'] - df['close'].shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return tr.ewm(alpha=1/length, adjust=False).mean()

def send_telegram_msg(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        res = requests.post(url, json=payload)
        return res.status_code == 200
    except Exception as e:
        print(f"❌ Telegram Error: {e}")
        return False

def scan_new_signals():
    active_signals = load_active_signals()
    
    if len(active_signals) >= MAX_ACTIVE_SIGNALS:
        print(f"⏸️ Active signal slots full ({len(active_signals)}/{MAX_ACTIVE_SIGNALS}). Skipping AI scan.")
        return

    print(f"🧠 Gathering market data for AI Analysis... (Active Slots: {len(active_signals)}/{MAX_ACTIVE_SIGNALS})")
    
    active_symbols = [s['symbol'] for s in active_signals]
    tickers = exchange.fetch_tickers()
    usdt_pairs = {k: v.get('quoteVolume', 0) for k, v in tickers.items() if k.endswith('/USDT') and '3L' not in k and '3S' not in k}
    sorted_symbols = sorted(usdt_pairs, key=usdt_pairs.get, reverse=True)[:TOP_COINS_LIMIT]

    market_candidates = []

    for symbol in sorted_symbols:
        if symbol in active_symbols:
            continue

        try:
            bars = exchange.fetch_ohlcv(symbol, timeframe=TIMEFRAME, limit=30)
            df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            
            df['EMA_FAST'] = calculate_ema(df, 9)
            df['EMA_SLOW'] = calculate_ema(df, 21)
            df['RSI'] = calculate_rsi(df, 14)
            df['ATR'] = calculate_atr(df, 14)

            curr = df.iloc[-1]
            prev = df.iloc[-2]

            market_candidates.append({
                "symbol": symbol,
                "price": curr['close'],
                "volume_24h": usdt_pairs[symbol],
                "rsi_15m": round(curr['RSI'], 2),
                "ema9": round(curr['EMA_FAST'], 4),
                "ema21": round(curr['EMA_SLOW'], 4),
                "ema_cross": "BULLISH_CROSS" if (prev['EMA_FAST'] <= prev['EMA_SLOW'] and curr['EMA_FAST'] > curr['EMA_SLOW']) else ("BEARISH_CROSS" if (prev['EMA_FAST'] >= prev['EMA_SLOW'] and curr['EMA_FAST'] < curr['EMA_SLOW']) else "NONE"),
                "atr": round(curr['ATR'], 6)
            })
        except Exception:
            continue

    if not market_candidates:
        print("⚠️ No valid candidates fetched.")
        return

    # 🤖 AI එකට Market Data යවා Single Best Trade එක තෝරාගැනීම
    ai_raw_res = ai_evaluate_market_candidates(market_candidates)
    
    if not ai_raw_res or "NO_TRADE" in ai_raw_res:
        print("🤖 AI Evaluated Markets: No high-probability setup found right now.")
        return

    try:
        # Clean JSON String from AI Response
        clean_json = ai_raw_res.replace("```json", "").replace("```", "").strip()
        ai_decision = json.loads(clean_json)

        selected_symbol = ai_decision['symbol']
        side = ai_decision['side']
        reason = ai_decision.get('reason', 'AI High Conviction Setup')

        # Selected Coin එකේ Full Technical Details ලබා ගැනීම
        selected_data = next((c for c in market_candidates if c['symbol'] == selected_symbol), None)
        if not selected_data:
            return

        entry = selected_data['price']
        atr_val = selected_data['atr']

        tp1 = entry + (atr_val * 2.0) if "LONG" in side else entry - (atr_val * 2.0)
        tp2 = entry + (atr_val * 4.0) if "LONG" in side else entry - (atr_val * 4.0)
        tp3 = entry + (atr_val * 6.0) if "LONG" in side else entry - (atr_val * 6.0)
        tp4 = entry + (atr_val * 8.0) if "LONG" in side else entry - (atr_val * 8.0)
        sl = entry - (atr_val * 2.0) if "LONG" in side else entry + (atr_val * 2.0)

        new_signal = {
            'symbol': selected_symbol,
            'side': side,
            'entry': entry,
            'tp1': tp1, 'tp2': tp2, 'tp3': tp3, 'tp4': tp4,
            'sl': sl,
            'last_status': "INITIAL"
        }

        active_signals.append(new_signal)
        save_active_signals(active_signals)

        clean_symbol = selected_symbol.replace('/', '')
        p = 4 if entry >= 1 else 6

        msg = f"""
🧠 **AI SMART VIP SIGNAL** 🔥
*(Selected by Gemini AI Quant Engine)*

📌 **Pair:** #{clean_symbol}
📊 **Action:** {side}
🎯 **Entry Price:** `{entry:.{p}f}`

💡 **AI Setup Reason:** {reason}

💰 **Take-Profit Targets:**
1️⃣ TP1: `{tp1:.{p}f}`
2️⃣ TP2: `{tp2:.{p}f}`
3️⃣ TP3: `{tp3:.{p}f}`
4️⃣ TP4: `{tp4:.{p}f}`

🛡️ **Stop Loss:** `{sl:.{p}f}`
⚡ **Leverage:** 10x - 20x

🤖 *AI Copilot Active for Live Monitoring!*
"""
        send_telegram_msg(msg)
        print(f"✅ AI Selected and Sent Signal for {clean_symbol}!")

    except Exception as e:
        print(f"❌ Failed to parse AI decision JSON: {e}")

if __name__ == '__main__':
    scan_new_signals()
