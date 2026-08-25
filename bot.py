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
        print("Ralat get_data: " + str(e))
        return None

def get_price(symbol):
    try:
        df = yf.download(symbol, period="1d", interval="1m", progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return round(float(df['Close'].iloc[-1]), 2)
    except Exception:
        return None

def detect_fvg(df):
    c1_high = float(df['High'].iloc[-3])
    c1_low = float(df['Low'].iloc[-3])
    c3_low = float(df['Low'].iloc[-1])
    c3_high = float(df['High'].iloc[-1])
    fvg_b = (round(c1_high, 2), round(c3_low, 2)) if c3_low > c1_high else None
    fvg_s = (round(c1_low, 2), round(c3_high, 2)) if c3_high < c1_low else None
    return fvg_b, fvg_s

def detect_bos(df, st_dir):
    price = float(df['Close'].iloc[-1])
    swing_h = float(df['High'].iloc[-6:-1].max())
    swing_l = float(df['Low'].iloc[-6:-1].min())
    if price > swing_h and st_dir == 1:
        return "✅ Bullish BOS (Pecah $" + f"{swing_h:,.2f})"
    elif price < swing_l and st_dir == -1:
        return "✅ Bearish BOS (Pecah $" + f"{swing_l:,.2f})"
    return "⏳ Tiada BOS"

def find_col(df, keyword, exclude=None):
    for col in df.columns:
        col_str = str(col)
        if keyword in col_str:
            if exclude and exclude in col_str:
                continue
            return col
    return None

def get_indicators(df):
    st = ta.supertrend(df['High'], df['Low'], df['Close'], length=10, multiplier=3)
    df = pd.concat([df, st], axis=1)
    st_col = find_col(df, 'SUPERT_', exclude='SUPERTd')
    st_dir_col = find_col(df, 'SUPERTd')
    if not st_col or not st_dir_col:
        return None
    price = round(float(df['Close'].iloc[-1]), 2)
    st_val = round(float(df[st_col].iloc[-1]), 2)
    st_dir = int(df[st_dir_col].iloc[-1])
    df['RSI'] = ta.rsi(df['Close'], length=14)
    rsi = round(float(df['RSI'].iloc[-1]), 2)
    bb = ta.bbands(df['Close'], length=20, std=2)
    df = pd.concat([df, bb], axis=1)
    bb_up_col = find_col(df, 'BBU_')
    bb_lo_col = find_col(df, 'BBL_')
    bb_upper = round(float(df[bb_up_col].iloc[-1]), 2) if bb_up_col else price
    bb_lower = round(float(df[bb_lo_col].iloc[-1]), 2) if bb_lo_col else price
    df['EMA9'] = ta.ema(df['Close'], length=9)
    df['EMA21'] = ta.ema(df['Close'], length=21)
    ema9 = round(float(df['EMA9'].iloc[-1]), 2)
    ema21 = round(float(df['EMA21'].iloc[-1]), 2)
    fvg_b, fvg_s = detect_fvg(df)
    bos = detect_bos(df, st_dir)
    return {
        "df": df,
        "price": price,
        "st_dir": st_dir,
        "st_val": st_val,
        "rsi": rsi,
        "bb_upper": bb_upper,
        "bb_lower": bb_lower,
        "ema9": ema9,
        "ema21": ema21,
        "fvg_b": fvg_b,
        "fvg_s": fvg_s,
        "bos": bos
    }

def generate_signal(symbol="GC=F", name="GOLD"):
    try:
        df = get_data(symbol)
        if df is None or len(df) < 10:
            return "❌ Data " + name + " tidak mencukupi."
        result = get_indicators(df)
        if result is None:
            return "❌ Kolom Supertrend tidak jumpa."
        price = result["price"]
        st_dir = result["st_dir"]
        rsi = result["rsi"]
        bb_upper = result["bb_upper"]
        bb_lower = result["bb_lower"]
        ema9 = result["ema9"]
        ema21 = result["ema21"]
        fvg_b = result["fvg_b"]
        fvg_s = result["fvg_s"]
        bos = result["bos"]
        trend = "BULLISH 🟢" if st_dir == 1 else "BEARISH 🔴"
        signal = "BUY 🟢" if st_dir == 1 else "SELL 🔴"
        if rsi >= 70:
            rsi_status = "🔴 Overbought (" + str(rsi) + ")"
        elif rsi <= 30:
            rsi_status = "🟢 Oversold (" + str(rsi) + ")"
        else:
            rsi_status = "🟡 Neutral (" + str(rsi) + ")"
        ema_sig = "🟢 BUY (Golden Cross)" if ema9 > ema21 else "🔴 SELL (Death Cross)"
        fvg_b_str = "✅ Bullish: $" + f"{fvg_b[0]:,.2f}" + " - $" + f"{fvg_b[1]:,.2f}" if fvg_b else "❌ Tiada Bullish FVG"
        fvg_s_str = "✅ Bearish: $" + f"{fvg_s[0]:,.2f}" + " - $" + f"{fvg_s[1]:,.2f}" if fvg_s else "❌ Tiada Bearish FVG"
        risk = 0.005
        ratio = 2.0
        buy_entry = fvg_b[0] if fvg_b else round(price * 0.998, 2)
        buy_sl = round(buy_entry * (1 - risk), 2)
        buy_tp = round(buy_entry + ((buy_entry - buy_sl) * ratio), 2)
        sell_entry = fvg_s[1] if fvg_s else round(price * 1.002, 2)
        sell_sl = round(sell_entry * (1 + risk), 2)
        sell_tp = round(sell_entry - ((sell_sl - sell_entry) * ratio), 2)
        ts = datetime.now().strftime("%d/%m/%Y %H:%M")
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
            "🏗 *BOS (Break of Structure):*",
            "   " + bos,
            "",
            "🕳 *FVG (Fair Value Gap):*",
            "   " + fvg_b_str,
            "   " + fvg_s_str,
            "",
            "🟢 *ZON BUY (LONG):*",
            "   Entry: $" + f"{buy_entry:,.2f}",
            "   Stop Loss: $" + f"{buy_sl:,.2f}",
            "   Take Profit: $" + f"{buy_tp:,.2f}",
            "",
            "🔴 *ZON SELL (SHORT):*",
            "   Entry: $" + f"{sell_entry:,.2f}",
            "   Stop Loss: $" + f"{sell_sl:,.2f}",
            "   Take Profit: $" + f"{sell_tp:,.2f}",
            "",
            "⚠ *Amaran:* Gunakan pengurusan modal.",
            "   Analisis automatik sahaja.",
            "   (Dijana: " + ts + ")"
        ]
        return "\n".join(lines)
    except Exception as e:
        return "❌ Ralat menjana signal: " + str(e)

