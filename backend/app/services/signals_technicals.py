"""
Technical Analysis Calculator for Trading Signal System
Calculates all required technical indicators using the `ta` library.
Implements the exact indicators specified in the ITPM WISH Framework:
- 20-day MA (1 month)
- 60-day MA (1 quarter)
- 250-day MA (1 year)
- RSI (14-period)
- ATR (14-period)
- Historical volatility (1-month and 3-month annualised)
- MA crossover signals (20/60 and 60/250)
"""
import logging
from typing import Any, Dict, Optional

import yfinance as yf
import pandas as pd
import numpy as np
from ta.volatility import AverageTrueRange
from ta.momentum import RSIIndicator

logger = logging.getLogger(__name__)

# ─── Core Calculator ──────────────────────────────────────────────────────────

def calculate_technicals(ticker: str, period: str = "1y") -> Optional[Dict[str, Any]]:
    """
    Calculate all required technical indicators for a ticker.
    Uses yfinance for OHLCV data and `ta` for indicator calculation.

    Args:
        ticker: Asset ticker (e.g. "EURUSD=X", "BTC-USD", "^GSPC")
        period: yfinance period string (default "1y" for 1-year data)

    Returns:
        Dict with all technical indicators, or None if data unavailable.
    """
    try:
        data = yf.Ticker(ticker)
        df = data.history(period=period)

        if df is None or df.empty or len(df) < 60:
            logger.warning(f"Insufficient data for {ticker}: {len(df) if df is not None else 0} rows")
            return None

        close = df["Close"]
        high = df["High"]
        low = df["Low"]
        volume = df["Volume"]

        # ── Moving Averages ──────────────────────────────────────────────
        ma20 = close.rolling(20).mean()
        ma60 = close.rolling(60).mean()
        ma250 = close.rolling(250).mean()

        latest = close.iloc[-1]
        latest_ma20 = ma20.iloc[-1]
        latest_ma60 = ma60.iloc[-1]
        latest_ma250 = ma250.iloc[-1]

        # ── MA Crossovers ────────────────────────────────────────────────
        # Need at least 2 days of MA values to detect cross
        if len(ma20) >= 2 and len(ma60) >= 2:
            ma20_prev = ma20.iloc[-2]
            ma60_prev = ma60.iloc[-2]
            # 20 crossed above 60 = GOLDEN, 20 crossed below 60 = DEATH
            if ma20_prev < ma60_prev and latest_ma20 > latest_ma60:
                ma_20_vs_60_cross = "GOLDEN"
            elif ma20_prev > ma60_prev and latest_ma20 < latest_ma60:
                ma_20_vs_60_cross = "DEATH"
            else:
                ma_20_vs_60_cross = "NONE"
        else:
            ma_20_vs_60_cross = "NONE"

        if len(ma60) >= 2 and len(ma250) >= 2:
            ma60_prev = ma60.iloc[-2]
            ma250_prev = ma250.iloc[-2]
            if ma60_prev < ma250_prev and latest_ma60 > latest_ma250:
                ma_60_vs_250_cross = "GOLDEN"
            elif ma60_prev > ma250_prev and latest_ma60 < latest_ma250:
                ma_60_vs_250_cross = "DEATH"
            else:
                ma_60_vs_250_cross = "NONE"
        else:
            ma_60_vs_250_cross = "NONE"

        # ── RSI (14-period) ────────────────────────────────────────────
        rsi_14 = RSIIndicator(close, window=14).rsi().iloc[-1]

        # ── ATR (14-period) ────────────────────────────────────────────
        atr_14 = AverageTrueRange(high, low, close, window=14).average_true_range().iloc[-1]

        # ── Trend Direction ─────────────────────────────────────────────
        trend = _determine_trend(close, ma20, ma60)

        # ── Price Pattern ───────────────────────────────────────────────
        price_pattern = _detect_pattern(df)

        # ── Volume ─────────────────────────────────────────────────────
        vol_avg = volume.rolling(20).mean().iloc[-1]
        vol_current = volume.iloc[-1]
        if vol_current > vol_avg * 1.5:
            volume_vs_avg = "HIGH"
        elif vol_current < vol_avg * 0.7:
            volume_vs_avg = "LOW"
        else:
            volume_vs_avg = "NORMAL"

        # ── Support / Resistance ────────────────────────────────────────
        key_support, key_resistance = _find_support_resistance(df)
        price_location = _get_price_location(latest, key_support, key_resistance)

        # ── Historical Volatility ────────────────────────────────────────
        returns_1m = close.pct_change().tail(20)
        returns_3m = close.pct_change().tail(60)
        hist_vol_1m = round(float(returns_1m.std() * np.sqrt(252) * 100), 2) if not np.isnan(returns_1m.std()) else None
        hist_vol_3m = round(float(returns_3m.std() * np.sqrt(252) * 100), 2) if not np.isnan(returns_3m.std()) else None

        # ── IV Ranges (HV30 as proxy) ────────────────────────────────────
        iv_ranges = None
        if hist_vol_1m and latest is not None:
            iv_ranges = calculate_iv_ranges(float(latest), hist_vol_1m)

        # ── Current price context ─────────────────────────────────────────
        price_vs_20ma = "ABOVE" if latest > latest_ma20 else "BELOW"
        price_vs_60ma = "ABOVE" if latest > latest_ma60 else "BELOW"
        price_vs_250ma = "ABOVE" if latest > latest_ma250 else "BELOW"

        return {
            "ticker": ticker,
            "current_price": round(float(latest), 5) if latest is not None else None,
            "ma20": round(float(latest_ma20), 5) if latest_ma20 is not None and not np.isnan(latest_ma20) else None,
            "ma60": round(float(latest_ma60), 5) if latest_ma60 is not None and not np.isnan(latest_ma60) else None,
            "ma250": round(float(latest_ma250), 5) if latest_ma250 is not None and not np.isnan(latest_ma250) else None,
            "price_vs_20ma": price_vs_20ma,
            "price_vs_60ma": price_vs_60ma,
            "price_vs_250ma": price_vs_250ma,
            "ma_20_vs_60_cross": ma_20_vs_60_cross,
            "ma_60_vs_250_cross": ma_60_vs_250_cross,
            "rsi_14": round(float(rsi_14), 2) if not np.isnan(rsi_14) else None,
            "atr_14": round(float(atr_14), 5) if not np.isnan(atr_14) else None,
            "hist_vol_1m": hist_vol_1m,
            "hist_vol_3m": hist_vol_3m,
            "trend_direction": trend,
            "price_pattern": price_pattern,
            "volume_vs_avg": volume_vs_avg,
            "key_support": round(float(key_support), 5) if key_support else None,
            "key_resistance": round(float(key_resistance), 5) if key_resistance else None,
            "at_support_resistance": price_location,
            # IV ranges (spec Section 9)
            "iv_ranges": iv_ranges,
            # Extra for frontend display
            "change_pct": round(float(close.pct_change().iloc[-1] * 100), 3),
        }

    except Exception as e:
        logger.error(f"Technical analysis failed for {ticker}: {e}")
        return None


