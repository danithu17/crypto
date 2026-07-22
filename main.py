import os
import random
import requests
import ccxt
import pandas as pd

# ==================== CONFIGURATION ====================
BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN_HERE")
CHAT_ID = os.environ.get("CHAT_ID", "@YOUR_TELEGRAM_CHANNEL_USERNAME")

TOP_COINS_LIMIT = 30 
TIMEFRAME = '15m' 

exchange = ccxt.mexc({'enableRateLimit': True})

# ==================== DYNAMIC COIN SELECTION ====================
def get_top_volume_symbols(limit=30):
    try:
        tickers = exchange.fetch_tickers()
        usdt_pairs = {}
        
        for symbol, ticker in tickers.items():
            if symbol.endswith('/USDT') and '3L' not in symbol and '3S' not in symbol:
                quote_vol = ticker.get('quoteVolume', 0)
                if quote_vol is not None and quote_vol > 0:
                    usdt_pairs[symbol] = quote_vol
        
        sorted_symbols = sorted(usdt_pairs, key=usdt_pairs.get, reverse=True)
        return sorted_symbols[:limit]
        
    except Exception as e:
        print(f"⚠️ Error fetching top volume coins: {e}")
        return ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'XRP/USDT']

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
def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"}
    try:
        response = requests.post(url, json=payload)
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Telegram Error: {e}")
        return False

def send_community_reaction(clean_symbol):
    """ Group එකේ මිනිස්සු කතා කරනවා වගේ Simulated Reactions යැවීම """
    reactions = [
        f"🔥 Locked in on #{clean_symbol}! Let's get this bread 🚀",
        f"Admin signals never miss. Entered #{clean_symbol} with 15x leverage! 🟢",
        f"Clean breakout on #{clean_symbol}. Holding till TP3! 🎯",
        f"In this trade! Let's smash TP1 family 💪🔥",
        f"#{clean_symbol} volume looks crazy right now. Good setup! 📈"
    ]
    reaction_msg = random.choice(reactions)
    send_telegram_message(reaction_msg)

def send_telegram_signal(symbol, side, entry, tp1, tp2, tp3, tp4, sl):
    clean_symbol = symbol.replace('/', '')
    price_precision = 4 if entry >= 1 else 6
    
    message = f"""
🔥 **VIP CRYPTO SIGNAL** 🔥

📌 **Pair:** #{clean_symbol}
📊 **Action:** {side}
🎯 **Entry Price:** {entry:.{price_precision}f}

💰 **Take-Profit Targets:**
1️⃣ TP1: {tp1:.{price_precision}f}
2️⃣ TP2: {tp2:.{price_precision}f}
3️⃣ TP3: {tp3:.{price_precision}f}
4️⃣ TP4: {tp4:.{price_precision}f}

🛡️ **Stop Loss:** {sl:.{price_precision}f}
⚡ **Leverage:** 10x - 20x (High Profit Target)

⚠️ *Advice: Move SL to Entry after TP1 hits!*
"""
    success = send_telegram_message(message)
    if success:
        print(f"✅ [{symbol}] Best Signal successfully sent to Telegram!")
        # Signal එක ගිහින් තත්පර කිහිපයකට පසු Community Reaction එක යැවීම
        import time
        time.sleep(3)
        send_community_reaction(clean_symbol)
    else:
        print(f"❌ Failed to send Telegram signal.")

# ==================== SMART MARKET RANKER ====================
def check_signals():
    print("🔍 Fetching target markets for AI Scoring...")
    symbols_to_scan = get_top_volume_symbols(TOP_COINS_LIMIT)
    
    candidates = []
    
    print(f"🔍 Analyzing and scoring {len(symbols_to_scan)} coins...")
    
    for symbol in symbols_to_scan:
        try:
            bars = exchange.fetch_ohlcv(symbol, timeframe=TIMEFRAME, limit=100)
            df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            
            df['EMA_FAST'] = calculate_ema(df, 9)   
            df['EMA_SLOW'] = calculate_ema(df, 21)  
            df['RSI'] = calculate_rsi(df, 14)       
            df['ATR'] = calculate_atr(df, 14) 

            curr = df.iloc[-1]
            prev = df.iloc[-2]

            close_price = curr['close']
            atr_val = curr['ATR']
            volume_score = curr['volume'] * close_price # Volume Weight Score

            long_condition = (prev['EMA_FAST'] <= prev['EMA_SLOW']) and (curr['EMA_FAST'] > curr['EMA_SLOW']) and (curr['RSI'] > 50)
            short_condition = (prev['EMA_FAST'] >= prev['EMA_SLOW']) and (curr['EMA_FAST'] < curr['EMA_SLOW']) and (curr['RSI'] < 50)

            if long_condition:
                candidates.append({
                    'symbol': symbol,
                    'side': 'LONG 🟢',
                    'entry': close_price,
                    'tp1': close_price + (atr_val * 2.0),
                    'tp2': close_price + (atr_val * 4.0),
                    'tp3': close_price + (atr_val * 6.0),
                    'tp4': close_price + (atr_val * 8.0),
                    'sl': close_price - (atr_val * 2.0),
                    'score': volume_score # වැඩිම Volume තියෙන එකට වැඩි Score එකක් ලැබෙයි
                })

            elif short_condition:
                candidates.append({
                    'symbol': symbol,
                    'side': 'SHORT 🔴',
                    'entry': close_price,
                    'tp1': close_price - (atr_val * 2.0),
                    'tp2': close_price - (atr_val * 4.0),
                    'tp3': close_price - (atr_val * 6.0),
                    'tp4': close_price - (atr_val * 8.0),
                    'sl': close_price + (atr_val * 2.0),
                    'score': volume_score
                })

        except Exception as e:
            print(f"❌ Error checking {symbol}: {e}")

    # 🧠 SMART DECISION: සියලුම Candidates ලාගෙන් හොඳම (Highest Volume/Momentum) එකම එක Coin එක පමණක් තෝරාගැනීම
    if candidates:
        # Score එක අනුව Descending (වැඩිම එක උඩට) Sort කිරීම
        candidates = sorted(candidates, key=lambda x: x['score'], reverse=True)
        best_signal = candidates[0] # අංක 1 හොඳම Signal එක පමණයි!
        
        print(f"🎯 Selected Best Signal: {best_signal['symbol']} (Score: {best_signal['score']:.2f})")
        
        send_telegram_signal(
            best_signal['symbol'],
            best_signal['side'],
            best_signal['entry'],
            best_signal['tp1'],
            best_signal['tp2'],
            best_signal['tp3'],
            best_signal['tp4'],
            best_signal['sl']
        )
    else:
        print("ℹ️ No high-probability signals found in this scan cycle.")

if __name__ == '__main__':
    check_signals()
