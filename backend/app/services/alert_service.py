"""
Alert Service — checks alert rules against market context and sends notifications.
Called by the cron scheduler after each pipeline run.
"""
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.models import AlertRule, AlertLog

logger = logging.getLogger(__name__)

# Telegram user ID for Home channel (Ali)
TELEGRAM_HOME_ID = "120584345"


def _get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class AlertMatch:
    """Represents a triggered alert."""
    def __init__(self, rule: AlertRule, message: str):
        self.rule = rule
        self.message = message


def _send_telegram_message(message: str) -> bool:
    """
    Send a Telegram message via the gateway if configured.
    Returns True if sent successfully, False otherwise.
    """
    try:
        # Try to use the gateway's TelegramBot if available
        from app.core.config import settings
        
        # Check if gateway is configured (TelegramBot)
        gateway_token = getattr(settings, "TELEGRAM_BOT_TOKEN", None) or getattr(settings, "TELEGRAM_TOKEN", None)
        
        if not gateway_token:
            logger.warning("Telegram bot token not configured, skipping notification")
            return False
        
        import httpx
        # Send to the Home channel (Ali)
        url = f"https://api.telegram.org/bot{gateway_token}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_HOME_ID,
            "text": message,
            "parse_mode": "HTML"
        }
        resp = httpx.post(url, json=payload, timeout=10)
        if resp.status_code == 200:
            logger.info(f"Telegram notification sent: {message[:50]}...")
            return True
        else:
            logger.warning(f"Telegram send failed: {resp.status_code} {resp.text}")
            return False
    except Exception as e:
        logger.error(f"Failed to send Telegram message: {e}")
        return False


def _format_alert_message(rule: AlertRule, context: Dict[str, Any]) -> str:
    """Format a human-readable alert message."""
    instrument = rule.instrument or "ALL"
    condition = rule.condition_type
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    
    msg = f"🔔 <b>Alert: {rule.name}</b>\n"
    msg += f"📊 Instrument: {instrument}\n"
    msg += f"⏰ {timestamp}\n\n"
    msg += f"Condition: <b>{condition}</b>\n"
    
    # Add context-specific details
    params = json.loads(rule.condition_params) if isinstance(rule.condition_params, str) else rule.condition_params
    
    if condition == "regime_change":
        old_regime = context.get("old_regime", "N/A")
        new_regime = context.get("new_regime", "N/A")
        msg += f"Regime changed: {old_regime} → {new_regime}"
    elif condition == "setup_generated":
        msg += f"New setup generated with R:R >= {params.get('min_rr', 'N/A')}"
    elif condition == "cot_change":
        msg += f"COT net position changed by {params.get('threshold_pct', 20)}%"
    elif condition == "price_cross":
        level = params.get("level", "N/A")
        direction = params.get("direction", "cross")
        current_price = context.get("current_price", "N/A")
        msg += f"Price {current_price} crossed {direction} {level}"
    elif condition == "rsi_level":
        zone = params.get("zone", "any")
        level = params.get("level", 70)
        current_rsi = context.get("current_rsi", "N/A")
        msg += f"RSI({level}) reached {zone} zone at {current_rsi}"
    else:
        msg += f"Params: {json.dumps(params)}"
    
    return msg


async def check_alerts(market_context: Dict[str, Any]) -> List[AlertMatch]:
    """
    Check all enabled alert rules against current market context.
    Returns list of triggered alerts.
    Called by the cron job after each pipeline run.
    """
    db = SessionLocal()
    triggered = []
    
    try:
        rules = db.query(AlertRule).filter(AlertRule.enabled == True).all()
        
        for rule in rules:
            try:
                if _check_rule(rule, market_context):
                    # Create alert log
                    message = _format_alert_message(rule, market_context)
                    log = AlertLog(
                        alert_rule_id=rule.id,
                        triggered_at=datetime.utcnow(),
                        message=message,
                        acknowledged=False
                    )
                    db.add(log)
                    
                    # Update last triggered
                    rule.last_triggered = datetime.utcnow()
                    
                    # Send notification
                    if rule.notify_via in ("telegram", "both"):
                        _send_telegram_message(message)
                    
                    triggered.append(AlertMatch(rule, message))
                    logger.info(f"Alert triggered: {rule.name}")
            except Exception as e:
                logger.error(f"Error checking rule {rule.id} ({rule.name}): {e}")
        
        db.commit()
    finally:
        db.close()
    
    return triggered


def _check_rule(rule: AlertRule, context: Dict[str, Any]) -> bool:
    """Check if a single rule's condition is met given the market context."""
    condition = rule.condition_type
    params = json.loads(rule.condition_params) if isinstance(rule.condition_params, str) else rule.condition_params
    instrument = rule.instrument
    
    # Instrument filter
    if instrument and instrument != context.get("instrument"):
        return False
    
    if condition == "regime_change":
        return _check_regime_change(rule, context, params)
    elif condition == "setup_generated":
        return _check_setup_generated(rule, context, params)
    elif condition == "cot_change":
        return _check_cot_change(rule, context, params)
    elif condition == "price_cross":
        return _check_price_cross(rule, context, params)
    elif condition == "rsi_level":
        return _check_rsi_level(rule, context, params)
    
    return False


