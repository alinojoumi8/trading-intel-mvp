"""
Generic Dukascopy 1-minute intraday data loader.

Handles any Dukascopy CSV with the format:
    Time (EET),Open,High,Low,Close,Volume
    2019.01.30 21:00:00,95.600,95.600,95.295,95.310,0.63370

Stores cleaned data as per-symbol/per-year Parquet files in:
    backend/data/intraday/cleaned/{symbol}/{symbol}_1m_{year}.parquet

Each symbol has its own subdirectory so we can store many instruments without
collision. Per-year files keep individual loads small (~5 MB each) and allow
fast random-access reads for backtest scenarios.

The DXY loader (`dxy_intraday_loader.py`) is now a thin wrapper around this
module — kept for backwards compatibility with the FSM backtest.
"""
import logging
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

logger = logging.getLogger(__name__)


# ─── Paths ───────────────────────────────────────────────────────────────────

_DATA_DIR = Path(__file__).parent.parent.parent / "data"
RAW_DIR = _DATA_DIR  # raw CSVs sit at the top level of /data
CLEANED_DIR = _DATA_DIR / "intraday" / "cleaned"


# ─── Symbol catalog ──────────────────────────────────────────────────────────

# Maps the V3 pipeline asset name → Dukascopy CSV filename prefix.
# When we add more symbols, just extend this map.
SYMBOL_CATALOG: Dict[str, str] = {
    "EURUSD": "EURUSD",
    "GBPUSD": "GBPUSD",
    "USDJPY": "USDJPY",
    "XAUUSD": "XAUUSD",       # Gold
    "USA500": "USA500IDXUSD",  # S&P 500 index
    "NAS100": "USATECHIDXUSD", # Nasdaq 100 index
    "DXY":    "DOLLARIDXUSD", # Already loaded by dxy_intraday_loader
}

# Reverse lookup: Dukascopy prefix → canonical asset name
_PREFIX_TO_ASSET = {v: k for k, v in SYMBOL_CATALOG.items()}


def _find_raw_csv(symbol: str) -> Optional[Path]:
    """
    Find the Dukascopy CSV for a given canonical symbol.
    Searches the data dir for files matching `{prefix}_*Min*.csv`.
    """
    prefix = SYMBOL_CATALOG.get(symbol)
    if not prefix:
        return None

    # Search in RAW_DIR and any subdirectories
    candidates = []
    for f in RAW_DIR.rglob(f"{prefix}_*.csv"):
        # Skip the cleaned dir
        if "cleaned" in str(f):
            continue
        candidates.append(f)

    if not candidates:
        return None
    # Prefer the one with the longest date range in its name
    candidates.sort(key=lambda p: p.stat().st_size, reverse=True)
    return candidates[0]


# ─── Loader: CSV → Parquet ───────────────────────────────────────────────────

