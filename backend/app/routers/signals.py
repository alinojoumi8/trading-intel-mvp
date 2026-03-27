"""
Trading Signals API Router
Provides endpoints for generating and retrieving trading signals.
"""
import json
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.models import TradingSignal
from app.services.signals_service import (
    generate_signal,
    get_signals,
    get_signal_by_id,
    resolve_signal,
)

router = APIRouter(prefix="/signals", tags=["signals"])


# ─── Schemas (inline to avoid circular imports) ──────────────────────────────

SIGNAL_STAGE_SCHEMA = {
    "type": "object",
    "description": "Full output from each stage (raw JSON)",
}


# ─── GET /signals/ ─────────────────────────────────────────────────────────────

@router.get("/", response_model=dict)
def list_signals(
    asset: Optional[str] = Query(None, description="Filter by asset e.g. EURUSD"),
    outcome: Optional[str] = Query(None, description="Filter by outcome: ACTIVE, WIN, LOSS, BREAKEVEN"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """List stored trading signals with optional filtering."""
    signals, total = get_signals(db, asset=asset, outcome=outcome, limit=limit, offset=offset)

    return {
        "items": [_signal_to_dict(s) for s in signals],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


# ─── GET /signals/{id} ────────────────────────────────────────────────────────

@router.get("/{signal_id}", response_model=dict)
def get_signal(signal_id: int, db: Session = Depends(get_db)):
    """Get a single signal by ID including full stage outputs."""
    signal = get_signal_by_id(db, signal_id)
    if not signal:
        raise HTTPException(status_code=404, detail="Signal not found")
    return _signal_to_dict(signal, include_stages=True)


# ─── POST /signals/generate ──────────────────────────────────────────────────

@router.post("/generate", response_model=dict)
def create_signal(
    asset: str = Query(..., description="Asset ticker e.g. EURUSD, BTCUSD, SPY"),
    save: bool = Query(True, description="Whether to save to database"),
    db: Session = Depends(get_db),
):
    """
    Generate a new trading signal for the given asset.
    Runs the full 4-stage pipeline: Regime → Macro → Gatekeeping → Signal.

    Takes ~10-20 seconds due to LLM calls.
    """
    asset = asset.upper().strip()
    if not asset:
        raise HTTPException(status_code=400, detail="Asset is required")

    try:
        result = generate_signal(asset, save=save)
        return _pipeline_result_to_dict(result)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Signal generation failed: {e}")


# ─── POST /signals/resolve ────────────────────────────────────────────────────

@router.patch("/resolve", response_model=dict)
def resolve(
    signal_id: int = Query(..., description="Signal ID to resolve"),
    outcome: str = Query(..., description="Outcome: WIN, LOSS, BREAKEVEN"),
    notes: Optional[str] = Query(None, description="Optional resolution notes"),
    db: Session = Depends(get_db),
):
    """Mark a signal as resolved with its outcome."""
    outcome = outcome.upper()
    if outcome not in ("WIN", "LOSS", "BREAKEVEN"):
        raise HTTPException(status_code=400, detail="Outcome must be WIN, LOSS, or BREAKEVEN")

    signal = resolve_signal(db, signal_id, outcome, notes)
    if not signal:
        raise HTTPException(status_code=404, detail="Signal not found")
    return _signal_to_dict(signal)


# ─── GET /signals/stats ──────────────────────────────────────────────────────

@router.get("/stats/summary", response_model=dict)
def signal_stats(db: Session = Depends(get_db)):
    """Get aggregate statistics for all stored signals."""
    from sqlalchemy import func

    signals = db.query(TradingSignal).all()
    total = len(signals)

    if total == 0:
        return {
            "total_signals": 0,
            "active": 0,
            "win_rate": None,
            "avg_confidence": None,
            "by_regime": {},
            "by_direction": {},
        }

    active = sum(1 for s in signals if s.outcome == "ACTIVE")
    resolved = [s for s in signals if s.outcome in ("WIN", "LOSS", "BREAKEVEN")]
    wins = sum(1 for s in resolved if s.outcome == "WIN")
    win_rate = round(wins / len(resolved) * 100, 1) if resolved else None

    confidences = [s.signal_confidence for s in signals if s.signal_confidence is not None]
    avg_confidence = round(sum(confidences) / len(confidences), 1) if confidences else None

    # By regime
    by_regime = {}
    for s in signals:
        regime = s.market_regime or "UNKNOWN"
        by_regime[regime] = by_regime.get(regime, 0) + 1

    # By direction
    by_direction = {}
    for s in signals:
        direction = s.direction or "UNKNOWN"
        by_direction[direction] = by_direction.get(direction, 0) + 1

    return {
        "total_signals": total,
        "active": active,
        "resolved": len(resolved),
        "win_rate": win_rate,
        "avg_confidence": avg_confidence,
        "by_regime": by_regime,
        "by_direction": by_direction,
    }


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _signal_to_dict(signal: TradingSignal, include_stages: bool = False) -> dict:
    """Convert a TradingSignal model object to a dict for JSON serialization."""
    result = {
        "id": signal.id,
        "asset": signal.asset,
        "asset_class": signal.asset_class,
        "generated_at": signal.generated_at.isoformat() if signal.generated_at else None,
        "outcome": signal.outcome,
        "resolved_at": signal.resolved_at.isoformat() if signal.resolved_at else None,
        # Stage 1
        "market_regime": signal.market_regime,
        "volatility_regime": signal.volatility_regime,
        "trading_mode": signal.trading_mode,
        "position_size_modifier": signal.position_size_modifier,
        # Stage 2
        "fundamental_bias": signal.fundamental_bias,
        "bias_strength": signal.bias_strength,
        "top_drivers": json.loads(signal.top_drivers) if signal.top_drivers else [],
        # Stage 3
        "gate_signal": signal.gate_signal,
        "entry_recommendation": signal.entry_recommendation,
        "technical_alignment": signal.technical_alignment,
        # Trade params
        "entry_price": signal.entry_price,
        "stop_loss": signal.stop_loss,
        "target_price": signal.target_price,
        "risk_reward_ratio": signal.risk_reward_ratio,
        # Stage 4
        "final_signal": signal.final_signal,
        "signal_confidence": signal.signal_confidence,
        "direction": signal.direction,
        "recommended_position_size_pct": signal.recommended_position_size_pct,
        "trade_horizon": signal.trade_horizon,
        "signal_summary": signal.signal_summary,
        "key_risks": json.loads(signal.key_risks) if signal.key_risks else [],
        "invalidation_conditions": json.loads(signal.invalidation_conditions) if signal.invalidation_conditions else [],
    }

    if include_stages:
        result["stage1_output"] = json.loads(signal.stage1_output) if signal.stage1_output else None
        result["stage2_output"] = json.loads(signal.stage2_output) if signal.stage2_output else None
        result["stage3_output"] = json.loads(signal.stage3_output) if signal.stage3_output else None
        result["stage4_output"] = json.loads(signal.stage4_output) if signal.stage4_output else None

    return result


def _pipeline_result_to_dict(result: dict) -> dict:
    """Convert a pipeline result dict to API response format."""
    stage1 = result.get("stage1", {})
    stage2 = result.get("stage2", {})
    stage3 = result.get("stage3") or {}
    stage4 = result.get("stage4", {})

    return {
        "asset": result["asset"],
        "asset_class": result.get("asset_class"),
        "ticker_used": result.get("ticker_used"),
        # Stage 1 summary
        "market_regime": stage1.get("market_regime"),
        "volatility_regime": stage1.get("volatility_regime"),
        "trading_mode": stage1.get("trading_mode"),
        "position_size_modifier": stage1.get("position_size_modifier"),
        "regime_reasoning": stage1.get("regime_reasoning"),
        # Stage 2 summary
        "fundamental_bias": stage2.get("fundamental_bias"),
        "bias_strength": stage2.get("bias_strength"),
        "top_drivers": stage2.get("top_drivers", []),
        "fundamental_reasoning": stage2.get("fundamental_reasoning"),
        # Stage 3 summary
        "gate_signal": stage3.get("gate_signal"),
        "entry_recommendation": stage3.get("entry_recommendation"),
        "technical_alignment": stage3.get("technical_alignment"),
        "gate_reasoning": stage3.get("gate_reasoning"),
        "watch_list_trigger": stage3.get("watch_list_trigger"),
        # Trade params
        "entry_price": stage3.get("suggested_entry_price"),
        "stop_loss": stage3.get("stop_loss_price"),
        "target_price": stage3.get("target_price"),
        "risk_reward_ratio": stage3.get("risk_reward_ratio"),
        # Stage 4
        "final_signal": stage4.get("final_signal"),
        "signal_confidence": stage4.get("signal_confidence"),
        "direction": stage4.get("direction"),
        "recommended_position_size_pct": stage4.get("recommended_position_size_pct"),
        "trade_horizon": stage4.get("trade_horizon"),
        "signal_summary": stage4.get("signal_summary"),
        "key_risks": stage4.get("key_risks", []),
        "invalidation_conditions": stage4.get("invalidation_conditions", []),
        # Full stage outputs (for debugging/transparency)
        "stage1": stage1,
        "stage2": stage2,
        "stage3": stage3,
        "stage4": stage4,
    }
