import pandas as pd
import pandas_ta as ta
import yfinance as yf
from datetime import datetime

def get_data(symbol, interval="15m", period="5d"):
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
    try:
        df = yf.download(symbol, period="1d", interval="1m", progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return round(float(df['Close'].iloc[-1]), 2)
    except:
        return None

def detect_fvg(df):
    c1_high = float(df['High'].iloc[-3])
    c1_low  = float(df['Low'].iloc[-3])
    c3_low  = float(df['Low'].iloc[-1])
    c3_high = float(df['High'].iloc[-1])
    fvg_b = (round(c1_high, 2), round(c3_low, 2)) if c3_low > c1_high else None
    fvg_s = (round(c1_low, 2), round(c3_high, 2)) if c3_high < c1_low else None
    return fvg_b, fvg_s

def detect_bos(df, st_dir):
    price   = float(df['Close'].iloc[-1])
    swing_h = float(df['High'].iloc[-6:-1].max())
    swing_l = float(df['Low'].iloc[-6:-1].min())
    if price > swing_h and st_dir == 1:
        return "✅ Bullish BOS (Pecah $" + f"{swing_h:,.2f})"
    elif price < swing_l and st_dir == -1:
        return "✅ Bearish BOS (Pecah $" + f"{swing_l:,.2f})"
    else:
        return "⏳ Tiada BOS"

def generate_signal(symbol="GC=F", name="GOLD"):
    try:
        df = get_data(symbol)
        if df is None or len(df) < 10:
            return "❌ Data " + name + " tidak mencukupi."

        # Supertrend
        st = ta.supertrend(df['High'], df['Low'], df['Close'], length=10, multiplier=3)
        df = pd.concat([df, st], axis=1)

        price  = round(float(df['Close'].iloc[-1]), 2)
        st_val = round(float(df['SUPERT_10_3.0'].iloc[-1]), 2)
        st_dir = int(df['SUPERTd_10_3.0'].iloc[-1])

        trend  = "BULLISH 🟢" if st_dir == 1 else "BEARISH 🔴"
        signal = "BUY 🟢" if st_dir == 1 else "SELL 🔴"

        # RSI
        df['RSI'] = ta.rsi(df['Close'], length=14)
        rsi = round(float(df['RSI'].iloc[-1]), 2)
        if rsi >= 70:
            rsi_status = "🔴 Overbought (" + str(rsi) + ")"
        elif rsi <= 30:
            rsi_status = "🟢 Oversold (" + str(rsi) + ")"
        else:
            rsi_status = "🟡 Neutral (" + str(rsi) + ")"

        # Bollinger Bands
        bb = ta.bbands(df['Close'], length=20, std=2)
        df = pd.concat([df, bb], axis=1)
        bb_upper = round(float(df['BBU_20_2.0'].iloc[-1]), 2)
        bb_lower = round(float(df['BBL_20_2.0'].iloc[-1]), 2)

        # EMA
        df['EMA9']  = ta.ema(df['Close'], length=9)
        df['EMA21'] = ta.ema(df['Close'], length=21)
        ema9  = round(float(df['EMA9'].iloc[-1]), 2)
        ema21 = round(float(df['EMA21'].iloc[-1]), 2)
        ema_sig = "🟢 BUY (Golden Cross)" if ema9 > ema21 else "🔴 SELL (Death Cross)"

        # FVG
        fvg_b, fvg_s = detect_fvg(df)
        if fvg_b:
            fvg_b_str = "✅ Bullish: $" + f"{fvg_b[0]:,.2f}" + " – $" + f"{fvg_b[1]:,.2f}"
        else:
            fvg_b_str = "❌ Tiada Bullish FVG"

        if fvg_s:
            fvg_s_str = "✅ Bearish: $" + f"{fvg_s[0]:,.2f}" + " – $" + f"{fvg_s[1]:,.2f}"
        else:
            fvg_s_str = "❌ Tiada Bearish FVG"

        # BOS
        bos = detect_bos(df, st_dir)

        # Entry, SL, TP
        risk  = 0.005
        ratio = 2.0
        if st_dir == 1:
            entry = fvg_b[0] if fvg_b else price
            sl    = round(entry * (1 - risk), 2)
            tp    = round(entry + ((entry - sl) * ratio), 2)
        else:
            entry = fvg_s[1] if fvg_s else price
            sl    = round(entry * (1 + risk), 2)
            tp    = round(entry - ((sl - entry) * ratio), 2)

        ts = datetime.now().strftime("%d/%m/%Y %H:%M")

        # Bina mesej baris per baris (TIADA f-string kompleks)
        lines = [
            "📊 *SIGNAL ULTIMATE: " + name + "*",
            "",
            "💰 *Harga:* $" + f"{price:,.2f}",
            "📈 *Trend:* " + trend,
            "⚡ *Supertrend:* " + signal,
            "",
            "📉 *RSI (14):*",
            "   " + rsi_status,
            "",
            "📊 *Bollinger Band:*",
            "   Upper: $" + f"{bb_upper:,.2f}" + " | Lower: $" + f"{bb_lower:,.2f}",
            "",
            "📉 *EMA Crossover:*",
            "   EMA9: $" + f"{ema9:,.2f}" + " | EMA21: $" + f"{ema21:,.2f}",
            "   Isyarat: " + ema_sig,
            "",
            "🏗️ *BOS (Break of Structure):*",
            "   " + bos,
            "",
            "🕳️ *FVG (Fair Value Gap):*",
            "   " + fvg_b_str,
            "   " + fvg_s_str,
            "",
            "🟢 *ZON BUY (LONG):*",
            "   Entry: $" + f"{entry:,.2f}",
            "   Stop Loss: $" + f"{sl:,.2f}",
            "   Take Profit: $" + f"{tp:,.2f}",
            "",
            "🔴 *ZON SELL (SHORT):*",
            "   Entry: $" + f"{entry:,.2f}",
            "   Stop Loss: $" + f"{sl:,.2f}",
            "   Take Profit: $" + f"{tp:,.2f}",
            "",
            "⚠️ *Amaran:* Gunakan pengurusan modal.",
            "   Analisis automatik sahaja.",
            "   (Dijana: " + ts + ")"
        ]

        return "\n".join(lines)

    except Exception as e:
        return "❌ Ralat menjana signal: " + str(e)
