"""
Market Regime Indicator API Router
Provides endpoints for market regime detection and volatility analysis.
"""
import logging
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db, Base, engine
from app.models.models import RegimeSnapshot
from app.services.signals_technicals import calculate_technicals, normalise_ticker

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/regime", tags=["regime"])

# Ensure tables exist
Base.metadata.create_all(bind=engine)

# ─── Pydantic Schemas ─────────────────────────────────────────────────────────

class RegimeItem(BaseModel):
    instrument: str
    trend: str  # TRENDING_UP | TRENDING_DOWN | RANGING
    rsi: float
    atr_percent: float  # ATR as % of price (volatility)
    volatility_regime: str  # LOW | NORMAL | HIGH
    confidence: str  # HIGH | MEDIUM | LOW
    signals: List[str]
    regime_history: List[dict] = []

class RegimeResponse(BaseModel):
    items: List[RegimeItem]
    generated_at: str


# ─── Helpers ──────────────────────────────────────────────────────────────────

TRACKED_INSTRUMENTS = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "NZDUSD", "XAUUSD", "BTCUSD", "ETHUSD", "SPY"]

# Map trend_direction from calculate_technicals to regime format
def _map_trend(raw_trend: str) -> str:
    if raw_trend == "UPTREND":
        return "TRENDING_UP"
    if raw_trend == "DOWNTREND":
        return "TRENDING_DOWN"
    return "RANGING"


def _volatility_regime(atr_percent: float) -> str:
    """Classify volatility regime based on ATR as % of price."""
    if atr_percent < 0.3:
        return "LOW"
    if atr_percent > 1.0:
        return "HIGH"
    return "NORMAL"


def _confidence(rsi: float, atr_percent: float, trend: str) -> str:
    """
    Calculate regime confidence based on RSI clarity and volatility regime.
    """
    # RSI distance from neutral (50)
    rsi_strength = abs(rsi - 50)
    # Strong RSI signal: far from 50
    rsi_confident = rsi_strength > 20
    # Volatility regime clarity
    vol_clear = atr_percent < 0.3 or atr_percent > 1.0
    # Trend is clearly defined (not ranging)
    trend_clear = trend != "RANGING"

    score = sum([rsi_confident, vol_clear, trend_clear])
    if score >= 2:
        return "HIGH"
    if score == 1:
        return "MEDIUM"
    return "LOW"


def _generate_signals(rsi: float, trend: str, price_vs_20ma: str, ma_cross: str) -> List[str]:
    signals = []
    if rsi > 70:
        signals.append("RSI Overbought")
    elif rsi < 30:
        signals.append("RSI Oversold")
    if trend == "TRENDING_UP":
        signals.append("Uptrend Confirmed")
    elif trend == "TRENDING_DOWN":
        signals.append("Downtrend Confirmed")
    if price_vs_20ma == "ABOVE":
        signals.append("Price above MA20")
    elif price_vs_20ma == "BELOW":
        signals.append("Price below MA20")
    if ma_cross == "GOLDEN":
        signals.append("Golden Cross (MA20/60)")
    elif ma_cross == "DEATH":
        signals.append("Death Cross (MA20/60)")
    return signals


def _get_regime_history(db: Session, instrument: str, limit: int = 20) -> List[dict]:
    """Get last N regime snapshots for an instrument."""
    snapshots = (
        db.query(RegimeSnapshot)
        .filter(RegimeSnapshot.instrument == instrument)
        .order_by(RegimeSnapshot.recorded_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "regime": s.regime,
            "rsi_14": s.rsi_14,
            "atr_percent": s.atr_percent,
            "trend": s.trend,
            "recorded_at": s.recorded_at.isoformat() if s.recorded_at else None,
        }
        for s in reversed(snapshots)  # oldest first for charts
    ]


def _should_store_snapshot(db: Session, instrument: str) -> bool:
    """Check if we should store a new snapshot (once per day max)."""
    last_snapshot = (
        db.query(RegimeSnapshot)
        .filter(RegimeSnapshot.instrument == instrument)
        .order_by(RegimeSnapshot.recorded_at.desc())
        .first()
    )
    if not last_snapshot:
        return True
    # Store if last snapshot was more than 20 hours ago
    return (datetime.utcnow() - last_snapshot.recorded_at) > timedelta(hours=20)


