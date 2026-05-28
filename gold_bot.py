import asyncio
import time
import threading
import aiohttp
import pandas as pd
import numpy as np
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler

TELEGRAM_TOKEN = "8958333782:AAEXDJhCBAq-W59LhaYBU6xzSrsLHoPeNKY"
CHAT_ID = "7452230597"
SYMBOL = "GC=F"
INTERVAL = "5m"
SL_PIPS = 15
TP_PIPS = 30
COOLDOWN_SECS = 300
CHECK_EVERY = 60

last_alert_time = 0

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Gold Bot Running!")
    def log_message(self, *args): pass

def start_server():
    HTTPServer(("0.0.0.0", 10000), Handler).serve_forever()

async def send_telegram(session, message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        async with session.post(url, json={"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"}) as r:
            pass
    except: pass

def get_gold_data():
    import yfinance as yf
    df = yf.download(SYMBOL, period="1d", interval=INTERVAL, progress=False)
    return df

def calculate_indicators(df):
    close = df["Close"].squeeze()
    df["ema9"] = close.ewm(span=9, adjust=False).mean()
    df["ema21"] = close.ewm(span=21, adjust=False).mean()
    delta = close.diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = -delta.where(delta < 0, 0).rolling(14).mean()
    rs = gain / loss
    df["rsi"] = 100 - (100 / (1 + rs))
    return df

def check_signal(df):
    latest = df.iloc[-1]
    prev = df.iloc[-2]

    price = float(latest["Close"].squeeze() if hasattr(latest["Close"], 'squeeze') else latest["Close"])
    ema9 = float(latest["ema9"])
    ema21 = float(latest["ema21"])
    prev_ema9 = float(prev["ema9"])
    prev_ema21 = float(prev["ema21"])
    rsi = float(latest["rsi"])

    # BUY: EMA9 crosses above EMA21 and RSI < 70
    if prev_ema9 < prev_ema21 and ema9 > ema21 and rsi < 70:
        sl = round(price - (SL_PIPS * 0.1), 2)
        tp = round(price + (TP_PIPS * 0.1), 2)
        return "BUY", price, sl, tp

    # SELL: EMA9 crosses below EMA21 and RSI > 30
    if prev_ema9 > prev_ema21 and ema9 < ema21 and rsi > 30:
        sl = round(price + (SL_PIPS * 0.1), 2)
        tp = round(price - (TP_PIPS * 0.1), 2)
        return "SELL", price, sl, tp

    return None, None, None, None

async def run_bot():
    global last_alert_time
    async with aiohttp.ClientSession() as session:
        await send_telegram(session,
            "🥇 <b>Gold Scalping Bot Started!</b>\n"
            "📊 Timeframe: M5\n"
            "📈 Indicators: EMA9/21 + RSI\n"
            f"🛑 SL: {SL_PIPS} pips | 🎯 TP: {TP_PIPS} pips\n"
            "Watching XAUUSD...")

        while True:
            try:
                df = get_gold_data()
                if df is not None and len(df) > 30:
                    df = calculate_indicators(df)
                    signal, price, sl, tp = check_signal(df)
                    now = time.time()

                    if signal and now - last_alert_time >= COOLDOWN_SECS:
                        last_alert_time = now
                        emoji = "🟢" if signal == "BUY" else "🔴"
                        await send_telegram(session,
                            f"{emoji} <b>{signal} SIGNAL — GOLD (XAUUSD)</b>\n\n"
                            f"💰 Entry: <b>${price}</b>\n"
                            f"🛑 SL: <b>${sl}</b>\n"
                            f"🎯 TP: <b>${tp}</b>\n"
                            f"⏱ M5\n"
                            f"🕐 {datetime.utcnow().strftime('%H:%M UTC')}\n\n"
                            "⚠️ <i>Trade at your own risk</i>")
            except:
                pass

            await asyncio.sleep(CHECK_EVERY)

if __name__ == "__main__":
    threading.Thread(target=start_server, daemon=True).start()
    asyncio.run(run_bot())
    
