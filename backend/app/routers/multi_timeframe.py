"""
Multi-Timeframe Analysis API Router
Provides H4, D1, W1 technical analysis for instruments.
"""
import logging
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.models import ContentItem, ContentType
from app.services.signals_technicals import calculate_technicals, normalise_ticker

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/multi-timeframe", tags=["multi-timeframe"])

# ─── Pydantic Schemas ─────────────────────────────────────────────────────────

class TimeframeData(BaseModel):
    timeframe: str  # H4 | D1 | W1
    current_price: float
    trend: str
    rsi_14: float
    ma_20: float
    ma_60: float
    key_support: float
    key_resistance: float
    atr_14: float
    signals: List[str]


class MultiTimeframeResponse(BaseModel):
    instrument: str
    timeframes: List[TimeframeData]
    consensus: str  # BULLISH | BEARISH | MIXED
    setups: List[dict]


# ─── Helpers ──────────────────────────────────────────────────────────────────

TIMEFRAME_PERIODS = {
    "H4": "3mo",
    "D1": "6mo",
    "W1": "1y",
}


def _map_trend(raw_trend: str) -> str:
    if raw_trend == "UPTREND":
        return "TRENDING_UP"
    if raw_trend == "DOWNTREND":
        return "TRENDING_DOWN"
    return "RANGING"


def _generate_tf_signals(
    trend: str,
    rsi: float,
    price_vs_20ma: str,
    price_vs_60ma: str,
    ma_cross_20_60: str,
    price_location: str,
) -> List[str]:
    signals = []

    # Trend signals
    if trend == "TRENDING_UP":
        signals.append("Uptrend on " + trend.split("_")[0].lower())
    elif trend == "TRENDING_DOWN":
        signals.append("Downtrend on " + trend.split("_")[0].lower())
    else:
        signals.append("Ranging market")

    # RSI signals
    if rsi > 70:
        signals.append("RSI Overbought (>70)")
    elif rsi < 30:
        signals.append("RSI Oversold (<30)")
    elif rsi > 60:
        signals.append("RSI Bullish Zone")
    elif rsi < 40:
        signals.append("RSI Bearish Zone")

    # MA signals
    if price_vs_20ma == "ABOVE":
        signals.append("Price above MA20")
    elif price_vs_20ma == "BELOW":
        signals.append("Price below MA20")

    if price_vs_60ma == "ABOVE":
        signals.append("Price above MA60")
    elif price_vs_60ma == "BELOW":
        signals.append("Price below MA60")

    # MA crossover
    if ma_cross_20_60 == "GOLDEN":
        signals.append("Golden Cross (bullish)")
    elif ma_cross_20_60 == "DEATH":
        signals.append("Death Cross (bearish)")

    # Support/Resistance
    if price_location == "AT_SUPPORT":
        signals.append("At Support")
    elif price_location == "AT_RESISTANCE":
        signals.append("At Resistance")

    return signals


def _determine_consensus(trends: List[str]) -> str:
    """
    Determine consensus from list of trend directions.
    BULLISH if all TRENDING_UP, BEARISH if all TRENDING_DOWN, MIXED otherwise.
    """
    non_ranging = [t for t in trends if t != "RANGING"]
    if not non_ranging:
        return "MIXED"
    if all(t == "TRENDING_UP" for t in non_ranging):
        return "BULLISH"
    if all(t == "TRENDING_DOWN" for t in non_ranging):
        return "BEARISH"
    return "MIXED"


# ─── GET /multi-timeframe/{instrument} ───────────────────────────────────────

@router.get("/{instrument}", response_model=MultiTimeframeResponse)
def get_multi_timeframe(
    instrument: str,
    db: Session = Depends(get_db),
) -> MultiTimeframeResponse:
    """
    Get H4, D1, W1 technical analysis for a single instrument.
    """
    instrument = instrument.upper()

    timeframes_data: List[TimeframeData] = []
    trends: List[str] = []

    for tf, period in TIMEFRAME_PERIODS.items():
        ticker = normalise_ticker(instrument)
        data = calculate_technicals(ticker, period=period)

        if data is None:
            logger.warning(f"Could not calculate {tf} data for {instrument}")
            continue

        raw_trend = data.get("trend_direction", "RANGING")
        trend = _map_trend(raw_trend)
        trends.append(trend)

        rsi = data.get("rsi_14", 50.0) or 50.0

        signals = _generate_tf_signals(
            trend=trend,
            rsi=rsi,
            price_vs_20ma=data.get("price_vs_20ma", ""),
            price_vs_60ma=data.get("price_vs_60ma", ""),
            ma_cross_20_60=data.get("ma_20_vs_60_cross", "NONE"),
            price_location=data.get("at_support_resistance", ""),
        )

        timeframes_data.append(
            TimeframeData(
                timeframe=tf,
                current_price=data.get("current_price", 0.0) or 0.0,
                trend=trend,
                rsi_14=round(rsi, 2),
                ma_20=data.get("ma20") or 0.0,
                ma_60=data.get("ma60") or 0.0,
                key_support=data.get("key_support") or 0.0,
                key_resistance=data.get("key_resistance") or 0.0,
                atr_14=data.get("atr_14") or 0.0,
                signals=signals,
            )
        )

    if not timeframes_data:
        raise HTTPException(
            status_code=422,
            detail=f"Could not retrieve data for {instrument}",
        )

    consensus = _determine_consensus(trends)

    # Fetch related setups from DB
    setups_raw = (
        db.query(ContentItem)
        .filter(ContentItem.instrument.has(symbol=instrument))
        .filter(ContentItem.content_type == ContentType.SETUP)
        .order_by(ContentItem.published_at.desc())
        .limit(5)
        .all()
    )

    setups = [
        {
            "id": s.id,
            "title": s.title,
            "direction": s.direction.value if s.direction else None,
            "timeframe": s.timeframe.value if s.timeframe else None,
            "confidence": s.confidence.value if s.confidence else None,
            "entry_zone": s.entry_zone,
            "stop_loss": s.stop_loss,
            "take_profit": s.take_profit,
            "risk_reward_ratio": s.risk_reward_ratio,
            "published_at": s.published_at.isoformat() if s.published_at else None,
        }
        for s in setups_raw
    ]

    return MultiTimeframeResponse(
        instrument=instrument,
        timeframes=timeframes_data,
        consensus=consensus,
        setups=setups,
    )
