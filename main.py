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

# Signal එකක් valid වෙන්න ඕන අවම Score එක (0 - 100)
MINIMUM_SIGNAL_SCORE = 70 

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
        print(f"⚠️ Error fetching coins: {e}")
        return ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'XRP/USDT', 'DOGE/USDT', 'AVAX/USDT']

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

# ==================== ENGAGEMENT / REACTION POSTS ====================
def send_random_engagement():
    messages = [
        "📊 **Market Scan Complete!** Currently monitoring Top 30 pairs for high-probability setups. Stay tuned! 🔥",
        "💡 **VIP Trading Tip:** Never risk more than 2% of your portfolio on a single 10x-20x trade. Risk management is key! 🛡️",
        "⚡ **Market Update:** High volatility detected in Altcoins! React with 🔥 if you are active right now!",
        "🎯 **Target Locked:** Our scanner is tracking potential breakouts. Get ready for the next setup! 🚀"
    ]
    # 25% chance of posting engagement if no signals found
    if random.random() < 0.25:
        msg = random.choice(messages)
        send_telegram_msg(msg)

# ==================== PRE-ENTRY ALERT ====================
def send_watchlist_alert(symbol, direction):
    clean_symbol = symbol.replace('/', '')
    msg = f"""
👀 **WATCHLIST ALERT** 👀

📌 **Pair:** #{clean_symbol}
📈 **Potential Direction:** {direction}
⚡ **Status:** EMA Crossover is forming on 15m Chart!

⚠️ *Get your exchange ready! Formal VIP Signal coming soon if confirmed.*
"""
    send_telegram_msg(msg)

# ==================== VIP SIGNAL SENDER ====================
def send_vip_signal(signal):
    symbol = signal['symbol']
    side = signal['side']
    entry = signal['entry']
    tp1, tp2, tp3, tp4 = signal['tp1'], signal['tp2'], signal['tp3'], signal['tp4']
    sl = signal['sl']
    score = signal['score']
    
    clean_symbol = symbol.replace('/', '')
    precision = 4 if entry >= 1 else 6

    msg = f"""
🔥 **VIP CRYPTO SIGNAL** 🔥
*(Signal Quality Score: {score}/100 ⭐️)*

📌 **Pair:** #{clean_symbol}
📊 **Action:** {side}
🎯 **Entry Price:** {entry:.{precision}f}

💰 **Take-Profit Targets:**
1️⃣ TP1: {tp1:.{precision}f}
2️⃣ TP2: {tp2:.{precision}f}
3️⃣ TP3: {tp3:.{precision}f}
4️⃣ TP4: {tp4:.{precision}f}

🛡️ **Stop Loss:** {sl:.{precision}f}
⚡ **Leverage:** 10x - 20x

⚠️ *Advice: Move SL to Entry after TP1 hits!*
"""
    send_telegram_msg(msg)

# ==================== MARKET SCANNER & WISE DECISION ENGINE ====================
def check_signals():
    print("🔍 Fetching target markets...")
    symbols = get_top_volume_symbols(TOP_COINS_LIMIT)
    
    valid_signals = []
    watchlist_candidates = []

    for symbol in symbols:
        try:
            bars = exchange.fetch_ohlcv(symbol, timeframe=TIMEFRAME, limit=100)
            df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            
            df['EMA_FAST'] = calculate_ema(df, 9)   
            df['EMA_SLOW'] = calculate_ema(df, 21)
            df['EMA_TREND'] = calculate_ema(df, 50)
            df['RSI'] = calculate_rsi(df, 14)       
            df['ATR'] = calculate_atr(df, 14)
            df['VOL_MA'] = df['volume'].rolling(20).mean()

            curr = df.iloc[-1]
            prev = df.iloc[-2]

            close_price = curr['close']
            atr_val = curr['ATR']

            # --- 1. FULL SIGNAL CONDITIONS ---
            long_cross = (prev['EMA_FAST'] <= prev['EMA_SLOW']) and (curr['EMA_FAST'] > curr['EMA_SLOW'])
            short_cross = (prev['EMA_FAST'] >= prev['EMA_SLOW']) and (curr['EMA_FAST'] < curr['EMA_SLOW'])

            # --- 2. PRE-ENTRY ALERT CONDITIONS (EMA diff < 0.1%) ---
            ema_gap = abs(curr['EMA_FAST'] - curr['EMA_SLOW']) / curr['close']
            if ema_gap < 0.001 and not long_cross and not short_cross:
                direction = "LONG 🟢" if curr['EMA_FAST'] > curr['EMA_SLOW'] else "SHORT 🔴"
                watchlist_candidates.append({'symbol': symbol, 'direction': direction})

            if long_cross or short_cross:
                # --- WISE SCORE CALCULATION (0 - 100) ---
                score = 50 # Base Score

                # Volume Surge Bonus (+20)
                if curr['volume'] > (curr['VOL_MA'] * 1.3):
                    score += 20
                
                # Trend Alignment Bonus (+15)
                if long_cross and close_price > curr['EMA_TREND']:
                    score += 15
                elif short_cross and close_price < curr['EMA_TREND']:
                    score += 15

                # RSI Momentum Bonus (+15)
                if long_cross and (55 <= curr['RSI'] <= 70):
                    score += 15
                elif short_cross and (30 <= curr['RSI'] <= 45):
                    score += 15

                if score >= MINIMUM_SIGNAL_SCORE:
                    if long_cross:
                        valid_signals.append({
                            'symbol': symbol, 'side': "LONG 🟢", 'entry': close_price,
                            'tp1': close_price + (atr_val * 2.0),
                            'tp2': close_price + (atr_val * 4.0),
                            'tp3': close_price + (atr_val * 6.0),
                            'tp4': close_price + (atr_val * 8.0),
                            'sl': close_price - (atr_val * 2.0),
                            'score': score
                        })
                    elif short_cross:
                        valid_signals.append({
                            'symbol': symbol, 'side': "SHORT 🔴", 'entry': close_price,
                            'tp1': close_price - (atr_val * 2.0),
                            'tp2': close_price - (atr_val * 4.0),
                            'tp3': close_price - (atr_val * 6.0),
                            'tp4': close_price - (atr_val * 8.0),
                            'sl': close_price + (atr_val * 2.0),
                            'score': score
                        })

        except Exception as e:
            print(f"Error checking {symbol}: {e}")

    # ==================== EXECUTION DECISION ====================
    if valid_signals:
        # 🌟 Wise Decision: Pick ONLY THE SINGLE BEST SIGNAL (Highest Score)
        best_signal = max(valid_signals, key=lambda x: x['score'])
        print(f"🎯 Selected Best Signal: {best_signal['symbol']} with Score {best_signal['score']}")
        send_vip_signal(best_signal)
    
    elif watchlist_candidates:
        # 🌟 Send Watchlist Pre-Alert if potential setup forms
        alert = random.choice(watchlist_candidates)
        print(f"👀 Sending Watchlist Pre-alert for {alert['symbol']}")
        send_watchlist_alert(alert['symbol'], alert['direction'])
    
    else:
        # 🌟 Send random engagement post if no signals/alerts
        send_random_engagement()

if __name__ == '__main__':
    check_signals()
