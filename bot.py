# ----------------------------------------------------------------------
#  Zone Entry, TP & SL Calculator
# ----------------------------------------------------------------------
def compute_atr(candles, period=14):
    """Average True Range untuk kira jarak TP/SL"""
    if len(candles) < period + 1:
        return None
    trs = []
    for i in range(1, len(candles)):
        high = candles[i]["high"]
        low  = candles[i]["low"]
        prev_close = candles[i - 1]["close"]
        tr = max(
            high - low,
            abs(high - prev_close),
            abs(low - prev_close)
        )
        trs.append(tr)
    atr = sum(trs[-period:]) / period
    return round(atr, 4)


def compute_support_resistance(candles, lookback=20):
    """Kira paras support dan resistance dari candle terkini"""
    if len(candles) < lookback:
        return None, None
    recent = candles[-lookback:]
    support    = min(c["low"]  for c in recent)
    resistance = max(c["high"] for c in recent)
    return round(support, 4), round(resistance, 4)


def compute_zones(asset, candles):
    """
    Kira zon entry BUY dan SELL lengkap dengan TP dan SL.
    Guna ATR untuk jarak TP/SL dan Support/Resistance untuk zon.
    """
    if len(candles) < 30:
        return None

    closes     = [c["close"] for c in candles]
    current    = closes[-1]
    atr        = compute_atr(candles)
    support, resistance = compute_support_resistance(candles)
    rsi        = compute_rsi(closes)
    ema20      = compute_ema(closes, 20)
    ema50      = compute_ema(closes, 50) if len(closes) >= 50 else None
    bb_low, bb_mid, bb_high = compute_bollinger(closes)

    if not atr or not support or not resistance:
        return None

    # Multiplier ATR untuk TP dan SL
    atr_tp = atr * 2.0   # TP = 2x ATR
    atr_sl = atr * 1.0   # SL = 1x ATR

    # ── BUY ZONE ──────────────────────────────────────────────
    # Masuk BUY bila harga dekat support / BB Low
    buy_zone_low  = round(support, 4)
    buy_zone_high = round(support + atr * 0.5, 4)
    buy_entry     = round((buy_zone_low + buy_zone_high) / 2, 4)
    buy_sl        = round(buy_entry - atr_sl, 4)
    buy_tp1       = round(buy_entry + atr_tp, 4)
    buy_tp2       = round(buy_entry + atr_tp * 2, 4)
    buy_tp3       = round(resistance, 4)
    buy_rr        = round(atr_tp / atr_sl, 2)

    # ── SELL ZONE ─────────────────────────────────────────────
    # Masuk SELL bila harga dekat resistance / BB High
    sell_zone_low  = round(resistance - atr * 0.5, 4)
    sell_zone_high = round(resistance, 4)
    sell_entry     = round((sell_zone_low + sell_zone_high) / 2, 4)
    sell_sl        = round(sell_entry + atr_sl, 4)
    sell_tp1       = round(sell_entry - atr_tp, 4)
    sell_tp2       = round(sell_entry - atr_tp * 2, 4)
    sell_tp3       = round(support, 4)
    sell_rr        = round(atr_tp / atr_sl, 2)

    # Tentukan signal semasa
    signal = generate_signal(asset, candles)

    return {
        "current":        current,
        "atr":            atr,
        "support":        support,
        "resistance":     resistance,
        "rsi":            rsi,
        "ema20":          ema20,
        "ema50":          ema50,
        "bb_low":         bb_low,
        "bb_high":        bb_high,
        "signal":         signal,
        "buy": {
            "zone_low":   buy_zone_low,
            "zone_high":  buy_zone_high,
            "entry":      buy_entry,
            "sl":         buy_sl,
            "tp1":        buy_tp1,
            "tp2":        buy_tp2,
            "tp3":        buy_tp3,
            "rr":         buy_rr,
        },
        "sell": {
            "zone_low":   sell_zone_low,
            "zone_high":  sell_zone_high,
            "entry":      sell_entry,
            "sl":         sell_sl,
            "tp1":        sell_tp1,
            "tp2":        sell_tp2,
            "tp3":        sell_tp3,
            "rr":         sell_rr,
        },
    }


