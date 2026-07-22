import os
import requests
import ccxt
import pandas as pd

# ==================== CONFIGURATION ====================
BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN_HERE")
CHAT_ID = os.environ.get("CHAT_ID", "@YOUR_TELEGRAM_CHANNEL_USERNAME")

# Scan කිරීමට අවශ්‍ය Top Coins ගණන
TOP_COINS_LIMIT = 30 
TIMEFRAME = '15m' 

exchange = ccxt.mexc({'enableRateLimit': True})

# ==================== DYNAMIC COIN SELECTION ====================
def get_top_volume_symbols(limit=30):
    """ MEXC හි 24h Volume එක වැඩිම USDT Pairs Auto-Fetch කිරීම """
    try:
        tickers = exchange.fetch_tickers()
        usdt_pairs = {}
        
        for symbol, ticker in tickers.items():
            # leveraged tokens (3L, 3S වගේ ඒවා) අයින් කර ස්පොට් USDT පරීක්ෂා කිරීම
            if symbol.endswith('/USDT') and '3L' not in symbol and '3S' not in symbol:
                quote_vol = ticker.get('quoteVolume', 0)
                if quote_vol is not None and quote_vol > 0:
                    usdt_pairs[symbol] = quote_vol
        
        # Volume එක අනුව Sort කර Top Pairs තෝරා ගැනීම
        sorted_symbols = sorted(usdt_pairs, key=usdt_pairs.get, reverse=True)
        top_symbols = sorted_symbols[:limit]
        print(f"📊 Successfully fetched Top {len(top_symbols)} volume coins for scanning!")
        return top_symbols
        
    except Exception as e:
        print(f"⚠️ Error fetching top volume coins: {e}. Using fallback list.")
        # මොකක් හරි අවුලක් ආවොත් Run වන Fallback List එක
        return [
            'BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'XRP/USDT', 
            'DOGE/USDT', 'ADA/USDT', 'AVAX/USDT', 'NEAR/USDT', 'SUI/USDT',
            'PEPE/USDT', 'FET/USDT', 'LINK/USDT', 'APT/USDT', 'RENDER/USDT'
        ]

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

# ==================== TELEGRAM NOTIFIER ====================
def send_telegram_signal(symbol, side, entry, tp1, tp2, sl):
    clean_symbol = symbol.replace('/', '')
    message = f"""
🚀 **AUTOMATED CRYPTO SIGNAL** 🚀

📌 **Pair:** #{clean_symbol}
📊 **Action:** {side}
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
    print("🔍 Fetching target markets...")
    symbols_to_scan = get_top_volume_symbols(TOP_COINS_LIMIT)
    
    print(f"🔍 Scanning market data for {len(symbols_to_scan)} coins...")
    
    for symbol in symbols_to_scan:
        try:
            bars = exchange.fetch_ohlcv(symbol, timeframe=TIMEFRAME, limit=100)
            df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            
            # Technical Indicators
            df['EMA_FAST'] = calculate_ema(df, 9)   
            df['EMA_SLOW'] = calculate_ema(df, 21)  
            df['RSI'] = calculate_rsi(df, 14)       
            df['ATR'] = calculate_atr(df, 14) 

            curr = df.iloc[-1]
            prev = df.iloc[-2]

            close_price = curr['close']
            atr_val = curr['ATR']

            # Trading Conditions
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
