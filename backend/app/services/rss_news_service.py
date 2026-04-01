"""
RSS News Service
Fetches and stores market news from RSS feeds stored in the database.
Feeds are seeded from rss.txt and managed via the NewsSource model.
"""
import asyncio
import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional
from email.utils import parsedate_to_datetime

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from app.core.database import SessionLocal
from app.models.models import NewsSource, NewsItem

logger = logging.getLogger(__name__)

# ─── Parsing helpers ────────────────────────────────────────────────────────

RSS_FEEDS: Dict[str, str] = {}  # Deprecated — kept for backward compat


def _parse_rss_date(date_str: str) -> Optional[datetime]:
    """Parse RSS date string to datetime. Returns None if unparseable."""
    if not date_str:
        return None
    try:
        dt = parsedate_to_datetime(date_str)
        # Ensure we return a naive datetime for SQLite compatibility
        return dt.replace(tzinfo=None) if dt.tzinfo else dt
    except Exception:
        pass
    # Fallback: try ISO 8601 format
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(date_str.strip(), fmt)
            return dt.replace(tzinfo=None) if dt.tzinfo else dt
        except ValueError:
            continue
    return None


def _strip_html(text: str) -> str:
    """Remove HTML tags from text."""
    if not text:
        return ""
    return re.sub(r"<[^>]+>", "", text).strip()


def _parse_rss_feed(xml_content: str, source_name: str) -> List[Dict[str, Any]]:
    """Parse RSS XML content into a list of news item dicts."""
    import xml.etree.ElementTree as ET

    items = []
    try:
        root = ET.fromstring(xml_content)
        for item in root.findall(".//item"):
            title = item.findtext("title", "")
            description = item.findtext("description", "")
            link = item.findtext("link", "")
            pub_date = item.findtext("pubDate", "")
            guid = item.findtext("guid", "")

            # Try content:encoded for full content
            content_encoded = item.findtext("{http://purl.org/rss/1.0/modules/content/}encoded")
            if content_encoded:
                description = content_encoded

            description = _strip_html(description or "")[:500]

            items.append({
                "title": (title or "").strip()[:500],
                "description": description,
                "url": (link or guid or "").strip(),
                "published_at": _parse_rss_date(pub_date),
                "source_name": source_name,
            })
    except ET.ParseError as e:
        logger.warning(f"Failed to parse RSS feed: {e}")
    except Exception as e:
        logger.warning(f"Error processing RSS feed: {e}")
    return items


# ─── Fetching ────────────────────────────────────────────────────────────────

async def _fetch_single_feed(
    client: httpx.AsyncClient,
    source: NewsSource,
    semaphore: asyncio.Semaphore,
) -> tuple[NewsSource, List[Dict[str, Any]], Optional[str]]:
    """Fetch one RSS feed. Returns (source, items, error_message)."""
    async with semaphore:
        try:
            response = await client.get(source.url, timeout=15.0, follow_redirects=True)
            response.raise_for_status()
            items = _parse_rss_feed(response.text, source.name)
            return (source, items, None)
        except httpx.TimeoutException:
            return (source, [], f"Timeout after 15s")
        except httpx.HTTPStatusError as e:
            return (source, [], f"HTTP {e.response.status_code}")
        except Exception as e:
            return (source, [], str(e))