def _store_snapshot(
    db: Session,
    instrument: str,
    trend: str,
    rsi_14: float,
    atr_percent: float,
    regime: str,
) -> None:
    """Store a regime snapshot."""
    snapshot = RegimeSnapshot(
        instrument=instrument,
        trend=trend,
        rsi_14=rsi_14,
        atr_percent=atr_percent,
        regime=regime,
        recorded_at=datetime.utcnow(),
    )
    db.add(snapshot)
    db.commit()


# ─── GET /regime ───────────────────────────────────────────────────────────────

@router.get("/", response_model=RegimeResponse)
def get_regime(db: Session = Depends(get_db)) -> RegimeResponse:
    """
    Get current market regime for all tracked instruments.
    Returns trend direction, RSI levels, volatility regime, and regime confidence.
    """
    items: List[RegimeItem] = []

    for instrument in TRACKED_INSTRUMENTS:
        ticker = normalise_ticker(instrument)
        data = calculate_technicals(ticker, period="3mo")

        if data is None:
            # Instrument data unavailable — skip but don't fail
            logger.warning(f"Could not calculate regime for {instrument}")
            continue

        raw_trend = data.get("trend_direction", "RANGING")
        trend = _map_trend(raw_trend)
        rsi = data.get("rsi_14", 50.0) or 50.0
        current_price = data.get("current_price", 1.0) or 1.0
        atr = data.get("atr_14", 0.0) or 0.0

        # ATR as percentage of price
        atr_percent = round((atr / current_price) * 100, 4) if current_price else 0.0

        volatility_regime = _volatility_regime(atr_percent)
        confidence = _confidence(rsi, atr_percent, trend)
        signals = _generate_signals(
            rsi=rsi,
            trend=trend,
            price_vs_20ma=data.get("price_vs_20ma", ""),
            ma_cross=data.get("ma_20_vs_60_cross", "NONE"),
        )

        # Get regime history from DB
        regime_history = _get_regime_history(db, instrument, limit=20)

        # Store snapshot if needed (once per day)
        if _should_store_snapshot(db, instrument):
            _store_snapshot(db, instrument, trend, rsi, atr_percent, trend)

        items.append(
            RegimeItem(
                instrument=instrument,
                trend=trend,
                rsi=round(rsi, 2),
                atr_percent=round(atr_percent, 4),
                volatility_regime=volatility_regime,
                confidence=confidence,
                signals=signals,
                regime_history=regime_history,
            )
        )

    return RegimeResponse(
        items=items,
        generated_at=datetime.utcnow().isoformat(),
    )


# ─── GET /regime/{instrument} ────────────────────────────────────────────────

class RegimeInstrumentResponse(BaseModel):
    instrument: str
    trend: str
    rsi: float
    atr_percent: float
    volatility_regime: str
    confidence: str
    signals: List[str]
    regime_history: List[dict]


@router.get("/{instrument}", response_model=RegimeInstrumentResponse)
def get_regime_instrument(
    instrument: str,
    db: Session = Depends(get_db),
) -> RegimeInstrumentResponse:
    """
    Get market regime for a single instrument with full history.
    """
    instrument = instrument.upper()
    ticker = normalise_ticker(instrument)
    data = calculate_technicals(ticker, period="3mo")

    if data is None:
        raise ValueError(f"Could not calculate regime for {instrument}")

    raw_trend = data.get("trend_direction", "RANGING")
    trend = _map_trend(raw_trend)
    rsi = data.get("rsi_14", 50.0) or 50.0
    current_price = data.get("current_price", 1.0) or 1.0
    atr = data.get("atr_14", 0.0) or 0.0

    atr_percent = round((atr / current_price) * 100, 4) if current_price else 0.0
    volatility_regime = _volatility_regime(atr_percent)
    confidence = _confidence(rsi, atr_percent, trend)
    signals = _generate_signals(
        rsi=rsi,
        trend=trend,
        price_vs_20ma=data.get("price_vs_20ma", ""),
        ma_cross=data.get("ma_20_vs_60_cross", "NONE"),
    )
    regime_history = _get_regime_history(db, instrument, limit=60)

    return RegimeInstrumentResponse(
        instrument=instrument,
        trend=trend,
        rsi=round(rsi, 2),
        atr_percent=round(atr_percent, 4),
        volatility_regime=volatility_regime,
        confidence=confidence,
        signals=signals,
        regime_history=regime_history,
    )
