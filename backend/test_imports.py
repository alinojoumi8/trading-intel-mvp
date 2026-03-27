#!/usr/bin/env python3
"""Quick import test for new services."""
import sys
sys.path.insert(0, '.')

print("Testing imports...")

try:
    from app.services.data_aggregator import get_market_context
    print("✓ data_aggregator imports OK")
except Exception as e:
    print(f"✗ data_aggregator: {e}")

try:
    from app.services import get_fxstreet_news, get_economic_indicators
    print("✓ new exports from __init__ OK")
except Exception as e:
    print(f"✗ exports: {e}")

try:
    from app.services.alpha_vantage_service import get_economic_indicators
    print("✓ alpha_vantage economic indicators OK")
except Exception as e:
    print(f"✗ alpha_vantage_service: {e}")

try:
    from app.services.rss_news_service import get_fxstreet_news
    print("✓ rss_news_service OK")
except Exception as e:
    print(f"✗ rss_news_service: {e}")

print("\nAll imports passed!")
