"""
Data Fetcher for Trading Signal System
Fetches all required inputs for the 4-stage trading signal pipeline:
- OHLCV data from Yahoo Finance (yfinance)
- Macro data from FRED API
- VIX and index data from Yahoo Finance
- Existing market data from the app's data services
"""
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import yfinance as yf
from fredapi import Fred

from app.core.config import settings

logger = logging.getLogger(__name__)

# ─── Asset Classification ────────────────────────────────────────────────────

FX_PAIRS = {
    "EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "USDCAD",
    "NZDUSD", "EURGBP", "EURJPY", "GBPJPY", "AUDJPY", "EURAUD",
    "EURCHF", "EURCAD", "CADJPY", "GBPAUD", "GBPCAD", "GBPNZD",
    "XAUUSD", "XAGUSD",  # metals treated as FX pairs for trading
}
CRYPTO_TICKERS = {
    "BTCUSD", "ETHUSD", "SOLUSD", "XRPUSD", "ADAUSD", "DOGEUSD",
    "DOTUSD", "AVAXUSD", "LINKUSD", "MATICUSD",
}
EQUITY_TICKERS = {
    "SPY", "QQQ", "DIA",  # US indices
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA",  # stocks
    "^GSPC", "^DJI", "^IXIC", "^RUT",  # indices
}
COMMODITY_TICKERS = {
    "CL", "NG", "GC", "SI", "HG", "ZC", "ZS", "ZW",  # energy, metals, grains
    "USO", "GLD", "SLV",  # ETFs
}


def classify_asset(asset: str) -> str:
    """Classify an asset ticker into its asset class."""
    upper = asset.upper()
    if upper in FX_PAIRS or "/" not in upper:
        # Check if it's forex-like (common forex patterns)
        if any(x in upper for x in ["EUR", "GBP", "JPY", "CHF", "AUD", "CAD", "NZD", "USD"]):
            return "FX"
    if upper in CRYPTO_TICKERS or "BTC" in upper or "ETH" in upper:
        return "CRYPTO"
    if upper in EQUITY_TICKERS or upper.startswith("^"):
        return "EQUITY"
    if upper in COMMODITY_TICKERS:
        return "COMMODITY"
    return "FX"  # default to FX for forex pairs


# ─── FRED Helpers ────────────────────────────────────────────────────────────

def _get_fred() -> Optional[Fred]:
    if not settings.FRED_API_KEY:
        logger.warning("FRED_API_KEY not configured")
        return None
    return Fred(api_key=settings.FRED_API_KEY)


def fetch_fred_series(series_id: str, days: int = 90) -> Optional[float]:
    """Fetch the latest value of a FRED series."""
    fred = _get_fred()
    if not fred:
        return None
    try:
        end = datetime.utcnow()
        start = end - timedelta(days=days)
        df = fred.get_series(series_id, start, end)
        if df is not None and len(df) > 0:
            val = df.dropna().iloc[-1]
            return float(val) if val is not None else None
    except Exception as e:
        logger.warning(f"FRED series {series_id} failed: {e}")
    return None


def fetch_fred_series_history(series_id: str, days: int = 90) -> list[float]:
    """Fetch full history of a FRED series as a list of values."""
    fred = _get_fred()
    if not fred:
        return []
    try:
        end = datetime.utcnow()
        start = end - timedelta(days=days)
        df = fred.get_series(series_id, start, end)
        if df is not None:
            return [float(v) for v in df.dropna().tolist()]
    except Exception as e:
        logger.warning(f"FRED series {series_id} failed: {e}")
    return []


_ROC_FALLBACK = {"latest": None, "prior": None, "roc_pct": None, "direction": "UNKNOWN"}


