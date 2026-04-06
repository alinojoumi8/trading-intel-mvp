"""
V3 Backtest API router.

Exposes the historical V3 LLM pipeline backtest results to the frontend.
"""
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.models import BacktestSignal
from app.services.v3_backtest_runner import (
    run_v3_backtest,
    get_backtest_results,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v3-backtest", tags=["v3-backtest"])


# ─── Schemas ─────────────────────────────────────────────────────────────────

class BacktestRunSummary(BaseModel):
    run_id: str
    total_signals: int
    actionable: int
    closed: int
    wins: int
    losses: int
    win_rate: Optional[float]
    total_pnl_pct: float
    started_at: Optional[str]
    last_signal_at: Optional[str]


class BacktestSignalDetail(BaseModel):
    id: int
    asset: str
    as_of_date: str
    final_signal: Optional[str]
    direction: Optional[str]
    signal_confidence: Optional[int]
    market_regime: Optional[str]
    fundamental_bias: Optional[str]
    gate_signal: Optional[str]
    entry_price: Optional[float]
    stop_loss: Optional[float]
    target_price: Optional[float]
    risk_reward_ratio: Optional[float]
    fsm_composite_score: Optional[float]
    fsm_divergence_category: Optional[str]
    outcome: Optional[str]
    entry_triggered: bool
    entry_actual_price: Optional[float]
    exit_price: Optional[float]
    pnl_pct: Optional[float]
    r_multiple: Optional[float]
    bars_in_trade: Optional[int]
    max_favorable_excursion_pct: Optional[float]
    max_adverse_excursion_pct: Optional[float]


# ─── Endpoints ───────────────────────────────────────────────────────────────

@router.get("/runs")
def list_runs(db: Session = Depends(get_db)) -> List[BacktestRunSummary]:
    """List all backtest runs with summary metrics."""
    # Get distinct run IDs
    run_ids = (
        db.query(BacktestSignal.backtest_run_id)
        .distinct()
        .all()
    )

    summaries = []
    for (run_id,) in run_ids:
        signals = (
            db.query(BacktestSignal)
            .filter(BacktestSignal.backtest_run_id == run_id)
            .all()
        )
        if not signals:
            continue
        actionable = [s for s in signals if s.final_signal in ("BUY", "SELL")]
        closed = [s for s in actionable if s.outcome in ("WIN", "LOSS")]
        wins = [s for s in closed if s.outcome == "WIN"]
        losses = [s for s in closed if s.outcome == "LOSS"]
        total_pnl = sum(s.pnl_pct for s in closed if s.pnl_pct is not None)

        first = min(signals, key=lambda s: s.generated_at or datetime.min)
        last = max(signals, key=lambda s: s.generated_at or datetime.min)

        summaries.append(BacktestRunSummary(
            run_id=run_id,
            total_signals=len(signals),
            actionable=len(actionable),
            closed=len(closed),
            wins=len(wins),
            losses=len(losses),
            win_rate=round(len(wins) / len(closed), 3) if closed else None,
            total_pnl_pct=round(total_pnl, 2),
            started_at=first.generated_at.isoformat() if first.generated_at else None,
            last_signal_at=last.generated_at.isoformat() if last.generated_at else None,
        ))

    return sorted(summaries, key=lambda s: s.started_at or "", reverse=True)


@router.get("/runs/{run_id}")
def get_run_details(run_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Detailed metrics for one backtest run, including per-asset breakdown.
    Mirrors the shape of get_backtest_results() from v3_backtest_runner.
    """
    return get_backtest_results(run_id)


@router.get("/runs/{run_id}/signals", response_model=List[BacktestSignalDetail])
def get_run_signals(
    run_id: str,
    asset: Optional[str] = Query(None),
    outcome: Optional[str] = Query(None),
    limit: int = Query(500),
    db: Session = Depends(get_db),
) -> List[BacktestSignalDetail]:
    """List individual signals from a backtest run, with optional filters."""
    q = db.query(BacktestSignal).filter(BacktestSignal.backtest_run_id == run_id)
    if asset:
        q = q.filter(BacktestSignal.asset == asset)
    if outcome:
        q = q.filter(BacktestSignal.outcome == outcome)
    q = q.order_by(BacktestSignal.as_of_date.asc()).limit(limit)

    signals = q.all()
    return [
        BacktestSignalDetail(
            id=s.id,
            asset=s.asset,
            as_of_date=s.as_of_date.isoformat() if s.as_of_date else "",
            final_signal=s.final_signal,
            direction=s.direction,
            signal_confidence=s.signal_confidence,
            market_regime=s.market_regime,
            fundamental_bias=s.fundamental_bias,
            gate_signal=s.gate_signal,
            entry_price=s.entry_price,
            stop_loss=s.stop_loss,
            target_price=s.target_price,
            risk_reward_ratio=s.risk_reward_ratio,
            fsm_composite_score=s.fsm_composite_score,
            fsm_divergence_category=s.fsm_divergence_category,
            outcome=s.outcome,
            entry_triggered=s.entry_triggered or False,
            entry_actual_price=s.entry_actual_price,
            exit_price=s.exit_price,
            pnl_pct=s.pnl_pct,
            r_multiple=s.r_multiple,
            bars_in_trade=s.bars_in_trade,
            max_favorable_excursion_pct=s.max_favorable_excursion_pct,
            max_adverse_excursion_pct=s.max_adverse_excursion_pct,
        )
        for s in signals
    ]


@router.get("/runs/{run_id}/equity-curve")
def get_equity_curve(
    run_id: str,
    asset: Optional[str] = Query(None),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Build a cumulative P&L equity curve from closed signals in chronological order.
    Optionally filter by asset.
    """
    q = (
        db.query(BacktestSignal)
        .filter(BacktestSignal.backtest_run_id == run_id)
        .filter(BacktestSignal.outcome.in_(["WIN", "LOSS"]))
        .order_by(BacktestSignal.as_of_date.asc())
    )
    if asset:
        q = q.filter(BacktestSignal.asset == asset)

    signals = q.all()
    if not signals:
        return {"run_id": run_id, "asset": asset, "points": []}

    points = []
    cumulative = 0.0
    peak = 0.0
    max_drawdown = 0.0

    for s in signals:
        pnl = s.pnl_pct or 0
        cumulative += pnl
        if cumulative > peak:
            peak = cumulative
        drawdown = peak - cumulative
        if drawdown > max_drawdown:
            max_drawdown = drawdown

        points.append({
            "date": s.as_of_date.isoformat() if s.as_of_date else None,
            "asset": s.asset,
            "pnl_pct": round(pnl, 3),
            "cumulative_pct": round(cumulative, 3),
            "drawdown_pct": round(drawdown, 3),
            "outcome": s.outcome,
        })

    return {
        "run_id": run_id,
        "asset": asset,
        "points": points,
        "max_drawdown_pct": round(max_drawdown, 3),
        "final_pnl_pct": round(cumulative, 3),
        "trades_count": len(points),
    }


@router.post("/runs")
def trigger_backtest(
    run_id: Optional[str] = Query(None),
    assets: str = Query("EURUSD,XAUUSD,USA500", description="Comma-separated asset list"),
    start_date: str = Query("2020-01-01"),
    end_date: str = Query("2025-01-01"),
    frequency: str = Query("weekly"),
    max_signals: Optional[int] = Query(None),
) -> Dict[str, Any]:
    """
    Trigger a new V3 backtest run synchronously.
    WARNING: Long-running (~14h for 5y × 3 assets weekly).
    For real use, kick off in a background process.
    """
    asset_list = [a.strip().upper() for a in assets.split(",")]
    try:
        result = run_v3_backtest(
            run_id=run_id,
            assets=asset_list,
            start_date=start_date,
            end_date=end_date,
            frequency=frequency,
            max_signals=max_signals,
            resume=True,
        )
        return result
    except Exception as e:
        logger.exception("V3 backtest run failed")
        raise HTTPException(status_code=500, detail=str(e))
