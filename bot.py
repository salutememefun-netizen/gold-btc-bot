#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import logging
import signal
import sys
import requests
from datetime import datetime
from zoneinfo import ZoneInfo

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# ----------------------------------------------------------------------
#  Configuration & Global Variables
# ----------------------------------------------------------------------
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

TOKEN             = os.getenv("BOT_TOKEN")
ALPHA_VANTAGE_KEY = os.getenv("ALPHA_VANTAGE_KEY", "demo")
MY_TZ             = ZoneInfo("Asia/Kuala_Lumpur")

SYMBOLS = {
    "gold": ["GC=F", "XAUUSD=X"],
    "btc":  ["BTC-USD"],
}

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 "
        "Chrome/120 Safari/537.36"
    )
})

# ----------------------------------------------------------------------
#  Market Status
# ----------------------------------------------------------------------
def gold_market_status():
    now  = datetime.now(MY_TZ)
    wd   = now.weekday()
    mins = now.hour * 60 + now.minute
    if wd == 5:
        return False, "WEEKEND"
    if wd == 6 and mins < 360:
        return False, "WEEKEND"
    if 300 <= mins < 360:
        return False, "DAILY BREAK"
    return True, "OPEN"


def btc_market_status():
    return True, "OPEN 24/7"


# ----------------------------------------------------------------------
#  Live Price - Gold (gold-api.com)
# ----------------------------------------------------------------------
def get_gold_price_goldapi():
    try:
        r = SESSION.get("https://gold-api.com/price/XAU", timeout=10)
        if r.status_code == 200:
            price = r.json().get("price")
            if price:
                return float(price), "gold-api.com"
    except Exception as exc:
        logger.warning(f"gold-api.com error: {exc}")
    return None, None


# ----------------------------------------------------------------------
#  Live Price - BTC (Binance)
# ----------------------------------------------------------------------
def get_btc_price_binance():
    try:
        r = SESSION.get(
            "https://api.binance.com/api/v3/ticker/price",
            params={"symbol": "BTCUSDT"},
            timeout=10,
        )
        if r.status_code == 200:
            price = r.json().get("price")
            if price:
                return float(price), "Binance"
    except Exception as exc:
        logger.warning(f"Binance price error: {exc}")
    return None, None


# ----------------------------------------------------------------------
#  BTC Candles - Binance
# ----------------------------------------------------------------------
def get_btc_candles_binance(interval="15m", limit=100):
    try:
        r = SESSION.get(
            "https://api.binance.com/api/v3/klines",
            params={"symbol": "BTCUSDT", "interval": interval, "limit": limit},
            timeout=15,
        )
        if r.status_code != 200:
            return []
        candles = []
        for k in r.json():
            try:
                candles.append({
                    "time":  int(k[0]) // 1000,
                    "open":  float(k[1]),
                    "high":  float(k[2]),
                    "low":   float(k[3]),
                    "close": float(k[4]),
                })
            except (IndexError, ValueError):
                continue
        return candles
    except Exception as exc:
        logger.warning(f"Binance candles error: {exc}")
        return []


# ----------------------------------------------------------------------
#  Gold Candles - Yahoo Finance (fallback: Binance XAUUSDT)
# ----------------------------------------------------------------------
def yahoo_candles(symbol, interval="15m", range_value="5d"):
    try:
        r = SESSION.get(
            f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}",
            params={
                "interval":       interval,
                "range":          range_value,
                "includePrePost": "true",
                "events":         "div,splits",
            },
            timeout=20,
        )
        if r.status_code != 200:
            return []
        result = r.json().get("chart", {}).get("result")
        if not result:
            return []
        x  = result[0]
        ts = x.get("timestamp") or []
        ql = x.get("indicators", {}).get("quote", [])
        if not ql:
            return []
        q = ql[0]
        o = q.get("open",  [])
        h = q.get("high",  [])
        l = q.get("low",   [])
        c = q.get("close", [])
        out = []
        for i, t in enumerate(ts):
            try:
                vals = (o[i], h[i], l[i], c[i])
                if any(v is None for v in vals):
                    continue
                out.append({
                    "time":  t,
                    "open":  float(o[i]),
                    "high":  float(h[i]),
                    "low":   float(l[i]),
                    "close": float(c[i]),
                })
            except (IndexError, TypeError, ValueError):
                continue
        return out
    except Exception as e:
        logger.warning("Yahoo %s error: %s", symbol, e)
        return []


