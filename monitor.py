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

# 📈 PnL Threshold (%): PnL එක 1.5% කින් වෙනස් වුණොත් විතරක් AI Message එක යවයි
PNL_CHANGE_THRESHOLD = 1.5 

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
            entry = signal['entry']
            side = signal['side']
            sl = signal['sl']
            tp1, tp2, tp3, tp4 = signal['tp1'], signal['tp2'], signal['tp3'], signal['tp4']
            
            clean_symbol = symbol.replace('/', '')
            p = 4 if current_price >= 1 else 6

            # Live PnL % calculation
            current_pnl = ((current_price - entry) / entry) * 100 if "LONG" in side else ((entry - current_price) / entry) * 100

            # 🛑 1. STOP LOSS CHECK
            if ("LONG" in side and current_price <= sl) or ("SHORT" in side and current_price >= sl):
                msg = f"🛑 **TRADE CLOSED (STOP LOSS HIT)** 🛑\n\n📌 **Pair:** #{clean_symbol}\n❌ Price hit Stop Loss at `{current_price:.{p}f}`. Risk Managed!"
                send_telegram_msg(msg)
                print(f"🗑️ SL Hit for {symbol}. Trade removed.")
                continue

            # 🎯 2. STEP-BY-STEP TP TARGETS CHECK
            if "LONG" in side:
                if not signal.get('tp1_hit') and current_price >= tp1:
                    signal['tp1_hit'] = True
                    send_telegram_msg(f"🎯 **TP1 TARGET ACHIEVED!** 🚀\n\n📌 **Pair:** #{clean_symbol}\n💰 Price reached TP1 Target at `{current_price:.{p}f}`!")

                if not signal.get('tp2_hit') and current_price >= tp2:
                    signal['tp2_hit'] = True
                    send_telegram_msg(f"🎯 **TP2 TARGET ACHIEVED!** 🚀\n\n📌 **Pair:** #{clean_symbol}\n💰 Price reached TP2 Target at `{current_price:.{p}f}`!")

                if not signal.get('tp3_hit') and current_price >= tp3:
                    signal['tp3_hit'] = True
                    send_telegram_msg(f"🎯 **TP3 TARGET ACHIEVED!** 🚀\n\n📌 **Pair:** #{clean_symbol}\n💰 Price reached TP3 Target at `{current_price:.{p}f}`!")

                if current_price >= tp4:
                    send_telegram_msg(f"🎯 **ALL TARGETS ACHIEVED (TP4 HIT)!** 🚀🔥\n\n📌 **Pair:** #{clean_symbol}\n💰 Maximum Profit Unlocked at `{current_price:.{p}f}`!")
                    print(f"🗑️ TP4 Hit for {symbol}. Trade removed.")
                    continue

            elif "SHORT" in side:
                if not signal.get('tp1_hit') and current_price <= tp1:
                    signal['tp1_hit'] = True
                    send_telegram_msg(f"🎯 **TP1 TARGET ACHIEVED!** 🚀\n\n📌 **Pair:** #{clean_symbol}\n💰 Price reached TP1 Target at `{current_price:.{p}f}`!")

                if not signal.get('tp2_hit') and current_price <= tp2:
                    signal['tp2_hit'] = True
                    send_telegram_msg(f"🎯 **TP2 TARGET ACHIEVED!** 🚀\n\n📌 **Pair:** #{clean_symbol}\n💰 Price reached TP2 Target at `{current_price:.{p}f}`!")

                if not signal.get('tp3_hit') and current_price <= tp3:
                    signal['tp3_hit'] = True
                    send_telegram_msg(f"🎯 **TP3 TARGET ACHIEVED!** 🚀\n\n📌 **Pair:** #{clean_symbol}\n💰 Price reached TP3 Target at `{current_price:.{p}f}`!")

                if current_price <= tp4:
                    send_telegram_msg(f"🎯 **ALL TARGETS ACHIEVED (TP4 HIT)!** 🚀🔥\n\n📌 **Pair:** #{clean_symbol}\n💰 Maximum Profit Unlocked at `{current_price:.{p}f}`!")
                    print(f"🗑️ TP4 Hit for {symbol}. Trade removed.")
                    continue

            # 🤖 3. AI ANALYSIS (SMART SIGNIFICANT CHANGE FILTER)
            last_pnl = signal.get('last_pnl', None)
            pnl_diff = abs(current_pnl - last_pnl) if last_pnl is not None else 999.0

            ai_msg = get_ai_trade_decision(signal, current_price, curr['RSI'], curr['EMA_FAST'], curr['EMA_SLOW'])
            
            if ai_msg:
                is_hold = "HOLD & WAIT" in ai_msg.upper()

                # Filter Logic: PnL එක 1.5% කින් වෙනස් වුණොත් හෝ Action එක HOLD එකෙන් වෙනස් වුණොත් විතරක් යවන්න
                should_send_update = False

                if last_pnl is None:
                    should_send_update = True  # පළමු පාර Run වෙද්දී
                elif not is_hold:
                    should_send_update = True  # MOVE SL, TAKE PROFIT වගේ විශේෂ Action එකක් ආවොත්
                elif pnl_diff >= PNL_CHANGE_THRESHOLD:
                    should_send_update = True  # PnL වෙනස 1.5% ට වඩා වැඩි වුණොත්

                if should_send_update:
                    send_telegram_msg(ai_msg)
                    signal['last_pnl'] = current_pnl
                    signal['last_status'] = "HOLD & WAIT" if is_hold else "ACTION_TAKEN"
                    print(f"✅ Significant update sent for {symbol} (PnL Diff: {pnl_diff:.2f}%)")
                else:
                    print(f"⏳ No significant change for {symbol} (PnL Diff: {pnl_diff:.2f}% < {PNL_CHANGE_THRESHOLD}%). Skipping message.")

                if "CLOSE POSITION NOW" in ai_msg.upper():
                    print(f"🔴 AI advised to close {symbol}. Trade removed.")
                    continue

            remaining_signals.append(signal)

        except Exception as e:
            print(f"❌ Error monitoring {symbol}: {e}")
            remaining_signals.append(signal)

    save_active_signals(remaining_signals)

if __name__ == '__main__':
    monitor_trades()
