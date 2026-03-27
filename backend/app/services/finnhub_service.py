"""
Finnhub Market Data Service
Provides market news, company sentiment, economic calendar, and quote data.
"""
import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

FINNHUB_BASE_URL = "https://finnhub.io/api/v1"

# Rate limiting: Finnhub free tier = 60 calls/min
RATE_LIMIT_CALLS = 60
RATE_LIMIT_PERIOD = 60.0  # seconds

# Track API calls for rate limiting
_call_timestamps: List[float] = []


def _check_rate_limit() -> None:
    """Check and enforce rate limit for Finnhub API."""
    global _call_timestamps
    now = time.time()
    
    # Remove timestamps outside the rate limit window
    _call_timestamps = [ts for ts in _call_timestamps if now - ts < RATE_LIMIT_PERIOD]
    
    if len(_call_timestamps) >= RATE_LIMIT_CALLS:
        sleep_time = RATE_LIMIT_PERIOD - (now - _call_timestamps[0])
        if sleep_time > 0:
            logger.info(f"Finnhub rate limit reached, sleeping {sleep_time:.1f}s")
            time.sleep(sleep_time)
            _call_timestamps = [ts for ts in _call_timestamps if now - ts < RATE_LIMIT_PERIOD]
    
    _call_timestamps.append(now)


async def _make_request(endpoint: str, params: Dict[str, str]) -> Optional[Dict[str, Any]]:
    """Make async request to Finnhub API with rate limiting."""
    _check_rate_limit()
    
    url = f"{FINNHUB_BASE_URL}{endpoint}"
    params["token"] = settings.FINNHUB_API_KEY
    
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 429:
            logger.warning("Finnhub rate limit hit (429)")
            await asyncio.sleep(5)
            return None
        logger.error(f"Finnhub HTTP error: {e}")
        return None
    except Exception as e:
        logger.error(f"Finnhub request failed: {e}")
        return None


async def get_market_news(category: str = "forex") -> List[Dict[str, Any]]:
    """
    Get market news for a category.
    
    Args:
        category: News category - "forex", "crypto", "general", "merger"
    
    Returns:
        List of news items with id, headline, summary, source, url, datetime
    """
    valid_categories = ["forex", "crypto", "general", "merger"]
    if category not in valid_categories:
        category = "forex"
    
    params = {"category": category}
    result = await _make_request("/news", params)
    
    if result and isinstance(result, list):
        # Filter to recent news (last 7 days)
        cutoff = datetime.now() - timedelta(days=7)
        recent_news = []
        for item in result:
            if isinstance(item, dict):
                item_time = item.get("datetime", 0)
                if item_time and item_time > cutoff.timestamp():
                    recent_news.append({
                        "id": item.get("id"),
                        "headline": item.get("headline", ""),
                        "summary": item.get("summary", ""),
                        "source": item.get("source", ""),
                        "url": item.get("url", ""),
                        "datetime": item.get("datetime"),
                    })
        return recent_news
    
    return []


async def get_company_sentiment(symbol: str) -> Dict[str, Any]:
    """
    Get company sentiment data for a symbol.
    
    Args:
        symbol: Stock ticker symbol (e.g., "AAPL", "TSLA")
    
    Returns:
        Dict with sentiment metrics (sentiment score, mentioned, etc.)
    """
    params = {"symbol": symbol.upper()}
    result = await _make_request("/news/sentiment", params)
    
    if result and isinstance(result, dict):
        return {
            "symbol": symbol.upper(),
            "sentiment_score": result.get("sentimentScore", 0),
            "sentiment_description": result.get("sentimentDescription", "neutral"),
            "reddit_mention": result.get("redditMention", 0),
            "twitter_mention": result.get("twitterMention", 0),
            "article_count": result.get("articleCount", 0),
        }
    
    return {
        "symbol": symbol.upper(),
        "sentiment_score": 0,
        "sentiment_description": "unavailable",
        "reddit_mention": 0,
        "twitter_mention": 0,
        "article_count": 0,
    }


async def get_economic_calendar() -> List[Dict[str, Any]]:
    """
    Get upcoming economic events calendar.
    
    Returns:
        List of economic events with time, country, event, importance, forecast
    """
    params = {}
    result = await _make_request("/calendar/economic", params)
    
    if result and isinstance(result, dict):
        events = result.get("economicCalendar", [])
        # Filter to upcoming events only
        cutoff = datetime.now() - timedelta(hours=24)
        upcoming = []
        for event in events:
            if isinstance(event, dict):
                event_time = event.get("time", "")
                upcoming.append({
                    "time": event.get("time", ""),
                    "country": event.get("country", ""),
                    "event": event.get("event", ""),
                    "importance": event.get("importance", ""),
                    "forecast": event.get("forecast", ""),
                    "actual": event.get("actual", ""),
                    "previous": event.get("previous", ""),
                })
        return upcoming
    
    return []


async def get_quote(symbol: str) -> Dict[str, Any]:
    """
    Get basic quote data for a symbol.
    
    Args:
        symbol: Ticker symbol (e.g., "AAPL", "EURUSD")
    
    Returns:
        Dict with price data (c, h, l, o, pc, t)
    """
    params = {"symbol": symbol.upper()}
    result = await _make_request("/quote", params)
    
    if result and isinstance(result, dict):
        return {
            "symbol": symbol.upper(),
            "current_price": result.get("c", 0),
            "high": result.get("h", 0),
            "low": result.get("l", 0),
            "open": result.get("o", 0),
            "previous_close": result.get("pc", 0),
            "timestamp": result.get("t", 0),
        }
    
    return {
        "symbol": symbol.upper(),
        "current_price": 0,
        "high": 0,
        "low": 0,
        "open": 0,
        "previous_close": 0,
        "timestamp": 0,
    }


# Synchronous wrappers for backward compatibility
def get_market_news_sync(category: str = "forex") -> List[Dict[str, Any]]:
    """Synchronous wrapper for get_market_news."""
    return asyncio.run(get_market_news(category))


def get_company_sentiment_sync(symbol: str) -> Dict[str, Any]:
    """Synchronous wrapper for get_company_sentiment."""
    return asyncio.run(get_company_sentiment(symbol))


def get_economic_calendar_sync() -> List[Dict[str, Any]]:
    """Synchronous wrapper for get_economic_calendar."""
    return asyncio.run(get_economic_calendar())


def get_quote_sync(symbol: str) -> Dict[str, Any]:
    """Synchronous wrapper for get_quote."""
    return asyncio.run(get_quote(symbol))