def get_gold_candles_binance(interval="15m", limit=100):
    try:
        r = SESSION.get(
            "https://api.binance.com/api/v3/klines",
            params={"symbol": "XAUUSDT", "interval": interval, "limit": limit},
            timeout=15,
        )
        if r.status_code != 200:
            return []
        candles = []
        for k in r.json():
            try:
                candles.append({
                    "time":  int(k[0]) // 1000,
                    "open":  float(k[1]),
                    "high":  float(k[2]),
                    "low":   float(k[3]),
                    "close": float(k[4]),
                })
            except (IndexError, ValueError):
                continue
        return candles
    except Exception as exc:
        logger.warning(f"Binance Gold candles error: {exc}")
        return []


def get_candles(asset, interval="15m", minimum=20):
    if asset == "btc":
        candles = get_btc_candles_binance(interval=interval, limit=100)
        if len(candles) >= minimum:
            return candles, "Binance"
        return [], None

    if asset == "gold":
        for symbol in SYMBOLS["gold"]:
            for rv in ["5d", "1mo", "3mo"]:
                candles = yahoo_candles(symbol, interval, rv)
                if len(candles) >= minimum:
                    return candles, symbol
        candles = get_gold_candles_binance(interval=interval, limit=100)
        if len(candles) >= minimum:
            return candles, "Binance XAUUSDT"
        return [], None

    return [], None


# ----------------------------------------------------------------------
#  Live Price (main)
# ----------------------------------------------------------------------
def get_live_price(asset):
    if asset == "gold":
        price, src = get_gold_price_goldapi()
        if price:
            return price, src
        for symbol in SYMBOLS["gold"]:
            try:
                r = SESSION.get(
                    f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}",
                    params={"interval": "1m", "range": "1d", "includePrePost": "true"},
                    timeout=15,
                )
                if r.status_code == 200:
                    result = r.json().get("chart", {}).get("result")
                    if result:
                        price = result[0].get("meta", {}).get("regularMarketPrice")
                        if price:
                            return float(price), symbol
            except Exception as exc:
                logger.warning(f"Yahoo gold error: {exc}")
        try:
            r = SESSION.get(
                "https://www.alphavantage.co/query",
                params={
                    "function": "GLOBAL_QUOTE",
                    "symbol":   "GC=F",
                    "apikey":   ALPHA_VANTAGE_KEY,
                },
                timeout=10,
            )
            if r.status_code == 200:
                price = r.json().get("Global Quote", {}).get("05. price")
                if price:
                    return float(price), "AlphaVantage"
        except Exception as exc:
            logger.warning(f"AlphaVantage error: {exc}")
        return None, None

    if asset == "btc":
        price, src = get_btc_price_binance()
        if price:
            return price, src
        try:
            r = SESSION.get(
                "https://api.coingecko.com/api/v3/simple/price",
                params={"ids": "bitcoin", "vs_currencies": "usd"},
                timeout=10,
            )
            if r.status_code == 200:
                price = r.json().get("bitcoin", {}).get("usd")
                if price:
                    return float(price), "Coingecko"
        except Exception as exc:
            logger.warning(f"Coingecko error: {exc}")
        for symbol in SYMBOLS["btc"]:
            try:
                r = SESSION.get(
                    f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}",
                    params={"interval": "1m", "range": "1d", "includePrePost": "true"},
                    timeout=15,
                )
                if r.status_code == 200:
                    result = r.json().get("chart", {}).get("result")
                    if result:
                        price = result[0].get("meta", {}).get("regularMarketPrice")
                        if price:
                            return float(price), symbol
            except Exception as exc:
                logger.warning(f"Yahoo BTC error: {exc}")
        return None, None

    return None, None


