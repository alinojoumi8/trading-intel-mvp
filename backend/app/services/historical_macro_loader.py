"""
Historical FRED macro data loader with point-in-time correctness.

For honest backtesting we need to know "what value was publicly known on
date X" — not the latest revised value. FRED's API supports this via
`get_series_all_releases()` which returns every vintage (publication) of
every observation.

We pull all vintages once and store as Parquet:
    data/macro_history/fred_{series_id}.parquet

Each row: (observation_date, realtime_date, value)
  - observation_date: the period the data refers to (e.g., 2022-01-01 for Jan CPI)
  - realtime_date: when this value was published/revised by BLS or BEA
  - value: the number

At backtest time, `get_value_as_of(series_id, as_of_date)` returns the
most recent observation that was publicly known on as_of_date.
"""
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from app.core.config import settings

logger = logging.getLogger(__name__)


_DATA_DIR = Path(__file__).parent.parent.parent / "data"
MACRO_DIR = _DATA_DIR / "macro_history"


# ─── FRED series catalog ─────────────────────────────────────────────────────

# Series ID → friendly name + frequency
FRED_SERIES: Dict[str, Dict[str, str]] = {
    # Growth
    "GDPC1":         {"name": "Real GDP",                    "freq": "Q"},
    "INDPRO":        {"name": "Industrial Production",       "freq": "M"},
    # Inflation
    "CPIAUCSL":      {"name": "CPI All Items",               "freq": "M"},
    "PCEPI":         {"name": "PCE Price Index",             "freq": "M"},
    "PCEPILFE":      {"name": "Core PCE",                    "freq": "M"},
    # Labor
    "UNRATE":        {"name": "Unemployment Rate",           "freq": "M"},
    "PAYEMS":        {"name": "Nonfarm Payrolls",            "freq": "M"},
    "CES0500000003": {"name": "Avg Hourly Earnings",         "freq": "M"},
    # Sentiment / Activity
    "UMCSENT":       {"name": "Consumer Sentiment",          "freq": "M"},
    "USSLIND":       {"name": "Leading Index",               "freq": "M"},
    "CFNAI":         {"name": "Chicago Fed National Activity Index (ISM Mfg proxy)", "freq": "M"},
    "IPMAN":         {"name": "Industrial Production: Manufacturing (ISM proxy)",    "freq": "M"},
    "DGORDER":       {"name": "Durable Goods Orders",        "freq": "M"},
    "RSAFS":         {"name": "Retail Sales",                "freq": "M"},
    # Rates / Markets
    "DFF":           {"name": "Fed Funds Rate (Effective)",  "freq": "D"},
    "FEDFUNDS":      {"name": "Fed Funds Rate (Monthly)",    "freq": "M"},
    "DGS2":          {"name": "2Y Treasury",                 "freq": "D"},
    "DGS10":         {"name": "10Y Treasury",                "freq": "D"},
    "T10Y2Y":        {"name": "10Y-2Y Spread",               "freq": "D"},
    "DTWEXBGS":      {"name": "DXY (Broad USD)",             "freq": "D"},
}


def _get_fred():
    """Get a Fred client instance."""
    if not settings.FRED_API_KEY:
        raise RuntimeError("FRED_API_KEY not configured")
    from fredapi import Fred
    return Fred(api_key=settings.FRED_API_KEY)


# ─── Backfill: FRED → Parquet ────────────────────────────────────────────────

def backfill_fred_series(
    series_id: str,
    start_date: str = "2010-01-01",
    force: bool = False,
) -> Dict[str, Any]:
    """
    Pull all historical vintages of one FRED series and store as Parquet.

    Args:
        series_id: FRED series identifier (e.g. "CPIAUCSL")
        start_date: Earliest observation date to fetch (YYYY-MM-DD)
        force: Re-download even if Parquet exists

    Returns: {series_id, rows, observations, vintages, date_range, path}
    """
    MACRO_DIR.mkdir(parents=True, exist_ok=True)
    out_path = MACRO_DIR / f"fred_{series_id}.parquet"

    if out_path.exists() and not force:
        existing = pd.read_parquet(out_path)
        return {
            "series_id": series_id,
            "skipped": True,
            "rows": len(existing),
        }

    fred = _get_fred()

    # Fetch all vintages. Using get_series_all_releases() returns a DataFrame
    # with columns [date (observation), realtime_start, value]
    try:
        df = fred.get_series_all_releases(series_id, realtime_start=start_date)
    except Exception as e:
        logger.warning(f"[MACRO] {series_id}: get_series_all_releases failed ({e}), falling back to current vintage only")
        # Fallback: just the latest observations (no vintage history).
        # Daily rates (DFF, DGS2, DGS10, T10Y2Y) typically aren't revised, so we
        # set realtime_date = observation_date + 1 day (next business day publish).
        try:
            current = fred.get_series(series_id, observation_start=start_date)
            obs_dates = pd.to_datetime(current.index)
            # Treat each daily observation as published the next calendar day
            realtime_dates = obs_dates + pd.Timedelta(days=1)
            df = pd.DataFrame({
                "date": obs_dates,
                "realtime_start": realtime_dates,
                "value": current.values,
            })
        except Exception as e2:
            logger.error(f"[MACRO] {series_id}: also failed: {e2}")
            return {"series_id": series_id, "error": str(e2)}

    if df is None or df.empty:
        return {"series_id": series_id, "error": "no data"}

    # Normalize columns
    df = df.rename(columns={"date": "observation_date", "realtime_start": "realtime_date"})
    df["observation_date"] = pd.to_datetime(df["observation_date"])
    df["realtime_date"] = pd.to_datetime(df["realtime_date"])
    df = df.dropna(subset=["value"])
    df = df.sort_values(["observation_date", "realtime_date"])

    df.to_parquet(out_path, compression="snappy")

    obs_count = df["observation_date"].nunique()
    vintage_count = len(df)
    date_range = (str(df["observation_date"].min().date()), str(df["observation_date"].max().date()))
    size_kb = out_path.stat().st_size / 1024

    logger.info(
        f"[MACRO] {series_id}: {obs_count} observations × ~{vintage_count // max(obs_count, 1)} vintages = "
        f"{vintage_count} rows ({date_range[0]} to {date_range[1]}, {size_kb:.0f} KB)"
    )

    return {
        "series_id": series_id,
        "skipped": False,
        "rows": vintage_count,
        "observations": obs_count,
        "date_range": date_range,
        "path": str(out_path),
    }


