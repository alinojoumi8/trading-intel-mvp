"""
Admin Router — AI Content Generation Pipeline
Provides endpoints for triggering AI content generation manually.
"""
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.services.content_pipeline import (
    run_morning_briefing_pipeline,
    run_setup_pipeline,
    run_macro_roundup_pipeline,
    run_contrarian_check_pipeline,
    run_full_daily_pipeline,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/generate", tags=["admin"])


class ContentItemResponse(BaseModel):
    id: int
    title: str
    content_type: str
    direction: Optional[str]
    instrument: Optional[str]
    rationale: str
    confidence: Optional[str]
    timeframe: Optional[str]
    entry_zone: Optional[str]
    stop_loss: Optional[str]
    take_profit: Optional[str]
    risk_reward_ratio: Optional[float]
    featured: bool
    published_at: str

    class Config:
        from_attributes = True


class PipelineResponse(BaseModel):
    items: list[ContentItemResponse]
    message: str


class FullPipelineResponse(BaseModel):
    briefings: list[ContentItemResponse]
    setups: list[ContentItemResponse]
    roundup: Optional[ContentItemResponse]
    contrarian: list[ContentItemResponse]
    total_count: int
    message: str


def _serialize_item(item) -> dict:
    """Serialize a ContentItem model to a dict for JSON response."""
    return {
        "id": item.id,
        "title": item.title,
        "content_type": item.content_type.value if hasattr(item.content_type, "value") else str(item.content_type),
        "direction": item.direction.value if item.direction else None,
        "instrument": item.instrument.symbol if item.instrument else None,
        "rationale": item.rationale,
        "confidence": item.confidence.value if item.confidence else None,
        "timeframe": item.timeframe.value if item.timeframe else None,
        "entry_zone": item.entry_zone,
        "stop_loss": item.stop_loss,
        "take_profit": item.take_profit,
        "risk_reward_ratio": item.risk_reward_ratio,
        "featured": item.featured,
        "published_at": item.published_at.isoformat() if item.published_at else None,
    }


@router.post("/briefing", response_model=FullPipelineResponse)
async def generate_briefing(
    instrument: Optional[str] = Query(None, description="Optional specific instrument (e.g., EURUSD)")
):
    """
    Trigger morning briefing generation.
    If no instrument is specified, generates briefings for top 3 instruments.
    """
    try:
        items = await run_morning_briefing_pipeline(instrument=instrument)
        serialized = [_serialize_item(i) for i in items]
        return FullPipelineResponse(
            briefings=serialized,
            setups=[],
            roundup=None,
            contrarian=[],
            total_count=len(serialized),
            message=f"{len(serialized)} briefing(s) generated successfully",
        )
    except Exception as e:
        logger.error(f"Briefing generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Briefing generation failed: {str(e)}")


@router.post("/setup", response_model=PipelineResponse)
async def generate_setup(
    instrument: str = Query(..., description="Instrument symbol (e.g., EURUSD, XAUUSD, BTC)")
):
    """
    Trigger trade setup generation for a specific instrument.
    Only generates if R:R >= 1.5:1.
    """
    if not instrument:
        raise HTTPException(status_code=400, detail="instrument query parameter is required")

    try:
        item = await run_setup_pipeline(instrument=instrument)
        if item is None:
            return PipelineResponse(
                items=[],
                message=f"No valid setup generated for {instrument} (R:R < 1.5:1 or parsing failed)",
            )
        return PipelineResponse(
            items=[_serialize_item(item)],
            message=f"Trade setup generated for {instrument}",
        )
    except Exception as e:
        logger.error(f"Setup generation failed for {instrument}: {e}")
        raise HTTPException(status_code=500, detail=f"Setup generation failed: {str(e)}")


@router.post("/roundup", response_model=PipelineResponse)
async def generate_roundup():
    """Trigger weekly macro roundup generation."""
    try:
        item = await run_macro_roundup_pipeline()
        return PipelineResponse(
            items=[_serialize_item(item)],
            message="Macro roundup generated successfully",
        )
    except Exception as e:
        logger.error(f"Macro roundup generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Macro roundup generation failed: {str(e)}")


@router.post("/contrarian", response_model=PipelineResponse)
async def generate_contrarian(
    instrument: str = Query(..., description="Instrument symbol (e.g., EURUSD, XAUUSD, BTC)")
):
    """
    Trigger contrarian alert check for a specific instrument.
    Only generates if COT or sentiment shows extreme positioning.
    """
    if not instrument:
        raise HTTPException(status_code=400, detail="instrument query parameter is required")

    try:
        item = await run_contrarian_check_pipeline(instrument=instrument)
        if item is None:
            return PipelineResponse(
                items=[],
                message=f"No contrarian alert for {instrument} (positioning not extreme)",
            )
        return PipelineResponse(
            items=[_serialize_item(item)],
            message=f"Contrarian alert generated for {instrument}",
        )
    except Exception as e:
        logger.error(f"Contrarian check failed for {instrument}: {e}")
        raise HTTPException(status_code=500, detail=f"Contrarian check failed: {str(e)}")


@router.post("/full", response_model=FullPipelineResponse)
async def generate_full():
    """
    Run the complete daily pipeline:
    - Morning briefings for EURUSD, XAUUSD, BTC
    - Trade setups for EURUSD, XAUUSD, BTC
    - Weekly macro roundup
    - Contrarian checks for EURUSD, XAUUSD, BTC
    """
    try:
        results = await run_full_daily_pipeline()

        def serialize_or_none(item):
            return _serialize_item(item) if item else None

        return FullPipelineResponse(
            briefings=[_serialize_item(i) for i in results["briefings"]],
            setups=[_serialize_item(i) for i in results["setups"]],
            roundup=serialize_or_none(results["roundup"]),
            contrarian=[_serialize_item(i) for i in results["contrarian"]],
            total_count=(
                len(results["briefings"])
                + len(results["setups"])
                + (1 if results["roundup"] else 0)
                + len(results["contrarian"])
            ),
            message="Full daily pipeline completed",
        )
    except Exception as e:
        logger.error(f"Full pipeline failed: {e}")
        raise HTTPException(status_code=500, detail=f"Full pipeline failed: {str(e)}")
