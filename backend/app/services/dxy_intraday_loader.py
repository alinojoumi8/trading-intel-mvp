"""
DXY 1-minute intraday data loader and reader.

Processes Dukascopy DOLLARIDXUSD bid CSV (~145 MB, 2.7M rows, 2017-2026) into
per-year Parquet files for fast random-access reads. Used by the FSM backtest
to compute precise intraday FOMC reaction windows instead of noisy 24h
close-to-close moves.

Source format (Dukascopy):
    Time (EET),Open,High,Low,Close,Volume
    2019.01.30 21:00:00,95.600,95.600,95.295,95.310,0.63370
    ^ Helsinki time (auto-DST: EET in winter / EEST in summer)

Cleaned format (Parquet, one file per year):
    Index: timestamp_utc (datetime64[ns, UTC])
    Columns: open, high, low, close, volume
    Sorted ascending by timestamp.
"""
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)


# ─── Paths ───────────────────────────────────────────────────────────────────

_DATA_DIR = Path(__file__).parent.parent.parent / "data"
RAW_CSV_DIR = _DATA_DIR / "dxy_fomc-intraday"
CLEANED_PARQUET_DIR = _DATA_DIR / "dxy_intraday" / "cleaned"


def _find_raw_csv() -> Optional[Path]:
    """Find the Dukascopy DXY CSV in the raw directory."""
    if not RAW_CSV_DIR.exists():
        return None
    csvs = list(RAW_CSV_DIR.glob("DOLLARIDXUSD*.csv"))
    if not csvs:
        return None
    return csvs[0]  # Take the first match


# ─── Loader: CSV → Parquet ───────────────────────────────────────────────────

def build_parquet_from_csv(
    csv_path: Optional[Path] = None,
    chunksize: int = 200_000,
    force: bool = False,
) -> Dict[str, Any]:
    """
    Read the Dukascopy DXY CSV and write per-year Parquet files.
    Idempotent: skips if Parquet files already exist (unless force=True).

    Returns stats: {years_written, total_rows, ...}
    """
    csv_path = csv_path or _find_raw_csv()
    if not csv_path or not csv_path.exists():
        raise FileNotFoundError(
            f"DXY raw CSV not found in {RAW_CSV_DIR}. "
            "Drop a Dukascopy DOLLARIDXUSD*.csv file there."
        )

    CLEANED_PARQUET_DIR.mkdir(parents=True, exist_ok=True)

    # Skip if already processed (unless forced)
    existing = list(CLEANED_PARQUET_DIR.glob("dxy_1m_*.parquet"))
    if existing and not force:
        logger.info(
            f"[DXY] Parquet files already exist in {CLEANED_PARQUET_DIR} "
            f"({len(existing)} years). Use force=True to rebuild."
        )
        return {"skipped": True, "existing_files": len(existing)}

    logger.info(f"[DXY] Building Parquet from {csv_path.name} (chunksize={chunksize})")

    # Buffer per year — accumulate chunks then write
    year_buffers: Dict[int, List[pd.DataFrame]] = {}
    total_rows = 0

    # Strip the trailing space in "Volume " column header (Dukascopy quirk)
    reader = pd.read_csv(
        csv_path,
        chunksize=chunksize,
        names=["time_eet", "open", "high", "low", "close", "volume"],
        header=0,
        dtype={"open": "float32", "high": "float32", "low": "float32", "close": "float32", "volume": "float32"},
    )

    for chunk_idx, chunk in enumerate(reader):
        # Parse Dukascopy timestamp format: "2019.01.30 21:00:00"
        # Localize to Europe/Helsinki (handles EET/EEST DST transitions)
        chunk["time_eet"] = pd.to_datetime(chunk["time_eet"], format="%Y.%m.%d %H:%M:%S")
        chunk["time_eet"] = chunk["time_eet"].dt.tz_localize(
            "Europe/Helsinki",
            ambiguous="NaT",       # Drop the 1 ambiguous hour at fall-back DST
            nonexistent="shift_forward",  # Shift the missing hour at spring-forward DST
        )
        chunk["timestamp_utc"] = chunk["time_eet"].dt.tz_convert("UTC")
        chunk = chunk.dropna(subset=["timestamp_utc"])
        chunk = chunk.drop(columns=["time_eet"])

        # Bucket by year
        years = chunk["timestamp_utc"].dt.year.unique()
        for year in years:
            year_chunk = chunk[chunk["timestamp_utc"].dt.year == year]
            year_buffers.setdefault(int(year), []).append(year_chunk)

        total_rows += len(chunk)
        if chunk_idx % 5 == 0:
            logger.info(f"[DXY] Processed chunk {chunk_idx}, total rows so far: {total_rows:,}")

    # Write each year's buffer to Parquet
    years_written = []
    for year, chunks in sorted(year_buffers.items()):
        df = pd.concat(chunks, ignore_index=True)
        df = df.sort_values("timestamp_utc").drop_duplicates(subset=["timestamp_utc"])
        df = df.set_index("timestamp_utc")
        out_path = CLEANED_PARQUET_DIR / f"dxy_1m_{year}.parquet"
        df.to_parquet(out_path, compression="snappy")
        size_mb = out_path.stat().st_size / 1024 / 1024
        logger.info(f"[DXY] Wrote {out_path.name}: {len(df):,} rows, {size_mb:.1f} MB")
        years_written.append(year)

    return {
        "skipped": False,
        "csv_path": str(csv_path),
        "total_rows": total_rows,
        "years_written": years_written,
        "parquet_dir": str(CLEANED_PARQUET_DIR),
    }