async def fetch_all_sources(
    db: DBSession,
    category: Optional[str] = None,
    limit_per_source: int = 20,
) -> tuple[int, int, int]:
    """
    Fetch all enabled RSS sources (optionally filtered by category).
    Stores new items in DB. Deduplication via unique constraint on (source_id, url).

    Returns (sources_updated, new_items_stored, error_count).
    """
    # Build query for sources to fetch
    query = select(NewsSource).where(NewsSource.enabled == True)
    if category:
        query = query.where(NewsSource.category == category)
    sources = db.execute(query).scalars().all()

    if not sources:
        return (0, 0, 0)

    semaphore = asyncio.Semaphore(10)  # max 10 concurrent fetches
    async with httpx.AsyncClient() as client:
        tasks = [
            _fetch_single_feed(client, source, semaphore)
            for source in sources
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    sources_updated = 0
    new_items = 0
    errors = 0

    for result in results:
        if isinstance(result, Exception):
            errors += 1
            continue

        source, items, error = result

        if error:
            source.last_error = error[:500]
            source.last_fetched_at = datetime.utcnow()
            errors += 1
            continue

        # Store new items
        stored = 0
        for item_data in items[:limit_per_source]:
            try:
                # Check for duplicate
                existing = db.execute(
                    select(NewsItem).where(
                        NewsItem.source_id == source.id,
                        NewsItem.url == item_data["url"]
                    )
                ).scalar_one_or_none()

                if existing is None:
                    pub_at = item_data.get("published_at")
                    # Ensure published_at is a proper datetime or None
                    if pub_at and not isinstance(pub_at, datetime):
                        pub_at = None
                    news_item = NewsItem(
                        source_id=source.id,
                        title=item_data["title"],
                        description=item_data.get("description"),
                        url=item_data["url"],
                        published_at=pub_at,
                        fetched_at=datetime.utcnow(),
                        tags=source.category.lower(),
                    )
                    db.add(news_item)
                    stored += 1
            except Exception as e:
                logger.warning(f"Error storing news item: {e}")

        source.fetch_count = (source.fetch_count or 0) + 1
        source.last_fetched_at = datetime.utcnow()
        source.last_error = None
        sources_updated += 1
        new_items += stored

    db.commit()
    return (sources_updated, new_items, errors)


# ─── DB queries ─────────────────────────────────────────────────────────────

def get_news_items(
    db: DBSession,
    category: Optional[str] = None,
    source_name: Optional[str] = None,
    is_read: Optional[bool] = None,
    is_starred: Optional[bool] = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[List[NewsItem], int]:
    """Get paginated news items with optional filters. Returns (items, total_count)."""
    query = select(NewsItem).join(NewsSource)

    if category:
        query = query.where(NewsSource.category == category)
    if source_name:
        query = query.where(NewsSource.name == source_name)
    if is_read is not None:
        query = query.where(NewsItem.is_read == is_read)
    if is_starred is not None:
        query = query.where(NewsItem.is_starred == is_starred)

    # Total count (before pagination)
    count_query = select(NewsItem.id).join(NewsSource)
    if category:
        count_query = count_query.where(NewsSource.category == category)
    if source_name:
        count_query = count_query.where(NewsSource.name == source_name)
    if is_read is not None:
        count_query = count_query.where(NewsItem.is_read == is_read)
    if is_starred is not None:
        count_query = count_query.where(NewsItem.is_starred == is_starred)
    total = len(db.execute(count_query).scalars().all())

    items = (
        db.execute(
            query.order_by(NewsItem.published_at.desc().nullsfirst())
            .offset(offset)
            .limit(limit)
        )
        .scalars()
        .all()
    )
    return (list(items), total)


def get_sources(
    db: DBSession,
    category: Optional[str] = None,
    enabled: Optional[bool] = None,
) -> List[NewsSource]:
    """Get news sources with optional filters."""
    query = select(NewsSource)
    if category:
        query = query.where(NewsSource.category == category)
    if enabled is not None:
        query = query.where(NewsSource.enabled == enabled)
    return list(db.execute(query.order_by(NewsSource.category, NewsSource.name)).scalars().all())


def get_categories(db: DBSession) -> List[str]:
    """Get distinct source categories."""
    result = db.execute(
        select(NewsSource.category).distinct().order_by(NewsSource.category)
    ).scalars().all()
    return list(result)


def mark_read(db: DBSession, item_id: int, is_read: bool = True) -> Optional[NewsItem]:
    item = db.execute(select(NewsItem).where(NewsItem.id == item_id)).scalar_one_or_none()
    if item:
        item.is_read = is_read
        db.commit()
    return item


def mark_starred(db: DBSession, item_id: int, is_starred: bool) -> Optional[NewsItem]:
    item = db.execute(select(NewsItem).where(NewsItem.id == item_id)).scalar_one_or_none()
    if item:
        item.is_starred = is_starred
        db.commit()
    return item


def purge_old_items(db: DBSession, days: int = 30) -> int:
    """Delete news items older than `days` days. Returns count deleted."""
    from datetime import timedelta
    cutoff = datetime.utcnow() - timedelta(days=days)
    count = db.execute(
        NewsItem.__table__.delete().where(NewsItem.fetched_at < cutoff)
    ).rowcount
    db.commit()
    return count


# ─── Seed from CSV ───────────────────────────────────────────────────────────

def seed_sources_from_csv(csv_path: str, db: DBSession) -> tuple[int, int]:
    """
    Seed NewsSource rows from a CSV with columns: Category,Name,RSS URL.
    Skips URLs that already exist. Returns (inserted, skipped).
    """
    import csv

    inserted = 0
    skipped = 0

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            category = row.get("Category", "").strip()
            name = row.get("Name", "").strip()
            url = row.get("RSS URL", "").strip()

            if not url or not name:
                skipped += 1
                continue

            # Check if already exists
            existing = db.execute(
                select(NewsSource).where(NewsSource.url == url)
            ).scalar_one_or_none()

            if existing:
                skipped += 1
                continue

            source = NewsSource(category=category, name=name, url=url, enabled=True)
            db.add(source)
            inserted += 1

    db.commit()
    return (inserted, skipped)


# ─── Sync wrapper ─────────────────────────────────────────────────────────────

def fetch_all_sources_sync(
    category: Optional[str] = None,
    limit_per_source: int = 20,
) -> tuple[int, int, int]:
    """Synchronous wrapper for fetch_all_sources."""
    db = SessionLocal()
    try:
        return asyncio.run(fetch_all_sources(db, category, limit_per_source))
    finally:
        db.close()


async def get_fxstreet_news_async(limit: int = 15) -> List[Dict[str, Any]]:
    """Async version — use this in async contexts (e.g. data_aggregator)."""
    db = SessionLocal()
    try:
        sources = get_sources(db, category="Forex")
        if not sources:
            return []
        fx_sources = [s for s in sources if "fxstreet" in s.name.lower()]
        if not fx_sources:
            return []

        semaphore = asyncio.Semaphore(3)
        async with httpx.AsyncClient() as client:
            tasks = [_fetch_single_feed(client, s, semaphore) for s in fx_sources]
            results = await asyncio.gather(*tasks, return_exceptions=True)
        all_items = []
        for r in results:
            if isinstance(r, tuple):
                _, items, _ = r
                all_items.extend(items)

        dated = [i for i in all_items if i.get("published_at")]
        undated = [i for i in all_items if not i.get("published_at")]
        dated.sort(key=lambda x: x["published_at"], reverse=True)
        return (dated + undated)[:limit]
    finally:
        db.close()


# Backward-compatible alias — returns raw dicts, doesn't store to DB
def get_fxstreet_news(limit: int = 15) -> List[Dict[str, Any]]:
    """Deprecated: use get_fxstreet_news_async() instead. Returns raw dicts."""
    import asyncio
    db = SessionLocal()
    try:
        sources = get_sources(db, category="Forex")
        if not sources:
            return []
        # Fetch only fxstreet sources
        fx_sources = [s for s in sources if "fxstreet" in s.name.lower()]
        if not fx_sources:
            return []

        async def _fetch():
            semaphore = asyncio.Semaphore(3)
            async with httpx.AsyncClient() as client:
                tasks = [_fetch_single_feed(client, s, semaphore) for s in fx_sources]
                results = await asyncio.gather(*tasks, return_exceptions=True)
            all_items = []
            for r in results:
                if isinstance(r, tuple):
                    _, items, _ = r
                    all_items.extend(items)
            return all_items

        all_items = asyncio.run(_fetch())
        dated = [i for i in all_items if i.get("published_at")]
        undated = [i for i in all_items if not i.get("published_at")]
        dated.sort(key=lambda x: x["published_at"], reverse=True)
        return (dated + undated)[:limit]
    finally:
        db.close()


def get_fxstreet_news_sync(limit: int = 15) -> List[Dict[str, Any]]:
    """Synchronous wrapper for backward compatibility."""
    return get_fxstreet_news(limit)
