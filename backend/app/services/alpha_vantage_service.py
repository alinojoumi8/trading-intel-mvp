"""
Alpha Vantage Service
Provides forex quotes and intraday data using the premium API key.
"""
import asyncio
import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

ALPHA_VANTAGE_BASE_URL = "https://www.alphavantage.co/query"

# Premium key supports 75 req/min
RATE_LIMIT_CALLS = 75
RATE_LIMIT_PERIOD = 60.0  # seconds

# Track API calls for rate limiting
_call_timestamps: List[float] = []


def _check_rate_limit() -> None:
    """Check and enforce rate limit for Alpha Vantage API."""
    global _call_timestamps
    now = time.time()
    
    # Remove timestamps outside the rate limit window
    _call_timestamps = [ts for ts in _call_timestamps if now - ts < RATE_LIMIT_PERIOD]
    
    if len(_call_timestamps) >= RATE_LIMIT_CALLS:
        sleep_time = RATE_LIMIT_PERIOD - (now - _call_timestamps[0])
        if sleep_time > 0:
            logger.info(f"Alpha Vantage rate limit reached, sleeping {sleep_time:.1f}s")
            time.sleep(sleep_time)
            _call_timestamps = [ts for ts in _call_timestamps if now - ts < RATE_LIMIT_PERIOD]
    
    _call_timestamps.append(now)


async def _make_request(params: Dict[str, str]) -> Optional[Dict[str, Any]]:
    """Make async request to Alpha Vantage API with rate limiting."""
    _check_rate_limit()
    
    params["apikey"] = settings.ALPHA_VANTAGE_API_KEY
    
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(ALPHA_VANTAGE_BASE_URL, params=params)
            response.raise_for_status()
            return response.json()
    except Exception as e:
        logger.error(f"Alpha Vantage request failed: {e}")
        return None


async def get_forex_quote(pair: str) -> Dict[str, Any]:
    """
    Get forex quote for a currency pair.
    
    Args:
        pair: Currency pair symbol (e.g., "EURUSD", "GBPUSD", "USDJPY")
    
    Returns:
        Dict with symbol, open, high, low, price, volume, latest_day
    """
    # Alpha Vantage forex quotes use different symbol format
    # For EURUSD, we use function=CURRENCY_EXCHANGE_RATE or GLOBAL_QUOTE
    # But GLOBAL_QUOTE works better for forex pairs
    
    params = {
        "function": "GLOBAL_QUOTE",
        "symbol": pair.upper(),
    }
    
    result = await _make_request(params)
    
    if result and isinstance(result, dict):
        quote_data = result.get("Global Quote", {})
        if quote_data:
            return {
                "symbol": pair.upper(),
                "open": float(quote_data.get("02. open", 0) or 0),
                "high": float(quote_data.get("03. high", 0) or 0),
                "low": float(quote_data.get("04. low", 0) or 0),
                "price": float(quote_data.get("05. price", 0) or 0),
                "volume": int(quote_data.get("06. volume", 0) or 0),
                "latest_day": quote_data.get("07. latest trading day", ""),
                "previous_close": float(quote_data.get("08. previous close", 0) or 0),
                "change": float(quote_data.get("09. change", 0) or 0),
                "change_percent": quote_data.get("10. change percent", ""),
            }
    
    # Fallback - return empty structure
    return {
        "symbol": pair.upper(),
        "open": 0.0,
        "high": 0.0,
        "low": 0.0,
        "price": 0.0,
        "volume": 0,
        "latest_day": "",
        "previous_close": 0.0,
        "change": 0.0,
        "change_percent": "",
    }


async def get_intraday_data(symbol: str, interval: str = "60min") -> List[Dict[str, Any]]:
    """
    Get intraday OHLCV data for a symbol.
    
    Args:
        symbol: Symbol to fetch (e.g., "AAPL", "EURUSD")
        interval: Time interval (1min, 5min, 15min, 30min, 60min)
    
    Returns:
        List of OHLCV data points
    """
    valid_intervals = ["1min", "5min", "15min", "30min", "60min"]
    if interval not in valid_intervals:
        interval = "60min"
    
    params = {
        "function": "TIME_SERIES_INTRADAY",
        "symbol": symbol.upper(),
        "interval": interval,
        "outputsize": "compact",  # Last 100 data points
    }
    
    result = await _make_request(params)
    
    if result and isinstance(result, dict):
        # Find the time series key
        ts_key = f"Time Series ({interval})"
        time_series = result.get(ts_key, {})
        
        if time_series:
            data_points = []
            for datetime_str, values in time_series.items():
                data_points.append({
                    "datetime": datetime_str,
                    "open": float(values.get("1. open", 0) or 0),
                    "high": float(values.get("2. high", 0) or 0),
                    "low": float(values.get("3. low", 0) or 0),
                    "close": float(values.get("4. close", 0) or 0),
                    "volume": int(values.get("5. volume", 0) or 0),
                })
            
            # Sort by datetime descending (most recent first)
            data_points.sort(key=lambda x: x["datetime"], reverse=True)
            return data_points
    
    return []


# Synchronous wrappers
def get_forex_quote_sync(pair: str) -> Dict[str, Any]:
    """Synchronous wrapper for get_forex_quote."""
    return asyncio.run(get_forex_quote(pair))


def get_intraday_data_sync(symbol: str, interval: str = "60min") -> List[Dict[str, Any]]:
    """Synchronous wrapper for get_intraday_data."""
    return asyncio.run(get_intraday_data(symbol, interval))


# ─── Economic Data (Alpha Vantage Premium) ────────────────────────────────────

