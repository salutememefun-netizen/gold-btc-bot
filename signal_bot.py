import pandas as pd
import pandas_ta as ta
import yfinance as yf
from datetime import datetime

def get_data(symbol, interval="15m", period="5d"):
    """Ambil data OHLC dari Yahoo Finance"""
    try:
        df = yf.download(symbol, period=period, interval=interval, progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        if df.empty:
            return None
        return df
    except Exception as e:
        print(f"Ralat get_data: {e}")
        return None

def get_price(symbol):
    """Ambil harga terkini sahaja"""
    try:
        df = yf.download(symbol, period="1d", interval="1m", progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return round(float(df['Close'].iloc[-1]), 2)
    except:
        return None

def detect_fvg(df):
    """Detect Fair Value Gap dari 3 candle terakhir"""
    c1_high = df['High'].iloc[-3]
    c1_low  = df['Low'].iloc[-3]
    c3_low  = df['Low'].iloc[-1]
    c3_high = df['High'].iloc[-1]

    fvg_bullish = (round(c1_high, 2), round(c3_low, 2)) if c3_low > c1_high else None
    fvg_bearish = (round(c1_low, 2), round(c3_high, 2)) if c3_high < c1_low else None

    return fvg_bullish, fvg_bearish

def detect_bos(df, st_dir):
    """Detect Break of Structure berdasarkan swing high/low"""
    price     = df['Close'].iloc[-1]
    swing_h   = df['High'].iloc[-6:-1].max()
    swing_l   = df['Low'].iloc[-6:-1].min()

    if price > swing_h and st_dir == 1:
        return f"✅ Bullish BOS (Pecah ${swing_h:,.2f})"
    elif price < swing_l and st_dir == -1:
        return f"✅ Bearish BOS (Pecah ${swing_l:,.2f})"
    else:
        return "⏳ Tiada BOS"

def generate_signal(symbol="GC=F", name="GOLD"):
    """Jana signal lengkap dengan Supertrend, FVG, BOS"""
    try:
        df = get_data(symbol)
        if df is None or len(df) < 10:
            return f"❌ Data {name} tidak mencukupi."

        # --- Supertrend ---
        st = ta.supertrend(df['High'], df['Low'], df['Close'],
                           length=10, multiplier=3)
        df = pd.concat([df, st], axis=1)

        price   = round(float(df['Close'].iloc[-1]), 2)
        st_val  = round(float(df['SUPERT_10_3.0'].iloc[-1]), 2)
        st_dir  = int(df['SUPERTd_10_3.0'].iloc[-1])

        trend   = "BULLISH 🟢" if st_dir == 1 else "BEARISH 🔴"
        signal  = "BUY 🟢"    if st_dir == 1 else "SELL 🔴"

        # --- RSI ---
        df['RSI'] = ta.rsi(df['Close'], length=14)
        rsi = round(float(df['RSI'].iloc[-1]), 2)
        if rsi >= 70:
            rsi_status = f"🔴 Overbought ({rsi}) — Harga terlalu tinggi"
        elif rsi <= 30:
            rsi_status = f"🟢 Oversold ({rsi}) — Harga terlalu rendah"
        else:
            rsi_status = f"🟡 Neutral ({rsi})"

        # --- Bollinger Bands ---
        bb = ta.bbands(df['Close'], length=20, std=2)
        df = pd.concat([df, bb], axis=1)
        bb_upper = round(float(df['BBU_20_2.0'].iloc[-1]), 2)
        bb_lower = round(float(df['BBL_20_2.0'].iloc[-1]), 2)

        # --- EMA ---
        df['EMA9']  = ta.ema(df['Close'], length=9)
        df['EMA21'] = ta.ema(df['Close'], length=21)
        ema9  = round(float(df['EMA9'].iloc[-1]), 2)
        ema21 = round(float(df['EMA21'].iloc[-1]), 2)
        ema_signal = "🟢 BUY (Golden Cross)" if ema9 > ema21 else "🔴 SELL (Death Cross)"

        # --- FVG ---
        fvg_b, fvg_s = detect_fvg(df)

        # --- BOS ---
        bos = detect_bos(df, st_dir)

        # --- Kira Entry, SL, TP ---
        risk  = 0.005 # 0.5% risiko
        ratio = 2.0   # 1:2 reward

        if st_dir == 1: # BUY
            entry = fvg_b[0] if fvg_b else price
            sl    = round(entry * (1 - risk), 2)
            tp    = round(entry + ((entry - sl) * ratio), 2)
        else: # SELL
            entry = fvg_s[1] if fvg_s else price
            sl    = round(entry * (1 + risk), 2)
            tp    = round(entry - ((sl - entry) * ratio), 2)

        ts = datetime.now().strftime("%d/%m/%Y %H:%M")

        # --- Format Mesej Telegram (ELAKKAN kutip dalam f-string) ---
        fvg_b_str = f"✅ Bullish: ${fvg_b[0]:,.2f} – ${fvg_b[1]:,.2f}" if fvg_b else "❌ Tiada Bullish FVG"
        fvg_s_str = f"✅ Bearish: ${fvg_s[0]:,.2f} – ${fvg_s[1]:,.2f}" if fvg_s else "❌ Tiada Bearish FVG"

        msg = (
            f"📊 *SIGNAL ULTIMATE: {name}*\n\n"
            f"💰 *Harga:* ${price:,.2f}\n"
            f"📈 *Trend:* {trend}\n"
            f"⚡ *Supertrend:* {signal}\n\n"
            f"📉 *RSI (14):*\n   {rsi_status}\n\n"
            f"📊 *Bollinger Band:*\n   Upper: ${bb_upper:,.2f} | Lower: ${bb_lower:,.2f}\n\n"
            f"📉 *EMA Crossover:*\n   EMA9: ${ema9:,.2f} | EMA21: ${ema21:,.2f}\n"
            f"   Isyarat: {ema_signal}\n\n"
            f"🏗️ *BOS (Break of Structure):*\n   {bos}\n\n"
            f"🕳️ *FVG (Fair Value Gap):*\n   {fvg_b_str}\n   {fvg_s_str}\n\n"
            f"🟢 *ZON BUY (LONG):*\n"
            f"   Entry: ${entry:,.2f}\n"
            f"   Stop Loss: ${sl:,.2f}\n"
            f"   Take Profit: ${tp:,.2f}\n\n"
            f"🔴 *ZON SELL (SHORT):*\n"
            f"   Entry: ${entry:,.2f}\n"
            f"   Stop Loss: ${sl:,.2f}\n"
            f"   Take Profit: ${tp:,.2f}\n\n"
            f"⚠️ *Amaran:* Gunakan pengurusan modal.\n"
            f"   Analisis automatik sahaja.\n"
            f"   (Dijana: {ts})"
        )
        return msg

    except Exception as e:
        return f"❌ Ralat menjana signal: {e}"