# ----------------------------------------------------------------------
#  Technical Analysis
# ----------------------------------------------------------------------
def compute_rsi(closes, period=14):
    if len(closes) < period + 1:
        return None
    gains, losses = [], []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i - 1]
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    if avg_loss == 0:
        return 100.0
    return round(100 - (100 / (1 + avg_gain / avg_loss)), 2)


def compute_ema(closes, period):
    if len(closes) < period:
        return None
    k   = 2 / (period + 1)
    ema = sum(closes[:period]) / period
    for price in closes[period:]:
        ema = price * k + ema * (1 - k)
    return round(ema, 4)


def compute_macd(closes):
    if len(closes) < 26:
        return None, None, None
    k12 = 2 / 13
    k26 = 2 / 27
    k9  = 2 / 10
    e12 = sum(closes[:12]) / 12
    e26 = sum(closes[:26]) / 26
    macd_vals = []
    for i, price in enumerate(closes):
        if i >= 12:
            e12 = price * k12 + e12 * (1 - k12)
        if i >= 26:
            e26 = price * k26 + e26 * (1 - k26)
            macd_vals.append(e12 - e26)
    if not macd_vals:
        return None, None, None
    macd_line = round(macd_vals[-1], 4)
    if len(macd_vals) < 9:
        return macd_line, None, None
    signal = sum(macd_vals[:9]) / 9
    for v in macd_vals[9:]:
        signal = v * k9 + signal * (1 - k9)
    signal    = round(signal, 4)
    histogram = round(macd_line - signal, 4)
    return macd_line, signal, histogram


def compute_bollinger(closes, period=20):
    if len(closes) < period:
        return None, None, None
    recent = closes[-period:]
    sma    = sum(recent) / period
    std    = (sum((x - sma) ** 2 for x in recent) / period) ** 0.5
    return round(sma - 2 * std, 4), round(sma, 4), round(sma + 2 * std, 4)


def compute_stochastic(candles, k_period=14, d_period=3):
    if len(candles) < k_period + d_period:
        return None, None
    recent  = candles[-k_period:]
    lo      = min(c["low"]  for c in recent)
    hi      = max(c["high"] for c in recent)
    if hi == lo:
        return None, None
    k = round(((candles[-1]["close"] - lo) / (hi - lo)) * 100, 2)
    k_vals = []
    for j in range(d_period):
        end = -(d_period - j - 1) if (d_period - j - 1) > 0 else len(candles)
        seg = candles[-(k_period + d_period - j): end]
        if len(seg) < k_period:
            continue
        seg_lo = min(c["low"]  for c in seg)
        seg_hi = max(c["high"] for c in seg)
        if seg_hi == seg_lo:
            continue
        k_vals.append(((seg[-1]["close"] - seg_lo) / (seg_hi - seg_lo)) * 100)
    d = round(sum(k_vals) / len(k_vals), 2) if k_vals else None
    return k, d


def compute_atr(candles, period=14):
    if len(candles) < period + 1:
        return None
    trs = []
    for i in range(1, len(candles)):
        high       = candles[i]["high"]
        low        = candles[i]["low"]
        prev_close = candles[i - 1]["close"]
        trs.append(max(high - low, abs(high - prev_close), abs(low - prev_close)))
    return round(sum(trs[-period:]) / period, 4)


def compute_support_resistance(candles, lookback=20):
    if len(candles) < lookback:
        return None, None
    recent = candles[-lookback:]
    return (
        round(min(c["low"]  for c in recent), 4),
        round(max(c["high"] for c in recent), 4),
    )


