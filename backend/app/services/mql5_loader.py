"""
MQL5 Economic Calendar data loader.

Downloads and caches ISM Manufacturing PMI, ISM Non-Manufacturing PMI,
and other MQL5-hosted indicators as Parquet files for point-in-time
backtesting.

MQL5 export URL pattern:
    https://www.mql5.com/en/economic-calendar/united-states/{slug}/export

Export format: Tab-separated, columns:
    Date (YYYY.MM.DD)   — the release date (when data became publicly known)
    ActualValue         — the published reading
    ForecastValue       — analyst consensus before release
    PreviousValue       — prior month's reading

Parquet schema (matches historical_macro_loader.py for API consistency):
    observation_date    datetime64[ns, UTC]   release date
    realtime_date       datetime64[ns, UTC]   same as observation_date
    value               float64               ActualValue
    forecast            float64               ForecastValue
    previous            float64               PreviousValue

Usage:
    from app.services.mql5_loader import backfill_mql5_series, get_mql5_value_as_of

    backfill_mql5_series("ism-manufacturing-pmi")
    result = get_mql5_value_as_of("ism-manufacturing-pmi", datetime(2020, 6, 1))
    # → {"value": 43.1, "observation_date": "2020-06-01", "forecast": 43.5, "previous": 41.5}
"""
import logging
from datetime import datetime
from io import StringIO
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import requests

logger = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).parent.parent.parent / "data"
MACRO_DIR = _DATA_DIR / "macro_history"

BASE_URL = "https://www.mql5.com/en/economic-calendar/united-states/{slug}/export"

# Supported slugs — extend as needed
MQL5_SERIES: Dict[str, str] = {
    "ism-manufacturing-pmi": "ISM Manufacturing PMI",
    "ism-non-manufacturing-pmi": "ISM Non-Manufacturing (Services) PMI",
    "ism-manufacturing-employment": "ISM Manufacturing Employment",
}

# Module-level in-memory cache (slug → DataFrame)
_cache: Dict[str, pd.DataFrame] = {}


# ─── Storage helpers ──────────────────────────────────────────────────────────

def _parquet_path(slug: str) -> Path:
    return MACRO_DIR / f"mql5_{slug}.parquet"


def _load_cached(slug: str) -> Optional[pd.DataFrame]:
    """Return DataFrame from memory cache, then disk, or None."""
    if slug in _cache:
        return _cache[slug]
    path = _parquet_path(slug)
    if not path.exists():
        return None
    try:
        df = pd.read_parquet(path)
        _cache[slug] = df
        return df
    except Exception as e:
        logger.warning(f"[MQL5] Failed to read parquet for {slug}: {e}")
        return None


# ─── Download & Parse ─────────────────────────────────────────────────────────

def _fetch_tsv(slug: str) -> Optional[pd.DataFrame]:
    """
    Download TSV from MQL5 export endpoint and return a clean DataFrame.

    Returns None on any network or parse failure.
    """
    url = BASE_URL.format(slug=slug)
    try:
        resp = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
    except requests.RequestException as e:
        logger.error(f"[MQL5] Download failed for {slug}: {e}")
        return None

    text = resp.text.strip()
    if not text:
        logger.error(f"[MQL5] Empty response for {slug}")
        return None

    try:
        df = pd.read_csv(
            StringIO(text),
            sep="\t",
            header=0,
            names=["date_raw", "value", "forecast", "previous"],
            dtype=str,
        )
    except Exception as e:
        logger.error(f"[MQL5] TSV parse failed for {slug}: {e}")
        return None

    # Parse dates — MQL5 uses YYYY.MM.DD format
    df["observation_date"] = pd.to_datetime(df["date_raw"], format="%Y.%m.%d", errors="coerce", utc=True)
    df["realtime_date"] = df["observation_date"]  # release date IS the known date

    # Numeric columns — coerce empties to NaN
    for col in ("value", "forecast", "previous"):
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Drop rows where observation_date or value could not be parsed
    df = df.dropna(subset=["observation_date", "value"]).copy()

    df = df[["observation_date", "realtime_date", "value", "forecast", "previous"]]
    df = df.sort_values("observation_date").reset_index(drop=True)

    logger.info(f"[MQL5] Fetched {len(df)} rows for {slug} "
                f"({df['observation_date'].iloc[0].date()} → {df['observation_date'].iloc[-1].date()})")
    return df


# ─── Public API ───────────────────────────────────────────────────────────────

