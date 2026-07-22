import os
import json
import requests
import ccxt
import pandas as pd

# 🧠 Import AI Analysis Module
from ai_analyzer import get_ai_trade_decision

# ==================== CONFIGURATION ====================
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
CHAT_ID = os.environ.get("CHAT_ID", "")

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
        print("🗑️ Active trade cleared from state!")

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

# ==================== MANAGING ACTIVE TRADE ====================
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
            return True # Trade was closed

        # 2. Final TP Hit Check
        if ("LONG" in side and current_price >= tp4) or ("SHORT" in side and current_price <= tp4):
            msg = f"🎯 **ALL TARGETS ACHIEVED! (TP4 HIT)** 🚀\n\n📌 **Pair:** #{symbol.replace('/', '')}\n💰 Maximum Profit Unlocked at {current_price:.4f}!"
            send_telegram_msg(msg)
            clear_active_signal()
            return True # Trade was closed

        # 3. AI Powered Decision Update
        ai_msg = get_ai_trade_decision(signal, current_price, curr['RSI'], curr['EMA_FAST'], curr['EMA_SLOW'])
        if ai_msg:
            send_telegram_msg(ai_msg)
            # AI එකෙන් Close කරන්න කියලා තිබ්බොත් Trade එක අයින් කිරීම
            if "CLOSE POSITION NOW" in ai_msg.upper():
                print("🔴 AI advised to close position. Clearing trade state...")
                clear_active_signal()
                return True
        
        return False # Trade is still active

    except Exception as e:
        print(f"❌ Error managing trade {symbol}: {e}")
        return False

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
        best_signal = valid_signals[0]
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

# ==================== MAIN EXECUTION FLOW ====================
if __name__ == '__main__':
    active_signal = load_active_signal()
    trade_closed = False
    
    if active_signal:
        # Active trade එක AI එකෙන් Manage කිරීම
        trade_closed = manage_active_trade(active_signal)
    
    # Active trade එකක් නොතිබුණොත් හෝ Active trade එක ක්ලෝස් වුණොත්,
    # එසැණින්ම අලුත් Signal එකක් සඳහා Scan කිරීම!
    if not active_signal or trade_closed:
        scan_new_signals()