def generate_signal(asset, candles):
    if len(candles) < 30:
        return "❓ Data tidak mencukupi"
    closes = [c["close"] for c in candles]
    rsi    = compute_rsi(closes)
    ema20  = compute_ema(closes, 20)
    ema50  = compute_ema(closes, 50) if len(closes) >= 50 else None
    macd, signal_line, histogram = compute_macd(closes)
    bb_low, _, bb_high = compute_bollinger(closes)
    stoch_k, stoch_d   = compute_stochastic(candles)
    current = closes[-1]
    score   = 0

    if rsi is not None:
        if rsi < 35:   score += 2
        elif rsi < 45: score += 1
        elif rsi > 65: score -= 2
        elif rsi > 55: score -= 1

    if ema20 and ema50:
        if current > ema20 > ema50:   score += 2
        elif current < ema20 < ema50: score -= 2

    if macd and signal_line:
        score += 1 if macd > signal_line else -1

    if histogram:
        score += 1 if histogram > 0 else -1

    if bb_low and bb_high:
        if current < bb_low:    score += 2
        elif current > bb_high: score -= 2

    if stoch_k and stoch_d:
        if stoch_k < 20 and stoch_d < 20:   score += 1
        elif stoch_k > 80 and stoch_d > 80: score -= 1

    if score >= 4:    return "📈 STRONG BUY"
    elif score >= 2:  return "🟢 BUY"
    elif score <= -4: return "📉 STRONG SELL"
    elif score <= -2: return "🔴 SELL"
    else:             return "⏸️ NEUTRAL"


# ----------------------------------------------------------------------
#  Zone Entry, TP & SL
# ----------------------------------------------------------------------
def compute_zones(asset, candles):
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

    atr_tp = atr * 2.0
    atr_sl = atr * 1.0

    buy_zone_low  = round(support, 4)
    buy_zone_high = round(support + atr * 0.5, 4)
    buy_entry     = round((buy_zone_low + buy_zone_high) / 2, 4)
    buy_sl        = round(buy_entry - atr_sl, 4)
    buy_tp1       = round(buy_entry + atr_tp, 4)
    buy_tp2       = round(buy_entry + atr_tp * 2, 4)
    buy_tp3       = round(resistance, 4)

    sell_zone_low  = round(resistance - atr * 0.5, 4)
    sell_zone_high = round(resistance, 4)
    sell_entry     = round((sell_zone_low + sell_zone_high) / 2, 4)
    sell_sl        = round(sell_entry + atr_sl, 4)
    sell_tp1       = round(sell_entry - atr_tp, 4)
    sell_tp2       = round(sell_entry - atr_tp * 2, 4)
    sell_tp3       = round(support, 4)

    return {
        "current":    current,
        "atr":        atr,
        "support":    support,
        "resistance": resistance,
        "rsi":        rsi,
        "ema20":      ema20,
        "ema50":      ema50,
        "bb_low":     bb_low,
        "bb_high":    bb_high,
        "signal":     generate_signal(asset, candles),
        "buy": {
            "zone_low":  buy_zone_low,
            "zone_high": buy_zone_high,
            "entry":     buy_entry,
            "sl":        buy_sl,
            "tp1":       buy_tp1,
            "tp2":       buy_tp2,
            "tp3":       buy_tp3,
            "rr":        round(atr_tp / atr_sl, 2),
        },
        "sell": {
            "zone_low":  sell_zone_low,
            "zone_high": sell_zone_high,
            "entry":     sell_entry,
            "sl":        sell_sl,
            "tp1":       sell_tp1,
            "tp2":       sell_tp2,
            "tp3":       sell_tp3,
            "rr":        round(atr_tp / atr_sl, 2),
        },
    }


# ----------------------------------------------------------------------
#  Format Helpers
# ----------------------------------------------------------------------
def format_price(asset, price):
    if price is None:
        return "N/A"
    if asset == "gold":
        return f"${price:,.2f}"
    return f"${price:,.0f}"


