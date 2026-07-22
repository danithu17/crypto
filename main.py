import os
import json
import random
import requests
import ccxt
import pandas as pd

# ==================== CONFIGURATION ====================
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
CHAT_ID = os.environ.get("CHAT_ID", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

TOP_COINS_LIMIT = 30 
TIMEFRAME = '15m' 
ACTIVE_SIGNAL_FILE = 'active_signal.json'

exchange = ccxt.mexc({'enableRateLimit': True})

# ==================== STATE MANAGEMENT ====================
def load_active_signal():
    if os.path.exists(ACTIVE_SIGNAL_FILE):
        try:
            with open(ACTIVE_SIGNAL_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading active signal file: {e}")
    return None

def save_active_signal(signal_data):
    try:
        with open(ACTIVE_SIGNAL_FILE, 'w') as f:
            json.dump(signal_data, f, indent=4)
    except Exception as e:
        print(f"Error saving active signal file: {e}")

def clear_active_signal():
    if os.path.exists(ACTIVE_SIGNAL_FILE):
        os.remove(ACTIVE_SIGNAL_FILE)

# ==================== TECHNICAL INDICATORS ====================
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

# ==================== TELEGRAM SENDER ====================
def send_telegram_msg(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        res = requests.post(url, json=payload)
        return res.status_code == 200
    except Exception as e:
        print(f"❌ Telegram Error: {e}")
        return False

# ==================== AI DECISION ENGINE (GEMINI AI) ====================
def get_ai_trade_decision(signal, current_price, rsi, ema_fast, ema_slow):
    """ Google Gemini AI Model එක පාවිච්චි කරමින් Live Position Decision එකක් ගැනීම """
    if not GEMINI_API_KEY:
        print("⚠️ Gemini API Key missing! Fallback to standard tracking.")
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
    - PnL Percentage: {pnl_pct:.2f}%
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

    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
        headers = {'Content-Type': 'application/json'}
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code == 200:
            res_data = response.json()
            ai_text = res_data['candidates'][0]['content']['parts'][0]['text']
            return ai_text
        else:
            print(f"❌ AI Error: {response.text}")
            return None
    except Exception as e:
        print(f"❌ AI Exception: {e}")
        return None

# ==================== MANAGING OPEN ACTIVE TRADE ====================
def manage_active_trade(signal):
    symbol = signal['symbol']
    print(f"🔄 Managing Active AI Trade for {symbol}...")
    
    try:
        bars = exchange.fetch_ohlcv(symbol, timeframe=TIMEFRAME, limit=50)
        df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        
        df['EMA_FAST'] = calculate_ema(df, 9)
        df['EMA_SLOW'] = calculate_ema(df, 21)
        df['RSI'] = calculate_rsi(df, 14)
        
        curr = df.iloc[-1]
        current_price = curr['close']
        
        side = signal['side']
        sl = signal['sl']
        tp4 = signal['tp4']

        # 1. Stop Loss Hit Check
        if ("LONG" in side and current_price <= sl) or ("SHORT" in side and current_price >= sl):
            msg = f"🛑 **TRADE CLOSED (STOP LOSS HIT)** 🛑\n\n📌 **Pair:** #{symbol.replace('/', '')}\n❌ Price hit Stop Loss at {current_price:.4f}. Risk Managed!"
            send_telegram_msg(msg)
            clear_active_signal()
            return

        # 2. Final TP Hit Check
        if ("LONG" in side and current_price >= tp4) or ("SHORT" in side and current_price <= tp4):
            msg = f"🎯 **ALL TARGETS ACHIEVED! (TP4 HIT)** 🚀\n\n📌 **Pair:** #{symbol.replace('/', '')}\n💰 Maximum Profit Unlocked at {current_price:.4f}!"
            send_telegram_msg(msg)
            clear_active_signal()
            return

        # 3. AI Powered Decision Update
        ai_msg = get_ai_trade_decision(signal, current_price, curr['RSI'], curr['EMA_FAST'], curr['EMA_SLOW'])
        if ai_msg:
            send_telegram_msg(ai_msg)
        else:
            print("Could not get AI decision.")

    except Exception as e:
        print(f"❌ Error managing trade {symbol}: {e}")

# ==================== SCANNING NEW SIGNALS ====================
def scan_new_signals():
    print("🔍 Fetching target markets for new setup...")
    tickers = exchange.fetch_tickers()
    usdt_pairs = {k: v.get('quoteVolume', 0) for k, v in tickers.items() if k.endswith('/USDT') and '3L' not in k and '3S' not in k}
    sorted_symbols = sorted(usdt_pairs, key=usdt_pairs.get, reverse=True)[:TOP_COINS_LIMIT]

    valid_signals = []

    for symbol in sorted_symbols:
        try:
            bars = exchange.fetch_ohlcv(symbol, timeframe=TIMEFRAME, limit=50)
            df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            
            df['EMA_FAST'] = calculate_ema(df, 9)
            df['EMA_SLOW'] = calculate_ema(df, 21)
            df['RSI'] = calculate_rsi(df, 14)
            df['ATR'] = calculate_atr(df, 14)

            curr = df.iloc[-1]
            prev = df.iloc[-2]
            close_price = curr['close']
            atr_val = curr['ATR']

            long_cross = (prev['EMA_FAST'] <= prev['EMA_SLOW']) and (curr['EMA_FAST'] > curr['EMA_SLOW']) and (curr['RSI'] > 50)
            short_cross = (prev['EMA_FAST'] >= prev['EMA_SLOW']) and (curr['EMA_FAST'] < curr['EMA_SLOW']) and (curr['RSI'] < 50)

            if long_cross:
                valid_signals.append({
                    'symbol': symbol, 'side': "LONG 🟢", 'entry': close_price,
                    'tp1': close_price + (atr_val * 2.0), 'tp2': close_price + (atr_val * 4.0),
                    'tp3': close_price + (atr_val * 6.0), 'tp4': close_price + (atr_val * 8.0),
                    'sl': close_price - (atr_val * 2.0)
                })
            elif short_cross:
                valid_signals.append({
                    'symbol': symbol, 'side': "SHORT 🔴", 'entry': close_price,
                    'tp1': close_price - (atr_val * 2.0), 'tp2': close_price - (atr_val * 4.0),
                    'tp3': close_price - (atr_val * 6.0), 'tp4': close_price - (atr_val * 8.0),
                    'sl': close_price + (atr_val * 2.0)
                })
        except Exception as e:
            continue

    if valid_signals:
        best_signal = valid_signals[0] # Pick top quality
        save_active_signal(best_signal)
        
        clean_symbol = best_signal['symbol'].replace('/', '')
        p = 4 if best_signal['entry'] >= 1 else 6
        
        msg = f"""
🔥 **VIP CRYPTO SIGNAL** 🔥

📌 **Pair:** #{clean_symbol}
📊 **Action:** {best_signal['side']}
🎯 **Entry Price:** {best_signal['entry']:.{p}f}

💰 **Take-Profit Targets:**
1️⃣ TP1: {best_signal['tp1']:.{p}f}
2️⃣ TP2: {best_signal['tp2']:.{p}f}
3️⃣ TP3: {best_signal['tp3']:.{p}f}
4️⃣ TP4: {best_signal['tp4']:.{p}f}

🛡️ **Stop Loss:** {best_signal['sl']:.{p}f}
⚡ **Leverage:** 10x - 20x

🤖 *AI Trade Copilot initialized to monitor this trade!*
"""
        send_telegram_msg(msg)

# ==================== MAIN EXECUTION ====================
if __name__ == '__main__':
    active_signal = load_active_signal()
    if active_signal:
        # Open Trade එකක් තියෙනවා නම් AI එකෙන් ඒක Monitor කරනවා
        manage_active_trade(active_signal)
    else:
        # Open Trade එකක් නැත්නම් අලුත් Best Signal එකක් හොයනවා
        scan_new_signals()
