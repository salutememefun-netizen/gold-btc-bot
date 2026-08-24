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
ALPHA_VANTAGE_KEY = os.getenv("ALPHA_VANTAGE_KEY", "demo")   # change if you have a real key
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
#  Yahoo data helpers (unchanged)
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
        x = result
        ts = x.get("timestamp") or []
        ql = x.get("indicators", {}).get("quote", [])
        if not ql:
            return []
        q = ql
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
                out.append(
                    {
                        "time": t,
                        "open": float(o[i]),
                        "high": float(h[i]),
                        "low": float(l[i]),
                        "close": float(c[i]),
                    }
                )
            except (IndexError, TypeError, ValueError):
                continue
        return out
    except Exception as e:
        logger.warning("Yahoo %s error: %s", symbol, e)
        return []


def get_candles(asset, interval, ranges=None, minimum=20):
    if ranges is None:
        ranges = ["5d", "1mo", "3mo"]
    for symbol in SYMBOLS.get(asset, []):
        for rv in ranges:
            candles = yahoo_candles(symbol, interval, rv)
            if len(candles) >= minimum:
                logger.info(
                    "%s %s = %d candles [%s/%s]",
                    asset,
                    interval,
                    len(candles),
                    symbol,
                    rv,
                )
                return candles, symbol
            logger.warning(
                "%s %s insufficient: %d [%s/%s]",
                asset,
                interval,
                len(candles),
                symbol,
                rv,
            )
    return [], None


def get_live_price(asset):
    """
    Return (price, source_symbol).  Tries multiple sources in order:
    1. Yahoo chart API
    2. Yahoo quote API
    3. Coingecko (BTC only)
    4. Alpha Vantage (Gold only, demo key by default)
    """
    session = SESSION  # reuse the global session

    # 1️⃣ Yahoo chart API
    for symbol in SYMBOLS.get(asset, []):
        try:
            r = session.get(
                f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}",
                params={
                    "interval": "1m",
                    "range": "1d",
                    "includePrePost": "true",
                },
                timeout=15,
            )
            if r.status_code != 200:
                logger.debug(f"Yahoo chart {symbol} returned {r.status_code}")
                continue

            data = r.json()
            result = data.get("chart", {}).get("result")
            if not result:
                logger.debug(f"No chart result for {symbol}")
                continue

            meta = result[0].get("meta", {})
            price = meta.get("regularMarketPrice")
            if price is None:
                quotes = result[0].get("indicators", {}).get("quote", [])
                closes = quotes[0].get("close", []) if quotes else []
                for v in reversed(closes):
                    if v is not None:
                        price = v
                        break

            if price is not None:
                return float(price), symbol
        except Exception as exc:
            logger.warning(f"Yahoo chart error for {symbol}: {exc}")

    # 2️⃣ Yahoo quote API
    for symbol in SYMBOLS.get(asset, []):
        try:
            r = session.get(
                "https://query1.finance.yahoo.com/v7/finance/quote",
                params={"symbols": symbol},
                timeout=10,
            )
            if r.status_code != 200:
                logger.debug(f"Yahoo quote {symbol} returned {r.status_code}")
                continue

            data = r.json()
            result = data.get("quoteResponse", {}).get("result", [])
            if not result:
                logger.debug(f"No quote result for {symbol}")
                continue

            quote = result[0]
            price = quote.get("regularMarketPrice")
            if price is not None:
                return float(price), symbol
        except Exception as exc:
            logger.warning(f"Yahoo quote error for {symbol}: {exc}")

    # 3️⃣ Coingecko for BTC
    if asset == "btc":
        try:
            r = session.get(
                "https://api.coingecko.com/api/v3/simple/price",
                params={"ids": "bitcoin", "vs_currencies": "usd"},
                timeout=10,
            )
            if r.status_code == 200:
                data = r.json()
                price = data.get("bitcoin", {}).get("usd")
                if price is not None:
                    return float(price), "Coingecko"
        except Exception as exc:
            logger.warning(f"Coingecko error: {exc}")

    # 4️⃣ Alpha Vantage for Gold
    if asset == "gold":
        try:
            r = session.get(
                "https://www.alphavantage.co/query",
                params={
                    "function": "GLOBAL_QUOTE",
                    "symbol": "GC=F