def backfill_all_fred_series(
    start_date: str = "2010-01-01",
    force: bool = False,
) -> Dict[str, Any]:
    """Backfill every series in the FRED_SERIES catalog."""
    results = {}
    for sid in FRED_SERIES:
        try:
            results[sid] = backfill_fred_series(sid, start_date=start_date, force=force)
        except Exception as e:
            logger.exception(f"[MACRO] {sid}: backfill failed")
            results[sid] = {"series_id": sid, "error": str(e)}
    return results


# ─── Reader: point-in-time queries ───────────────────────────────────────────

_series_cache: Dict[str, pd.DataFrame] = {}


def load_series(series_id: str) -> Optional[pd.DataFrame]:
    """Load one FRED series into memory (cached)."""
    if series_id in _series_cache:
        return _series_cache[series_id]
    path = MACRO_DIR / f"fred_{series_id}.parquet"
    if not path.exists():
        return None
    df = pd.read_parquet(path)
    _series_cache[series_id] = df
    return df


def get_value_as_of(series_id: str, as_of: datetime) -> Optional[Dict[str, Any]]:
    """
    Return the most recent value for `series_id` that was publicly known
    as of `as_of` date. Uses point-in-time vintages so there's no look-ahead.

    Returns a dict with {value, observation_date, realtime_date} or None.
    """
    df = load_series(series_id)
    if df is None or df.empty:
        return None

    target = pd.Timestamp(as_of.date()) if hasattr(as_of, "date") else pd.Timestamp(as_of)

    # Filter to vintages published BEFORE as_of date
    available = df[df["realtime_date"] <= target]
    if available.empty:
        return None

    # For each observation_date, take the most recent realtime version
    latest_per_obs = (
        available.sort_values("realtime_date")
        .groupby("observation_date")
        .last()
        .reset_index()
    )
    # Then take the most recent observation
    latest_per_obs = latest_per_obs.sort_values("observation_date")
    latest_row = latest_per_obs.iloc[-1]

    return {
        "value": float(latest_row["value"]),
        "observation_date": str(latest_row["observation_date"].date()),
        "realtime_date": str(latest_row["realtime_date"].date()),
    }


def get_series_history_as_of(
    series_id: str,
    as_of: datetime,
    limit: int = 12,
) -> List[Dict[str, Any]]:
    """
    Return the last N values that were publicly known as of `as_of`.
    Useful for computing rate-of-change: latest value vs prior value.
    """
    df = load_series(series_id)
    if df is None or df.empty:
        return []

    target = pd.Timestamp(as_of.date()) if hasattr(as_of, "date") else pd.Timestamp(as_of)
    available = df[df["realtime_date"] <= target]
    if available.empty:
        return []

    latest_per_obs = (
        available.sort_values("realtime_date")
        .groupby("observation_date")
        .last()
        .reset_index()
        .sort_values("observation_date")
    )
    tail = latest_per_obs.tail(limit)
    return [
        {
            "value": float(r["value"]),
            "observation_date": str(r["observation_date"].date()),
            "realtime_date": str(r["realtime_date"].date()),
        }
        for _, r in tail.iterrows()
    ]


def get_value_with_roc(series_id: str, as_of: datetime) -> Dict[str, Any]:
    """
    Return latest + prior value + rate of change as of a date.
    Mirrors `fetch_fred_series_with_roc()` shape used by signals_data_fetcher.
    """
    history = get_series_history_as_of(series_id, as_of, limit=2)
    if not history:
        return {"latest": "N/A", "prior": "N/A", "roc_pct": "N/A", "direction": "UNKNOWN"}

    latest = history[-1]["value"]
    if len(history) < 2:
        return {"latest": round(latest, 4), "prior": "N/A", "roc_pct": "N/A", "direction": "UNKNOWN"}

    prior = history[-2]["value"]
    roc_pct = (latest - prior) / prior * 100 if prior != 0 else 0.0

    if abs(roc_pct) < 0.1:
        direction = "FLAT"
    elif roc_pct > 0:
        direction = "ACCELERATING" if roc_pct > 1 else "RISING"
    else:
        direction = "DECELERATING" if roc_pct < -1 else "FALLING"

    return {
        "latest": round(latest, 4),
        "prior": round(prior, 4),
        "roc_pct": round(roc_pct, 3),
        "direction": direction,
        "observation_date": history[-1]["observation_date"],
    }
