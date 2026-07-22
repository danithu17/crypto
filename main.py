from flask import Flask
from threading import Thread
import os
import time
import requests
import ccxt
import pandas as pd
import pandas_ta as ta

# ==================== FLASK SERVER (FOR FREE RENDER HOSTING) ====================
app = Flask('')

@app.route('/')
def home():
    return "✅ AlgoTrend Bot is Running 24/7 Online!"

def run_flask():
    # Render එකෙන් auto assign කරන Port එක ගන්නවා
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_flask)
    t.start()

# ==================== CONFIGURATION ====================
BOT_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN_HERE" 
CHAT_ID = "@YOUR_TELEGRAM_CHANNEL_USERNAME" 

SYMBOLS = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT'] 
TIMEFRAME = '15m' 

last_signals = {symbol: None for symbol in SYMBOLS}
exchange = ccxt.binance({'enableRateLimit': True})

def send_telegram_signal(symbol, side, entry, tp1, tp2, sl):
    message = f"""
🚀 **AUTOMATED CRYPTO SIGNAL** 🚀

📌 **Pair:** #{symbol.replace('/', '')}
📊 **Action:** {side.upper()}
🎯 **Entry Price:** {entry:.4f}

💰 **Take-Profit Targets:**
1️⃣ TP1: {tp1:.4f}
2️⃣ TP2: {tp2:.4f}

🛡️ **Stop Loss:** {sl:.4f}
⚡ **Leverage:** 5x - 10x

⚠️ *Risk Warning: Always use Proper Position Sizing!*
"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
    
    try:
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            print(f"✅ [{symbol}] Signal sent successfully!")
    except Exception as e:
        print(f"❌ Error: {e}")

def check_signals():
    print("🔍 Scanning market data...")
    for symbol in SYMBOLS:
        try:
            bars = exchange.fetch_ohlcv(symbol, timeframe=TIMEFRAME, limit=100)
            df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            
            df['EMA_FAST'] = ta.ema(df['close'], length=9)   
            df['EMA_SLOW'] = ta.ema(df['close'], length=21)  
            df['RSI'] = ta.rsi(df['close'], length=14)       
            df['ATR'] = ta.atr(df['high'], df['low'], df['close'], length=14) 

            curr = df.iloc[-1]
            prev = df.iloc[-2]

            close_price = curr['close']
            atr_val = curr['ATR']

            long_condition = (prev['EMA_FAST'] <= prev['EMA_SLOW']) and (curr['EMA_FAST'] > curr['EMA_SLOW']) and (curr['RSI'] > 50)
            short_condition = (prev['EMA_FAST'] >= prev['EMA_SLOW']) and (curr['EMA_FAST'] < curr['EMA_SLOW']) and (curr['RSI'] < 50)

            if long_condition and last_signals[symbol] != 'LONG':
                entry = close_price
                sl = entry - (atr_val * 1.5)
                tp1 = entry + (atr_val * 1.5)
                tp2 = entry + (atr_val * 3.0)
                send_telegram_signal(symbol, "LONG 🟢", entry, tp1, tp2, sl)
                last_signals[symbol] = 'LONG'

            elif short_condition and last_signals[symbol] != 'SHORT':
                entry = close_price
                sl = entry + (atr_val * 1.5)
                tp1 = entry - (atr_val * 1.5)
                tp2 = entry - (atr_val * 3.0)
                send_telegram_signal(symbol, "SHORT 🔴", entry, tp1, tp2, sl)
                last_signals[symbol] = 'SHORT'

        except Exception as e:
            print(f"❌ Error checking {symbol}: {e}")

# ==================== MAIN LOOP ====================
if __name__ == '__main__':
    # 1. Background Web Server එක Start කිරීම
    keep_alive()
    
    print("🚀 Free Crypto Signal Bot Started...")
    
    # 2. Main Signal Loop එක Start කිරීම
    while True:
        check_signals()
        time.sleep(60)
