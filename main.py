import time
import requests
import ccxt
import pandas as pd
import pandas_ta as ta

# ==================== CONFIGURATION ====================
BOT_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN_HERE"  # BotFather ගෙන් ලැබුණු Token එක
CHAT_ID = "@YOUR_TELEGRAM_CHANNEL_USERNAME" # උදා: @MyCryptoVIPChannel හෝ Channel Chat ID එක

SYMBOLS = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT'] # Signal බලන්න ඕන Coins
TIMEFRAME = '15m'  # 15 Min Candles

# ඩියුප්ලිකේට් Signals යන එක නවත්වන්න Signal History එක තියාගන්නවා
last_signals = {symbol: None for symbol in SYMBOLS}

# Exchange Object එක සාදා ගැනීම (Binance Free Public API)
exchange = ccxt.binance({
    'enableRateLimit': True,
})

def send_telegram_signal(symbol, side, entry, tp1, tp2, sl):
    """ Telegram එකට formatted signal එකක් යවන Function එක """
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
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    
    try:
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            print(f"✅ [{symbol}] Signal successfully sent to Telegram!")
        else:
            print(f"❌ Failed to send Telegram message: {response.text}")
    except Exception as e:
        print(f"❌ Error sending Telegram message: {e}")

def check_signals():
    """ Binance එකෙන් data අරන් Strategy එක Calculate කරන Function එක """
    print("🔍 Scanning market data...")
    
    for symbol in SYMBOLS:
        try:
            # Binance එකෙන් අන්තිම Candles 100 ඩේටා ගන්නවා
            bars = exchange.fetch_ohlcv(symbol, timeframe=TIMEFRAME, limit=100)
            df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            
            # Technical Indicators Calculate කිරීම (100% Free)
            df['EMA_FAST'] = ta.ema(df['close'], length=9)   # EMA 9
            df['EMA_SLOW'] = ta.ema(df['close'], length=21)  # EMA 21
            df['RSI'] = ta.rsi(df['close'], length=14)       # RSI 14
            df['ATR'] = ta.atr(df['high'], df['low'], df['close'], length=14) # Volatility සඳහා ATR

            # අන්තිම සහ ඊට කලින් Candle එකේ Indicators ගන්නවා
            curr = df.iloc[-1]
            prev = df.iloc[-2]

            close_price = curr['close']
            atr_val = curr['ATR']

            # --- BUY / LONG CONDITION ---
            # Fast EMA එක Slow EMA එක කපාගෙන උඩට යාම (Crossover) සහ RSI > 50 වීම
            long_condition = (prev['EMA_FAST'] <= prev['EMA_SLOW']) and (curr['EMA_FAST'] > curr['EMA_SLOW']) and (curr['RSI'] > 50)

            # --- SELL / SHORT CONDITION ---
            # Fast EMA එක Slow EMA එක කපාගෙන පහළට යාම සහ RSI < 50 වීම
            short_condition = (prev['EMA_FAST'] >= prev['EMA_SLOW']) and (curr['EMA_FAST'] < curr['EMA_SLOW']) and (curr['RSI'] < 50)

            # LONG Signal එකක් හමුවුවහොත්
            if long_condition and last_signals[symbol] != 'LONG':
                entry = close_price
                sl = entry - (atr_val * 1.5)  # Stop Loss (1.5 x ATR)
                tp1 = entry + (atr_val * 1.5) # Take Profit 1 (1:1 Risk Reward)
                tp2 = entry + (atr_val * 3.0) # Take Profit 2 (1:2 Risk Reward)

                send_telegram_signal(symbol, "LONG 🟢", entry, tp1, tp2, sl)
                last_signals[symbol] = 'LONG'

            # SHORT Signal එකක් හමුවුවහොත්
            elif short_condition and last_signals[symbol] != 'SHORT':
                entry = close_price
                sl = entry + (atr_val * 1.5)  # Stop Loss
                tp1 = entry - (atr_val * 1.5) # Take Profit 1
                tp2 = entry - (atr_val * 3.0) # Take Profit 2

                send_telegram_signal(symbol, "SHORT 🔴", entry, tp1, tp2, sl)
                last_signals[symbol] = 'SHORT'

        except Exception as e:
            print(f"❌ Error checking {symbol}: {e}")

# ==================== MAIN LOOP ====================
if __name__ == '__main__':
    print("🚀 Free Crypto Signal Bot Started...")
    
    # සෑම තප්පර 60කට වරක්ම Market එක Auto-Scan වෙනවා
    while True:
        check_signals()
        time.sleep(60)