def build_parquet_for_symbol(
    symbol: str,
    csv_path: Optional[Path] = None,
    chunksize: int = 200_000,
    force: bool = False,
) -> Dict[str, Any]:
    """
    Read a Dukascopy CSV for one symbol and write per-year Parquet files.
    Idempotent: skips if Parquet files already exist for this symbol.

    Args:
        symbol: Canonical asset name (e.g., "EURUSD") — must be in SYMBOL_CATALOG
        csv_path: Optional explicit path; otherwise auto-discover from RAW_DIR
        chunksize: Rows per chunk when reading the CSV
        force: Rebuild even if Parquet files already exist

    Returns:
        {symbol, total_rows, years_written, parquet_dir, skipped}
    """
    if symbol not in SYMBOL_CATALOG:
        raise ValueError(
            f"Unknown symbol '{symbol}'. Add it to SYMBOL_CATALOG with its "
            f"Dukascopy prefix."
        )

    csv_path = csv_path or _find_raw_csv(symbol)
    if not csv_path or not csv_path.exists():
        raise FileNotFoundError(
            f"No raw CSV found for {symbol} in {RAW_DIR}. "
            f"Expected pattern: {SYMBOL_CATALOG[symbol]}*.csv"
        )

    symbol_dir = CLEANED_DIR / symbol
    symbol_dir.mkdir(parents=True, exist_ok=True)

    # Skip if already processed
    existing = list(symbol_dir.glob(f"{symbol}_1m_*.parquet"))
    if existing and not force:
        logger.info(
            f"[INTRADAY] {symbol}: Parquet already exists ({len(existing)} years). "
            f"Use force=True to rebuild."
        )
        return {"symbol": symbol, "skipped": True, "existing_files": len(existing)}

    logger.info(f"[INTRADAY] {symbol}: Building from {csv_path.name}")
    file_size_mb = csv_path.stat().st_size / 1024 / 1024
    logger.info(f"[INTRADAY] {symbol}: CSV size {file_size_mb:.1f} MB")

    year_buffers: Dict[int, List[pd.DataFrame]] = {}
    total_rows = 0

    reader = pd.read_csv(
        csv_path,
        chunksize=chunksize,
        names=["time_eet", "open", "high", "low", "close", "volume"],
        header=0,
        dtype={
            "open": "float32", "high": "float32", "low": "float32",
            "close": "float32", "volume": "float32",
        },
    )

    for chunk_idx, chunk in enumerate(reader):
        # Parse Dukascopy timestamp format: "2019.01.30 21:00:00"
        chunk["time_eet"] = pd.to_datetime(chunk["time_eet"], format="%Y.%m.%d %H:%M:%S")
        # Localize to Helsinki (auto-handles EET/EEST DST), then convert to UTC
        chunk["time_eet"] = chunk["time_eet"].dt.tz_localize(
            "Europe/Helsinki",
            ambiguous="NaT",
            nonexistent="shift_forward",
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
        if chunk_idx % 10 == 0:
            logger.info(f"[INTRADAY] {symbol}: chunk {chunk_idx}, rows so far: {total_rows:,}")

    # Write each year's buffer to Parquet
    years_written = []
    for year, chunks in sorted(year_buffers.items()):
        df = pd.concat(chunks, ignore_index=True)
        df = df.sort_values("timestamp_utc").drop_duplicates(subset=["timestamp_utc"])
        df = df.set_index("timestamp_utc")
        out_path = symbol_dir / f"{symbol}_1m_{year}.parquet"
        df.to_parquet(out_path, compression="snappy")
        size_mb = out_path.stat().st_size / 1024 / 1024
        logger.info(f"[INTRADAY] {symbol}: wrote {out_path.name}: {len(df):,} rows, {size_mb:.1f} MB")
        years_written.append(year)

    return {
        "symbol": symbol,
        "skipped": False,
        "csv_path": str(csv_path),
        "total_rows": total_rows,
        "years_written": years_written,
        "parquet_dir": str(symbol_dir),
    }


def build_parquet_for_all_symbols(force: bool = False) -> Dict[str, Any]:
    """
    Convert every symbol in SYMBOL_CATALOG that has a raw CSV available.
    Skips symbols whose CSV is missing (logs a warning).
    """
    results = {}
    for symbol in SYMBOL_CATALOG:
        try:
            results[symbol] = build_parquet_for_symbol(symbol, force=force)
        except FileNotFoundError as e:
            logger.warning(f"[INTRADAY] {symbol}: skipping — {e}")
            results[symbol] = {"symbol": symbol, "error": "csv_not_found"}
        except Exception as e:
            logger.exception(f"[INTRADAY] {symbol}: build failed")
            results[symbol] = {"symbol": symbol, "error": str(e)}
    return results


# ─── Reader: Parquet → DataFrame for a date range ────────────────────────────

# Process-level cache: {(symbol, year): DataFrame}
_year_cache: Dict[Tuple[str, int], pd.DataFrame] = {}


def load_year(symbol: str, year: int) -> Optional[pd.DataFrame]:
    """
    Load one year of 1-minute bars for a symbol from Parquet.
    Returns None if the file doesn't exist.
    Cached in process memory after first load.
    """
    cache_key = (symbol, year)
    if cache_key in _year_cache:
        return _year_cache[cache_key]

    path = CLEANED_DIR / symbol / f"{symbol}_1m_{year}.parquet"
    if not path.exists():
        return None

    df = pd.read_parquet(path)
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    _year_cache[cache_key] = df
    return df


def get_window(
    symbol: str,
    start_utc: datetime,
    end_utc: datetime,
) -> pd.DataFrame:
    """
    Return 1-minute OHLCV bars for a symbol between two UTC timestamps.
    Spans years if needed. Empty DataFrame if no data available.
    """
    if start_utc.tzinfo is None:
        start_utc = start_utc.replace(tzinfo=pd.Timestamp.utcnow().tz)
    if end_utc.tzinfo is None:
        end_utc = end_utc.replace(tzinfo=pd.Timestamp.utcnow().tz)

    years_needed = list(range(start_utc.year, end_utc.year + 1))
    frames = []
    for year in years_needed:
        df = load_year(symbol, year)
        if df is not None:
            frames.append(df)

    if not frames:
        return pd.DataFrame()

    full = pd.concat(frames) if len(frames) > 1 else frames[0]
    return full[(full.index >= start_utc) & (full.index < end_utc)]


def get_bar_at(symbol: str, ts_utc: datetime) -> Optional[pd.Series]:
    """
    Get the 1-minute bar at a specific UTC timestamp (or the most recent
    bar before it if exact match is missing).
    """
    df = load_year(symbol, ts_utc.year)
    if df is None:
        return None
    if ts_utc.tzinfo is None:
        ts_utc = ts_utc.replace(tzinfo=df.index.tz)
    in_window = df[df.index <= ts_utc]
    if in_window.empty:
        return None
    return in_window.iloc[-1]


def get_available_symbols() -> List[str]:
    """List symbols that have at least one Parquet year file built."""
    if not CLEANED_DIR.exists():
        return []
    return sorted([d.name for d in CLEANED_DIR.iterdir() if d.is_dir()])


def get_symbol_coverage(symbol: str) -> Dict[str, Any]:
    """Return date range coverage stats for a symbol."""
    symbol_dir = CLEANED_DIR / symbol
    if not symbol_dir.exists():
        return {"symbol": symbol, "available": False}
    files = sorted(symbol_dir.glob(f"{symbol}_1m_*.parquet"))
    if not files:
        return {"symbol": symbol, "available": False}

    years = []
    total_rows = 0
    for f in files:
        match = re.search(r"_(\d{4})\.parquet$", f.name)
        if match:
            years.append(int(match.group(1)))
    if not years:
        return {"symbol": symbol, "available": False}

    # Quick row count from each file (cheap with parquet metadata)
    import pyarrow.parquet as pq
    for f in files:
        try:
            total_rows += pq.read_metadata(f).num_rows
        except Exception:
            pass

    return {
        "symbol": symbol,
        "available": True,
        "year_range": (min(years), max(years)),
        "years_count": len(years),
        "total_bars": total_rows,
        "files": len(files),
    }
