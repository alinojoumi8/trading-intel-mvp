"""
Trade Outcomes API Router
Tracks outcomes of trade setups for performance statistics.
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.models import TradeOutcome, ContentItem, Instrument

router = APIRouter(prefix="/trade-outcomes", tags=["trade-outcomes"])


# ─── Schemas ──────────────────────────────────────────────────────────────────

class TradeOutcomeBase(BaseModel):
    content_item_id: int
    status: str = "open"
    result_note: Optional[str] = None
    actual_entry: Optional[str] = None
    actual_sl: Optional[str] = None
    actual_tp: Optional[str] = None
    pnl_pips: Optional[float] = None
    outcome_date: Optional[datetime] = None


class TradeOutcomeCreate(TradeOutcomeBase):
    pass


class TradeOutcomeUpdate(BaseModel):
    status: Optional[str] = None
    result_note: Optional[str] = None
    actual_entry: Optional[str] = None
    actual_sl: Optional[str] = None
    actual_tp: Optional[str] = None
    pnl_pips: Optional[float] = None
    outcome_date: Optional[datetime] = None


class TradeOutcomeResponse(TradeOutcomeBase):
    id: int
    created_at: datetime
    updated_at: datetime
    content_title: Optional[str] = None
    instrument_symbol: Optional[str] = None

    class Config:
        from_attributes = True


class OutcomeStats(BaseModel):
    total_setups: int
    open_count: int
    won_count: int
    lost_count: int
    breakeven_count: int
    cancelled_count: int
    resolved_count: int
    win_rate: Optional[float]
    avg_pnl_pips: Optional[float]
    avg_risk_reward: Optional[float]
    by_instrument: dict
    by_direction: dict
    by_timeframe: dict
    by_confidence: dict
    by_tag: dict


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _outcome_to_dict(outcome: TradeOutcome, include_content: bool = False) -> dict:
    result = {
        "id": outcome.id,
        "content_item_id": outcome.content_item_id,
        "status": outcome.status,
        "result_note": outcome.result_note,
        "actual_entry": outcome.actual_entry,
        "actual_sl": outcome.actual_sl,
        "actual_tp": outcome.actual_tp,
        "pnl_pips": outcome.pnl_pips,
        "outcome_date": outcome.outcome_date.isoformat() if outcome.outcome_date else None,
        "created_at": outcome.created_at.isoformat() if outcome.created_at else None,
        "updated_at": outcome.updated_at.isoformat() if outcome.updated_at else None,
    }
    if include_content and outcome.content_item:
        result["content_title"] = outcome.content_item.title
        if outcome.content_item.instrument:
            result["instrument_symbol"] = outcome.content_item.instrument.symbol
    return result


# ─── POST /trade-outcomes/ ────────────────────────────────────────────────────

@router.post("/", response_model=dict)
def create_or_update_outcome(
    outcome_in: TradeOutcomeCreate,
    db: Session = Depends(get_db),
):
    """
    Create or update a trade outcome for a content item.
    If an outcome already exists for the content_item_id, update it.
    """
    existing = db.query(TradeOutcome).filter(
        TradeOutcome.content_item_id == outcome_in.content_item_id
    ).first()

    if existing:
        # Update existing
        for field in ["status", "result_note", "actual_entry", "actual_sl", "actual_tp", "pnl_pips"]:
            val = getattr(outcome_in, field, None)
            if val is not None:
                setattr(existing, field, val)
        if outcome_in.outcome_date:
            existing.outcome_date = outcome_in.outcome_date
        existing.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(existing)
        return _outcome_to_dict(existing, include_content=True)

    # Create new
    outcome = TradeOutcome(
        content_item_id=outcome_in.content_item_id,
        status=outcome_in.status,
        result_note=outcome_in.result_note,
        actual_entry=outcome_in.actual_entry,
        actual_sl=outcome_in.actual_sl,
        actual_tp=outcome_in.actual_tp,
        pnl_pips=outcome_in.pnl_pips,
        outcome_date=outcome_in.outcome_date,
    )
    db.add(outcome)
    db.commit()
    db.refresh(outcome)
    return _outcome_to_dict(outcome, include_content=True)


# ─── GET /trade-outcomes/ ─────────────────────────────────────────────────────

@router.get("/", response_model=dict)
def list_outcomes(
    status: Optional[str] = Query(None, description="Filter by status: open, won, lost, breakeven, cancelled"),
    instrument: Optional[str] = Query(None, description="Filter by instrument symbol"),
    timeframe: Optional[str] = Query(None, description="Filter by timeframe: scalp, h4, d1, w1"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """List trade outcomes with optional filters."""
    query = db.query(TradeOutcome).join(ContentItem).outerjoin(Instrument)

    if status:
        query = query.filter(TradeOutcome.status == status)
    if instrument:
        query = query.filter(Instrument.symbol == instrument.upper())
    if timeframe:
        query = query.filter(ContentItem.timeframe == timeframe)

    total = query.count()
    outcomes = query.order_by(TradeOutcome.outcome_date.desc().nullslast()).offset(offset).limit(limit).all()

    return {
        "items": [_outcome_to_dict(o, include_content=True) for o in outcomes],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


# ─── GET /trade-outcomes/stats ────────────────────────────────────────────────

@router.get("/stats", response_model=dict)
def get_outcome_stats(
    db: Session = Depends(get_db),
):
    """Get aggregate performance statistics for trade outcomes."""
    outcomes = db.query(TradeOutcome).join(ContentItem).outerjoin(Instrument).all()

    total = len(outcomes)
    if total == 0:
        return {
            "total_setups": 0,
            "open_count": 0,
            "won_count": 0,
            "lost_count": 0,
            "breakeven_count": 0,
            "cancelled_count": 0,
            "resolved_count": 0,
            "win_rate": None,
            "avg_pnl_pips": None,
            "avg_risk_reward": None,
            "by_instrument": {},
            "by_direction": {},
            "by_timeframe": {},
            "by_confidence": {},
            "by_tag": {},
        }

    open_count = sum(1 for o in outcomes if o.status == "open")
    won_count = sum(1 for o in outcomes if o.status == "won")
    lost_count = sum(1 for o in outcomes if o.status == "lost")
    breakeven_count = sum(1 for o in outcomes if o.status == "breakeven")
    cancelled_count = sum(1 for o in outcomes if o.status == "cancelled")
    resolved = total - open_count - cancelled_count

    win_rate = round(won_count / resolved * 100, 1) if resolved > 0 else None

    # Average PnL
    pnl_values = [o.pnl_pips for o in outcomes if o.pnl_pips is not None]
    avg_pnl_pips = round(sum(pnl_values) / len(pnl_values), 2) if pnl_values else None

    # Average R:R from content items
    rr_values = [o.content_item.risk_reward_ratio for o in outcomes
                 if o.content_item and o.content_item.risk_reward_ratio is not None]
    avg_risk_reward = round(sum(rr_values) / len(rr_values), 2) if rr_values else None

    # By instrument
    by_instrument = {}
    for o in outcomes:
        inst = o.content_item.instrument.symbol if o.content_item and o.content_item.instrument else "UNKNOWN"
        if inst not in by_instrument:
            by_instrument[inst] = {"total": 0, "won": 0, "lost": 0, "breakeven": 0}
        by_instrument[inst]["total"] += 1
        if o.status in ("won", "lost", "breakeven"):
            by_instrument[inst][o.status] += 1

    # Compute win rate per instrument
    for inst, data in by_instrument.items():
        resolved_inst = data["won"] + data["lost"] + data["breakeven"]
        data["win_rate"] = round(data["won"] / resolved_inst * 100, 1) if resolved_inst > 0 else None

    # By direction
    by_direction = {}
    for o in outcomes:
        direction = o.content_item.direction.value if o.content_item and o.content_item.direction else "UNKNOWN"
        if direction not in by_direction:
            by_direction[direction] = {"total": 0, "won": 0, "lost": 0}
        by_direction[direction]["total"] += 1
        if o.status in ("won", "lost"):
            by_direction[direction][o.status] += 1

    for direction, data in by_direction.items():
        resolved_dir = data["won"] + data["lost"]
        data["win_rate"] = round(data["won"] / resolved_dir * 100, 1) if resolved_dir > 0 else None

    # By timeframe
    by_timeframe = {}
    for o in outcomes:
        tf = o.content_item.timeframe.value if o.content_item and o.content_item.timeframe else "UNKNOWN"
        if tf not in by_timeframe:
            by_timeframe[tf] = {"total": 0, "won": 0, "lost": 0}
        by_timeframe[tf]["total"] += 1
        if o.status in ("won", "lost"):
            by_timeframe[tf][o.status] += 1

    for tf, data in by_timeframe.items():
        resolved_tf = data["won"] + data["lost"]
        data["win_rate"] = round(data["won"] / resolved_tf * 100, 1) if resolved_tf > 0 else None

    # By confidence
    by_confidence = {}
    for o in outcomes:
        conf = o.content_item.confidence.value if o.content_item and o.content_item.confidence else "UNKNOWN"
        if conf not in by_confidence:
            by_confidence[conf] = {"total": 0, "won": 0, "lost": 0}
        by_confidence[conf]["total"] += 1
        if o.status in ("won", "lost"):
            by_confidence[conf][o.status] += 1

    for conf, data in by_confidence.items():
        resolved_conf = data["won"] + data["lost"]
        data["win_rate"] = round(data["won"] / resolved_conf * 100, 1) if resolved_conf > 0 else None

    # By tag
    by_tag = {}
    for o in outcomes:
        if not o.content_item:
            continue
        for tag in o.content_item.tags:
            tag_name = tag.name
            if tag_name not in by_tag:
                by_tag[tag_name] = {"total": 0, "won": 0, "lost": 0}
            by_tag[tag_name]["total"] += 1
            if o.status in ("won", "lost"):
                by_tag[tag_name][o.status] += 1

    for tag_name, data in by_tag.items():
        resolved_tag = data["won"] + data["lost"]
        data["win_rate"] = round(data["won"] / resolved_tag * 100, 1) if resolved_tag > 0 else None

    return {
        "total_setups": total,
        "open_count": open_count,
        "won_count": won_count,
        "lost_count": lost_count,
        "breakeven_count": breakeven_count,
        "cancelled_count": cancelled_count,
        "resolved_count": resolved,
        "win_rate": win_rate,
        "avg_pnl_pips": avg_pnl_pips,
        "avg_risk_reward": avg_risk_reward,
        "by_instrument": by_instrument,
        "by_direction": by_direction,
        "by_timeframe": by_timeframe,
        "by_confidence": by_confidence,
        "by_tag": by_tag,
    }


# ─── PATCH /trade-outcomes/{id} ───────────────────────────────────────────────

@router.patch("/{outcome_id}", response_model=dict)
def update_outcome(
    outcome_id: int,
    update: TradeOutcomeUpdate,
    db: Session = Depends(get_db),
):
    """Update a specific trade outcome."""
    outcome = db.query(TradeOutcome).filter(TradeOutcome.id == outcome_id).first()
    if not outcome:
        raise HTTPException(status_code=404, detail="Trade outcome not found")

    for field in ["status", "result_note", "actual_entry", "actual_sl", "actual_tp", "pnl_pips"]:
        val = getattr(update, field, None)
        if val is not None:
            setattr(outcome, field, val)
    if update.outcome_date:
        outcome.outcome_date = update.outcome_date

    outcome.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(outcome)
    return _outcome_to_dict(outcome, include_content=True)