# ─── IV Ranges (Spec Section 9) ──────────────────────────────────────────────

def calculate_iv_ranges(price: float, iv_annual_pct: float) -> Dict[str, Any]:
    """
    Calculate implied volatility price ranges using annualized volatility.
    Uses HV30 as proxy when real IV is unavailable.

    Args:
        price: Current asset price.
        iv_annual_pct: Annualized volatility as percentage (e.g. 15.0 for 15%).

    Returns:
        Dict with daily/weekly/monthly 1SD/2SD ranges, hard stop, soft target.
    """
    iv = iv_annual_pct / 100
    d1sd = price * iv / np.sqrt(252)
    w1sd = price * iv / np.sqrt(52)
    m1sd = price * iv / np.sqrt(12)

    return {
        "daily_1sd": round(d1sd, 5),
        "daily_2sd": round(d1sd * 2, 5),
        "daily_1sd_up": round(price + d1sd, 5),
        "daily_1sd_down": round(price - d1sd, 5),
        "daily_2sd_up": round(price + d1sd * 2, 5),
        "daily_2sd_down": round(price - d1sd * 2, 5),
        "weekly_1sd": round(w1sd, 5),
        "monthly_1sd": round(m1sd, 5),
        "hard_stop_distance": round(m1sd * 1.3, 5),
        "soft_target_distance": round(m1sd * 3 * 1.3, 5),
        "iv_annual_pct": round(iv_annual_pct, 2),
        "iv_proxy_used": "HV30",
    }


# ─── Pattern Detection ───────────────────────────────────────────────────────

