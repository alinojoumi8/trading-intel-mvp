"""
Trading Signals Service
Orchestrates the 4-stage signal pipeline and stores results to the database.
"""
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import select, desc
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.models import TradingSignal
from app.services.signals_stages import run_full_pipeline

logger = logging.getLogger(__name__)


def generate_signal(asset: str, save: bool = True) -> Dict[str, Any]:
    """
    Run the full 4-stage signal pipeline for an asset.

    Args:
        asset: Asset ticker (e.g. "EURUSD", "BTCUSD", "SPY")
        save: Whether to save the result to the database

    Returns:
        Full pipeline result dict with all 4 stages
    """
    result = run_full_pipeline(asset)

    if save:
        _save_signal(result)

    return result


def _save_signal(result: Dict[str, Any]) -> TradingSignal:
    """Save a pipeline result to the database."""
    db = SessionLocal()
    try:
        stage1 = result.get("stage1", {})
        stage2 = result.get("stage2", {})
        stage3 = result.get("stage3") or {}
        stage4 = result.get("stage4", {})

        # Position size: base 100% × modifier from stage 1
        base_pct = stage4.get("recommended_position_size_pct", 100)
        modifier = stage1.get("position_size_modifier", 1.0)
        final_position_pct = int(base_pct * modifier)

        signal = TradingSignal(
            asset=result["asset"],
            asset_class=result.get("asset_class"),
            # Stage 1
            market_regime=stage1.get("market_regime"),
            volatility_regime=stage1.get("volatility_regime"),
            trading_mode=stage1.get("trading_mode"),
            position_size_modifier=stage1.get("position_size_modifier"),
            # Stage 2
            fundamental_bias=stage2.get("fundamental_bias"),
            bias_strength=stage2.get("bias_strength"),
            top_drivers=json.dumps(stage2.get("top_drivers", [])),
            # Stage 3
            gate_signal=stage3.get("gate_signal"),
            entry_recommendation=stage3.get("entry_recommendation"),
            technical_alignment=stage3.get("technical_alignment"),
            entry_price=stage3.get("suggested_entry_price"),
            stop_loss=stage3.get("stop_loss_price"),
            target_price=stage3.get("target_price"),
            risk_reward_ratio=stage3.get("risk_reward_ratio"),
            # Stage 4
            final_signal=stage4.get("final_signal"),
            signal_confidence=stage4.get("signal_confidence"),
            direction=stage4.get("direction"),
            recommended_position_size_pct=final_position_pct,
            trade_horizon=stage4.get("trade_horizon", "1-5 days"),
            signal_summary=stage4.get("signal_summary"),
            key_risks=json.dumps(stage4.get("key_risks", [])),
            invalidation_conditions=json.dumps(stage4.get("invalidation_conditions", [])),
            # Raw stage outputs
            stage1_output=json.dumps(stage1),
            stage2_output=json.dumps(stage2),
            stage3_output=json.dumps(stage3) if stage3 else None,
            stage4_output=json.dumps(stage4),
            # Metadata
            outcome="ACTIVE",
            generated_at=datetime.utcnow(),
        )

        db.add(signal)
        db.commit()
        db.refresh(signal)
        logger.info(f"[SIGNALS] Saved signal id={signal.id} for {signal.asset}: {signal.final_signal}")
        return signal

    finally:
        db.close()


def get_signals(
    db: Session,
    asset: Optional[str] = None,
    outcome: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[List[TradingSignal], int]:
    """
    Get stored signals with optional filtering.
    Returns (signals, total_count).
    """
    query = select(TradingSignal)
    if asset:
        query = query.where(TradingSignal.asset == asset.upper())
    if outcome:
        query = query.where(TradingSignal.outcome == outcome)

    # Total count
    count_q = select(TradingSignal.id)
    if asset:
        count_q = count_q.where(TradingSignal.asset == asset.upper())
    if outcome:
        count_q = count_q.where(TradingSignal.outcome == outcome)
    total = len(list(db.execute(count_q).scalars().all()))

    signals = list(
        db.execute(
            query.order_by(desc(TradingSignal.generated_at))
            .offset(offset)
            .limit(limit)
        ).scalars().all()
    )
    return signals, total


def get_signal_by_id(db: Session, signal_id: int) -> Optional[TradingSignal]:
    return db.execute(
        select(TradingSignal).where(TradingSignal.id == signal_id)
    ).scalar_one_or_none()


def resolve_signal(
    db: Session,
    signal_id: int,
    outcome: str,  # WIN, LOSS, BREAKEVEN
    notes: Optional[str] = None,
) -> Optional[TradingSignal]:
    """
    Mark a signal as resolved with its outcome.
    """
    signal = get_signal_by_id(db, signal_id)
    if not signal:
        return None
    signal.outcome = outcome.upper()
    signal.outcome_notes = notes
    signal.resolved_at = datetime.utcnow()
    db.commit()
    db.refresh(signal)
    logger.info(f"[SIGNALS] Resolved signal {signal_id} as {outcome}")
    return signal


# ─── Sync wrapper ──────────────────────────────────────────────────────────

def generate_signal_sync(asset: str) -> Dict[str, Any]:
    """Synchronous wrapper for generate_signal."""
    return generate_signal(asset, save=True)
