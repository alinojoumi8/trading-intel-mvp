"""
VIX historical data loader.

Reads the official CBOE VIX_History.csv (daily OHLC since 1990) into a
queryable Parquet file. Used by historical regime detection in the V3 backtest.

Source format (CBOE):
    DATE,OPEN,HIGH,LOW,CLOSE
    01/02/1990,17.240000,17.240000,17.240000,17.240000
"""
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd

logger = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).parent.parent.parent / "data"
RAW_VIX_PATH = _DATA_DIR / "VIX_History.csv"
CLEANED_VIX_PATH = _DATA_DIR / "vix_history.parquet"


def build_vix_parquet(force: bool = False) -> Dict[str, Any]:
    """Convert VIX_History.csv → vix_history.parquet. Idempotent."""
    if not RAW_VIX_PATH.exists():
        raise FileNotFoundError(f"VIX raw CSV not found at {RAW_VIX_PATH}")

    if CLEANED_VIX_PATH.exists() and not force:
        existing = pd.read_parquet(CLEANED_VIX_PATH)
        return {
            "skipped": True,
            "rows": len(existing),
            "date_range": (str(existing.index.min().date()), str(existing.index.max().date())),
        }

    df = pd.read_csv(RAW_VIX_PATH)
    df.columns = [c.strip().lower() for c in df.columns]  # date, open, high, low, close
    df["date"] = pd.to_datetime(df["date"], format="%m/%d/%Y")
    df = df.set_index("date").sort_index()
    # Cast numerics
    for col in ["open", "high", "low", "close"]:
        df[col] = df[col].astype("float32")

    df.to_parquet(CLEANED_VIX_PATH, compression="snappy")
    size_mb = CLEANED_VIX_PATH.stat().st_size / 1024
    logger.info(f"[VIX] Wrote {CLEANED_VIX_PATH.name}: {len(df):,} rows, {size_mb:.1f} KB")

    return {
        "skipped": False,
        "rows": len(df),
        "date_range": (str(df.index.min().date()), str(df.index.max().date())),
        "path": str(CLEANED_VIX_PATH),
    }


_vix_cache: Optional[pd.DataFrame] = None


def load_vix() -> pd.DataFrame:
    """Load the full VIX history into memory (cached). Returns DataFrame indexed by date."""
    global _vix_cache
    if _vix_cache is None:
        if not CLEANED_VIX_PATH.exists():
            build_vix_parquet()
        _vix_cache = pd.read_parquet(CLEANED_VIX_PATH)
    return _vix_cache


def get_vix_at(as_of: datetime) -> Optional[float]:
    """
    Get the VIX close as of a given date (or most recent prior trading day).
    Returns None if no data available before that date.
    """
    df = load_vix()
    target = pd.Timestamp(as_of.date())
    in_window = df[df.index <= target]
    if in_window.empty:
        return None
    return float(in_window.iloc[-1]["close"])


def get_vix_change_pct(as_of: datetime, days_back: int = 30) -> Optional[Dict[str, float]]:
    """
    Compute VIX % change over the last N trading days as of a given date.
    Used by Stage 1 regime classification.

    Returns dict with current, prior, pct_change, or None if insufficient data.
    """
    df = load_vix()
    target = pd.Timestamp(as_of.date())
    window = df[df.index <= target]
    if window.empty:
        return None

    current = float(window.iloc[-1]["close"])
    if len(window) <= days_back:
        return {"current": current, "prior": None, "pct_change": None}

    # Use calendar approximation: days_back trading days back ≈ days_back * 1.4 calendar days
    target_prior = target - timedelta(days=int(days_back * 1.45))
    prior_window = df[df.index <= target_prior]
    if prior_window.empty:
        return {"current": current, "prior": None, "pct_change": None}

    prior = float(prior_window.iloc[-1]["close"])
    pct_change = (current - prior) / prior * 100 if prior > 0 else None

    return {
        "current": round(current, 2),
        "prior": round(prior, 2),
        "pct_change": round(pct_change, 2) if pct_change is not None else None,
    }
