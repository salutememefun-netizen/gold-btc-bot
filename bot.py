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

TOKEN = os.getenv("BOT_TOKEN")
ALPHA_VANTAGE_KEY = os.getenv("ALPHA_VANTAGE_KEY", "demo")
MY_TZ = ZoneInfo("Asia/Kuala_Lumpur")

SYMBOLS = {
    "gold": ["GC=F", "XAUUSD=X"],
    "btc": ["BTC-USD"],
}

SESSION = requests.Session()
SESSION.headers.update(
    {
        "User-Agent": (
            "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 "
            "Chrome/120 Safari/537.36"
        )
    }
)

# ----------------------------------------------------------------------
#  Market status
# ----------------------------------------------------------------------
def gold_market_status():
    now = datetime.now(MY_TZ)
    wd = now.weekday()
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
#  Live Price - Gold (gold-api.com - FREE, no key needed)
# ----------------------------------------------------------------------
def get_gold_price_goldapi():
    """Ambil harga Gold dari gold-api.com (percuma, tiada API key)"""
    try:
        r = SESSION.get(
            "https://gold-api.com/price/XAU",
            timeout=10,
        )
        if r.status_code == 200:
            data = r.json()
            price = data.get("price")
            if price:
                return float(price), "gold-api.com"
    except Exception as exc:
        logger.warning(f"gold-api.com error: {exc}")
    return None, None


# ----------------------------------------------------------------------
#  Live Price - BTC (Binance - FREE, no key needed)
# ----------------------------------------------------------------------
def get_btc_price_binance():
    """Ambil harga BTC dari Binance API (percuma, tiada API key)"""
    try:
        r = SESSION.get(
            "https://api.binance.com/api/v3/ticker/price",
            params={"symbol": "BTCUSDT"},
            timeout=10,
        )
        if r.status_code == 200:
            data = r.json()
            price = data.get("price")
            if price:
                return float(price), "Binance"
    except Exception as exc:
        logger.warning(f"Binance price error: {exc}")
    return None, None


# ----------------------------------------------------------------------
#  BTC Candles - Binance
# ----------------------------------------------------------------------
def get_btc_candles_binance(interval="15m", limit=100):
    """
    Ambil candle BTC dari Binance.
    interval: 1m, 3m, 5m, 15m, 30m, 1h, 4h, 1d
    """
    try:
        r = SESSION.get(
            "https://api.binance.com/api/v3/klines",
            params={
                "symbol": "BTCUSDT",
                "interval": interval,
                "limit": limit,
            },
            timeout=15,
        )
        if r.status_code != 200:
            logger.warning(f"Binance candles HTTP {r.status_code}")
            return []
        raw = r.json()
        candles = []
        for k in raw:
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
#  Gold Candles - Yahoo Finance (fallback ke Binance XAUUSDT jika gagal)
# ----------------------------------------------------------------------
def yahoo_candles(symbol, interval="15m", range_value="5d"):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    try:
        r = SESSION.get(
            url,
            params={
                "interval": interval,
                "range": range_value,
                "includePrePost": "true",
                "events": "div,splits",
            },
            timeout=20,
        )
        if r.status_code != 200:
            logger.warning("%s HTTP %s", symbol, r.status_code)
            return []
        result = r.json().get("chart", {}).get("result")
        if not result:
            return []
        x = result[0]
        ts = x.get("timestamp") or []
        ql = x.get("indicators", {}).get("quote", [])
        if not ql:
            return []
        q = ql[0]
        o, h, l, c = (
            q.get("open", []),
            q.get("high", []),
            q.get("low", []),
            q.get("close", []),
        )
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
    """Fallback: ambil candle XAUUSDT dari Binance"""
    try:
        r = SESSION.get(
            "https://api.binance.com/api/v3/klines",
            params={
                "symbol": "XAUUSDT",
                "interval": interval,
                "limit": limit,
            },
            timeout=15,
        )
        if r.status_code != 200:
            logger.warning(f"Binance Gold candles HTTP {r.status_code}")
            return []
        raw = r.json()
        candles = []
        for k in raw:
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
    """Ambil candle - Cuba Yahoo dulu, fallback ke Binance"""
    if asset == "btc":
        candles = get_btc_candles_binance(interval=interval, limit=100)
        if len(candles) >= minimum:
            logger.info("BTC candles dari Binance: %d", len(candles))
            return candles, "Binance"
        return [], None

    if asset == "gold":
        # Cuba Yahoo Finance dulu
        ranges = ["5d", "1mo", "3mo"]
        for symbol in SYMBOLS.get("gold", []):
            for rv in ranges:
                candles = yahoo_candles(symbol, interval, rv)
                if len(candles) >= minimum:
                    logger.info("Gold candles dari Yahoo [%s/%s]: %d", symbol, rv, len(candles))
                    return candles, symbol
        # Fallback ke Binance XAUUSDT
        logger.warning("Yahoo gagal, cuba Binance XAUUSDT...")
        candles = get_gold_candles_binance(interval=interval, limit=100)
        if len(candles) >= minimum:
            logger.info("Gold candles dari Binance XAUUSDT: %d", len(candles))
            return candles, "Binance XAUUSDT"
        return [], None

    return [], None