def fetch_fred_series_with_roc(series_id: str, days: int = 365) -> Dict[str, Any]:
    """
    Fetch a FRED series and compute rate-of-change between the two most recent observations.
    Returns {latest, prior, roc_pct, direction} where direction is
    ACCELERATING (>0.5%), DECELERATING (<-0.5%), or FLAT.
    """
    values = fetch_fred_series_history(series_id, days)
    if len(values) < 2:
        return dict(_ROC_FALLBACK)

    latest = values[-1]
    prior = values[-2]
    if prior == 0:
        return {"latest": round(latest, 4), "prior": round(prior, 4), "roc_pct": 0.0, "direction": "FLAT"}

    roc = ((latest - prior) / abs(prior)) * 100
    if roc > 0.5:
        direction = "ACCELERATING"
    elif roc < -0.5:
        direction = "DECELERATING"
    else:
        direction = "FLAT"

    return {
        "latest": round(latest, 4),
        "prior": round(prior, 4),
        "roc_pct": round(roc, 2),
        "direction": direction,
    }


def classify_quadrant(gdp_dir: str, cpi_dir: str) -> str:
    """
    Map (GDP direction, CPI direction) to economic quadrant.
    Based on V3 spec Section 9.
    """
    return {
        ("ACCELERATING", "DECELERATING"): "EXPANSION",
        ("ACCELERATING", "ACCELERATING"): "REFLATION",
        ("DECELERATING", "DECELERATING"): "DISINFLATION",
        ("DECELERATING", "ACCELERATING"): "STAGFLATION",
    }.get((gdp_dir, cpi_dir), "TRANSITIONAL")


# ─── Yahoo Finance Helpers ──────────────────────────────────────────────────

def fetch_yf_ticker(ticker: str, period: str = "6mo") -> Optional[dict]:
    """Fetch OHLCV data for a ticker from Yahoo Finance."""
    try:
        data = yf.Ticker(ticker)
        hist = data.history(period=period)
        if hist is None or hist.empty:
            return None
        return hist
    except Exception as e:
        logger.warning(f"yfinance fetch failed for {ticker}: {e}")
        return None


def fetch_current_price(ticker: str) -> Optional[float]:
    """Get the current/last price for a ticker."""
    try:
        data = yf.Ticker(ticker)
        info = data.fast_info
        price = info.get("last_price") or info.get("previous_close")
        if price:
            return float(price)
        # Fallback to history
        hist = data.history(period="5d")
        if hist is not None and not hist.empty:
            return float(hist["Close"].iloc[-1])
    except Exception as e:
        logger.warning(f"Current price fetch failed for {ticker}: {e}")
    return None


def fetch_vix() -> tuple[Optional[float], Optional[float]]:
    """
    Fetch VIX current and VIX from 30 days ago.
    Returns (vix_current, vix_30d_ago).
    """
    try:
        vix = yf.Ticker("^VIX")
        hist = vix.history(period="40d")
        if hist is None or hist.empty or len(hist) < 2:
            return None, None
        current = float(hist["Close"].iloc[-1])
        ago_30 = float(hist["Close"].iloc[-31]) if len(hist) > 30 else float(hist["Close"].iloc[0])
        return current, ago_30
    except Exception as e:
        logger.warning(f"VIX fetch failed: {e}")
        return None, None


def fetch_spx_current() -> tuple[Optional[float], Optional[float]]:
    """
    Fetch S&P 500 current price and previous cycle high.
    Previous cycle high = peak before 2022 bear market (~4796).
    """
    try:
        spy = yf.Ticker("^GSPC")
        info = spy.fast_info
        current = info.get("last_price") or info.get("previous_close")
        if not current:
            hist = spy.history(period="5d")
            if hist is not None and not hist.empty:
                current = float(hist["Close"].iloc[-1])
        # Previous cycle high: use a hardcoded known value or fetch from yfinance history
        # For current purposes: 4796.23 (Jan 2022 high) as the previous cycle high
        prev_cycle_high = 4796.23
        return float(current) if current else None, prev_cycle_high
    except Exception as e:
        logger.warning(f"SPX fetch failed: {e}")
        return None, None


# ─── Stage 1: Regime Data ───────────────────────────────────────────────────