def check_zone_alert(symbol="GC=F", name="GOLD"):
    try:
        df = get_data(symbol)
        if df is None or len(df) < 10:
            return False, None, 0, 0, 0
        result = get_indicators(df)
        if result is None:
            return False, None, 0, 0, 0
        price = result["price"]
        st_dir = result["st_dir"]
        fvg_b = result["fvg_b"]
        fvg_s = result["fvg_s"]
        risk = 0.005
        ratio = 2.0
        buy_entry = fvg_b[0] if fvg_b else round(price * 0.998, 2)
        buy_sl = round(buy_entry * (1 - risk), 2)
        buy_tp = round(buy_entry + ((buy_entry - buy_sl) * ratio), 2)
        sell_entry = fvg_s[1] if fvg_s else round(price * 1.002, 2)
        sell_sl = round(sell_entry * (1 + risk), 2)
        sell_tp = round(sell_entry - ((sell_sl - sell_entry) * ratio), 2)
        if st_dir == 1 and buy_sl <= price <= buy_tp:
            return True, "BUY", buy_entry, buy_tp, buy_sl
        if st_dir == -1 and sell_tp <= price <= sell_sl:
            return True, "SELL", sell_entry, sell_tp, sell_sl
        return False, None, 0, 0, 0
    except Exception as e:
        print("Ralat check_zone_alert: " + str(e))
        return False, None, 0, 0, 0