# ----------------------------------------------------------------------
#  Live Price (main function)
# ----------------------------------------------------------------------
def get_live_price(asset):
    """
    Return (price, source_symbol). Cuba pelbagai sumber:
    Gold: gold-api.com → Yahoo chart → Yahoo quote → Alpha Vantage
    BTC:  Binance → Coingecko → Yahoo
    """
    session = SESSION

    if asset == "gold":
        # 1️⃣ gold-api.com (paling stabil untuk Gold)
        price, src = get_gold_price_goldapi()
        if price:
            return price, src

        # 2️⃣ Yahoo chart API
        for symbol in SYMBOLS.get("gold", []):
            try:
                r = session.get(
                    f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}",
                    params={"interval": "1m", "range": "1d", "includePrePost": "true"},
                    timeout=15,
                )
                if r.status_code == 200:
                    data = r.json()
                    result = data.get("chart", {}).get("result")
                    if result:
                        meta = result[0].get("meta", {})
                        price = meta.get("regularMarketPrice")
                        if price:
                            return float(price), symbol
            except Exception as exc:
                logger.warning(f"Yahoo chart gold error: {exc}")

        # 3️⃣ Alpha Vantage
        try:
            r = session.get(
                "https://www.alphavantage.co/query",
                params={
                    "function": "GLOBAL_QUOTE",
                    "symbol": "GC=F",
                    "apikey": ALPHA_VANTAGE_KEY,
                },
                timeout=10,
            )
            if r.status_code == 200:
                data = r.json()
                gq = data.get("Global Quote", {})
                price = gq.get("05. price")
                if price:
                    return float(price), "AlphaVantage"
        except Exception as exc:
            logger.warning(f"AlphaVantage error: {exc}")

        return None, None

    if asset == "btc":
        # 1️⃣ Binance (paling stabil untuk BTC)
        price, src = get_btc_price_binance()
        if price:
            return price, src

        # 2️⃣ Coingecko
        try:
            r = session.get(
                "https://api.coingecko.com/api/v3/simple/price",
                params={"ids": "bitcoin", "vs_currencies": "usd"},
                timeout=10,
            )
            if r.status_code == 200:
                data = r.json()
                price = data.get("bitcoin", {}).get("usd")
                if price:
                    return float(price), "Coingecko"
        except Exception as exc:
            logger.warning(f"Coingecko error: {exc}")

        # 3️⃣ Yahoo
        for symbol in SYMBOLS.get("btc", []):
            try:
                r = session.get(
                    f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}",
                    params={"interval": "1m", "range": "1d", "includePrePost": "true"},
                    timeout=15,
                )
                if r.status_code == 200:
                    data = r.json()
                    result = data.get("chart", {}).get("result")
                    if result:
                        meta = result[0].get("meta", {})
                        price = meta.get("regularMarketPrice")
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
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 2)


