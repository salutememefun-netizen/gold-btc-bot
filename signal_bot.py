import pandas as pd
import pandas_ta as ta
import yfinance as yf
from datetime import datetime

# --- 1. Konfigurasi ---
# Tukar simbol di sini: 'BTC-USD' (Bitcoin) atau 'GC=F' (Gold Futures)
SYMBOL = 'GC=F' 
INTERVAL = '15m'  # Timeframe: 15m, 1h, 4h, 1d

# --- 2. Fungsi Ambil Data ---
def get_data(symbol, interval):
    try:
        print(f"🔄 Mengambil data {symbol}...")
        df = yf.download(symbol, period="5d", interval=interval, progress=False)
        
        # Bersihkan data (yfinance kadang-kadang ada multi-level columns)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
            
        if df.empty:
            return None
            
        return df
    except Exception as e:
        print(f"❌ Ralat: {e}")
        return None

# --- 3. Fungsi Analisis (FVG, BOS, Supertrend) ---
def analyze(df):
    if df is None or len(df) < 10:
        return "❌ Data tidak mencukupi untuk analisis."

    # A. Supertrend (10, 3)
    st = ta.supertrend(df['High'], df['Low'], df['Close'], length=10, multiplier=3)
    df = pd.concat([df, st], axis=1)
    
    curr = df.iloc[-1]
    prev = df.iloc[-2]
    
    price = curr['Close']
    st_val = curr['SUPERT_10_3.0']
    st_dir = curr['SUPERTd_10_3.0'] # 1 = Buy, -1 = Sell
    
    trend = "BULLISH 🟢" if st_dir == 1 else "BEARISH 🔴"
    sig = "BUY" if st_dir == 1 else "SELL"
    
    # B. FVG (Fair Value Gap) - 3 Candle
    c1_high = df['High'].iloc[-3]
    c1_low = df['Low'].iloc[-3]
    c3_low = curr['Low']
    c3_high = curr['High']
    
    fvg_b = (c1_high, c3_low) if c3_low > c1_high else None
    fvg_s = (c1_low, c3_high) if c3_high < c1_low else None
    
    # C. BOS (Break of Structure)
    swing_h = df['High'].iloc[-5]
    swing_l = df['Low'].iloc[-5]
    bos = "None"
    if price > swing_h and st_dir == 1: bos = "Bullish BOS ✅"
    elif price < swing_l and st_dir == -1: bos = "Bearish BOS ✅"
    
    # D. SL & TP (Risk 1%, Reward 2%)
    risk = 0.01
    ratio = 2.0
    
    if st_dir == 1: # BUY
        entry = fvg_b[0] if fvg_b else price
        sl = fvg_b[0] * (1 - risk) if fvg_b else st_val
        tp = entry + ((entry - sl) * ratio)
    else: # SELL
        entry = fvg_s[1] if fvg_s else price
        sl = fvg_s[1] * (1 + risk) if fvg_s else st_val
        tp = entry - ((sl - entry) * ratio)
        
    # E. Format Output
    ts = datetime.now().strftime("%H:%M")
    name = "GOLD" if "GC" in SYMBOL else "BTC"
    
    return f"""
📊 *SIGNAL ULTIMATE: {name}*

💰 *Harga:* ${price:,.2f}
📈 *Trend:* {trend}
⚡ *Isyarat:* {sig}

🏗️ *BOS:* {bos}

🕳️ *FVG:*
   {'✅ Bullish: $' + f"{fvg_b[0]:,.2f}" + ' – $' + f"{fvg_b[1]:,.2f}" if fvg_b else '❌ Tiada'}
   {'✅ Bearish: $' + f"{fvg_s[0]:,.2f}" + ' – $' + f"{fvg_s[1]:,.2f}" if fvg_s else '❌ Tiada'}

🟢 *ZON BUY:*
   Entry: ${entry:,.2f}
   SL: ${sl:,.2f}
   TP: ${tp:,.2f}

🔴 *ZON SELL:*
   Entry: ${entry:,.2f}
   SL: ${sl:,.2f}
   TP: ${tp:,.2f}

⚠️ *Amaran:* Gunakan pengurusan modal.
   (Dijana: {ts})
"""

# --- 4. Jalankan ---
if __name__ == "__main__":
    data = get_data(SYMBOL, INTERVAL)
    if data is not None:
        print(analyze(data))
    else:
        print("Gagal menjana signal.")