def backfill_mql5_series(slug: str, force: bool = False) -> Dict[str, Any]:
    """
    Download and persist a MQL5 series to Parquet.

    Idempotent — skips download if file already exists unless force=True.

    Returns: {"slug": slug, "rows": int, "path": str, "status": "ok"|"skipped"|"error"}
    """
    path = _parquet_path(slug)
    MACRO_DIR.mkdir(parents=True, exist_ok=True)

    if path.exists() and not force:
        logger.info(f"[MQL5] Parquet already exists for {slug}, skipping (use force=True to re-download)")
        existing = _load_cached(slug)
        rows = len(existing) if existing is not None else 0
        return {"slug": slug, "rows": rows, "path": str(path), "status": "skipped"}

    df = _fetch_tsv(slug)
    if df is None or df.empty:
        return {"slug": slug, "rows": 0, "path": str(path), "status": "error"}

    df.to_parquet(path, compression="snappy", index=False)
    _cache[slug] = df
    logger.info(f"[MQL5] Saved {len(df)} rows → {path}")
    return {"slug": slug, "rows": len(df), "path": str(path), "status": "ok"}


def backfill_all(force: bool = False) -> List[Dict[str, Any]]:
    """Backfill all known MQL5 series. Returns a list of result dicts."""
    return [backfill_mql5_series(slug, force=force) for slug in MQL5_SERIES]


def get_mql5_value_as_of(slug: str, as_of: datetime) -> Optional[Dict[str, Any]]:
    """
    Return the most recent MQL5 reading publicly known on or before `as_of`.

    Uses realtime_date (= release date) for point-in-time correctness.

    Returns:
        {value, forecast, previous, observation_date} or None if no data.
    """
    df = _load_cached(slug)
    if df is None or df.empty:
        return None

    # Normalise as_of to UTC-aware for comparison
    if as_of.tzinfo is None:
        as_of_ts = pd.Timestamp(as_of, tz="UTC")
    else:
        as_of_ts = pd.Timestamp(as_of).tz_convert("UTC")

    mask = df["realtime_date"] <= as_of_ts
    filtered = df[mask]
    if filtered.empty:
        return None

    row = filtered.iloc[-1]
    return {
        "value": float(row["value"]),
        "forecast": float(row["forecast"]) if pd.notna(row["forecast"]) else None,
        "previous": float(row["previous"]) if pd.notna(row["previous"]) else None,
        "observation_date": row["observation_date"].isoformat(),
    }


def get_mql5_value_with_roc(slug: str, as_of: datetime) -> Dict[str, Any]:
    """
    Return value + rate-of-change vs prior reading.

    Mirrors the shape of `get_value_with_roc()` from historical_macro_loader.py:
        {latest, prior, roc_pct, direction, observation_date}

    Direction thresholds (PMI points, not %):
        |delta| < 0.2  → FLAT
        delta > 1.0    → ACCELERATING
        delta > 0      → RISING
        delta < -1.0   → DECELERATING
        delta < 0      → FALLING
    """
    df = _load_cached(slug)
    if df is None or df.empty:
        return {"latest": None, "prior": None, "roc_pct": None, "direction": "UNKNOWN", "observation_date": None}

    if as_of.tzinfo is None:
        as_of_ts = pd.Timestamp(as_of, tz="UTC")
    else:
        as_of_ts = pd.Timestamp(as_of).tz_convert("UTC")

    mask = df["realtime_date"] <= as_of_ts
    filtered = df[mask]
    if filtered.empty:
        return {"latest": None, "prior": None, "roc_pct": None, "direction": "UNKNOWN", "observation_date": None}

    latest_row = filtered.iloc[-1]
    latest_val = float(latest_row["value"])
    obs_date = latest_row["observation_date"].isoformat()

    prior_val = None
    direction = "UNKNOWN"
    roc_pct = None

    if len(filtered) >= 2:
        prior_row = filtered.iloc[-2]
        prior_val = float(prior_row["value"])
        delta = latest_val - prior_val
        roc_pct = round(delta, 2)  # PMI points delta (not %)

        if abs(delta) < 0.2:
            direction = "FLAT"
        elif delta > 1.0:
            direction = "ACCELERATING"
        elif delta > 0:
            direction = "RISING"
        elif delta < -1.0:
            direction = "DECELERATING"
        else:
            direction = "FALLING"

    return {
        "latest": latest_val,
        "prior": prior_val,
        "roc_pct": roc_pct,
        "direction": direction,
        "observation_date": obs_date,
    }
