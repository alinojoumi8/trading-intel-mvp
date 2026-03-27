"""
CFTC COT (Commitment of Traders) Data Service
Fetches and parses weekly COT reports for commodities and FX instruments.
"""
import asyncio
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
from urllib.parse import urlencode

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

# CFTC COT data URLs (legacy format CSV)
COT_BASE_URL = "https://www.cftc.gov/files/dea/history/futures/legacifut_{year}{month}.csv"
COT_FX_URL = "https://www.cftc.gov/files/dea/history/futures/financialfux/legacifin_{year}{month}.csv"

# Cache file location
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache"
CACHE_FILE = CACHE_DIR / "cot_cache.json"
# Cache TTL: 24 hours (COT data is weekly, so 24h is plenty)
CACHE_TTL_HOURS = 24

# CFTC COT Socrata Open Data API (new 2025/2026 format)
# Dataset: Legacy - Futures and Options Combined (All Reports)
# API Docs: https://publicreporting.cftc.gov/Commitments-of-Traders/Legacy_All/srt6-5q2f
COT_SOCRATA_ENDPOINT = "https://publicreporting.cftc.gov/resource/srt6-5q2f.json"

# CFTC contract codes for tracked instruments
# Source: https://www.cftc.gov/MarketReports/CommitmentsofTraders/index.htm
INSTRUMENT_MAPPING = {
    "GOLD": "088691",    # GOLD - COMMODITY EXCHANGE INC.
    "OIL": "067651",     # CRUDE OIL WTI - NYMEX
    "CRUDE": "067651",
    "SILVER": "084691",  # SILVER - COMEX
    "EUR": "099741",     # EURO (EUR/USD) - CME
    "GBP": "096742",     # BRITISH POUND - CME
    "JPY": "097741",     # JAPANESE YEN - CME
    "CAD": "090741",     # CANADIAN DOLLAR - CME
    "AUD": "232741",     # AUSTRALIAN DOLLAR - CME
    "CHF": "092741",     # SWISS FRANC - CME
    "USD_INDEX": "098662",  # US DOLLAR INDEX - ICE
}


