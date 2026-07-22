import os
import requests
import ccxt
import pandas as pd

# ==================== CONFIGURATION ====================
BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN_HERE")
CHAT_ID = os.environ.get("CHAT_ID", "@YOUR_TELEGRAM_CHANNEL_USERNAME")

SYMBOLS = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT'] 
TIMEFRAME = '15m' 
exchange = ccxt.mexc({'enableRateLimit': True}) 

# ==================== TECHNICAL INDICATORS (PURE PANDAS) ====================
def calculate_ema(df, length):
    """ Calculates Exponential Moving Average (EMA) """
    return df['close'].ewm(span=length, adjust=False).mean()

def calculate_rsi(df, length=14):
    """ Calculates Relative Strength Index (RSI) """
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    
    avg_gain = gain.ewm(alpha=1/length, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/length, adjust=False).mean()
    
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def calculate_atr(df, length=14):
    """ Calculates Average True Range (ATR) """
    high_low = df['high'] - df['low']
    high_close = (df['high'] - df['close'].shift()).abs()
    low_close = (df['low'] - df['close'].shift()).abs()
    
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return tr.ewm(alpha=1/length, adjust=False).mean()

# ==================== TELEGRAM NOTIFIER ====================
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
            print(f"✅ [{symbol}] Signal successfully sent to Telegram!")
        else:
            print(f"❌ Failed to send Telegram message: {response.text}")
    except Exception as e:
        print(f"❌ Error sending message: {e}")

# ==================== MARKET SCANNER ====================
def check_signals():
    print("🔍 Scanning market data...")
    for symbol in SYMBOLS:
        try:
            bars = exchange.fetch_ohlcv(symbol, timeframe=TIMEFRAME, limit=100)
            df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            
            # Pure Pandas Indicator Calculations
            df['EMA_FAST'] = calculate_ema(df, 9)   
            df['EMA_SLOW'] = calculate_ema(df, 21)  
            df['RSI'] = calculate_rsi(df, 14)       
            df['ATR'] = calculate_atr(df, 14) 

            curr = df.iloc[-1]
            prev = df.iloc[-2]

            close_price = curr['close']
            atr_val = curr['ATR']

            # Trading Logic Conditions
            long_condition = (prev['EMA_FAST'] <= prev['EMA_SLOW']) and (curr['EMA_FAST'] > curr['EMA_SLOW']) and (curr['RSI'] > 50)
            short_condition = (prev['EMA_FAST'] >= prev['EMA_SLOW']) and (curr['EMA_FAST'] < curr['EMA_SLOW']) and (curr['RSI'] < 50)

            if long_condition:
                entry = close_price
                sl = entry - (atr_val * 1.5)
                tp1 = entry + (atr_val * 1.5)
                tp2 = entry + (atr_val * 3.0)
                send_telegram_signal(symbol, "LONG 🟢", entry, tp1, tp2, sl)

            elif short_condition:
                entry = close_price
                sl = entry + (atr_val * 1.5)
                tp1 = entry - (atr_val * 1.5)
                tp2 = entry - (atr_val * 3.0)
                send_telegram_signal(symbol, "SHORT 🔴", entry, tp1, tp2, sl)

        except Exception as e:
            print(f"❌ Error checking {symbol}: {e}")

if __name__ == '__main__':
    check_signals()
