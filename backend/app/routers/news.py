"""
News API Router
Provides endpoints for browsing, fetching, and managing RSS news.
"""
import asyncio
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.models import NewsItem, NewsSource
from app.schemas.schemas import (
    NewsItemListResponse,
    NewsSourceResponse,
    NewsFetchRequest,
    NewsFetchResponse,
    NewsSourceUpdate,
)
from app.services import rss_news_service as news_service

router = APIRouter(prefix="/news", tags=["news"])


# ─── GET /news/ ────────────────────────────────────────────────────────────────

@router.get("/", response_model=dict)
def list_news(
    category: Optional[str] = Query(None, description="Filter by source category"),
    source: Optional[str] = Query(None, description="Filter by source name"),
    is_read: Optional[bool] = Query(None, description="Filter by read status"),
    is_starred: Optional[bool] = Query(None, description="Filter by starred status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """
    List news items with optional filtering.
    Returns a dict with items and metadata — not a raw list — so we can include total count.
    """
    items, total = news_service.get_news_items(
        db,
        category=category,
        source_name=source,
        is_read=is_read,
        is_starred=is_starred,
        limit=limit,
        offset=offset,
    )

    return {
        "items": [
            {
                "id": item.id,
                "title": item.title,
                "description": item.description,
                "url": item.url,
                "published_at": item.published_at,
                "is_read": item.is_read,
                "is_starred": item.is_starred,
                "tags": item.tags,
                "source_name": item.source.name if item.source else "",
                "source_category": item.source.category if item.source else "",
            }
            for item in items
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


# ─── GET /news/sources ────────────────────────────────────────────────────────

@router.get("/sources", response_model=list[NewsSourceResponse])
def list_sources(
    category: Optional[str] = Query(None),
    enabled: Optional[bool] = Query(None),
    db: Session = Depends(get_db),
):
    """List all configured RSS news sources."""
    return news_service.get_sources(db, category=category, enabled=enabled)


# ─── GET /news/categories ────────────────────────────────────────────────────

@router.get("/categories", response_model=list[str])
def list_categories(db: Session = Depends(get_db)):
    """Get distinct source categories."""
    return news_service.get_categories(db)


# ─── POST /news/fetch ─────────────────────────────────────────────────────────

@router.post("/fetch", response_model=NewsFetchResponse)
async def fetch_news(
    body: Optional[NewsFetchRequest] = None,
    db: Session = Depends(get_db),
):
    """
    Trigger a fetch of RSS feeds.
    If category is provided, only fetches feeds in that category.
    Otherwise fetches all enabled feeds.
    Runs asynchronously — returns immediately with initial status.
    """
    category = body.category if body else None

    # Run the async fetch in a thread pool so it doesn't block
    sources_updated, new_items, errors = await asyncio.to_thread(
        news_service.fetch_all_sources_sync,
        category=category,
        limit_per_source=20,
    )

    return NewsFetchResponse(
        sources_updated=sources_updated,
        new_items=new_items,
        errors=errors,
    )


# ─── PATCH /news/{id}/read ───────────────────────────────────────────────────

@router.patch("/{item_id}/read", response_model=dict)
def mark_read(
    item_id: int,
    is_read: bool = Query(True),
    db: Session = Depends(get_db),
):
    """Mark a news item as read or unread."""
    item = news_service.mark_read(db, item_id, is_read)
    if not item:
        raise HTTPException(status_code=404, detail="News item not found")
    return {"id": item.id, "is_read": item.is_read}


# ─── PATCH /news/{id}/star ───────────────────────────────────────────────────

@router.patch("/{item_id}/star", response_model=dict)
def mark_starred(
    item_id: int,
    is_starred: bool = Query(...),
    db: Session = Depends(get_db),
):
    """Star or unstar a news item."""
    item = news_service.mark_starred(db, item_id, is_starred)
    if not item:
        raise HTTPException(status_code=404, detail="News item not found")
    return {"id": item.id, "is_starred": item.is_starred}


# ─── DELETE /news/ ──────────────────────────────────────────────────────────

@router.delete("/", response_model=dict)
def purge_news(
    days: int = Query(30, ge=1, le=365, description="Delete items older than N days"),
    db: Session = Depends(get_db),
):
    """Purge news items older than `days` days (admin cleanup)."""
    count = news_service.purge_old_items(db, days)
    return {"deleted": count}


# ─── PATCH /news/sources/{id} ────────────────────────────────────────────────

@router.patch("/sources/{source_id}", response_model=NewsSourceResponse)
def update_source(
    source_id: int,
    update: NewsSourceUpdate,
    db: Session = Depends(get_db),
):
    """Enable/disable a news source or update its metadata."""
    from sqlalchemy import select

    source = db.execute(select(NewsSource).where(NewsSource.id == source_id)).scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="News source not found")

    if update.category is not None:
        source.category = update.category
    if update.name is not None:
        source.name = update.name
    if update.url is not None:
        source.url = update.url
    if update.enabled is not None:
        source.enabled = update.enabled

    db.commit()
    db.refresh(source)
    return source