def compute_ema(closes, period):
    if len(closes) < period:
        return None
    k = 2 / (period + 1)
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
    ema12 = sum(closes[:12]) / 12
    ema26 = sum(closes[:26]) / 26
    for price in closes[12:]:
        ema12 = price * k12 + ema12 * (1 - k12)
    for price in closes[26:]:
        ema26 = price * k26 + ema26 * (1 - k26)
    macd_line = round(ema12 - ema26, 4)

    # Kira signal line (EMA9 of MACD values)
    e12 = sum(closes[:12]) / 12
    e26 = sum(closes[:26]) / 26
    macd_vals = []
    for price in closes[26:]:
        e12 = price * k12 + e12 * (1 - k12)
        e26 = price * k26 + e26 * (1 - k26)
        macd_vals.append(e12 - e26)

    if len(macd_vals) < 9:
        return macd_line, None, None

    signal = sum(macd_vals[:9]) / 9
    for v in macd_vals[9:]:
        signal = v * k9 + signal * (1 - k9)
    signal = round(signal, 4)
    histogram = round(macd_line - signal, 4)
    return macd_line, signal, histogram


def compute_bollinger(closes, period=20):
    if len(closes) < period:
        return None, None, None
    recent = closes[-period:]
    sma = sum(recent) / period
    std = (sum((x - sma) ** 2 for x in recent) / period) ** 0.5
    return round(sma - 2 * std, 4), round(sma, 4), round(sma + 2 * std, 4)


def compute_stochastic(candles, k_period=14, d_period=3):
    if len(candles) < k_period + d_period:
        return None, None
    k_values = []
    for j in range(d_period):
        seg = candles[-(k_period + d_period - j): -(d_period - j) if (d_period - j) > 0 else len(candles)]
        if len(seg) < k_period:
            continue
        lo = min(c["low"] for c in seg)
        hi = max(c["high"] for c in seg)
        if hi == lo:
            continue
        k_values.append(((seg[-1]["close"] - lo) / (hi - lo)) * 100)
    if not k_values:
        return None, None
    recent = candles[-k_period:]
    lo = min(c["low"] for c in recent)
    hi = max(c["high"] for c in recent)
    if hi == lo:
        return None, None
    k = round(((candles[-1]["close"] - lo) / (hi - lo)) * 100, 2)
    d = round(sum(k_values) / len(k_values), 2)
    return k, d


def generate_signal(asset, candles):
    if len(candles) < 30:
        return "❓ Data tidak mencukupi"
    closes = [c["close"] for c in candles]
    rsi = compute_rsi(closes)
    ema20 = compute_ema(closes, 20)
    ema50 = compute_ema(closes, 50) if len(closes) >= 50 else None
    macd, signal_line, histogram = compute_macd(closes)
    bb_low, _, bb_high = compute_bollinger(closes)
    stoch_k, stoch_d = compute_stochastic(candles)
    current = closes[-1]
    score = 0

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
        if current < bb_low:   score += 2
        elif current > bb_high: score -= 2

    if stoch_k and stoch_d:
        if stoch_k < 20 and stoch_d < 20:   score += 1
        elif stoch_k > 80 and stoch_d > 80: score -= 1

    if score >= 4:   return "📈 STRONG BUY"
    elif score >= 2: return "🟢 BUY"
    elif score <= -4: return "📉 STRONG SELL"
    elif score <= -2: return "🔴 SELL"
    else:             return "⏸️ NEUTRAL"


# ----------------------------------------------------------------------
#  Format helpers
# ----------------------------------------------------------------------
def format_price(asset, price):
    if asset == "gold":
        return f"${price:,.2f}"
    return f"${price:,.0f}"