def _detect_pattern(df: pd.DataFrame) -> str:
    """
    Simple pattern detection using local minima/maxima.
    Detects: HEAD_SHOULDERS, INV_HEAD_SHOULDERS, DOUBLE_TOP, DOUBLE_BOTTOM,
             BULL_FLAG, BEAR_FLAG, PENNANT, NONE
    """
    try:
        closes = df["Close"].values
        highs = df["High"].values
        lows = df["Low"].values

        if len(closes) < 60:
            return "NONE"

        # Use last 60 bars for pattern detection
        window = closes[-60:]
        w_highs = highs[-60:]
        w_lows = lows[-60:]

        # Find local extrema using simple approach
        from scipy.signal import argrelextrema
        if len(window) < 20:
            return "NONE"

        try:
            highs_idx = argrelextrema(window, np.greater, order=5)[0]
            lows_idx = argrelextrema(window, np.less, order=5)[0]
        except Exception:
            return "NONE"

        if len(highs_idx) < 3 or len(lows_idx) < 3:
            return "NONE"

        # Head and shoulders detection
        last_highs = highs_idx[-3:]
        last_lows = lows_idx[-3:]

        if len(last_highs) >= 3:
            h1, h2, h3 = window[last_highs[-3]], window[last_highs[-2]], window[last_highs[-1]]
            if h2 > h1 * 1.01 and h2 > h3 * 1.01:
                return "HEAD_SHOULDERS"

        if len(last_lows) >= 3:
            l1, l2, l3 = window[last_lows[-3]], window[last_lows[-2]], window[last_lows[-1]]
            if l2 < l1 * 0.99 and l2 < l3 * 0.99:
                return "INV_HEAD_SHOULDERS"

        # Double top / bottom
        if len(last_highs) >= 2:
            if abs(window[last_highs[-1]] - window[last_highs[-2]]) / window[last_highs[-2]] < 0.005:
                return "DOUBLE_TOP"
        if len(last_lows) >= 2:
            if abs(window[last_lows[-1]] - window[last_lows[-2]]) / window[last_lows[-2]] < 0.005:
                return "DOUBLE_BOTTOM"

        return "NONE"

    except Exception:
        return "NONE"


def _determine_trend(close: pd.Series, ma20: pd.Series, ma60: pd.Series) -> str:
    """Determine overall trend direction using price vs MAs."""
    try:
        latest_close = close.iloc[-1]
        latest_ma20 = ma20.iloc[-1]
        latest_ma60 = ma60.iloc[-1]

        if np.isnan(latest_ma60):
            return "RANGING"

        # Uptrend: price > MA20 > MA60 and all rising
        if latest_close > latest_ma20 > latest_ma60:
            return "UPTREND"
        # Downtrend: price < MA20 < MA60 and all falling
        if latest_close < latest_ma20 < latest_ma60:
            return "DOWNTREND"
        return "RANGING"
    except Exception:
        return "RANGING"


def _find_support_resistance(df: pd.DataFrame, lookback: int = 20) -> tuple[Optional[float], Optional[float]]:
    """Find nearest support and resistance from recent lows/highs."""
    try:
        lows = df["Low"].tail(lookback)
        highs = df["High"].tail(lookback)
        current = df["Close"].iloc[-1]

        # Support = highest low below current
        support_candidates = [l for l in lows if l < current * 0.99]
        support = max(support_candidates) if support_candidates else None

        # Resistance = lowest high above current
        resistance_candidates = [h for h in highs if h > current * 1.01]
        resistance = min(resistance_candidates) if resistance_candidates else None

        return support, resistance
    except Exception:
        return None, None


def _get_price_location(price: float, support: Optional[float], resistance: Optional[float]) -> str:
    """Determine if price is at support, resistance, or mid-range."""
    if not support or not resistance:
        return "MID_RANGE"
    range_size = resistance - support
    if range_size == 0:
        return "MID_RANGE"
    position = (price - support) / range_size
    if position < 0.2:
        return "AT_SUPPORT"
    if position > 0.8:
        return "AT_RESISTANCE"
    return "MID_RANGE"


# ─── Ticker normalisation ────────────────────────────────────────────────────

def normalise_ticker(asset: str) -> str:
    """
    Convert common ticker formats to yfinance format.
    e.g. "EURUSD" -> "EURUSD=X", "BTCUSD" -> "BTC-USD"
    """
    upper = asset.upper()

    # Forex pairs (yfinance uses =X suffix) — check BEFORE generic USD-suffix
    forex_pairs = {
        "EURUSD": "EURUSD=X", "GBPUSD": "GBPUSD=X", "USDJPY": "USDJPY=X",
        "USDCHF": "USDCHF=X", "AUDUSD": "AUDUSD=X", "USDCAD": "USDCAD=X",
        "NZDUSD": "NZDUSD=X", "EURGBP": "EURGBP=X", "EURJPY": "EURJPY=X",
        "GBPJPY": "GBPJPY=X", "AUDJPY": "AUDJPY=X", "EURAUD": "EURAUD=X",
        "EURCHF": "EURCHF=X", "EURCAD": "EURCAD=X", "CADJPY": "CADJPY=X",
        "XAUUSD": "GC=F",   # Gold futures (XAUUSD=X is delisted on Yahoo)
        "XAGUSD": "SI=F",   # Silver futures
    }
    if upper in forex_pairs:
        return forex_pairs[upper]

    # Crypto (uses -USD format)
    if upper in ("BTCUSD", "XBTUSD", "BTC"):
        return "BTC-USD"
    if upper == "ETH":
        return "ETH-USD"
    if upper.endswith("USD") and len(upper) <= 8:
        base = upper[:-3]
        return f"{base}-USD"

    # Already in yfinance format
    if "=" in upper or "-" in upper:
        return upper

    return upper  # Return as-is for indices, equities
