"""
FX Correlation Matrix Router
Calculates and returns correlation matrices for currency pairs and commodities.
"""
from datetime import datetime
from typing import Dict, List, Tuple

from fastapi import APIRouter, Query
from pydantic import BaseModel

import yfinance as yf
import pandas as pd
import numpy as np

router = APIRouter(prefix="/correlation", tags=["correlation"])


class CorrelationResponse(BaseModel):
    instruments: List[str]
    matrix: List[List[float]]
    timeframe: str
    computed_at: datetime
    strongest_positive: Tuple[str, str, float]
    strongest_negative: Tuple[str, str, float]


# Map display names to yfinance tickers
INSTRUMENT_TO_TICKER: Dict[str, str] = {
    "EURUSD": "EURUSD=X",
    "GBPUSD": "GBPUSD=X",
    "USDJPY": "USDJPY=X",
    "AUDUSD": "AUDUSD=X",
    "USDCAD": "USDCAD=X",
    "NZDUSD": "NZDUSD=X",
    "XAUUSD": "GC=F",  # Gold Futures
    "XAGUSD": "SI=F",  # Silver Futures
    "BTCUSD": "BTC-USD",
    "ETHUSD": "ETH-USD",
    "SPY": "SPY",
    "QQQ": "QQQ",
    "DXY": "DX-Y.NYB",  # US Dollar Index
}

# Reverse mapping: ticker -> display name
TICKER_TO_INSTRUMENT: Dict[str, str] = {v: k for k, v in INSTRUMENT_TO_TICKER.items()}

TIMEFRAME_DAYS = {
    "1M": 30,
    "3M": 90,
    "6M": 180,
}


def get_ticker_for_instrument(instrument: str) -> str:
    """Get yfinance ticker for an instrument."""
    return INSTRUMENT_TO_TICKER.get(instrument.upper(), instrument.upper() + "=X")


def calculate_correlation_matrix(
    instruments: List[str],
    timeframe_days: int
) -> Tuple[List[List[float]], str]:
    """
    Fetch price data and calculate correlation matrix.
    Returns (matrix, error_message).
    """
    # Get tickers in the same order
    tickers = [get_ticker_for_instrument(inst) for inst in instruments]
    
    try:
        data = yf.download(
            tickers=tickers,
            period=f"{timeframe_days}d",
            interval="1d",
            progress=False,
            auto_adjust=True
        )
        
        if data.empty:
            return [], "No data available for the selected instruments"
        
        # Handle MultiIndex columns from yfinance (Price type, Ticker)
        if isinstance(data.columns, pd.MultiIndex):
            close_prices = data["Close"]
        else:
            close_prices = data["Close"] if "Close" in data.columns else data
        
        # Drop columns with all NaN
        close_prices = close_prices.dropna(axis=1, how="all")
        
        if close_prices.empty or close_prices.shape[0] < 5:
            return [], "Not enough data points to calculate correlation"
        
        # Build a mapping from ticker column to display instrument name
        # close_prices columns are tickers like "EURUSD=X", we need to map back to display names
        ticker_to_display: Dict[str, str] = {}
        for col in close_prices.columns:
            col_str = str(col)
            if col_str in TICKER_TO_INSTRUMENT:
                ticker_to_display[col_str] = TICKER_TO_INSTRUMENT[col_str]
            else:
                # Try to strip =X suffix or =F suffix and look up
                for display, ticker in INSTRUMENT_TO_TICKER.items():
                    if ticker == col_str:
                        ticker_to_display[col_str] = display
                        break
                else:
                    # Use as-is if not found
                    ticker_to_display[col_str] = col_str
        
        # Rename columns to display names
        close_prices = close_prices.rename(columns=ticker_to_display)
        
        # Calculate daily returns
        returns = close_prices.pct_change().dropna()
        
        if returns.shape[0] < 5:
            return [], "Not enough data points to calculate correlation"
        
        # Calculate Pearson correlation
        corr_matrix = returns.corr(method="pearson")
        
        # Convert to list of lists, matching instrument order
        matrix = []
        for inst in instruments:
            if inst in corr_matrix.columns:
                row = [round(float(corr_matrix.loc[inst, other]), 4) if other in corr_matrix.columns else 0.0
                       for other in instruments]
                matrix.append(row)
            else:
                # Instrument not found in data - use 1.0 on diagonal, 0.0 elsewhere
                idx = instruments.index(inst)
                row = [1.0 if i == idx else 0.0 for i in range(len(instruments))]
                matrix.append(row)
        
        return matrix, ""
        
    except Exception as e:
        return [], f"Error fetching data: {str(e)}"


def find_strongest_correlations(
    matrix: List[List[float]],
    instruments: List[str]
) -> Tuple[Tuple[str, str, float], Tuple[str, str, float]]:
    """
    Find the strongest positive and negative correlations (excluding diagonal).
    """
    n = len(instruments)
    strongest_pos = ("", "", -1.0)
    strongest_neg = ("", "", 1.0)
    
    for i in range(n):
        for j in range(i + 1, n):
            val = matrix[i][j]
            pair = (instruments[i], instruments[j], val)
            
            if val > strongest_pos[2]:
                strongest_pos = (instruments[i], instruments[j], val)
            if val < strongest_neg[2]:
                strongest_neg = (instruments[i], instruments[j], val)
    
    return strongest_pos, strongest_neg


@router.get("/", response_model=CorrelationResponse)
def get_correlation_matrix(
    instruments: str = Query(
        "EURUSD,GBPUSD,USDJPY,AUDUSD,USDCAD,NZDUSD,XAUUSD",
        description="Comma-separated list of instruments"
    ),
    timeframe: str = Query("3M", description="Timeframe: 1M, 3M, or 6M"),
):
    """
    Calculate correlation matrix for given instruments using historical price data.
    Uses yfinance to fetch daily returns and calculates Pearson correlation.
    """
    # Parse instruments
    instrument_list = [inst.strip() for inst in instruments.split(",") if inst.strip()]
    
    if not instrument_list:
        raise ValueError("At least one instrument is required")
    
    if len(instrument_list) < 2:
        raise ValueError("At least 2 instruments are required for correlation")
    
    # Validate timeframe
    if timeframe not in TIMEFRAME_DAYS:
        raise ValueError(f"Invalid timeframe. Must be one of: {list(TIMEFRAME_DAYS.keys())}")
    
    days = TIMEFRAME_DAYS[timeframe]
    
    # Calculate correlation matrix
    matrix, error = calculate_correlation_matrix(instrument_list, days)
    
    if error:
        raise ValueError(error)
    
    # Find strongest correlations
    strongest_pos, strongest_negative = find_strongest_correlations(matrix, instrument_list)
    
    return CorrelationResponse(
        instruments=instrument_list,
        matrix=matrix,
        timeframe=timeframe,
        computed_at=datetime.utcnow(),
        strongest_positive=strongest_pos,
        strongest_negative=strongest_negative,
    )