def get_regime_data() -> Dict[str, Any]:
    """
    Gather all data needed for Stage 1 (Market Regime Classification).
    """
    spx_current, spx_prev_high = fetch_spx_current()
    vix_current, vix_30d_ago = fetch_vix()

    # Calculate bear market level
    bear_market_level = spx_prev_high * 0.80 if spx_prev_high else None
    # Bull market level = when price recovered above bear level after a bear
    # For now, use same as prev cycle high as approximation
    bull_market_level = spx_prev_high if spx_prev_high else None

    # VIX % change
    vix_pct_change = None
    if vix_current and vix_30d_ago and vix_30d_ago != 0:
        vix_pct_change = round((vix_current - vix_30d_ago) / vix_30d_ago * 100, 2)

    return {
        "spx_current": spx_current,
        "spx_prev_cycle_high": spx_prev_high,
        "bear_market_level": bear_market_level,
        "bull_market_level": bull_market_level,
        "vix_current": vix_current,
        "vix_30d_ago": vix_30d_ago,
        "vix_pct_change": vix_pct_change,
    }


# ─── Stage 2: Macro Data ────────────────────────────────────────────────────

# FRED series IDs — these are confirmed working
# ISM Manufacturing PMI is not freely available on FRED (published by ISM separately)
FRED_SERIES = {
    "ism_manufacturing": "USSLIND",      # Leading Index (proxy for macro momentum)
    "ism_services": "NMP",               # ISM Services PMI — try this
    "consumer_confidence": "UMCSENT",     # University of Michigan Consumer Sentiment
    "unemployment": "UNRATE",            # Unemployment Rate
    "nfp": "PAYEMS",                    # Non-farm Payrolls (level, use diff for change)
    "gdp_growth": "GDP",                # GDP Q/Q %
    "cpi": "CPIAUCSL",                  # CPI F/P
    "core_pce": "PCEPILFE",            # Core PCE — confirmed working
    "fed_funds_rate": "FEDFUNDS",       # Fed Funds Rate
    "dxy": "DTWEXBGS",                 # Trade Weighted USD Index — confirmed working
    "wage_growth": "FRBATLWGTUMHWGO",  # Wage growth (FRB) — confirmed working
    "retail_sales": "RRSFS",            # Retail Sales — confirmed working
}


def get_macro_data(asset_class: str = "FX") -> Dict[str, Any]:
    """
    Gather all macro data for Stage 2 (Macro Fundamental Analysis).
    Key indicators include rate-of-change and direction per the V3 spec.
    """
    result: Dict[str, Any] = {}

    # ── Spec Section 9: ROC-enriched indicators ─────────────────────────
    result["gdp"] = fetch_fred_series_with_roc("GDPC1", days=730)        # quarterly — wide window
    result["cpi"] = fetch_fred_series_with_roc("CPIAUCSL", days=365)
    result["pce"] = fetch_fred_series_with_roc("PCEPI", days=365)
    result["unemployment"] = fetch_fred_series_with_roc("UNRATE", days=365)
    result["leading_indicator"] = fetch_fred_series_with_roc("USALOLITONOSTSAM", days=365)
    result["consumer_sentiment"] = fetch_fred_series_with_roc("UMCSENT", days=365)
    result["yield_curve"] = fetch_fred_series_with_roc("T10Y2YM", days=365)
    result["fed_funds"] = fetch_fred_series_with_roc("FEDFUNDS", days=365)

    # ── Economic quadrant from GDP + CPI directions ─────────────────────
    gdp_dir = result["gdp"].get("direction", "UNKNOWN")
    cpi_dir = result["cpi"].get("direction", "UNKNOWN")
    result["economic_quadrant"] = classify_quadrant(gdp_dir, cpi_dir)

    # ── Additional indicators (kept as raw values for compatibility) ────
    result["ism_manufacturing"] = fetch_fred_series("USSLIND", days=90)
    result["ism_services"] = fetch_fred_series("USSLIND", days=90)
    result["consumer_confidence"] = fetch_fred_series("UMCSENT", days=90)
    result["surprise_index"] = None

    # Employment — NFP change
    nfp_series = fetch_fred_series_history("PAYEMS", days=180)
    result["nfp_change"] = round(nfp_series[-1] - nfp_series[-2], 1) if len(nfp_series) >= 2 else None

    # Flat shortcuts for backward compat
    result["unemployment_rate"] = result["unemployment"].get("latest")
    result["gdp_growth"] = result["gdp"].get("latest")
    result["core_pce"] = fetch_fred_series("PCEPILFE", days=180)
    result["fed_funds_rate"] = result["fed_funds"].get("latest")

    # Fiscal balance
    result["fiscal_deficit"] = fetch_fred_series("FYFSD", days=365)

    # USD Index
    result["dxy"] = fetch_fred_series("DTWEXBGS", days=90)

    # Wage growth
    result["wage_growth"] = fetch_fred_series("FRBATLWGTUMHWGO", days=365)

    # Retail sales
    result["retail_sales"] = fetch_fred_series("RRSFS", days=90)

    # CB Target
    result["cb_inflation_target"] = 2.0

    # Rate trend + bias
    fed_rate_series = fetch_fred_series_history("FEDFUNDS", days=180)
    if len(fed_rate_series) >= 3:
        latest_rate = fed_rate_series[-1]
        prev_rate = fed_rate_series[-3]
        if latest_rate > prev_rate + 0.1:
            result["rate_trend"] = "HIKING"
        elif latest_rate < prev_rate - 0.1:
            result["rate_trend"] = "CUTTING"
        else:
            result["rate_trend"] = "PAUSING"
    else:
        result["rate_trend"] = "UNKNOWN"

    result["cb_bias"] = _estimate_cb_bias(fed_rate_series if fed_rate_series else [])

    return result


