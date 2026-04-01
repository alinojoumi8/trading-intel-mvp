"""
NewsAPI.ai Service (Event Registry)
Fetches news articles from eventregistry.org for forex and market topics.
Replaces the old NewsAPI.org integration.
"""
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

NEWSAPI_AI_BASE_URL = "https://eventregistry.org/api/v1/article/getArticles"


async def _fetch_articles(
    keywords: List[str],
    days_back: int = 1,
    count: int = 20,
) -> List[Dict[str, Any]]:
    """
    Fetch articles from NewsAPI.ai (Event Registry).
    Keywords are combined with OR logic.
    Returns normalized article dicts.
    """
    if not settings.NEWSAPI_KEY:
        logger.warning("NEWSAPI_KEY not configured")
        return []

    from_date = (datetime.utcnow() - timedelta(days=days_back)).strftime("%Y-%m-%d")

    payload = {
        "apiKey": settings.NEWSAPI_KEY,
        "keyword": keywords,
        "keywordOper": "or",
        "lang": "eng",
        "dateStart": from_date,
        "articlesSortBy": "date",
        "articlesSortByAsc": False,
        "articlesCount": count,
        "resultType": "articles",
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(NEWSAPI_AI_BASE_URL, json=payload)
            response.raise_for_status()
            data = response.json()

            articles_data = data.get("articles", {}).get("results", [])
            articles = []
            for article in articles_data:
                source_info = article.get("source", {})
                source_name = source_info.get("title", "") if isinstance(source_info, dict) else str(source_info)

                published = article.get("dateTimePub") or article.get("dateTime") or ""

                articles.append({
                    "title": article.get("title", ""),
                    "description": article.get("body", "")[:500] if article.get("body") else "",
                    "source": source_name,
                    "url": article.get("url", ""),
                    "published_at": published,
                    "author": "",
                    "sentiment": float(article.get("sentiment", 0) or 0),
                })
            return articles

    except Exception as e:
        logger.error(f"NewsAPI.ai fetch failed for '{keyword}': {e}")
        return []


async def get_forex_news(days_back: int = 1) -> List[Dict[str, Any]]:
    """Get forex-related news articles."""
    return await _fetch_articles(
        keywords=["forex", "currency", "EUR USD", "central bank", "interest rate"],
        days_back=days_back,
        count=20,
    )


async def get_market_news(topic: str = "markets") -> List[Dict[str, Any]]:
    """Get market-related news articles by topic."""
    topic_keywords = {
        "markets": ["stock market", "trading", "Wall Street", "S&P 500"],
        "economy": ["economy", "GDP", "Federal Reserve", "inflation", "employment"],
        "crypto": ["cryptocurrency", "bitcoin", "ethereum", "crypto market"],
        "commodities": ["gold price", "oil price", "commodities", "crude oil"],
    }
    keywords = topic_keywords.get(topic.lower(), [topic])
    return await _fetch_articles(keywords=keywords, days_back=1, count=20)


# Synchronous wrappers
def get_forex_news_sync(days_back: int = 1) -> List[Dict[str, Any]]:
    """Synchronous wrapper for get_forex_news."""
    import asyncio
    return asyncio.run(get_forex_news(days_back))


def get_market_news_sync(topic: str = "markets") -> List[Dict[str, Any]]:
    """Synchronous wrapper for get_market_news."""
    import asyncio
    return asyncio.run(get_market_news(topic))
