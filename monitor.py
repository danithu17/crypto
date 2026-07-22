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

def monitor_trade():
    if not os.path.exists(ACTIVE_SIGNAL_FILE):
        print("ℹ️ No active trade to monitor.")
        return

    with open(ACTIVE_SIGNAL_FILE, 'r') as f:
        signal = json.load(f)

    symbol = signal['symbol']
    print(f"🤖 AI Monitoring Active Trade: {symbol}...")

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

        # 1. Check Stop Loss
        if ("LONG" in side and current_price <= sl) or ("SHORT" in side and current_price >= sl):
            msg = f"🛑 **TRADE CLOSED (STOP LOSS HIT)** 🛑\n\n📌 **Pair:** #{symbol.replace('/', '')}\n❌ Price hit Stop Loss at {current_price:.4f}. Risk Managed!"
            send_telegram_msg(msg)
            os.remove(ACTIVE_SIGNAL_FILE)
            print("🗑️ SL Hit. Active trade cleared.")
            return

        # 2. Check Final TP
        if ("LONG" in side and current_price >= tp4) or ("SHORT" in side and current_price <= tp4):
            msg = f"🎯 **ALL TARGETS ACHIEVED! (TP4 HIT)** 🚀\n\n📌 **Pair:** #{symbol.replace('/', '')}\n💰 Maximum Profit Unlocked at {current_price:.4f}!"
            send_telegram_msg(msg)
            os.remove(ACTIVE_SIGNAL_FILE)
            print("🗑️ TP4 Hit. Active trade cleared.")
            return

        # 3. AI Analysis
        ai_msg = get_ai_trade_decision(signal, current_price, curr['RSI'], curr['EMA_FAST'], curr['EMA_SLOW'])
        
        if ai_msg:
            # 🛡️ Anti-Spam Logic: එකම "HOLD & WAIT" Message එක නැවත නැවත නොයැවීම
            last_status = signal.get('last_status', '')
            is_hold = "HOLD & WAIT" in ai_msg.upper()

            if is_hold and last_status == "HOLD & WAIT":
                print("⏳ Trade status still 'HOLD & WAIT'. Skipping duplicate message to prevent spam.")
            else:
                send_telegram_msg(ai_msg)
                
                # Status එක Update කර File එක Save කිරීම
                signal['last_status'] = "HOLD & WAIT" if is_hold else "ACTION_TAKEN"
                with open(ACTIVE_SIGNAL_FILE, 'w') as f:
                    json.dump(signal, f, indent=4)

            # AI එකෙන් Close කරන්න කිව්වොත් Trade එක අයින් කිරීම
            if "CLOSE POSITION NOW" in ai_msg.upper():
                print("🔴 AI advised to close position. Clearing trade state...")
                os.remove(ACTIVE_SIGNAL_FILE)

    except Exception as e:
        print(f"❌ Error monitoring trade {symbol}: {e}")

if __name__ == '__main__':
    monitor_trade()
