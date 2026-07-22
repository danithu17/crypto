import os
import json
import requests
import ccxt
import pandas as pd
from ai_analyzer import get_ai_trade_decision

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
CHAT_ID = os.environ.get("CHAT_ID", "")
TIMEFRAME = '15m'
ACTIVE_SIGNAL_FILE = 'active_signal.json'

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

def send_telegram_msg(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        res = requests.post(url, json=payload)
        return res.status_code == 200
    except Exception as e:
        print(f"❌ Telegram Error: {e}")
        return False

def monitor_trades():
    active_signals = load_active_signals()
    
    if not active_signals:
        print("ℹ️ No active trades to monitor.")
        return

    print(f"🤖 AI Monitoring {len(active_signals)} Active Trades...")
    remaining_signals = []

    for signal in active_signals:
        symbol = signal['symbol']
        print(f"🔄 Checking {symbol}...")

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
                print(f"🗑️ SL Hit for {symbol}. Trade removed.")
                continue  # Remaining list එකට එකතු නොකරයි (Closed)

            # 2. Final TP Hit Check
            if ("LONG" in side and current_price >= tp4) or ("SHORT" in side and current_price <= tp4):
                msg = f"🎯 **ALL TARGETS ACHIEVED! (TP4 HIT)** 🚀\n\n📌 **Pair:** #{symbol.replace('/', '')}\n💰 Maximum Profit Unlocked at {current_price:.4f}!"
                send_telegram_msg(msg)
                print(f"🗑️ TP4 Hit for {symbol}. Trade removed.")
                continue  # Remaining list එකට එකතු නොකරයි (Closed)

            # 3. AI Analysis & Updates
            ai_msg = get_ai_trade_decision(signal, current_price, curr['RSI'], curr['EMA_FAST'], curr['EMA_SLOW'])
            
            if ai_msg:
                last_status = signal.get('last_status', '')
                is_hold = "HOLD & WAIT" in ai_msg.upper()

                # Anti-Spam Check
                if is_hold and last_status == "HOLD & WAIT":
                    print(f"⏳ Status for {symbol} still 'HOLD & WAIT'. Skipping message.")
                else:
                    send_telegram_msg(ai_msg)
                    signal['last_status'] = "HOLD & WAIT" if is_hold else "ACTION_TAKEN"

                # AI Close Recommendation
                if "CLOSE POSITION NOW" in ai_msg.upper():
                    print(f"🔴 AI advised to close {symbol}. Trade removed.")
                    continue  # Closed

            remaining_signals.append(signal)

        except Exception as e:
            print(f"❌ Error monitoring {symbol}: {e}")
            remaining_signals.append(signal)

    # Updated remaining list එක Save කිරීම
    save_active_signals(remaining_signals)

if __name__ == '__main__':
    monitor_trades()