def _estimate_cb_bias(fed_rate_series: list[float]) -> str:
    """Estimate CB bias from recent rate changes."""
    if len(fed_rate_series) < 6:
        return "NEUTRAL"
    recent = fed_rate_series[-6:]
    if all(recent[i] > recent[i-1] for i in range(1, len(recent))):
        return "HAWKISH"
    if all(recent[i] < recent[i-1] for i in range(1, len(recent))):
        return "DOVISH"
    return "NEUTRAL"


# ─── Forex-specific data ─────────────────────────────────────────────────────

FOREX_COUNTRY_DATA = {
    "EUR": {"commo_dep": "No", "rate": None},
    "USD": {"commo_dep": "No", "rate": None},
    "JPY": {"commo_dep": "No", "rate": None},
    "GBP": {"commo_dep": "No", "rate": None},
    "AUD": {"commo_dep": "Yes: metals", "rate": None},
    "NZD": {"commo_dep": "Yes: dairy", "rate": None},
    "CAD": {"commo_dep": "Yes: oil", "rate": None},
    "CHF": {"commo_dep": "No", "rate": None},
}


def get_forex_pair_data(base_ccy: str, quote_ccy: str) -> Dict[str, Any]:
    """Get forex-specific macro data for a currency pair."""
    base_data = FOREX_COUNTRY_DATA.get(base_ccy.upper(), {"commo_dep": "Unknown", "rate": None})
    quote_data = FOREX_COUNTRY_DATA.get(quote_ccy.upper(), {"commo_dep": "Unknown", "rate": None})

    # Fetch forex rates from yfinance (more reliable than FRED for this)
    pair_str = f"{base_ccy.upper()}{quote_ccy.upper()}=X"
    pair_data: Dict[str, Any] = {"price": None, "change_percent": None}

    try:
        import yfinance as yf2
        ticker = yf2.Ticker(pair_str)
        info = ticker.info
        # yfinance FX pairs: currentPrice or regularMarketPrice
        price = info.get("currentPrice") or info.get("regularMarketPrice")
        change = info.get("regularMarketChangePercent")
        pair_data["price"] = price
        pair_data["change_percent"] = round(change, 2) if change is not None else None
    except Exception as e:
        logger.warning(f"Failed to fetch forex data for {pair_str}: {e}")

    rate_diff = None
    if pair_data["price"]:
        # Estimate rate differential from the pair price itself
        # For standard FX: if price > 1, quote is USD; if price < 1, base is USD
        # Use VIX + gold as macro proxies from regime data
        try:
            vix_current, _ = fetch_vix()
            if vix_current and vix_current > 25:
                rate_diff = -1.5  # Risk-off: USD tends to strengthen
            elif vix_current and vix_current < 15:
                rate_diff = 1.0   # Risk-on: AUD/NZD/EM tend to outperform
        except Exception:
            pass

    return {
        "forex": {
            f"{base_ccy.upper()}{quote_ccy.upper()}": pair_data,
        },
        "base_commodity_dep": base_data["commo_dep"],
        "quote_commodity_dep": quote_data["commo_dep"],
        "rate_differential": rate_diff,
    }


