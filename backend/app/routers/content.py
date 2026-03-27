from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from app.core.database import get_db
from app.models.models import ContentItem, Tag, Instrument
from app.schemas.schemas import (
    ContentItemCreate,
    ContentItemUpdate,
    ContentItemResponse,
    ContentItemListResponse,
    ContentType,
    Direction,
    Timeframe,
    Confidence,
)

router = APIRouter(prefix="/content", tags=["content"])


@router.get("/", response_model=List[ContentItemListResponse])
def get_content_items(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    content_type: Optional[ContentType] = None,
    direction: Optional[Direction] = None,
    timeframe: Optional[Timeframe] = None,
    confidence: Optional[Confidence] = None,
    featured: Optional[bool] = None,
    instrument_id: Optional[int] = None,
    tag_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    """
    Get paginated list of content items with optional filters.
    """
    query = db.query(ContentItem)

    if content_type:
        query = query.filter(ContentItem.content_type == content_type)
    if direction:
        query = query.filter(ContentItem.direction == direction)
    if timeframe:
        query = query.filter(ContentItem.timeframe == timeframe)
    if confidence:
        query = query.filter(ContentItem.confidence == confidence)
    if featured is not None:
        query = query.filter(ContentItem.featured == featured)
    if instrument_id:
        query = query.filter(ContentItem.instrument_id == instrument_id)
    if tag_id:
        query = query.filter(ContentItem.tags.any(Tag.id == tag_id))

    items = (
        query.order_by(ContentItem.published_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    result = []
    for item in items:
        result.append(
            ContentItemListResponse(
                id=item.id,
                title=item.title,
                content_type=item.content_type,
                direction=item.direction,
                timeframe=item.timeframe,
                confidence=item.confidence,
                featured=item.featured,
                published_at=item.published_at,
                entry_zone=item.entry_zone,
                stop_loss=item.stop_loss,
                take_profit=item.take_profit,
                rationale=item.rationale,
                tags=item.tags,
                instrument_symbol=item.instrument.symbol if item.instrument else None,
            )
        )
    return result


@router.get("/{content_id}", response_model=ContentItemResponse)
def get_content_item(content_id: int, db: Session = Depends(get_db)):
    """
    Get a single content item by ID.
    """
    item = db.query(ContentItem).filter(ContentItem.id == content_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Content item not found")
    return item


@router.post("/", response_model=ContentItemResponse, status_code=201)
def create_content_item(
    item_data: ContentItemCreate,
    db: Session = Depends(get_db),
):
    """
    Create a new content item.
    """
    # Validate instrument if provided
    if item_data.instrument_id:
        instrument = (
            db.query(Instrument)
            .filter(Instrument.id == item_data.instrument_id)
            .first()
        )
        if not instrument:
            raise HTTPException(
                status_code=400, detail="Instrument not found"
            )

    # Get tags
    tags = []
    if item_data.tag_ids:
        tags = db.query(Tag).filter(Tag.id.in_(item_data.tag_ids)).all()

    db_item = ContentItem(
        title=item_data.title,
        content_type=item_data.content_type,
        rationale=item_data.rationale,
        instrument_id=item_data.instrument_id,
        direction=item_data.direction,
        entry_zone=item_data.entry_zone,
        stop_loss=item_data.stop_loss,
        take_profit=item_data.take_profit,
        risk_reward_ratio=item_data.risk_reward_ratio,
        timeframe=item_data.timeframe,
        confidence=item_data.confidence,
        featured=item_data.featured,
    )
    db_item.tags = tags

    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item


@router.put("/{content_id}", response_model=ContentItemResponse)
def update_content_item(
    content_id: int,
    item_data: ContentItemUpdate,
    db: Session = Depends(get_db),
):
    """
    Update an existing content item.
    """
    item = db.query(ContentItem).filter(ContentItem.id == content_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Content item not found")

    update_data = item_data.model_dump(exclude_unset=True)
    tag_ids = update_data.pop("tag_ids", None)

    for field, value in update_data.items():
        setattr(item, field, value)

    if tag_ids is not None:
        tags = db.query(Tag).filter(Tag.id.in_(tag_ids)).all()
        item.tags = tags

    item.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(item)
    return item


@router.delete("/{content_id}", status_code=204)
def delete_content_item(content_id: int, db: Session = Depends(get_db)):
    """
    Delete a content item.
    """
    item = db.query(ContentItem).filter(ContentItem.id == content_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Content item not found")

    db.delete(item)
    db.commit()
    return None