def build_analysis_text(asset, label, emoji, candles, price, src):
    closes = [c["close"] for c in candles]
    rsi = compute_rsi(closes)
    ema20 = compute_ema(closes, 20)
    ema50 = compute_ema(closes, 50) if len(closes) >= 50 else None
    macd, signal_line, histogram = compute_macd(closes)
    bb_low, bb_mid, bb_high = compute_bollinger(closes)
    stoch_k, stoch_d = compute_stochastic(candles)
    sig = generate_signal(asset, candles)
    now_str = datetime.now(MY_TZ).strftime("%d/%m/%Y %H:%M MYT")

    lines = [
        f"{emoji} *{label}*",
        f"💰 Harga: `{format_price(asset, price)}`  _(src: {src})_",
        f"🕐 Masa: {now_str}",
        "",
        "📊 *Indikator Teknikal:*",
        f"  • RSI(14): `{rsi if rsi else 'N/A'}`",
        f"  • EMA20: `{format_price(asset, ema20) if ema20 else 'N/A'}`",
        f"  • EMA50: `{format_price(asset, ema50) if ema50 else 'N/A'}`",
        f"  • MACD: `{macd if macd else 'N/A'}` | Signal: `{signal_line if signal_line else 'N/A'}`",
        f"  • Histogram: `{histogram if histogram else 'N/A'}`",
        f"  • BB Low: `{format_price(asset, bb_low) if bb_low else 'N/A'}`",
        f"  • BB Mid: `{format_price(asset, bb_mid) if bb_mid else 'N/A'}`",
        f"  • BB High: `{format_price(asset, bb_high) if bb_high else 'N/A'}`",
        f"  • Stoch K: `{stoch_k if stoch_k else 'N/A'}` | D: `{stoch_d if stoch_d else 'N/A'}`",
        "",
        f"🎯 *Signal: {sig}*",
    ]
    return "\n".join(lines)


# ----------------------------------------------------------------------
#  Command Handlers
# ----------------------------------------------------------------------
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "👋 *Selamat datang ke Signal Bot!*\n\n"
        "📌 *Arahan tersedia:*\n"
        "  /harga — Harga semasa Gold & BTC\n"
        "  /gold — Analisis teknikal Gold\n"
        "  /btc — Analisis teknikal Bitcoin\n"
        "  /signal — Signal ringkas Gold & BTC\n"
        "  /help — Bantuan\n\n"
        "⚡ Data dari gold\\-api\\.com, Binance & Coingecko\\."
    )
    await update.message.reply_text(msg, parse_mode="Markdown")


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await cmd_start(update, context)


async def cmd_harga(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Mengambil harga semasa...")

    gold_price, gold_src = get_live_price("gold")
    btc_price, btc_src   = get_live_price("btc")

    now_str = datetime.now(MY_TZ).strftime("%d/%m/%Y %H:%M MYT")
    _, gold_status = gold_market_status()
    _, btc_status  = btc_market_status()

    gold_str = format_price("gold", gold_price) if gold_price else "❌ Harga tidak tersedia"
    btc_str  = format_price("btc", btc_price)  if btc_price  else "❌ Harga tidak tersedia"

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

    now_str = datetime.now(MY_TZ).strftime("%d/%m/%Y %H:%M MYT")

    gold_price, gold_src = get_live_price("gold")
    gold_candles, _      = get_candles("gold", "15m")
    gold_sig  = generate_signal("gold", gold_candles) if gold_candles else "❌ Tiada data"
    gold_str  = format_price("gold", gold_price) if gold_price else "❌ Tiada harga"

    btc_price, btc_src = get_live_price("btc")
    btc_candles, _     = get_candles("btc", "15m")
    btc_sig  = generate_signal("btc", btc_candles) if btc_candles else "❌ Tiada data"
    btc_str  = format_price("btc", btc_price) if btc_price else "❌ Tiada harga"

    msg = (
        f"🎯 *SIGNAL RINGKAS*\n\n"
        f"🥇 *Gold XAUUSD*\n"
        f"  💰 {gold_str}\n"
        f"  {gold_sig}\n\n"
        f"₿ *Bitcoin BTC*\n"
        f"  💰 {btc_str}\n"
        f"  {btc_sig}\n\n"
        f"🕐 {now_str}\n\n"
        f"⚠️ _Signal ini adalah untuk tujuan maklumat sahaja. "
        f"Bukan nasihat kewangan._"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")


# ----------------------------------------------------------------------
#  Graceful shutdown
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

    signal.signal(signal.SIGINT, handle_exit)
    signal.signal(signal.SIGTERM, handle_exit)

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start",  cmd_start))
    app.add_handler(CommandHandler("help",   cmd_help))
    app.add_handler(CommandHandler("harga",  cmd_harga))
    app.add_handler(CommandHandler("gold",   cmd_gold))
    app.add_handler(CommandHandler("btc",    cmd_btc))
    app.add_handler(CommandHandler("signal", cmd_signal))

    logger.info("Bot started. Polling...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