async def get_economic_indicators() -> Dict[str, Any]:
    """
    Fetch key US economic indicators from Alpha Vantage.
    Covers: GDP, Inflation (CPI), Retail Sales, Unemployment, ISM Manufacturing.
    Uses ECONOMIC_INDICATOR function with premium key.
    
    Returns:
        Dict with indicator name -> {value, date, description}
    """
    indicators = {}
    
    # Map of function -> metadata
    # Each of these costs 1 credit per call on premium tier
    economic_functions = {
        "REAL_GDP": {
            "interval": "quarterly",
            "description": "US Real GDP",
            "param": {},
        },
        "INFLATION": {
            "interval": "monthly", 
            "description": "US Inflation Rate (CPI YoY)",
            "param": {},
        },
        "RETAIL_SALES": {
            "interval": "monthly",
            "description": "US Retail Sales MoM",
            "param": {},
        },
        "UNEMPLOYMENT": {
            "interval": "monthly",
            "description": "US Unemployment Rate",
            "param": {},
        },
        "INTEREST_RATE": {
            "interval": "monthly",
            "description": "US Federal Funds Rate",
            "param": {},
        },
        "CONSUMER_SENTIMENT": {
            "interval": "monthly",
            "description": "US Consumer Sentiment (UMich)",
            "param": {},
        },
    }
    
    for func_name, meta in economic_functions.items():
        params = {
            "function": func_name,
        }
        params.update(meta["param"])
        
        result = await _make_request(params)
        
        if result and isinstance(result, dict) and "data" in result:
            data = result.get("data", [])
            if data:
                # Most recent entry
                latest = data[0]
                indicators[func_name] = {
                    "value": latest.get("value", "N/A"),
                    "date": latest.get("date", ""),
                    "description": meta["description"],
                }
        else:
            indicators[func_name] = {
                "value": "unavailable",
                "date": "",
                "description": meta["description"],
            }
    
    return indicators


def get_economic_indicators_sync() -> Dict[str, Any]:
    """Synchronous wrapper for get_economic_indicators."""
    return asyncio.run(get_economic_indicators())


# ─── News & Sentiment (Alpha Vantage NEWS_SENTIMENT) ────────────────────────

async def get_news_sentiment(
    tickers: str = "FOREX:EUR",
    topics: Optional[str] = None,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """
    Fetch news with sentiment scores from Alpha Vantage NEWS_SENTIMENT endpoint.

    Args:
        tickers: Comma-separated ticker list (e.g. "FOREX:EUR,FOREX:GBP").
                 Supports FOREX:XXX, CRYPTO:XXX, or stock tickers.
        topics: Optional topic filter (e.g. "economy_fiscal", "finance", "technology").
        limit: Max articles to return (API max 1000, default 50).

    Returns:
        List of news dicts with title, summary, source, url, sentiment, ticker_sentiment.
    """
    params: Dict[str, str] = {
        "function": "NEWS_SENTIMENT",
        "limit": str(min(limit, 200)),
    }
    if tickers:
        params["tickers"] = tickers
    if topics:
        params["topics"] = topics

    result = await _make_request(params)

    if not result or "feed" not in result:
        return []

    articles = []
    for item in result["feed"][:limit]:
        # Parse ticker-specific sentiment
        ticker_sentiments = []
        for ts in item.get("ticker_sentiment", []):
            ticker_sentiments.append({
                "ticker": ts.get("ticker", ""),
                "relevance": float(ts.get("relevance_score", 0) or 0),
                "sentiment_score": float(ts.get("ticker_sentiment_score", 0) or 0),
                "sentiment_label": ts.get("ticker_sentiment_label", "Neutral"),
            })

        # Parse published time (format: "20260401T132528")
        time_pub = item.get("time_published", "")
        published_at = ""
        if time_pub:
            try:
                dt = datetime.strptime(time_pub, "%Y%m%dT%H%M%S")
                published_at = dt.isoformat()
            except ValueError:
                published_at = time_pub

        articles.append({
            "title": item.get("title", ""),
            "summary": item.get("summary", ""),
            "source": item.get("source", ""),
            "url": item.get("url", ""),
            "published_at": published_at,
            "banner_image": item.get("banner_image", ""),
            "overall_sentiment_score": float(item.get("overall_sentiment_score", 0) or 0),
            "overall_sentiment_label": item.get("overall_sentiment_label", "Neutral"),
            "ticker_sentiment": ticker_sentiments,
            "topics": [t.get("topic", "") for t in item.get("topics", [])],
        })

    return articles


async def get_forex_news_sentiment(limit: int = 20) -> List[Dict[str, Any]]:
    """Get forex-specific news with sentiment."""
    return await get_news_sentiment(
        tickers="FOREX:EUR,FOREX:GBP,FOREX:JPY,FOREX:AUD,FOREX:CAD",
        limit=limit,
    )


async def get_market_news_sentiment(limit: int = 20) -> List[Dict[str, Any]]:
    """Get broad market news with sentiment (economy + finance topics)."""
    return await get_news_sentiment(
        tickers="",
        topics="economy_fiscal,economy_monetary,finance,financial_markets",
        limit=limit,
    )


def get_forex_news_sentiment_sync(limit: int = 20) -> List[Dict[str, Any]]:
    """Synchronous wrapper."""
    return asyncio.run(get_forex_news_sentiment(limit))


def get_market_news_sentiment_sync(limit: int = 20) -> List[Dict[str, Any]]:
    """Synchronous wrapper."""
    return asyncio.run(get_market_news_sentiment(limit))
