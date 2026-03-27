"""
Data Aggregator Service
Pulls data from all services and returns a unified market context dict.
This is the main entry point for the AI content generation pipeline.
"""
import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List

from app.services import (
    cot_service,
    finnhub_service,
    news_service,
    alpha_vantage_service,
    rss_news_service,
    crypto_service,
    kraken_service,
)

logger = logging.getLogger(__name__)


def _cot_async_wrapper() -> Dict[str, Any]:
    """Thread-safe wrapper for get_cot_summary_async — runs in asyncio.to_thread."""
    import asyncio
    return asyncio.run(cot_service.get_cot_summary_async())


async def _fetch_forex_data() -> Dict[str, Any]:
    """Fetch forex data from Alpha Vantage."""
    forex_pairs = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "NZDUSD"]
    result = {}
    
    for pair in forex_pairs:
        try:
            quote = await alpha_vantage_service.get_forex_quote(pair)
            if quote.get("price", 0) > 0:
                result[pair] = quote
        except Exception as e:
            logger.warning(f"Failed to fetch forex quote for {pair}: {e}")
    
    return result


async def _fetch_crypto_data() -> Dict[str, Any]:
    """
    Fetch crypto data from Kraken (primary) with Binance as fallback.
    Kraken provides: BTC, ETH, SOL, XRP, ADA, DOT, AVAX, LINK, MATIC
    Binance provides: additional coverage for any missed pairs.
    """
    result = {}
    kraken_pairs = ["BTC", "ETH", "SOL", "XRP", "ADA", "DOT", "AVAX", "LINK", "POL"]

    # Fetch from Kraken concurrently
    kraken_tasks = [kraken_service.get_crypto_price(f"{sym}USD") for sym in kraken_pairs]

    kraken_results = await asyncio.gather(*kraken_tasks, return_exceptions=True)
    for sym, quote in zip(kraken_pairs, kraken_results):
        if isinstance(quote, dict) and quote.get("last") and not quote.get("error"):
            result[sym] = quote

    # Binance fallback for any missed pairs
    for sym, fetch_fn in [("BTC", crypto_service.get_btc_quote), ("ETH", crypto_service.get_eth_quote)]:
        if sym not in result:
            try:
                quote = await fetch_fn()
                if quote.get("price"):
                    result[sym] = quote
            except Exception:
                pass

    return result


async def _fetch_commodities_data() -> Dict[str, Any]:
    """Fetch commodities data (Gold and Oil from COT + Finnhub)."""
    result = {}

    # Get COT data for gold and oil
    try:
        cot_data = await cot_service.get_cot_summary_async()
        if "GOLD" in cot_data:
            result["GOLD"] = cot_data["GOLD"]
        if "OIL" in cot_data:
            result["OIL"] = cot_data["OIL"]
    except Exception as e:
        logger.warning(f"Failed to fetch commodities COT data: {e}")

    # Get Finnhub quote for commodities
    try:
        gold_quote = await finnhub_service.get_quote("GC")
        if gold_quote.get("current_price", 0) > 0:
            result["GOLD"] = {**result.get("GOLD", {}), **gold_quote}
    except Exception as e:
        logger.warning(f"Failed to fetch gold quote: {e}")

    try:
        oil_quote = await finnhub_service.get_quote("CL")
        if oil_quote.get("current_price", 0) > 0:
            result["OIL"] = {**result.get("OIL", {}), **oil_quote}
    except Exception as e:
        logger.warning(f"Failed to fetch oil quote: {e}")

    return result


async def _fetch_news_data() -> List[Dict[str, Any]]:
    """Fetch top news from Finnhub, NewsAPI, and FXStreet RSS."""
    all_news = []
    
    # Get Finnhub forex news
    try:
        finnhub_news = await finnhub_service.get_market_news("forex")
        all_news.extend(finnhub_news[:5])  # Take top 5
    except Exception as e:
        logger.warning(f"Failed to fetch Finnhub news: {e}")
    
    # Get NewsAPI forex news
    try:
        newsapi_news = await news_service.get_forex_news(days_back=1)
        all_news.extend(newsapi_news[:5])  # Take top 5
    except Exception as e:
        logger.warning(f"Failed to fetch NewsAPI news: {e}")
    
    # Get FXStreet RSS news
    try:
        fxstreet_news = await rss_news_service.get_fxstreet_news_async(limit=10)
        all_news.extend(fxstreet_news[:5])
    except Exception as e:
        logger.warning(f"Failed to fetch FXStreet RSS news: {e}")
    
    # Deduplicate by headline
    seen = set()
    unique_news = []
    for item in all_news:
        headline = item.get("headline", item.get("title", ""))
        if headline and headline not in seen:
            seen.add(headline)
            unique_news.append(item)
    
    # Return top 10 unique news
    return unique_news[:10]


async def _fetch_economic_calendar() -> List[Dict[str, Any]]:
    """
    Fetch economic calendar from multiple sources:
    1. Finnhub economic calendar (primary) - free tier, may 403
    2. Alpha Vantage economic indicators (fallback) - premium key
    """
    # Try Finnhub first
    try:
        events = await finnhub_service.get_economic_calendar()
        if events:
            return events
    except Exception as e:
        logger.warning(f"Failed to fetch Finnhub economic calendar: {e}")
    
    # Fallback: Alpha Vantage economic indicators
    try:
        indicators = await alpha_vantage_service.get_economic_indicators()
        events = []
        for key, data in indicators.items():
            if data.get("value") and data["value"] != "unavailable":
                events.append({
                    "event": data.get("description", key),
                    "time": data.get("date", ""),
                    "country": "US",
                    "importance": "medium",
                    "value": data.get("value", ""),
                    "source": "Alpha Vantage",
                })
        if events:
            logger.info(f"Using Alpha Vantage economic indicators: {len(events)} events")
            return events
    except Exception as e:
        logger.warning(f"Failed to fetch Alpha Vantage economic indicators: {e}")
    
    return []


async def get_market_context() -> Dict[str, Any]:
    """
    Get unified market context from all services.
    
    Returns:
        Dict containing:
        - forex: FX price data
        - crypto: BTC, ETH price data
        - commodities: Gold, Oil data
        - indices: (empty for now)
        - cot_data: COT net position data
        - top_news: Recent news items
        - economic_calendar: Upcoming events
        - generated_at: Timestamp
    """
    logger.info("Fetching market context from all services...")
    
    # Run all fetches concurrently
    forex_task = _fetch_forex_data()
    crypto_task = _fetch_crypto_data()
    commodities_task = _fetch_commodities_data()
    news_task = _fetch_news_data()
    calendar_task = _fetch_economic_calendar()
    cot_task = asyncio.to_thread(_cot_async_wrapper)
    
    # Gather all results
    forex, crypto, commodities, top_news, economic_calendar, cot_data = await asyncio.gather(
        forex_task,
        crypto_task,
        commodities_task,
        news_task,
        calendar_task,
        cot_task,
    )
    
    context = {
        "forex": forex,
        "crypto": crypto,
        "commodities": commodities,
        "indices": {},  # Placeholder for future index data
        "cot_data": cot_data,
        "top_news": top_news,
        "economic_calendar": economic_calendar,
        "generated_at": datetime.now().isoformat(),
    }
    
    logger.info(f"Market context generated at {context['generated_at']}")
    return context


# Synchronous wrapper
def get_market_context_sync() -> Dict[str, Any]:
    """Synchronous wrapper for get_market_context."""
    return asyncio.run(get_market_context())
