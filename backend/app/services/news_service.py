"""
NewsAPI Service
Fetches news articles from NewsAPI.org for forex and market topics.
"""
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

NEWS_API_BASE_URL = "https://newsapi.org/v2"


def _build_news_params(
    query: str,
    from_date: datetime,
    language: str = "en",
    sort_by: str = "publishedAt",
    page_size: int = 20
) -> Dict[str, str]:
    """Build query parameters for NewsAPI."""
    return {
        "q": query,
        "from": from_date.isoformat(),
        "language": language,
        "sortBy": sort_by,
        "pageSize": str(page_size),
        "apiKey": settings.NEWSAPI_KEY,
    }


async def get_forex_news(days_back: int = 1) -> List[Dict[str, Any]]:
    """
    Get forex-related news articles.
    
    Args:
        days_back: Number of days to look back (default: 1)
    
    Returns:
        List of news items with title, description, source, url, published_at
    """
    from_date = datetime.now() - timedelta(days=days_back)
    
    params = _build_news_params(
        query="forex OR currency OR EUR OR GBP OR JPY OR USD",
        from_date=from_date,
    )
    
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                f"{NEWS_API_BASE_URL}/everything",
                params=params
            )
            response.raise_for_status()
            data = response.json()
            
            if data.get("status") == "ok":
                articles = []
                for article in data.get("articles", []):
                    articles.append({
                        "title": article.get("title", ""),
                        "description": article.get("description", ""),
                        "source": article.get("source", {}).get("name", ""),
                        "url": article.get("url", ""),
                        "published_at": article.get("publishedAt", ""),
                        "author": article.get("author", ""),
                    })
                return articles
    except Exception as e:
        logger.error(f"Failed to fetch forex news: {e}")
    
    return []


async def get_market_news(topic: str = "markets") -> List[Dict[str, Any]]:
    """
    Get market-related news articles.
    
    Args:
        topic: Topic to search for (default: "markets")
    
    Returns:
        List of news items with title, description, source, url, published_at
    """
    from_date = datetime.now() - timedelta(days=1)
    
    # Map common topics to search queries
    topic_queries = {
        "markets": "stock market OR trading OR investors",
        "economy": "economy OR GDP OR Federal Reserve",
        "crypto": "cryptocurrency OR bitcoin OR ethereum",
        "commodities": "gold OR oil OR commodities",
    }
    query = topic_queries.get(topic.lower(), topic)
    
    params = _build_news_params(
        query=query,
        from_date=from_date,
    )
    
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                f"{NEWS_API_BASE_URL}/everything",
                params=params
            )
            response.raise_for_status()
            data = response.json()
            
            if data.get("status") == "ok":
                articles = []
                for article in data.get("articles", []):
                    articles.append({
                        "title": article.get("title", ""),
                        "description": article.get("description", ""),
                        "source": article.get("source", {}).get("name", ""),
                        "url": article.get("url", ""),
                        "published_at": article.get("publishedAt", ""),
                        "author": article.get("author", ""),
                    })
                return articles
    except Exception as e:
        logger.error(f"Failed to fetch market news: {e}")
    
    return []


# Synchronous wrappers
def get_forex_news_sync(days_back: int = 1) -> List[Dict[str, Any]]:
    """Synchronous wrapper for get_forex_news."""
    import asyncio
    return asyncio.run(get_forex_news(days_back))


def get_market_news_sync(topic: str = "markets") -> List[Dict[str, Any]]:
    """Synchronous wrapper for get_market_news."""
    import asyncio
    return asyncio.run(get_market_news(topic))