def build_analysis_text(asset, label, emoji, candles, price, src):
    closes = [c["close"] for c in candles]
    rsi    = compute_rsi(closes)
    ema20  = compute_ema(closes, 20)
    ema50  = compute_ema(closes, 50) if len(closes) >= 50 else None
    macd, signal_line, histogram = compute_macd(closes)
    bb_low, bb_mid, bb_high      = compute_bollinger(closes)
    stoch_k, stoch_d             = compute_stochastic(candles)
    sig     = generate_signal(asset, candles)
    now_str = datetime.now(MY_TZ).strftime("%d/%m/%Y %H:%M MYT")
    fp      = lambda p: format_price(asset, p)

    lines = [
        f"{emoji} *{label}*",
        f"💰 Harga: `{fp(price)}`  _(src: {src})_",
        f"🕐 Masa: {now_str}",
        "",
        "📊 *Indikator Teknikal:*",
        f"  • RSI(14):   `{rsi if rsi else 'N/A'}`",
        f"  • EMA20:     `{fp(ema20)}`",
        f"  • EMA50:     `{fp(ema50)}`",
        f"  • MACD:      `{macd if macd else 'N/A'}` | Signal: `{signal_line if signal_line else 'N/A'}`",
        f"  • Histogram: `{histogram if histogram else 'N/A'}`",
        f"  • BB Low:    `{fp(bb_low)}`",
        f"  • BB Mid:    `{fp(bb_mid)}`",
        f"  • BB High:   `{fp(bb_high)}`",
        f"  • Stoch K:   `{stoch_k if stoch_k else 'N/A'}` | D: `{stoch_d if stoch_d else 'N/A'}`",
        "",
        f"🎯 *Signal: {sig}*",
    ]
    return "\n".join(lines)


def build_zone_text(asset, label, emoji, zones, price, src):
    if not zones:
        return f"{emoji} *{label}*\n❌ Tidak dapat mengira zon."
    now_str = datetime.now(MY_TZ).strftime("%d/%m/%Y %H:%M MYT")
    fp      = lambda p: format_price(asset, p)

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
        f"📊 EMA20:      `{fp(zones['ema20'])}`",
        f"📊 EMA50:      `{fp(zones['ema50'])}`",
        "",
        "⚠️ _Bukan nasihat kewangan. Guna pengurusan risiko._",
    ]
    return "\n".join(lines)


# ----------------------------------------------------------------------
#  Command Handlers
# ----------------------------------------------------------------------
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "👋 *Selamat datang ke Signal Bot!*\n\n"
        "📌 *Arahan tersedia:*\n"
        "  /harga  — Harga semasa Gold & BTC\n"
        "  /gold   — Analisis teknikal Gold\n"
        "  /btc    — Analisis teknikal Bitcoin\n"
        "  /signal — Signal ringkas Gold & BTC\n"
        "  /zone   — Zon entry BUY/SELL + TP & SL\n"
        "  /help   — Bantuan\n\n"
        "⚡ Data dari gold\-api\.com, Binance & Coingecko\."
    )
    await update.message.reply_text(msg, parse_mode="Markdown")


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await cmd_start(update, context)


