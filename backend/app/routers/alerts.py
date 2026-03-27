"""
Alerts API Router
Provides endpoints for managing alert rules and viewing alert logs.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.models import AlertRule, AlertLog
from app.schemas.schemas import (
    AlertRuleCreate,
    AlertRuleUpdate,
    AlertRuleResponse,
    AlertLogResponse,
)
from app.services import alert_service

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("/alert-rules", response_model=list[AlertRuleResponse])
def list_alert_rules(
    instrument: Optional[str] = Query(None, description="Filter by instrument"),
    enabled: Optional[bool] = Query(None, description="Filter by enabled status"),
    db: Session = Depends(get_db),
):
    """List alert rules with optional filters."""
    rules = alert_service.get_alert_rules(db, instrument=instrument, enabled=enabled)
    return [AlertRuleResponse.from_orm_with_params(r) for r in rules]


@router.post("/alert-rules", response_model=AlertRuleResponse)
def create_alert_rule(
    rule_data: AlertRuleCreate,
    db: Session = Depends(get_db),
):
    """Create a new alert rule."""
    # Validate condition_type
    valid_types = ["regime_change", "setup_generated", "cot_change", "price_cross", "rsi_level"]
    if rule_data.condition_type not in valid_types:
        raise HTTPException(
            status_code=422,
            detail=f"condition_type must be one of: {', '.join(valid_types)}"
        )
    
    # Basic validation of condition_params based on type
    params = rule_data.condition_params
    ctype = rule_data.condition_type
    
    if ctype == "cot_change" and "threshold_pct" not in params:
        pass  # has default
    elif ctype == "price_cross":
        if "level" not in params:
            raise HTTPException(status_code=422, detail="price_cross requires 'level' in condition_params")
        if params.get("direction") not in [None, "above", "below", "cross"]:
            raise HTTPException(status_code=422, detail="price_cross direction must be 'above', 'below', or 'cross'")
    elif ctype == "rsi_level":
        if "level" not in params:
            pass  # has default
        if params.get("zone") not in [None, "overbought", "oversold", "any"]:
            raise HTTPException(status_code=422, detail="rsi_level zone must be 'overbought', 'oversold', or 'any'")
    
    rule = alert_service.create_alert_rule(db, rule_data.model_dump())
    return AlertRuleResponse.from_orm_with_params(rule)


@router.delete("/alert-rules/{rule_id}")
def delete_alert_rule(
    rule_id: int,
    db: Session = Depends(get_db),
):
    """Delete an alert rule."""
    success = alert_service.delete_alert_rule(db, rule_id)
    if not success:
        raise HTTPException(status_code=404, detail="Alert rule not found")
    return {"message": "Alert rule deleted"}


@router.post("/alert-rules/{rule_id}/test")
def test_alert_rule(
    rule_id: int,
    db: Session = Depends(get_db),
):
    """Trigger a test notification for an alert rule."""
    rule = db.query(AlertRule).filter(AlertRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Alert rule not found")
    
    success = alert_service.test_alert_rule(rule_id)
    if success:
        return {"message": "Test notification sent"}
    else:
        raise HTTPException(status_code=500, detail="Failed to send test notification. Check Telegram configuration.")


@router.get("/alert-logs", response_model=list[AlertLogResponse])
def list_alert_logs(
    rule_id: Optional[int] = Query(None, description="Filter by rule ID"),
    acknowledged: Optional[bool] = Query(None, description="Filter by acknowledged status"),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """List alert logs with optional filters."""
    logs = alert_service.get_alert_logs(db, rule_id=rule_id, acknowledged=acknowledged, limit=limit)
    return logs


@router.post("/alert-logs/{log_id}/acknowledge")
def acknowledge_alert(
    log_id: int,
    db: Session = Depends(get_db),
):
    """Acknowledge an alert log entry."""
    success = alert_service.acknowledge_alert(db, log_id)
    if not success:
        raise HTTPException(status_code=404, detail="Alert log entry not found")
    return {"message": "Alert acknowledged"}


@router.patch("/alert-rules/{rule_id}")
def update_alert_rule(
    rule_id: int,
    update_data: AlertRuleUpdate,
    db: Session = Depends(get_db),
):
    """Update an alert rule."""
    rule = db.query(AlertRule).filter(AlertRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Alert rule not found")
    
    update_dict = update_data.model_dump(exclude_unset=True)
    
    if "condition_params" in update_dict and isinstance(update_dict["condition_params"], dict):
        import json
        update_dict["condition_params"] = json.dumps(update_dict["condition_params"])
    
    for key, value in update_dict.items():
        if value is not None:
            setattr(rule, key, value)
    
    db.commit()
    db.refresh(rule)
    return AlertRuleResponse.from_orm_with_params(rule)
