"""
Content Pipeline Orchestration
Runs the AI content generation pipeline, coordinating data aggregation,
LLM generation, and database persistence.
"""
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import text

from app.core.database import get_db_context
from app.models.models import ContentItem, ContentType, Direction, Timeframe, Confidence

logger = logging.getLogger(__name__)


def _utcnow():
    return datetime.utcnow()


def _get_instrument_id(db, symbol: str) -> Optional[int]:
    """Look up instrument ID by symbol, return None if not found."""
    try:
        result = db.execute(
            text("SELECT id FROM instruments WHERE symbol = :symbol LIMIT 1"),
            {"symbol": symbol.upper()}
        ).fetchone()
        return result[0] if result else None
    except Exception as e:
        logger.warning(f"Could not find instrument {symbol}: {e}")
        return None


def _get_or_create_tag(db, tag_name: str) -> int:
    """Get or create a tag and return its ID."""
    from app.models.models import Tag
    tag = db.query(Tag).filter(Tag.name == tag_name).first()
    if tag:
        return tag.id
    tag = Tag(name=tag_name)
    db.add(tag)
    db.flush()
    return tag.id


def _store_content_item(db, content_dict: dict) -> ContentItem:
    """
    Persist a content generator dict as a ContentItem row.

    Args:
        content_dict: Must contain content_type, title, rationale.
        For setups: also direction, instrument, entry_zone, sl, tp, timeframe, confidence, tags.

    Returns:
        Created ContentItem instance.
    """
    content_type_str = content_dict.get("content_type", "")
    content_type = ContentType(content_type_str)

    # Map direction string to enum
    direction_str = content_dict.get("direction", "neutral")
    try:
        direction = Direction(direction_str)
    except (ValueError, TypeError):
        direction = Direction.NEUTRAL

    # Timeframe
    timeframe_str = content_dict.get("timeframe", "D1")
    try:
        timeframe = Timeframe(timeframe_str.lower())
    except (ValueError, TypeError):
        timeframe = Timeframe.D1

    # Confidence
    confidence_str = content_dict.get("confidence", "medium")
    try:
        confidence = Confidence(confidence_str.lower())
    except (ValueError, TypeError):
        confidence = Confidence.MEDIUM

    # Build ContentItem
    item = ContentItem(
        title=content_dict.get("title", "Untitled"),
        content_type=content_type,
        direction=direction if content_type in (ContentType.SETUP, ContentType.BRIEFING, ContentType.CONTRARIAN_ALERT) else None,
        entry_zone=content_dict.get("entry_zone"),
        stop_loss=content_dict.get("sl"),
        take_profit=content_dict.get("tp"),
        risk_reward_ratio=content_dict.get("risk_reward_ratio"),
        timeframe=timeframe if content_type == ContentType.SETUP else None,
        confidence=confidence,
        rationale=content_dict.get("rationale", ""),
        featured=content_dict.get("featured", False),
        published_at=_utcnow(),
    )

    # Link instrument
    instrument_symbol = content_dict.get("instrument")
    if instrument_symbol and instrument_symbol.lower() != "multi":
        item.instrument_id = _get_instrument_id(db, instrument_symbol)

    db.add(item)
    db.flush()

    # Handle tags
    tags = content_dict.get("tags", [])
    if content_type == ContentType.MACRO_ROUNDUP:
        tags = ["macro-driven"]
    elif content_type == ContentType.CONTRARIAN_ALERT:
        tags = ["contrarian"]

    for tag_name in tags:
        tag_id = _get_or_create_tag(db, tag_name)
        # Insert into content_tags
        db.execute(
            text("INSERT INTO content_tags (content_item_id, tag_id) VALUES (:item_id, :tag_id)"),
            {"item_id": item.id, "tag_id": tag_id}
        )

    db.commit()
    logger.info(f"Stored content item: id={item.id}, type={content_type.value}, title={item.title}")
    return item


# ---------------------------------------------------------------------------
# Pipeline Functions
# ---------------------------------------------------------------------------

async def run_morning_briefing_pipeline(instrument: Optional[str] = None) -> List[ContentItem]:
    """
    Run the morning briefing pipeline:
    1. Fetch market context
    2. Generate morning briefing(s) via LLM
    3. Store in database

    Args:
        instrument: Optional specific instrument. If None, generates for top 3.

    Returns:
        List of created ContentItem records.
    """
    from app.services.data_aggregator import get_market_context
    from app.services.content_generators import generate_morning_briefing

    logger.info(f"Starting morning briefing pipeline (instrument={instrument})")

    # Fetch data
    market_context = await get_market_context()
    logger.info("Market context fetched successfully")

    # Generate briefing(s)
    briefing = await generate_morning_briefing(market_context, instrument)

    # Store in DB
    items = []
    with get_db_context() as db:
        item = _store_content_item(db, briefing)
        items.append(item)

    logger.info(f"Morning briefing pipeline complete: {len(items)} items generated")
    return items