# ─── Reader: Parquet → DataFrame for a date range ────────────────────────────

_year_cache: Dict[int, pd.DataFrame] = {}


def load_dxy_year(year: int) -> Optional[pd.DataFrame]:
    """
    Load a single year of DXY 1-minute data from Parquet.
    Cached in process memory after first load.
    Returns None if the year's Parquet file doesn't exist.
    """
    if year in _year_cache:
        return _year_cache[year]

    path = CLEANED_PARQUET_DIR / f"dxy_1m_{year}.parquet"
    if not path.exists():
        return None

    df = pd.read_parquet(path)
    # Ensure index is UTC-aware datetime
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    _year_cache[year] = df
    return df


def get_intraday_window(
    start_utc: datetime,
    end_utc: datetime,
) -> pd.DataFrame:
    """
    Return DXY 1-minute bars between two UTC timestamps (inclusive start, exclusive end).
    Spans years if needed. Empty DataFrame if no data available.
    """
    # Make timestamps tz-aware UTC
    if start_utc.tzinfo is None:
        start_utc = start_utc.replace(tzinfo=pd.Timestamp.utcnow().tz)
    if end_utc.tzinfo is None:
        end_utc = end_utc.replace(tzinfo=pd.Timestamp.utcnow().tz)

    # Load all needed years
    years_needed = list(range(start_utc.year, end_utc.year + 1))
    frames = []
    for year in years_needed:
        df = load_dxy_year(year)
        if df is not None:
            frames.append(df)

    if not frames:
        return pd.DataFrame()

    full = pd.concat(frames) if len(frames) > 1 else frames[0]
    return full[(full.index >= start_utc) & (full.index < end_utc)]


# ─── FOMC Reaction Computation ───────────────────────────────────────────────

def fomc_release_utc(date_str: str) -> datetime:
    """
    Get the UTC timestamp of the FOMC statement release for a given date.
    FOMC statements are released at 2:00 PM ET (DST-aware: EST in winter, EDT in summer).

    Args:
        date_str: YYYY-MM-DD format

    Returns:
        UTC datetime of the 2:00 PM ET release
    """
    # 2:00 PM in America/New_York timezone, then convert to UTC
    ny_dt = pd.Timestamp(f"{date_str} 14:00:00", tz="America/New_York")
    return ny_dt.tz_convert("UTC").to_pydatetime()


def compute_fomc_reaction_windows(date_str: str) -> Dict[str, Any]:
    """
    Compute multiple intraday DXY reaction windows for an FOMC event.

    Returns a dict with:
        - release_time_utc: when the statement dropped
        - baseline_close: DXY close at T-1 minute (last bar before release)
        - windows: dict of window_label → {close, pct_move}
            * "1m":   1 minute after release
            * "10m":  10 minutes after release (initial reaction)
            * "30m":  30 minutes after release (statement digested)
            * "90m":  90 minutes after release (post-press-conference)
            * "120m": 2 hours after release (full reaction window)
        - direction: USD_bullish / USD_bearish / neutral based on 30m window
        - available: True if data was loaded
    """
    release_time = fomc_release_utc(date_str)

    # Pull a wide window around the release: 5 min before, 3 hours after
    start = release_time - timedelta(minutes=5)
    end = release_time + timedelta(hours=3)

    bars = get_intraday_window(start, end)
    if bars.empty:
        return {
            "available": False,
            "release_time_utc": release_time.isoformat(),
            "reason": "No intraday data available for this date",
        }

    # Find the bar at or just before release_time as baseline
    pre_release = bars[bars.index < release_time]
    if pre_release.empty:
        return {
            "available": False,
            "release_time_utc": release_time.isoformat(),
            "reason": "No pre-release bars found",
        }
    baseline_close = float(pre_release.iloc[-1]["close"])
    baseline_time = pre_release.index[-1]

    # Compute each window
    window_minutes = [1, 10, 30, 90, 120]
    windows = {}
    for mins in window_minutes:
        target_time = release_time + timedelta(minutes=mins)
        # Find the bar at or just before target_time
        in_window = bars[bars.index <= target_time]
        if in_window.empty or in_window.index[-1] < release_time:
            windows[f"{mins}m"] = {"close": None, "pct_move": None, "available": False}
            continue
        close = float(in_window.iloc[-1]["close"])
        pct = (close - baseline_close) / baseline_close * 100
        windows[f"{mins}m"] = {
            "close": round(close, 4),
            "pct_move": round(pct, 4),
            "actual_time": in_window.index[-1].isoformat(),
            "available": True,
        }

    # Use 30m window as the primary direction signal (statement digested, before press conf dominates)
    primary_pct = windows["30m"].get("pct_move")
    if primary_pct is None:
        direction = "neutral"
    elif primary_pct > 0.10:  # Tighter threshold than daily (0.15)
        direction = "USD_bullish"
    elif primary_pct < -0.10:
        direction = "USD_bearish"
    else:
        direction = "neutral"

    return {
        "available": True,
        "release_time_utc": release_time.isoformat(),
        "baseline_time_utc": baseline_time.isoformat(),
        "baseline_close": round(baseline_close, 4),
        "windows": windows,
        "direction_30m": direction,
        "bars_loaded": len(bars),
    }