# ─── Crypto-specific data ───────────────────────────────────────────────────

def get_crypto_data(btc_price: Optional[float] = None) -> Dict[str, Any]:
    """Get crypto-specific macro data."""
    try:
        btc = yf.Ticker("BTC-USD")
        info = btc.fast_info
        current_btc = info.get("last_price") or fetch_current_price("BTC-USD")

        # BTC dominance (approx via Yahoo Finance)
        total_crypto_cap = fetch_current_price("TOTAL")  # Might fail

        # Risk environment: use VIX as proxy
        vix_current, _ = fetch_vix()
        if vix_current:
            risk_env = "RISK_ON" if vix_current < 20 else "RISK_OFF"
        else:
            risk_env = "UNKNOWN"

        return {
            "btc_dominance": None,  # Would need CMC or similar
            "risk_environment": risk_env,
            "regulatory_news": "Monitor SEC/CFTC actions",
            "btc_price": current_btc,
        }
    except Exception as e:
        logger.warning(f"Crypto data fetch failed: {e}")
        return {
            "btc_dominance": None,
            "risk_environment": "UNKNOWN",
            "regulatory_news": "Data unavailable",
            "btc_price": None,
        }


# ─── Full Macro Data for an Asset ─────────────────────────────────────────────

def get_full_macro_data(asset: str) -> Dict[str, Any]:
    """
    Get complete macro data for a given asset.
    Automatically determines asset class and includes relevant data.
    """
    asset_class = classify_asset(asset)
    macro = get_macro_data(asset_class)

    if asset_class == "FX":
        # Parse forex pair
        parts = asset.replace("=X", "").split("/")
        if len(parts) == 2:
            base, quote = parts[0][:3], parts[1][:3]
        else:
            # Handle XAUUSD, XAGUSD
            base, quote = parts[0][:3], parts[0][3:] if len(parts[0]) > 3 else "USD"
        fx_data = get_forex_pair_data(base, quote)
        macro.update(fx_data)
        macro["asset_class"] = "FX"

        # For precious metals (XAU/USD, XAG/USD), fetch live price via yfinance
        if base == "XAU":
            price = fetch_current_price("GC=F")
            if price:
                macro["commodities"] = {"GOLD": {"price": round(price, 2), "change_percent": 0.0}}
        elif base == "XAG":
            price = fetch_current_price("SI=F")
            if price:
                macro["commodities"] = {"SILVER": {"price": round(price, 2), "change_percent": 0.0}}
    elif asset_class == "CRYPTO":
        crypto_data = get_crypto_data()
        macro.update(crypto_data)
        macro["asset_class"] = "CRYPTO"
    elif asset_class == "EQUITY":
        macro["sector"] = "US Large Cap"
        macro["earnings_growth"] = None  # Would need earnings API
        macro["pe_vs_avg"] = None
        macro["asset_class"] = "EQUITY"
    elif asset_class == "COMMODITY":
        macro["supply_demand"] = "Monitor EIA weekly reports"
        macro["geopolitical_risk"] = "Medium"
        macro["dxy_level"] = fetch_fred_series("DTWEXBGS", days=30)
        macro["asset_class"] = "COMMODITY"

    return macro