def _check_regime_change(rule: AlertRule, context: Dict[str, Any], params: Dict) -> bool:
    """Regime changed for the instrument."""
    old_regime = context.get("regime_previous")
    new_regime = context.get("regime_current")
    if old_regime and new_regime and old_regime != new_regime:
        # Check if this instrument
        if rule.instrument and rule.instrument != context.get("instrument"):
            return False
        return True
    return False


def _check_setup_generated(rule: AlertRule, context: Dict[str, Any], params: Dict) -> bool:
    """New setup was generated that meets criteria."""
    setup = context.get("new_setup")
    if not setup:
        return False
    
    # Check instrument filter
    if rule.instrument and rule.instrument != setup.get("instrument"):
        return False
    
    # Check min_rr
    min_rr = params.get("min_rr", 0)
    rr = setup.get("risk_reward_ratio", 0)
    if rr < min_rr:
        return False
    
    # Check min_confidence
    min_conf = params.get("min_confidence", 0)
    conf = setup.get("confidence", 0)
    if conf < min_conf:
        return False
    
    return True


def _check_cot_change(rule: AlertRule, context: Dict[str, Any], params: Dict) -> bool:
    """COT net position changed by more than threshold."""
    threshold_pct = params.get("threshold_pct", 20)
    previous_net = context.get("cot_previous_net", 0)
    current_net = context.get("cot_current_net", 0)
    
    if previous_net == 0:
        return False
    
    change_pct = abs((current_net - previous_net) / previous_net * 100)
    return change_pct >= threshold_pct


def _check_price_cross(rule: AlertRule, context: Dict[str, Any], params: Dict) -> bool:
    """Price crossed a level."""
    level = params.get("level")
    direction = params.get("direction", "cross")
    current_price = context.get("current_price")
    previous_price = context.get("previous_price")
    
    if not all([level, current_price, previous_price]):
        return False
    
    level = float(level)
    
    if direction == "above":
        return previous_price <= level < current_price
    elif direction == "below":
        return previous_price >= level > current_price
    else:  # cross
        return (previous_price <= level < current_price) or (previous_price >= level > current_price)


def _check_rsi_level(rule: AlertRule, context: Dict[str, Any], params: Dict) -> bool:
    """RSI entered overbought/oversold zone."""
    zone = params.get("zone", "any")
    level = params.get("level", 70)
    current_rsi = context.get("current_rsi")
    
    if current_rsi is None:
        return False
    
    if zone == "overbought":
        return current_rsi >= level
    elif zone == "oversold":
        return current_rsi <= (100 - level)
    else:  # any
        return current_rsi >= level or current_rsi <= (100 - level)


def test_alert_rule(rule_id: int) -> bool:
    """Send a test notification for an alert rule."""
    db = SessionLocal()
    try:
        rule = db.query(AlertRule).filter(AlertRule.id == rule_id).first()
        if not rule:
            return False
        
        message = _format_alert_message(rule, {
            "instrument": rule.instrument or "EURUSD",
            "current_price": 1.0850,
            "current_rsi": 65,
            "regime_current": "TRENDING_UP",
            "regime_previous": "RANGING"
        })
        
        if rule.notify_via in ("telegram", "both"):
            return _send_telegram_message(message)
        return False
    finally:
        db.close()


# ─── CRUD helpers ─────────────────────────────────────────────────────────────

def get_alert_rules(db: Session, instrument: str = None, enabled: bool = None) -> List[AlertRule]:
    """Get alert rules with optional filters."""
    query = db.query(AlertRule)
    if instrument:
        query = query.filter(AlertRule.instrument == instrument)
    if enabled is not None:
        query = query.filter(AlertRule.enabled == enabled)
    return query.order_by(AlertRule.created_at.desc()).all()


def create_alert_rule(db: Session, rule_data: Dict[str, Any]) -> AlertRule:
    """Create a new alert rule."""
    params = rule_data.get("condition_params", {})
    if isinstance(params, dict):
        params = json.dumps(params)
    
    rule = AlertRule(
        name=rule_data["name"],
        instrument=rule_data.get("instrument"),
        condition_type=rule_data["condition_type"],
        condition_params=params,
        enabled=rule_data.get("enabled", True),
        notify_via=rule_data.get("notify_via", "telegram"),
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


def delete_alert_rule(db: Session, rule_id: int) -> bool:
    """Delete an alert rule."""
    rule = db.query(AlertRule).filter(AlertRule.id == rule_id).first()
    if not rule:
        return False
    db.delete(rule)
    db.commit()
    return True


def get_alert_logs(db: Session, rule_id: int = None, acknowledged: bool = None, limit: int = 50) -> List[AlertLog]:
    """Get alert logs with optional filters."""
    query = db.query(AlertLog)
    if rule_id:
        query = query.filter(AlertLog.alert_rule_id == rule_id)
    if acknowledged is not None:
        query = query.filter(AlertLog.acknowledged == acknowledged)
    return query.order_by(AlertLog.triggered_at.desc()).limit(limit).all()


def acknowledge_alert(db: Session, log_id: int) -> bool:
    """Acknowledge an alert log entry."""
    log = db.query(AlertLog).filter(AlertLog.id == log_id).first()
    if not log:
        return False
    log.acknowledged = True
    db.commit()
    return True
