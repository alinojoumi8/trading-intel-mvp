"""
Data Services Package
Exports all service functions for external use.
"""
from app.services.cot_service import get_cot_summary, get_cot_for_instrument
from app.services.finnhub_service import (
    get_market_news as finnhub_get_market_news,
    get_market_news_sync as finnhub_get_market_news_sync,
    get_company_sentiment,
    get_company_sentiment_sync,
    get_economic_calendar,
    get_economic_calendar_sync,
    get_quote,
    get_quote_sync,
)
from app.services.news_service import (
    get_forex_news,
    get_forex_news_sync,
    get_market_news,
    get_market_news_sync,
)
from app.services.alpha_vantage_service import (
    get_forex_quote,
    get_forex_quote_sync,
    get_intraday_data,
    get_intraday_data_sync,
    get_economic_indicators,
    get_economic_indicators_sync,
)
from app.services.rss_news_service import (
    get_fxstreet_news,
    get_fxstreet_news_sync,
)
from app.services.crypto_service import (
    get_btc_quote,
    get_btc_quote_sync,
    get_eth_quote,
    get_eth_quote_sync,
    get_crypto_price,
    get_crypto_price_sync,
)
from app.services.kraken_service import (
    get_ticker,
    get_ohlcv,
    get_btc_quote as kraken_btc_quote,
    get_eth_quote as kraken_eth_quote,
    get_sol_quote,
    get_crypto_price as kraken_crypto_price,
)
from app.services.data_aggregator import (
    get_market_context,
    get_market_context_sync,
)
from app.services.llm_service import (
    generate,
    generate_sync,
)
from app.services.content_generators import (
    generate_morning_briefing,
    generate_morning_briefing_sync,
    generate_trade_setup,
    generate_trade_setup_sync,
    generate_macro_roundup,
    generate_macro_roundup_sync,
    generate_contrarian_alert,
    generate_contrarian_alert_sync,
)
from app.services.content_pipeline import (
    run_morning_briefing_pipeline,
    run_setup_pipeline,
    run_macro_roundup_pipeline,
    run_contrarian_check_pipeline,
    run_full_daily_pipeline,
)

__all__ = [
    # COT Service
    "get_cot_summary",
    "get_cot_for_instrument",
    # Finnhub Service
    "finnhub_get_market_news",
    "finnhub_get_market_news_sync",
    "get_company_sentiment",
    "get_company_sentiment_sync",
    "get_economic_calendar",
    "get_economic_calendar_sync",
    "get_quote",
    "get_quote_sync",
    # News Service
    "get_forex_news",
    "get_forex_news_sync",
    "get_market_news",
    "get_market_news_sync",
    # Alpha Vantage Service
    "get_forex_quote",
    "get_forex_quote_sync",
    "get_intraday_data",
    "get_intraday_data_sync",
    "get_economic_indicators",
    "get_economic_indicators_sync",
    # RSS News Service
    "get_fxstreet_news",
    "get_fxstreet_news_sync",
    # Crypto Service (Binance)
    "get_btc_quote",
    "get_btc_quote_sync",
    "get_eth_quote",
    "get_eth_quote_sync",
    "get_crypto_price",
    "get_crypto_price_sync",
    # Kraken Service
    "get_ticker",
    "get_ohlcv",
    "kraken_btc_quote",
    "kraken_eth_quote",
    "get_sol_quote",
    "kraken_crypto_price",
    # Data Aggregator
    "get_market_context",
    "get_market_context_sync",
    # LLM Service
    "generate",
    "generate_sync",
    # Content Generators
    "generate_morning_briefing",
    "generate_morning_briefing_sync",
    "generate_trade_setup",
    "generate_trade_setup_sync",
    "generate_macro_roundup",
    "generate_macro_roundup_sync",
    "generate_contrarian_alert",
    "generate_contrarian_alert_sync",
    # Content Pipeline
    "run_morning_briefing_pipeline",
    "run_setup_pipeline",
    "run_macro_roundup_pipeline",
    "run_contrarian_check_pipeline",
    "run_full_daily_pipeline",
]