async def cmd_harga(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Mengambil harga semasa...")

    gold_price, gold_src = get_live_price("gold")
    btc_price,  btc_src  = get_live_price("btc")
    now_str              = datetime.now(MY_TZ).strftime("%d/%m/%Y %H:%M MYT")
    _, gold_status       = gold_market_status()
    _, btc_status        = btc_market_status()

    gold_str = format_price("gold", gold_price) if gold_price else "❌ Harga tidak tersedia"
    btc_str  = format_price("btc",  btc_price)  if btc_price  else "❌ Harga tidak tersedia"

    msg = (
        f"📈 *HARGA SEMASA*\n\n"
        f"🥇 *Gold XAUUSD*\n"
        f"  💰 {gold_str}\n"
        f"  📡 Status: {gold_status}\n\n"
        f"₿ *Bitcoin BTC*\n"
        f"  💰 {btc_str}\n"
        f"  📡 Status: {btc_status}\n\n"
        f"🕐 {now_str}"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")


async def cmd_gold(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Menganalisis Gold...")

    price, src = get_live_price("gold")
    if price is None:
        await update.message.reply_text("❌ Gagal mendapatkan harga Gold.")
        return

    candles, sym = get_candles("gold", "15m")
    if not candles:
        await update.message.reply_text("❌ Gagal mendapatkan data candle Gold.")
        return

    text = build_analysis_text("gold", "Gold XAUUSD", "🥇", candles, price, src)
    await update.message.reply_text(text, parse_mode="Markdown")


async def cmd_btc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Menganalisis Bitcoin...")

    price, src = get_live_price("btc")
    if price is None:
        await update.message.reply_text("❌ Gagal mendapatkan harga Bitcoin.")
        return

    candles, sym = get_candles("btc", "15m")
    if not candles:
        await update.message.reply_text("❌ Gagal mendapatkan data candle Bitcoin.")
        return

    text = build_analysis_text("btc", "Bitcoin BTC", "₿", candles, price, src)
    await update.message.reply_text(text, parse_mode="Markdown")


async def cmd_signal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Menjana signal...")

    now_str          = datetime.now(MY_TZ).strftime("%d/%m/%Y %H:%M MYT")
    gold_price, _    = get_live_price("gold")
    gold_candles, _  = get_candles("gold", "15m")
    gold_sig         = generate_signal("gold", gold_candles) if gold_candles else "❌ Tiada data"
    gold_str         = format_price("gold", gold_price) if gold_price else "❌ Tiada harga"

    btc_price, _     = get_live_price("btc")
    btc_candles, _   = get_candles("btc", "15m")
    btc_sig          = generate_signal("btc", btc_candles) if btc_candles else "❌ Tiada data"
    btc_str          = format_price("btc", btc_price) if btc_price else "❌ Tiada harga"

    msg = (
        f"🎯 *SIGNAL RINGKAS*\n\n"
        f"🥇 *Gold XAUUSD*\n"
        f"  💰 {gold_str}\n"
        f"  {gold_sig}\n\n"
        f"₿ *Bitcoin BTC*\n"
        f"  💰 {btc_str}\n"
        f"  {btc_sig}\n\n"
        f"🕐 {now_str}\n\n"
        f"⚠️ _Bukan nasihat kewangan._"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")


async def cmd_zone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Mengira zon entry...")

    gold_price, gold_src = get_live_price("gold")
    gold_candles, _      = get_candles("gold", "15m")
    if gold_price and gold_candles:
        gold_zones = compute_zones("gold", gold_candles)
        gold_text  = build_zone_text("gold", "Gold XAUUSD", "🥇", gold_zones, gold_price, gold_src)
    else:
        gold_text = "🥇 *Gold XAUUSD*\n❌ Gagal mendapatkan data Gold."
    await update.message.reply_text(gold_text, parse_mode="Markdown")

    btc_price, btc_src = get_live_price("btc")
    btc_candles, _     = get_candles("btc", "15m")
    if btc_price and btc_candles:
        btc_zones = compute_zones("btc", btc_candles)
        btc_text  = build_zone_text("btc", "Bitcoin BTC", "₿", btc_zones, btc_price, btc_src)
    else:
        btc_text = "₿ *Bitcoin BTC*\n❌ Gagal mendapatkan data BTC."
    await update.message.reply_text(btc_text, parse_mode="Markdown")


# ----------------------------------------------------------------------
#  Graceful Shutdown
# ----------------------------------------------------------------------
def handle_exit(signum, frame):
    logger.info("Received signal %s, shutting down...", signum)
    sys.exit(0)


# ----------------------------------------------------------------------
#  Main
# ----------------------------------------------------------------------
def main():
    if not TOKEN:
        logger.error("BOT_TOKEN environment variable not set!")
        sys.exit(1)

    signal.signal(signal.SIGINT,  handle_exit)
    signal.signal(signal.SIGTERM, handle_exit)

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start",  cmd_start))
    app.add_handler(CommandHandler("help",   cmd_help))
    app.add_handler(CommandHandler("harga",  cmd_harga))
    app.add_handler(CommandHandler("gold",   cmd_gold))
    app.add_handler(CommandHandler("btc",    cmd_btc))
    app.add_handler(CommandHandler("signal", cmd_signal))
    app.add_handler(CommandHandler("zone",   cmd_zone))

    logger.info("Bot started. Polling...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