async def run_setup_pipeline(instrument: str) -> Optional[ContentItem]:
    """
    Run the trade setup pipeline for a specific instrument:
    1. Fetch market context
    2. Generate trade setup via LLM
    3. Store in database (only if R:R >= 1.5:1)

    Returns:
        Created ContentItem, or None if no valid setup found.
    """
    from app.services.data_aggregator import get_market_context
    from app.services.content_generators import generate_trade_setup

    logger.info(f"Starting trade setup pipeline for {instrument}")

    market_context = await get_market_context()
    logger.info("Market context fetched successfully")

    setup = await generate_trade_setup(market_context, instrument)

    if not setup:
        logger.info(f"No valid setup generated for {instrument} (R:R < 1.5 or parsing failed)")
        return None

    with get_db_context() as db:
        item = _store_content_item(db, setup)
        logger.info(f"Trade setup pipeline complete: {item.title}")
        return item


async def run_macro_roundup_pipeline() -> ContentItem:
    """
    Run the macro roundup pipeline:
    1. Fetch market context
    2. Generate weekly macro roundup via LLM
    3. Store in database

    Returns:
        Created ContentItem record.
    """
    from app.services.data_aggregator import get_market_context
    from app.services.content_generators import generate_macro_roundup

    logger.info("Starting macro roundup pipeline")

    market_context = await get_market_context()
    logger.info("Market context fetched successfully")

    roundup = await generate_macro_roundup(market_context)

    with get_db_context() as db:
        item = _store_content_item(db, roundup)
        logger.info(f"Macro roundup pipeline complete: {item.title}")
        return item


async def run_contrarian_check_pipeline(instrument: str) -> Optional[ContentItem]:
    """
    Run the contrarian alert check pipeline:
    1. Fetch market context
    2. Check if positioning is extreme
    3. If extreme, generate contrarian alert and store

    Returns:
        Created ContentItem, or None if positioning not extreme.
    """
    from app.services.data_aggregator import get_market_context
    from app.services.content_generators import generate_contrarian_alert

    logger.info(f"Starting contrarian check pipeline for {instrument}")

    market_context = await get_market_context()
    logger.info("Market context fetched successfully")

    alert = await generate_contrarian_alert(market_context, instrument)

    if not alert:
        logger.info(f"No contrarian alert generated for {instrument} (positioning not extreme)")
        return None

    with get_db_context() as db:
        item = _store_content_item(db, alert)
        logger.info(f"Contrarian alert pipeline complete: {item.title}")
        return item


async def run_full_daily_pipeline() -> Dict[str, List[ContentItem]]:
    """
    Run the complete daily content pipeline in sequence:
    1. Morning briefings (EURUSD, XAUUSD, BTC)
    2. Trade setups (EURUSD, XAUUSD, BTC)
    3. Macro roundup
    4. Contrarian checks (EURUSD, XAUUSD, BTC)

    Returns:
        Dict mapping pipeline name -> list of generated ContentItems.
    """
    logger.info("Starting FULL DAILY PIPELINE")

    results = {
        "briefings": [],
        "setups": [],
        "roundup": None,
        "contrarian": [],
    }

    top_instruments = ["EURUSD", "XAUUSD", "BTC"]

    # 1. Morning briefings
    logger.info("=== PHASE 1: Morning Briefings ===")
    for instrument in top_instruments:
        try:
            items = await run_morning_briefing_pipeline(instrument=instrument)
            results["briefings"].extend(items)
        except Exception as e:
            logger.error(f"Morning briefing failed for {instrument}: {e}")

    # 2. Trade setups
    logger.info("=== PHASE 2: Trade Setups ===")
    for instrument in top_instruments:
        try:
            item = await run_setup_pipeline(instrument)
            if item:
                results["setups"].append(item)
        except Exception as e:
            logger.error(f"Trade setup failed for {instrument}: {e}")

    # 3. Macro roundup
    logger.info("=== PHASE 3: Macro Roundup ===")
    try:
        item = await run_macro_roundup_pipeline()
        results["roundup"] = item
    except Exception as e:
        logger.error(f"Macro roundup failed: {e}")

    # 4. Contrarian checks
    logger.info("=== PHASE 4: Contrarian Checks ===")
    for instrument in top_instruments:
        try:
            item = await run_contrarian_check_pipeline(instrument)
            if item:
                results["contrarian"].append(item)
        except Exception as e:
            logger.error(f"Contrarian check failed for {instrument}: {e}")

    total = (
        len(results["briefings"])
        + len(results["setups"])
        + (1 if results["roundup"] else 0)
        + len(results["contrarian"])
    )
    logger.info(f"=== FULL DAILY PIPELINE COMPLETE: {total} content items generated ===")
    return results
