import requests
import os
import pandas as pd
import numpy as np

FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY", "")

def get_price(symbol):
    s = str(symbol).upper()
    if s in ["GOLD", "GC=F", "XAUUSD"]:
        return get_gold_price()
    elif s in ["BTC", "BTC-USD", "BTCUSD"]:
        return get_btc_price()
    return 0

def get_gold_price():
    if FINNHUB_API_KEY:
        try:
            r = requests.get(f"https://finnhub.io/api/v1/quote?symbol=XAUUSD&token={FINNHUB_API_KEY}", timeout=10)
            p = r.json().get("c", 0)
            if p: return round(float(p), 2)
        except: pass
    try:
        r = requests.get("https://query1.finance.yahoo.com/v8/finance/chart/GC=F?interval=1m&range=1d", headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        p = r.json()["chart"]["result"][0]["meta"]["regularMarketPrice"]
        return round(float(p), 2)
    except: pass
    return 0

def get_btc_price():
    if FINNHUB_API_KEY:
        try:
            r = requests.get(f"https://finnhub.io/api/v1/quote?symbol=BINANCE:BTCUSDT&token={FINNHUB_API_KEY}", timeout=10)
            p = r.json().get("c", 0)
            if p: return round(float(p), 2)
        except: pass
    try:
        r = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd", timeout=10)
        return round(float(r.json()["bitcoin"]["usd"]), 2)
    except: pass
    return 0

def get_historical_data(symbol):
    sym = "GC=F" if str(symbol).upper() in ["GOLD", "GC=F", "XAUUSD"] else "BTC-USD"
    try:
        r = requests.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?interval=15m&range=5d", headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        d = r.json()["chart"]["result"][0]
        c, h, l = d["indicators"]["quote"][0]["close"], d["indicators"]["quote"][0]["high"], d["indicators"]["quote"][0]["low"]
        clean = [(c[i], h[i], l[i]) for i in range(len(c)) if c[i] and h[i] and l[i]]
        if len(clean) < 20: return None
        c, h, l = zip(*clean)
        return pd.DataFrame({"close": c, "high": h, "low": l})
    except: return None

def calculate_rsi(prices, period=14):
    if len(prices) < period + 1: return 50.0
    p = pd.Series(prices, dtype=float)
    d = p.diff()
    g = d.where(d > 0, 0.0)
    l = -d.where(d < 0, 0.0)
    rs = g.rolling(period).mean() / (l.rolling(period).mean() + 1e-10)
    return round((100 - 100 / (1 + rs)).dropna().iloc[-1], 2)

def calculate_ema(prices, period):
    return round(float(pd.Series(prices, dtype=float).ewm(span=period, adjust=False).mean().iloc[-1]), 2)

def calculate_bollinger(prices, period=20):
    p = pd.Series(prices, dtype=float)
    m = p.rolling(period).mean()
    s = p.rolling(period).std()
    return round(float((m + s * 2).dropna().iloc[-1]), 2), round(float((m - s * 2).dropna().iloc[-1]), 2)

def calculate_supertrend(df, period=10, mult=3):
    if len(df) < period + 1: return "NEUTRAL 🟡"
    h, l, c = pd.Series(df["high"], dtype=float), pd.Series(df["low"], dtype=float), pd.Series(df["close"], dtype=float)
    tr = pd.concat([h-l, (h-c.shift(1)).abs(), (l-c.shift(1)).abs()], axis=1).max(axis=1)
    atr = tr.rolling(period).mean()
    ub, lb = (h+l)/2 + mult*atr, (h+l)/2 - mult*atr
    dr = [1]
    for i in range(1, len(c)):
        if pd.isna(atr.iloc[i]): dr.append(dr[-1]); continue
        if c.iloc[i] > ub.iloc[i-1]: dr.append(1)
        elif c.iloc[i] < lb.iloc[i-1]: dr.append(-1)
        else: dr.append(dr[-1])
    return "BULLISH 🟢" if dr[-1] == 1 else "BEARISH 🔴"

def generate_signal(symbol, name):
    price = get_price(symbol)
    if price == 0: return "❌ Gagal ambil harga. Semak sambungan."
    df = get_historical_data(symbol)
    if not df or len(df) < 20:
        return f"{'🥇' if name=='GOLD' else '₿'} *SIGNAL {name}*\n💰 Harga: ${price}\n\n⚠️ Data tidak cukup."
    
    closes = df["close"].tolist()
    rsi = calculate_rsi(closes)
    ema9, ema21 = calculate_ema(closes, 9), calculate_ema(closes, 21)
    bb_u, bb_l = calculate_bollinger(closes)
    st = calculate_supertrend(df)
    
    ema_sig = "BUY" if ema9 > ema21 else "SELL" if ema9 < ema21 else "HOLD"
    
    buy_sc = (1 if ema_sig=="BUY" else 0) + (1 if rsi>55 else 0) + (1 if st=="BULLISH 🟢" else 0)
    sell_sc = (1 if ema_sig=="SELL" else 0) + (1 if rsi<45 else 0) + (1 if st=="BEARISH 🔴" else 0)
    
    sig = "🟢 BUY" if buy_sc > sell_sc else "🔴 SELL" if sell_sc > buy_sc else "🟡 HOLD"
    trend = "BULLISH" if buy_sc > sell_sc else "BEARISH" if sell_sc > buy_sc else "NEUTRAL"
    
    sl_p, tp_p = (10, 20) if name=="GOLD" else (300, 600)
    ent, sl, tp = price, round(price - sl_p, 2), round(price + tp_p, 2) if "BUY" in sig else round(price + sl_p, 2), round(price - tp_p, 2)
    
    txt = f"{'🥇' if name=='GOLD' else '₿'} *SIGNAL {name}*\n💰 Harga: ${price}\n\n"
    txt += f"⚡ Supertrend: {st}\n📊 RSI: {rsi}\n📉 Bollinger: {bb_u}/{bb_l}\n📈 EMA: {ema9}/{ema21}\n\n"
    txt += f"🎯 *SIGNAL: {sig}*\n📈 *Trend: {trend}*\n\n"
    txt += f"🟢 *ZON BUY:*\n   Entry: ${ent}\n   SL: ${sl}\n   TP: ${tp}\n\n"
    txt += f"⚠️ *NOTA:* Harga pasaran global. Semak MT5 anda sebelum entry."
    return txt

def check_zone_alert(symbol, name):
    price = get_price(symbol)
    if price == 0: return False, None, 0, 0, 0
    df = get_historical_data(symbol)
    if not df: return False, None, 0, 0, 0
    closes = df["close"].tolist()
    rsi = calculate_rsi(closes)
    ema9, ema21 = calculate_ema(closes, 9), calculate_ema(closes, 21)
    st = calculate_supertrend(df)
    
    sl_p, tp_p = (10, 20) if name=="GOLD" else (300, 600)
    if rsi <= 35 and ema9 > ema21 and st == "BULLISH 🟢":
        return True, "BUY", price, round(price+tp_p, 2), round(price-sl_p, 2)
    elif rsi >= 65 and ema9 < ema21 and st == "BEARISH 🔴":
        return True, "SELL", price, round(price-tp_p, 2), round(price+sl_p, 2)
    return False, None, 0, 0, 0