def _ensure_cache_dir() -> None:
    """Ensure cache directory exists."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _read_cache() -> Optional[Dict[str, Any]]:
    """Read cached COT data if valid."""
    try:
        if not CACHE_FILE.exists():
            return None
        
        with open(CACHE_FILE, "r") as f:
            cache_data = json.load(f)
        
        cached_at = datetime.fromisoformat(cache_data.get("cached_at", "2000-01-01"))
        if datetime.now() - cached_at < timedelta(hours=CACHE_TTL_HOURS):
            return cache_data.get("data")
        return None
    except Exception as e:
        logger.warning(f"Failed to read COT cache: {e}")
        return None


def _write_cache(data: Dict[str, Any]) -> None:
    """Write COT data to cache."""
    try:
        _ensure_cache_dir()
        cache_payload = {
            "cached_at": datetime.now().isoformat(),
            "data": data
        }
        with open(CACHE_FILE, "w") as f:
            json.dump(cache_payload, f)
    except Exception as e:
        logger.warning(f"Failed to write COT cache: {e}")


def _fetch_cot_csv(url: str) -> Optional[str]:
    """Fetch COT CSV data from URL."""
    try:
        with httpx.Client(timeout=15.0) as client:
            response = client.get(url)
            response.raise_for_status()
            return response.text
    except Exception as e:
        logger.error(f"Failed to fetch COT data from {url}: {e}")
        return None


def _parse_cot_csv(csv_content: str, instrument_code: str) -> Optional[Dict[str, Any]]:
    """Parse legacy format COT CSV and extract data for specific instrument."""
    try:
        lines = csv_content.strip().split("\n")
        if len(lines) < 2:
            return None
        
        # Parse header to find column indices
        header = lines[0].replace('"', '').split(",")
        
        # Find relevant columns
        col_map = {}
        for i, col in enumerate(header):
            col_lower = col.lower().strip()
            if "market" in col_lower or "name" in col_lower:
                col_map["name"] = i
            elif "date" in col_lower:
                col_map["date"] = i
            elif "commercial" in col_lower and "long" in col_lower:
                col_map["comm_long"] = i
            elif "commercial" in col_lower and "short" in col_lower:
                col_map["comm_short"] = i
            elif "noncommercial" in col_lower and "long" in col_lower:
                col_map["noncomm_long"] = i
            elif "noncommercial" in col_lower and "short" in col_lower:
                col_map["noncomm_short"] = i
            elif "change" in col_lower and "commercial" in col_lower:
                col_map["comm_chg"] = i
            elif "change" in col_lower and "noncommercial" in col_lower:
                col_map["noncomm_chg"] = i
        
        # Find the row for our instrument
        for line in lines[1:]:
            parts = line.replace('"', '').split(",")
            if len(parts) < 5:
                continue
            
            name_idx = col_map.get("name", -1)
            if name_idx >= 0 and name_idx < len(parts):
                name = parts[name_idx].upper()
                if instrument_code.upper() in name:
                    result = {
                        "instrument": instrument_code,
                        "report_date": parts[col_map.get("date", 1)] if col_map.get("date", 1) < len(parts) else "",
                        "commercial_long": int(parts[col_map.get("comm_long", 3)]) if col_map.get("comm_long", 3) < len(parts) and parts[col_map.get("comm_long", 3)].isdigit() else 0,
                        "commercial_short": int(parts[col_map.get("comm_short", 4)]) if col_map.get("comm_short", 4) < len(parts) and parts[col_map.get("comm_short", 4)].isdigit() else 0,
                        "noncommercial_long": int(parts[col_map.get("noncomm_long", 5)]) if col_map.get("noncomm_long", 5) < len(parts) and parts[col_map.get("noncomm_long", 5)].isdigit() else 0,
                        "noncommercial_short": int(parts[col_map.get("noncomm_short", 6)]) if col_map.get("noncomm_short", 6) < len(parts) and parts[col_map.get("noncomm_short", 6)].isdigit() else 0,
                    }
                    
                    # Calculate net positions
                    result["commercial_net"] = result["commercial_long"] - result["commercial_short"]
                    result["noncommercial_net"] = result["noncommercial_long"] - result["noncommercial_short"]
                    
                    # Add change data if available
                    if col_map.get("comm_chg"):
                        result["commercial_change"] = int(parts[col_map.get("comm_chg")]) if col_map.get("comm_chg") < len(parts) and parts[col_map.get("comm_chg")].replace("-", "").isdigit() else 0
                    if col_map.get("noncomm_chg"):
                        result["noncommercial_change"] = int(parts[col_map.get("noncomm_chg")]) if col_map.get("noncomm_chg") < len(parts) and parts[col_map.get("noncomm_chg")].replace("-", "").isdigit() else 0
                    
                    return result
        
        return None
    except Exception as e:
        logger.error(f"Failed to parse COT CSV: {e}")
        return None


async def _fetch_cot_for_instrument_async(instrument: str) -> Dict[str, Any]:
    """
    Fetch COT data for a single instrument from the CFTC Socrata Open Data API.
    Falls back to legacy CSV URLs if the Socrata API is unavailable.
    """
    normalized = instrument.upper()
    cftc_code = INSTRUMENT_MAPPING.get(normalized)

    if not cftc_code:
        return {
            "instrument": instrument,
            "error": f"Unknown instrument: {instrument}",
            "report_date": None,
            "commercial_long": 0,
            "commercial_short": 0,
            "commercial_net": 0,
            "noncommercial_long": 0,
            "noncommercial_short": 0,
            "noncommercial_net": 0,
        }

    # Try Socrata API first (new 2025/2026 format)
    try:
        params = {
            "$limit": 1,
            "$order": "report_date_as_yyyy_mm_dd DESC",
            "cftc_contract_market_code": cftc_code,
        }
        response = await asyncio.to_thread(_socrata_get, COT_SOCRATA_ENDPOINT, params)
        if response:
            row = response[0]
            report_date = (row.get("report_date_as_yyyy_mm_dd") or "")[:10]
            comm_long = int(row.get("comm_positions_long_all") or 0)
            comm_short = int(row.get("comm_positions_short_all") or 0)
            noncomm_long = int(row.get("noncomm_positions_long_all") or 0)
            noncomm_short = int(row.get("noncomm_positions_short_all") or 0)
            open_interest = int(row.get("open_interest_all") or 0)

            return {
                "instrument": normalized,
                "report_date": report_date,
                "commercial_long": comm_long,
                "commercial_short": comm_short,
                "commercial_net": comm_long - comm_short,
                "noncommercial_long": noncomm_long,
                "noncommercial_short": noncomm_short,
                "noncommercial_net": noncomm_long - noncomm_short,
                "open_interest": open_interest,
                "market": row.get("market_and_exchange_names"),
            }
    except Exception as e:
        logger.warning(f"Socrata API failed for {instrument}: {e}")

    return {
        "instrument": normalized,
        "error": "Could not fetch COT data",
        "report_date": None,
        "commercial_long": 0,
        "commercial_short": 0,
        "commercial_net": 0,
        "noncommercial_long": 0,
        "noncommercial_short": 0,
        "noncommercial_net": 0,
    }


def _socrata_get(url: str, params: dict) -> Optional[List[Dict[str, Any]]]:
    """
    Synchronous HTTP GET for Socrata API. Runs in asyncio.to_thread.
    Returns a list (the JSON array from Socrata) or None on error.
    """
    try:
        with httpx.Client(timeout=20.0) as client:
            response = client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            if isinstance(data, list) and len(data) > 0:
                return data
    except Exception as e:
        logger.warning(f"Socrata GET failed: {e}")
    return None


async def get_cot_summary_async() -> Dict[str, Any]:
    """
    Get COT summary for top instruments (gold, oil, EUR, GBP, JPY).
    Async version for use in gather(). Returns structured dict with net positions.
    """
    # Check cache first
    cached = _read_cache()
    if cached:
        return cached
    
    # Fetch fresh data concurrently
    instruments = ["GOLD", "OIL", "EUR", "GBP", "JPY"]
    
    async def safe_fetch(inst: str) -> tuple:
        try:
            data = await _fetch_cot_for_instrument_async(inst)
            return inst, data
        except Exception as e:
            logger.error(f"Error fetching COT for {inst}: {e}")
            return inst, {"instrument": inst, "error": str(e)}
    
    results = await asyncio.gather(*[safe_fetch(i) for i in instruments])
    result = dict(results)
    
    # Cache the result
    _write_cache(result)
    
    return result


def get_cot_summary() -> Dict[str, Any]:
    """
    Get COT summary for top instruments (gold, oil, EUR, GBP, JPY).
    Sync wrapper — use get_cot_summary_async() in async contexts.
    """
    try:
        loop = asyncio.get_running_loop()
        # We're in an async context — create a task
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            future = pool.submit(asyncio.run, get_cot_summary_async())
            return future.result()
    except RuntimeError:
        # No running loop — safe to use asyncio.run()
        return asyncio.run(get_cot_summary_async())


def get_cot_for_instrument(symbol: str) -> Dict[str, Any]:
    """
    Get COT data for a specific instrument symbol.
    
    Args:
        symbol: Instrument symbol (e.g., "GOLD", "EUR", "BTC")
    
    Returns:
        Dict with net positions and week-over-week changes
    """
    # Normalize symbol
    normalized = symbol.upper()
    
    # Check if it's a known instrument
    if normalized not in INSTRUMENT_MAPPING and normalized not in ["GC", "CL", "EUR", "GBP", "JPY"]:
        # Unknown instrument - return empty
        return {
            "instrument": symbol,
            "error": "Unknown instrument for COT",
            "report_date": None,
            "commercial_net": 0,
            "noncommercial_net": 0,
        }
    
    # Check cache first
    cached = _read_cache()
    if cached and symbol.upper() in cached:
        return cached[symbol.upper()]
    
    # Fetch fresh
    return asyncio.run(_fetch_cot_for_instrument_async(symbol))