def build_zone_text(asset, label, emoji, zones, price, src):
    """Format teks zon entry untuk Telegram"""
    if not zones:
        return f"{emoji} *{label}*\n❌ Tidak dapat mengira zon."

    now_str = datetime.now(MY_TZ).strftime("%d/%m/%Y %H:%M MYT")
    fp = lambda p: format_price(asset, p)

    lines = [
        f"{emoji} *{label} — ZON ENTRY*",
        f"💰 Harga Semasa: `{fp(price)}`  _(src: {src})_",
        f"🕐 {now_str}",
        f"📊 ATR(14): `{fp(zones['atr'])}`",
        f"🎯 Signal: {zones['signal']}",
        "",
        "─────────────────────",
        "🟢 *ZON BUY*",
        f"  📍 Zon Masuk: `{fp(zones['buy']['zone_low'])}` — `{fp(zones['buy']['zone_high'])}`",
        f"  ✅ Entry:     `{fp(zones['buy']['entry'])}`",
        f"  🛑 SL:        `{fp(zones['buy']['sl'])}`",
        f"  🎯 TP1:       `{fp(zones['buy']['tp1'])}`",
        f"  🎯 TP2:       `{fp(zones['buy']['tp2'])}`",
        f"  🎯 TP3:       `{fp(zones['buy']['tp3'])}`",
        f"  📐 R:R        `1 : {zones['buy']['rr']}`",
        "",
        "─────────────────────",
        "🔴 *ZON SELL*",
        f"  📍 Zon Masuk: `{fp(zones['sell']['zone_low'])}` — `{fp(zones['sell']['zone_high'])}`",
        f"  ✅ Entry:     `{fp(zones['sell']['entry'])}`",
        f"  🛑 SL:        `{fp(zones['sell']['sl'])}`",
        f"  🎯 TP1:       `{fp(zones['sell']['tp1'])}`",
        f"  🎯 TP2:       `{fp(zones['sell']['tp2'])}`",
        f"  🎯 TP3:       `{fp(zones['sell']['tp3'])}`",
        f"  📐 R:R        `1 : {zones['sell']['rr']}`",
        "",
        "─────────────────────",
        f"📈 Support:    `{fp(zones['support'])}`",
        f"📉 Resistance: `{fp(zones['resistance'])}`",
        f"〽️ RSI(14):   `{zones['rsi'] if zones['rsi'] else 'N/A'}`",
        f"📊 EMA20:      `{fp(zones['ema20']) if zones['ema20'] else 'N/A'}`",
        f"📊 EMA50:      `{fp(zones['ema50']) if zones['ema50'] else 'N/A'}`",
        "",
        "⚠️ _Bukan nasihat kewangan. Guna pengurusan risiko._",
    ]
    return "\n".join(lines)


# ----------------------------------------------------------------------
#  Command Handler - /zone
# ----------------------------------------------------------------------
async def cmd_zone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Paparkan zon entry BUY/SELL dengan TP dan SL untuk Gold & BTC"""
    await update.message.reply_text("⏳ Mengira zon entry...")

    # ── GOLD ──
    gold_price, gold_src = get_live_price("gold")
    gold_candles, _      = get_candles("gold", "15m")

    if gold_price and gold_candles:
        gold_zones = compute_zones("gold", gold_candles)
        gold_text  = build_zone_text("gold", "Gold XAUUSD", "🥇", gold_zones, gold_price, gold_src)
    else:
        gold_text = "🥇 *Gold XAUUSD*\n❌ Gagal mendapatkan data Gold."

    await update.message.reply_text(gold_text, parse_mode="Markdown")

    # ── BTC ──
    btc_price, btc_src = get_live_price("btc")
    btc_candles, _     = get_candles("btc", "15m")

    if btc_price and btc_candles:
        btc_zones = compute_zones("btc", btc_candles)
        btc_text  = build_zone_text("btc", "Bitcoin BTC", "₿", btc_zones, btc_price, btc_src)
    else:
        btc_text = "₿ *Bitcoin BTC*\n❌ Gagal mendapatkan data BTC."

    await update.message.reply_text(btc_text, parse_mode="Markdown")
