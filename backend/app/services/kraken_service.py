"""
Kraken API Service
Provides real-time crypto prices and historical OHLCV candles from Kraken.
Public endpoints — no auth required for price/candle data.
"""
import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

KRAKEN_BASE_URL = "https://api.kraken.com"
TIMEOUT = 15

# Kraken currency codes (not all are X/ Z prefix, but trading pairs use these)
# Kraken pair naming: XXBTZUSD = BTC/USD, SOLUSD = SOL/USD
PAIR_MAP = {
    # Crypto pairs
    "BTCUSD": "XXBTZUSD",
    "ETHUSD": "ETHUSD",
    "SOLUSD": "SOLUSD",
    "XRPUSD": "XXRPZUSD",
    "ADAUSD": "ADAUSD",
    "DOTUSD": "DOTUSD",
    "AVAXUSD": "AVAXUSD",
    "LINKUSD": "LINKUSD",
    # MATIC was renamed to POL on Kraken
    "POLUSD": "POLUSD",
    # FX pairs (for forex backup)
    "EURUSD": "EURUSD",
    "GBPUSD": "GBPUSD",
    "USDJPY": "USDJPY",
    "AUDUSD": "AUDUSD",
}

# Reverse lookup
SYMBOL_FROM_PAIR = {v: k for k, v in PAIR_MAP.items()}


def _format_pair(symbol: str) -> str:
    """Convert common symbol to Kraken pair name."""
    symbol = symbol.upper()
    if symbol in PAIR_MAP:
        return PAIR_MAP[symbol]
    # Already a Kraken pair
    if symbol.startswith("X") or symbol.startswith("Z"):
        return symbol
    return symbol  # Let Kraken reject it with a clear error


async def get_ticker(symbol: str) -> dict:
    """
    Get real-time ticker data for a pair.

    Returns:
        dict with keys: symbol, bid, ask, last, volume_24h, change_24h, high_24h, low_24h, open_24h
    """
    pair = _format_pair(symbol)
    url = f"{KRAKEN_BASE_URL}/0/public/Ticker"
    params = {"pair": pair}

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

        errors = data.get("error", [])
        if errors:
            logger.warning(f"Kraken ticker error for {symbol}: {errors}")
            return {"symbol": symbol.upper(), "error": errors[0]}

        result = data.get("result", {})
        if not result:
            return {"symbol": symbol.upper(), "error": "No result returned"}

        # Kraken returns data keyed by the canonical pair name (e.g. 'XXBTZUSD')
        pair_key = [k for k in result.keys() if k != "last"][0]
        ticker = result[pair_key]

        # c = [price, wholeLotVolume]
        # v = [volume today, volume 24h]
        # p = [vwap today, vwap 24h]
        # t = [number of trades today, number of trades 24h]
        # l = [low today, low 24h]
        # h = [high today, high 24h]
        # o = [open today, open 24h]

        # Kraken ticker fields:
        # Each can be a string OR an array [today, 24h ago] depending on the pair
        # Handle both: if it's a list, index [1] for 24h; if string, use it as today's open
        raw_open = ticker["o"]
        if isinstance(raw_open, list):
            open_24h = float(raw_open[1])   # 24h ago
            open_today = float(raw_open[0])  # today's open
        else:
            open_24h = float(raw_open)       # single value = today's open
            open_today = open_24h

        last_price = float(ticker["c"][0])
        change_24h = last_price - open_24h
        change_percent_24h = (change_24h / open_24h * 100) if open_24h else 0

        return {
            "symbol": symbol.upper(),
            "bid": float(ticker["b"][0]),
            "ask": float(ticker["a"][0]),
            "last": last_price,
            "volume_24h": float(ticker["v"][1]) if isinstance(ticker["v"], list) else float(ticker["v"]),
            "change_24h": change_24h,
            "change_percent_24h": change_percent_24h,
            "high_24h": float(ticker["h"][1]) if isinstance(ticker["h"], list) else float(ticker["h"]),
            "low_24h": float(ticker["l"][1]) if isinstance(ticker["l"], list) else float(ticker["l"]),
            "open_24h": open_24h,
            "vwap_24h": float(ticker["p"][1]) if isinstance(ticker["p"], list) else float(ticker["p"]),
            "trades_24h": ticker["t"][1] if isinstance(ticker["t"], list) else ticker["t"],
        }

    except httpx.HTTPStatusError as e:
        logger.error(f"Kraken ticker HTTP error for {symbol}: {e}")
        return {"symbol": symbol.upper(), "error": str(e)}
    except Exception as e:
        logger.error(f"Kraken ticker error for {symbol}: {e}")
        return {"symbol": symbol.upper(), "error": str(e)}


async def get_ohlcv(
    symbol: str,
    interval: int = 60,
    count: int = 168,
) -> list[dict]:
    """
    Get historical OHLCV candles for a pair.

    Args:
        symbol: Trading pair, e.g. 'BTCUSD', 'ETHUSD', 'SOLUSD'
        interval: Candle timeframe in minutes.
                  1=1m, 5=5m, 15=15m, 30=30m, 60=1h, 240=4h, 1440=1d, 10080=1w
        count: Max candles to return (default 168 = 1 week of 1h candles)

    Returns:
        List of dicts: [{time, open, high, low, close, vwap, volume, trades}, ...]
    """
    pair = _format_pair(symbol)
    url = f"{KRAKEN_BASE_URL}/0/public/OHLC"
    params = {"pair": pair, "interval": interval}

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

        errors = data.get("error", [])
        if errors:
            logger.warning(f"Kraken OHLCV error for {symbol}: {errors}")
            return []

        result = data.get("result", {})
        pair_key = [k for k in result.keys() if k != "last"][0]
        candles_raw = result[pair_key]

        candles = []
        for c in candles_raw[-count:]:
            candles.append({
                "time": int(c[0]),
                "open": float(c[1]),
                "high": float(c[2]),
                "low": float(c[3]),
                "close": float(c[4]),
                "vwap": float(c[5]),
                "volume": float(c[6]),
                "trades": int(c[8]) if len(c) > 8 else 0,
            })

        return candles

    except Exception as e:
        logger.error(f"Kraken OHLCV error for {symbol}: {e}")
        return []


# ─── Convenience functions ───────────────────────────────────────────────────────

async def get_btc_quote() -> dict:
    """Get real-time BTC/USD quote from Kraken."""
    return await get_ticker("BTCUSD")


async def get_eth_quote() -> dict:
    """Get real-time ETH/USD quote from Kraken."""
    return await get_ticker("ETHUSD")


async def get_sol_quote() -> dict:
    """Get real-time SOL/USD quote from Kraken."""
    return await get_ticker("SOLUSD")


async def get_crypto_price(symbol: str) -> dict:
    """Get real-time price for any supported Kraken pair."""
    return await get_ticker(symbol)


INTERVAL_LABELS = {
    1: "1m", 5: "5m", 15: "15m", 30: "30m",
    60: "1h", 240: "4h", 1440: "1d", 10080: "1w", 21600: "15d",
}
