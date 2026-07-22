import os
import json
import requests
import ccxt
import pandas as pd

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
CHAT_ID = os.environ.get("CHAT_ID", "")
TOP_COINS_LIMIT = 30 
TIMEFRAME = '15m' 
ACTIVE_SIGNAL_FILE = 'active_signal.json'
MAX_ACTIVE_SIGNALS = 2  # 🎯 එකපාර දිවෙන උපරිම Active Signals ගණන

exchange = ccxt.mexc({'enableRateLimit': True})

def load_active_signals():
    if os.path.exists(ACTIVE_SIGNAL_FILE):
        try:
            with open(ACTIVE_SIGNAL_FILE, 'r') as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
                elif isinstance(data, dict):
                    return [data]
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
    
    # Signals 2ක් දැනටමත් Open නම් Scan එක Pause වේ
    if len(active_signals) >= MAX_ACTIVE_SIGNALS:
        print(f"⏸️ Reached maximum active signals limit ({MAX_ACTIVE_SIGNALS}). Skipping scan.")
        return

    print(f"🔍 Scanning markets... (Current Active Trades: {len(active_signals)}/{MAX_ACTIVE_SIGNALS})")
    
    # දැනට Open වී ඇති Coins වල නම් (Duplicate නොවීමට)
    active_symbols = [s['symbol'] for s in active_signals]

    tickers = exchange.fetch_tickers()
    usdt_pairs = {k: v.get('quoteVolume', 0) for k, v in tickers.items() if k.endswith('/USDT') and '3L' not in k and '3S' not in k}
    sorted_symbols = sorted(usdt_pairs, key=usdt_pairs.get, reverse=True)[:TOP_COINS_LIMIT]

    valid_signals = []

    for symbol in sorted_symbols:
        if symbol in active_symbols:
            continue  # දැනටමත් Open Coin එකක් නම් Skip කරන්න

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
                    'sl': close_price - (atr_val * 2.0), 'last_status': "INITIAL"
                })
            elif short_cross:
                valid_signals.append({
                    'symbol': symbol, 'side': "SHORT 🔴", 'entry': close_price,
                    'tp1': close_price - (atr_val * 2.0), 'tp2': close_price - (atr_val * 4.0),
                    'tp3': close_price - (atr_val * 6.0), 'tp4': close_price - (atr_val * 8.0),
                    'sl': close_price + (atr_val * 2.0), 'last_status': "INITIAL"
                })
        except Exception:
            continue

    if valid_signals:
        best_signal = valid_signals[0]
        active_signals.append(best_signal)
        save_active_signals(active_signals)
        
        clean_symbol = best_signal['symbol'].replace('/', '')
        p = 4 if best_signal['entry'] >= 1 else 6
        
        msg = f"""
🔥 **VIP CRYPTO SIGNAL** 🔥
*(Active Trade Slot: {len(active_signals)}/{MAX_ACTIVE_SIGNALS})*

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
        print(f"✅ New Signal Sent for {clean_symbol}!")

if __name__ == '__main__':
    scan_new_signals()
