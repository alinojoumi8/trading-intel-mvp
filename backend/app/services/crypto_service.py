"""
Binance Public API Service
Fetches cryptocurrency price data from Binance public endpoints (no auth required).
"""
import logging
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)

BINANCE_BASE_URL = "https://api.binance.com/api/v3"


async def _get_ticker(symbol: str) -> Optional[Dict[str, Any]]:
    """
    Fetch 24hr ticker data from Binance for a symbol.
    
    Args:
        symbol: Binance symbol (e.g., "BTCUSDT", "ETHUSDT")
    
    Returns:
        Raw ticker data dict or None on failure
    """
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                f"{BINANCE_BASE_URL}/ticker/24hr",
                params={"symbol": symbol.upper()}
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as e:
        logger.error(f"Binance API error for {symbol}: {e}")
        return None
    except Exception as e:
        logger.error(f"Binance request failed for {symbol}: {e}")
        return None


def _parse_btc_ticker(data: Dict[str, Any]) -> Dict[str, Any]:
    """Parse Binance ticker data for BTC."""
    return {
        "symbol": "BTCUSDT",
        "price": float(data.get("lastPrice", 0) or 0),
        "volume_24h": float(data.get("volume", 0) or 0),
        "quote_volume_24h": float(data.get("quoteVolume", 0) or 0),
        "change_24h": float(data.get("priceChange", 0) or 0),
        "change_percent_24h": float(data.get("priceChangePercent", 0) or 0),
        "high_24h": float(data.get("highPrice", 0) or 0),
        "low_24h": float(data.get("lowPrice", 0) or 0),
    }


def _parse_eth_ticker(data: Dict[str, Any]) -> Dict[str, Any]:
    """Parse Binance ticker data for ETH."""
    return {
        "symbol": "ETHUSDT",
        "price": float(data.get("lastPrice", 0) or 0),
        "volume_24h": float(data.get("volume", 0) or 0),
        "quote_volume_24h": float(data.get("quoteVolume", 0) or 0),
        "change_24h": float(data.get("priceChange", 0) or 0),
        "change_percent_24h": float(data.get("priceChangePercent", 0) or 0),
        "high_24h": float(data.get("highPrice", 0) or 0),
        "low_24h": float(data.get("lowPrice", 0) or 0),
    }


def _parse_generic_ticker(data: Dict[str, Any]) -> Dict[str, Any]:
    """Parse Binance ticker data generically."""
    return {
        "symbol": data.get("symbol", ""),
        "price": float(data.get("lastPrice", 0) or 0),
        "volume_24h": float(data.get("volume", 0) or 0),
        "quote_volume_24h": float(data.get("quoteVolume", 0) or 0),
        "change_24h": float(data.get("priceChange", 0) or 0),
        "change_percent_24h": float(data.get("priceChangePercent", 0) or 0),
        "high_24h": float(data.get("highPrice", 0) or 0),
        "low_24h": float(data.get("lowPrice", 0) or 0),
    }


async def get_btc_quote() -> Dict[str, Any]:
    """
    Get BTC/USDT quote from Binance.
    
    Returns:
        Dict with price, volume_24h, change_24h
    """
    data = await _get_ticker("BTCUSDT")
    if data:
        return _parse_btc_ticker(data)
    
    return {
        "symbol": "BTCUSDT",
        "price": 0.0,
        "volume_24h": 0.0,
        "change_24h": 0.0,
        "error": "Could not fetch BTC price"
    }


async def get_eth_quote() -> Dict[str, Any]:
    """
    Get ETH/USDT quote from Binance.
    
    Returns:
        Dict with price, volume_24h, change_24h
    """
    data = await _get_ticker("ETHUSDT")
    if data:
        return _parse_eth_ticker(data)
    
    return {
        "symbol": "ETHUSDT",
        "price": 0.0,
        "volume_24h": 0.0,
        "change_24h": 0.0,
        "error": "Could not fetch ETH price"
    }


async def get_crypto_price(symbol: str) -> Dict[str, Any]:
    """
    Get cryptocurrency price from Binance.
    
    Args:
        symbol: Crypto symbol (e.g., "BTC", "ETH", "SOL")
    
    Returns:
        Dict with price data for the symbol against USDT
    """
    # Normalize symbol - append USDT if not already present
    if not symbol.upper().endswith("USDT"):
        symbol = f"{symbol.upper()}USDT"
    
    data = await _get_ticker(symbol)
    if data:
        return _parse_generic_ticker(data)
    
    return {
        "symbol": symbol.upper(),
        "price": 0.0,
        "volume_24h": 0.0,
        "change_24h": 0.0,
        "error": f"Could not fetch {symbol} price"
    }


# Synchronous wrappers
def get_btc_quote_sync() -> Dict[str, Any]:
    """Synchronous wrapper for get_btc_quote."""
    import asyncio
    return asyncio.run(get_btc_quote())


def get_eth_quote_sync() -> Dict[str, Any]:
    """Synchronous wrapper for get_eth_quote."""
    import asyncio
    return asyncio.run(get_eth_quote())


def get_crypto_price_sync(symbol: str) -> Dict[str, Any]:
    """Synchronous wrapper for get_crypto_price."""
    import asyncio
    return asyncio.run(get_crypto_price(symbol))
