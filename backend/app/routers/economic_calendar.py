"""
Economic Calendar API Router
Manages economic events that impact market trading (FOMC, NFP, CPI, GDP, etc.)
"""
from datetime import datetime, timedelta
from typing import Optional, List

from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel
from sqlalchemy import desc, and_
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.models import EconEvent

router = APIRouter(prefix="/economic-calendar", tags=["economic-calendar"])


# ─── Schemas ───────────────────────────────────────────────────────────────────

class EconEventBase(BaseModel):
    event_date: datetime
    country: str
    event_name: str
    importance: str = "medium"
    currency: str
    previous: Optional[str] = None
    forecast: Optional[str] = None
    actual: Optional[str] = None
    impact: str = "medium"
    source: str = "manual"


class EconEventCreate(EconEventBase):
    pass


class EconEventUpdate(BaseModel):
    event_date: Optional[datetime] = None
    country: Optional[str] = None
    event_name: Optional[str] = None
    importance: Optional[str] = None
    currency: Optional[str] = None
    previous: Optional[str] = None
    forecast: Optional[str] = None
    actual: Optional[str] = None
    impact: Optional[str] = None
    source: Optional[str] = None


class EconEventResponse(EconEventBase):
    id: int
    scraped_at: datetime
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class EconEventListResponse(BaseModel):
    items: List[EconEventResponse]
    total: int
    limit: int
    offset: int


class EconScrapeResponse(BaseModel):
    success: bool
    events_created: int
    events_updated: int
    errors: List[str]


# ─── Impact Mapping ───────────────────────────────────────────────────────────

# Maps economic events to typically affected instruments
EVENT_IMPACT_MAP = {
    "FOMC Rate Decision": ["DXY", "USD", "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD"],
    "Non-Farm Payrolls": ["DXY", "USD", "EURUSD", "GBPUSD", "USDJPY"],
    "CPI (YoY)": ["DXY", "USD", "US10Y", "US2Y"],
    "Core CPI (YoY)": ["DXY", "USD", "US10Y", "US2Y"],
    "GDP (QoQ)": ["DXY", "USD", "EURUSD", "GBPUSD"],
    "ECB Rate Decision": ["EUR", "EURUSD", "GBPEUR"],
    "BoE Rate Decision": ["GBP", "GBPUSD", "EURGBP"],
    "BoJ Rate Decision": ["JPY", "USDJPY", "EURJPY", "GBPJPY"],
    "RBA Rate Decision": ["AUD", "AUDUSD", "EURAUD"],
    "Unemployment Rate": ["DXY", "USD", "AUDUSD"],
    "Retail Sales": ["DXY", "USD", "AUDUSD"],
    "Consumer Confidence": ["DXY", "USD"],
    "ISM Manufacturing PMI": ["DXY", "USD", "EURUSD"],
    "Au Unemployment Rate": ["AUD", "AUDUSD"],
    "UK GDP (QoQ)": ["GBP", "GBPUSD", "EURGBP"],
    "Employment Change": ["CAD", "USDCAD", "AUDUSD"],
    "Manufacturing PMI": ["EUR", "GBP", "USD"],
    "Services PMI": ["EUR", "GBP", "USD"],
    "Trade Balance": ["AUD", "CAD", "NZD"],
    "Current Account": ["EUR", "GBP", "JPY"],
}


def get_impacted_instruments(event_name: str) -> List[str]:
    """Get list of instruments typically impacted by an event."""
    return EVENT_IMPACT_MAP.get(event_name, [])


# ─── Seed Data ────────────────────────────────────────────────────────────────

KNOWN_EVENTS = [
    {"event_name": "FOMC Rate Decision", "country": "US", "currency": "USD", "importance": "high", "impact": "high"},
    {"event_name": "Non-Farm Payrolls", "country": "US", "currency": "USD", "importance": "high", "impact": "high"},
    {"event_name": "CPI (YoY)", "country": "US", "currency": "USD", "importance": "high", "impact": "high"},
    {"event_name": "ECB Rate Decision", "country": "EU", "currency": "EUR", "importance": "high", "impact": "high"},
    {"event_name": "GDP (QoQ)", "country": "US", "currency": "USD", "importance": "medium", "impact": "medium"},
    {"event_name": "ISM Manufacturing PMI", "country": "US", "currency": "USD", "importance": "medium", "impact": "medium"},
    {"event_name": "BoE Rate Decision", "country": "UK", "currency": "GBP", "importance": "high", "impact": "high"},
    {"event_name": "BoJ Rate Decision", "country": "JP", "currency": "JPY", "importance": "high", "impact": "high"},
    {"event_name": "RBA Rate Decision", "country": "AU", "currency": "AUD", "importance": "high", "impact": "medium"},
    {"event_name": "Unemployment Rate", "country": "US", "currency": "USD", "importance": "medium", "impact": "medium"},
    {"event_name": "Retail Sales", "country": "US", "currency": "USD", "importance": "medium", "impact": "medium"},
    {"event_name": "Consumer Confidence", "country": "US", "currency": "USD", "importance": "low", "impact": "low"},
    {"event_name": "Core CPI (YoY)", "country": "EU", "currency": "EUR", "importance": "medium", "impact": "medium"},
    {"event_name": "Au Unemployment Rate", "country": "AU", "currency": "AUD", "importance": "medium", "impact": "medium"},
    {"event_name": "UK GDP (QoQ)", "country": "UK", "currency": "GBP", "importance": "medium", "impact": "medium"},
]


def seed_known_events(db: Session) -> int:
    """Seed the database with known recurring high-impact events."""
    now = datetime.utcnow()
    count = 0

    for i, event_data in enumerate(KNOWN_EVENTS):
        # Schedule events over the next 30 days (spread them out)
        days_offset = (i % 30) + 1
        event_date = (now + timedelta(days=days_offset)).replace(
            hour=14, minute=0, second=0, microsecond=0
        )
        # FOMC and major central bank events typically at 14:00 or 19:00 UTC
        if "Rate Decision" in event_data["event_name"]:
            event_date = event_date.replace(hour=19, minute=0)
        # US events typically at 13:30 or 14:30 UTC
        elif event_data["country"] == "US":
            event_date = event_date.replace(hour=13, minute=30)
        # UK/EU events typically at 09:00 or 10:00 UTC
        elif event_data["country"] in ("UK", "EU"):
            event_date = event_date.replace(hour=9, minute=0)
        # Japan at various times
        elif event_data["country"] == "JP":
            event_date = event_date.replace(hour=3, minute=0)
        # Australia typically at 02:00 or 03:00 UTC
        elif event_data["country"] == "AU":
            event_date = event_date.replace(hour=2, minute=30)

        # Check if event already exists for this date range
        existing = db.query(EconEvent).filter(
            EconEvent.event_name == event_data["event_name"],
            EconEvent.event_date >= event_date.replace(hour=0, minute=0, second=0),
            EconEvent.event_date <= event_date.replace(hour=23, minute=59, second=59),
        ).first()

        if not existing:
            event = EconEvent(
                event_date=event_date,
                country=event_data["country"],
                event_name=event_data["event_name"],
                importance=event_data["importance"],
                currency=event_data["currency"],
                impact=event_data["impact"],
                source="manual",
            )
            db.add(event)
            count += 1

    db.commit()
    return count


# ─── Scraping ─────────────────────────────────────────────────────────────────

async def scrape_fxstreet_calendar() -> List[dict]:
    """
    Scrape economic calendar events from FXStreet.
    Returns list of event dicts.
    """
    try:
        import httpx
        from bs4 import BeautifulSoup

        url = "https://www.fxstreet.com/economic-calendar"
        headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }

        response = httpx.get(url, headers=headers, timeout=30.0)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        events = []

        # FXStreet typically structures events in table rows with data attributes
        # Look for patterns like data-event-name, data-country, data-datetime
        rows = soup.select("tr[data-event]")

        country_map = {
            "US": ("USD", "US"),
            "United States": ("USD", "US"),
            "EU": ("EUR", "EU"),
            "Euro Zone": ("EUR", "EU"),
            "Eurozone": ("EUR", "EU"),
            "UK": ("GBP", "UK"),
            "United Kingdom": ("GBP", "UK"),
            "Japan": ("JPY", "JP"),
            "Australia": ("AUD", "AU"),
            "Canada": ("CAD", "CA"),
            "New Zealand": ("NZD", "NZ"),
            "Switzerland": ("CHF", "CH"),
        }

        importance_map = {
            "high": "high",
            "medium": "medium",
            "low": "low",
            "3": "high",
            "2": "medium",
            "1": "low",
        }

        for row in rows:
            try:
                event_name = row.get("data-event", "").strip()
                if not event_name:
                    continue

                datetime_str = row.get("data-datetime", "")
                country_name = row.get("data-country", "").strip()
                importance_val = row.get("data-importance", "2")

                # Parse datetime
                event_date = None
                if datetime_str:
                    try:
                        event_date = datetime.fromisoformat(datetime_str.replace("Z", "+00:00"))
                    except (ValueError, TypeError):
                        pass

                if not event_date:
                    continue

                # Map country to currency and code
                currency, country_code = country_map.get(country_name, ("USD", "US"))

                # Map importance
                importance = importance_map.get(str(importance_val).lower(), "medium")

                events.append({
                    "event_date": event_date,
                    "country": country_code,
                    "event_name": event_name,
                    "importance": importance,
                    "currency": currency,
                    "impact": importance,
                    "source": "fxstreet",
                })
            except Exception:
                continue

        return events

    except Exception as e:
        return []


async def scrape_investing_calendar() -> List[dict]:
    """
    Try to scrape from investing.com economic calendar widget API.
    """
    try:
        import httpx
        import json

        # Investing.com has an API endpoint for their economic calendar widget
        url = "https://api.investing.com/api/calendar/calendar"
        headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
            "Accept": "application/json",
            "Referer": "https://www.investing.com/economic-calendar/",
        }

        # Calculate date range (today + next 7 days)
        today = datetime.utcnow()
        date_from = today.strftime("%Y-%m-%d")
        date_to = (today + timedelta(days=7)).strftime("%Y-%m-%d")

        params = {
            "dateFrom": date_from,
            "dateTo": date_to,
            "importance": "1,2,3",
        }

        response = httpx.get(url, headers=headers, params=params, timeout=30.0)
        response.raise_for_status()

        data = response.json()

        events = []
        country_map = {
            "US": ("USD", "US"),
            "United States": ("USD", "US"),
            "EU": ("EUR", "EU"),
            "Euro Zone": ("EUR", "EU"),
            "UK": ("GBP", "UK"),
            "United Kingdom": ("GBP", "UK"),
            "Japan": ("JPY", "JP"),
            "Australia": ("AUD", "AU"),
            "Canada": ("CAD", "CA"),
        }

        for item in data.get("data", []):
            try:
                event_name = item.get("event_name", "")
                country_name = item.get("country", "")
                importance = item.get("importance", "medium")
                event_date_str = item.get("date", "")

                if not event_name or not event_date_str:
                    continue

                event_date = datetime.fromisoformat(event_date_str.replace("Z", "+00:00"))
                currency, country_code = country_map.get(country_name, ("USD", "US"))

                events.append({
                    "event_date": event_date,
                    "country": country_code,
                    "event_name": event_name,
                    "importance": importance,
                    "currency": currency,
                    "impact": importance,
                    "source": "investing",
                })
            except Exception:
                continue

        return events

    except Exception:
        return []


async def scrape_alpha_vantage_events() -> List[dict]:
    """
    Try Alpha Vantage economic indicators as secondary source.
    """
    try:
        from app.core.config import settings
        import httpx

        if not settings.ALPHA_VANTAGE_API_KEY:
            return []

        events = []

        # Alpha Vantage has economic indicators but limited calendar events
        # We can try to get CPI, GDP, employment data as events
        url = "https://www.alphavantage.co/query"
        functions = {
            "REAL_GDP": {"function": "REAL_GDP", "name": "GDP (QoQ)", "country": "US", "currency": "USD"},
            "CPI": {"function": "CPI", "name": "CPI (YoY)", "country": "US", "currency": "USD"},
            "UNEMPLOYMENT": {"function": "UNEMPLOYMENT", "name": "Unemployment Rate", "country": "US", "currency": "USD"},
            "RETAIL_SALES": {"function": "RETAIL_SALES", "name": "Retail Sales", "country": "US", "currency": "USD"},
        }

        for key, info in functions.items():
            try:
                params = {
                    "function": info["function"],
                    "apikey": settings.ALPHA_VANTAGE_API_KEY,
                }
                response = httpx.get(url, params=params, timeout=30.0)
                response.raise_for_status()
                data = response.json()

                # Parse and create events (Alpha Vantage returns quarterly/monthly data)
                if "data" in data and data["data"]:
                    for item in data["data"][:1]:  # Take most recent
                        date_str = item.get("date", "")
                        value = item.get("value", "")

                        if date_str:
                            event_date = datetime.fromisoformat(date_str)
                            events.append({
                                "event_date": event_date,
                                "country": info["country"],
                                "event_name": info["name"],
                                "importance": "medium",
                                "currency": info["currency"],
                                "previous": value,
                                "impact": "medium",
                                "source": "alphavantage",
                            })
            except Exception:
                continue

        return events

    except Exception:
        return []


# ─── Routes ──────────────────────────────────────────────────────────────────

@router.get("/", response_model=dict)
def list_events(
    start_date: Optional[str] = Query(None, description="Start date filter (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date filter (YYYY-MM-DD)"),
    country: Optional[str] = Query(None, description="Filter by country code: US, EU, UK, JP, AU, CA"),
    importance: Optional[str] = Query(None, description="Filter by importance: low, medium, high"),
    currency: Optional[str] = Query(None, description="Filter by currency: USD, EUR, GBP, JPY, AUD, CAD"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """
    List economic events with optional filters.
    """
    query = db.query(EconEvent)

    if start_date:
        try:
            dt_start = datetime.strptime(start_date, "%Y-%m-%d")
            query = query.filter(EconEvent.event_date >= dt_start)
        except ValueError:
            pass

    if end_date:
        try:
            dt_end = datetime.strptime(end_date, "%Y-%m-%d")
            dt_end = dt_end.replace(hour=23, minute=59, second=59)
            query = query.filter(EconEvent.event_date <= dt_end)
        except ValueError:
            pass

    if country:
        query = query.filter(EconEvent.country == country.upper())

    if importance:
        query = query.filter(EconEvent.importance == importance.lower())

    if currency:
        query = query.filter(EconEvent.currency == currency.upper())

    total = query.count()
    events = query.order_by(EconEvent.event_date.asc()).offset(offset).limit(limit).all()

    return {
        "items": [
            {
                "id": e.id,
                "event_date": e.event_date.isoformat() if e.event_date else None,
                "country": e.country,
                "event_name": e.event_name,
                "importance": e.importance,
                "currency": e.currency,
                "previous": e.previous,
                "forecast": e.forecast,
                "actual": e.actual,
                "impact": e.impact,
                "source": e.source,
                "scraped_at": e.scraped_at.isoformat() if e.scraped_at else None,
                "created_at": e.created_at.isoformat() if e.created_at else None,
                "updated_at": e.updated_at.isoformat() if e.updated_at else None,
                "impacted_instruments": get_impacted_instruments(e.event_name),
            }
            for e in events
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/upcoming", response_model=dict)
def get_upcoming_events(
    days: int = Query(7, ge=1, le=30, description="Number of days to look ahead"),
    country: Optional[str] = Query(None, description="Filter by country code"),
    importance: Optional[str] = Query(None, description="Filter by importance"),
    db: Session = Depends(get_db),
):
    """
    Get economic events for the next N days (default 7).
    """
    now = datetime.utcnow()
    end_date = now + timedelta(days=days)

    query = db.query(EconEvent).filter(
        EconEvent.event_date >= now,
        EconEvent.event_date <= end_date,
    )

    if country:
        query = query.filter(EconEvent.country == country.upper())

    if importance:
        query = query.filter(EconEvent.importance == importance.lower())

    events = query.order_by(EconEvent.event_date.asc()).all()

    return {
        "items": [
            {
                "id": e.id,
                "event_date": e.event_date.isoformat() if e.event_date else None,
                "country": e.country,
                "event_name": e.event_name,
                "importance": e.importance,
                "currency": e.currency,
                "previous": e.previous,
                "forecast": e.forecast,
                "actual": e.actual,
                "impact": e.impact,
                "source": e.source,
                "scraped_at": e.scraped_at.isoformat() if e.scraped_at else None,
                "impacted_instruments": get_impacted_instruments(e.event_name),
            }
            for e in events
        ],
        "total": len(events),
        "days": days,
    }


@router.post("/", response_model=dict)
def create_event(
    event: EconEventCreate,
    db: Session = Depends(get_db),
):
    """
    Create a new economic event manually.
    """
    db_event = EconEvent(
        event_date=event.event_date,
        country=event.country.upper(),
        event_name=event.event_name,
        importance=event.importance,
        currency=event.currency.upper(),
        previous=event.previous,
        forecast=event.forecast,
        actual=event.actual,
        impact=event.impact,
        source="manual",
    )
    db.add(db_event)
    db.commit()
    db.refresh(db_event)

    return {
        "id": db_event.id,
        "event_date": db_event.event_date.isoformat(),
        "country": db_event.country,
        "event_name": db_event.event_name,
        "importance": db_event.importance,
        "currency": db_event.currency,
        "previous": db_event.previous,
        "forecast": db_event.forecast,
        "actual": db_event.actual,
        "impact": db_event.impact,
        "source": db_event.source,
    }


@router.put("/{event_id}", response_model=dict)
def update_event(
    event_id: int,
    event: EconEventUpdate,
    db: Session = Depends(get_db),
):
    """
    Update an existing economic event.
    """
    db_event = db.query(EconEvent).filter(EconEvent.id == event_id).first()
    if not db_event:
        raise HTTPException(status_code=404, detail="Economic event not found")

    if event.event_date is not None:
        db_event.event_date = event.event_date
    if event.country is not None:
        db_event.country = event.country.upper()
    if event.event_name is not None:
        db_event.event_name = event.event_name
    if event.importance is not None:
        db_event.importance = event.importance
    if event.currency is not None:
        db_event.currency = event.currency.upper()
    if event.previous is not None:
        db_event.previous = event.previous
    if event.forecast is not None:
        db_event.forecast = event.forecast
    if event.actual is not None:
        db_event.actual = event.actual
    if event.impact is not None:
        db_event.impact = event.impact
    if event.source is not None:
        db_event.source = event.source

    db_event.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(db_event)

    return {
        "id": db_event.id,
        "event_date": db_event.event_date.isoformat(),
        "country": db_event.country,
        "event_name": db_event.event_name,
        "importance": db_event.importance,
        "currency": db_event.currency,
        "previous": db_event.previous,
        "forecast": db_event.forecast,
        "actual": db_event.actual,
        "impact": db_event.impact,
        "source": db_event.source,
    }


@router.delete("/{event_id}", response_model=dict)
def delete_event(
    event_id: int,
    db: Session = Depends(get_db),
):
    """
    Delete an economic event.
    """
    db_event = db.query(EconEvent).filter(EconEvent.id == event_id).first()
    if not db_event:
        raise HTTPException(status_code=404, detail="Economic event not found")

    db.delete(db_event)
    db.commit()

    return {"deleted": event_id}


@router.post("/scrape", response_model=dict)
async def scrape_events(db: Session = Depends(get_db)):
    """
    Scrape economic events from available sources (FXStreet, investing.com, Alpha Vantage).
    Falls back to seeding known recurring events if scraping fails.
    """
    errors = []
    created = 0
    updated = 0

    # Try FXStreet first
    fxstreet_events = await scrape_fxstreet_calendar()
    if fxstreet_events:
        for event_data in fxstreet_events:
            # Check if event already exists
            existing = db.query(EconEvent).filter(
                EconEvent.event_name == event_data["event_name"],
                EconEvent.country == event_data["country"],
                EconEvent.event_date >= event_data["event_date"].replace(hour=0, minute=0, second=0) - timedelta(hours=12),
                EconEvent.event_date <= event_data["event_date"].replace(hour=23, minute=59, second=59) + timedelta(hours=12),
            ).first()

            if existing:
                # Update existing
                existing.previous = event_data.get("previous", existing.previous)
                existing.forecast = event_data.get("forecast", existing.forecast)
                existing.actual = event_data.get("actual", existing.actual)
                existing.importance = event_data.get("importance", existing.importance)
                existing.impact = event_data.get("impact", existing.impact)
                existing.scraped_at = datetime.utcnow()
                updated += 1
            else:
                # Create new
                new_event = EconEvent(
                    event_date=event_data["event_date"],
                    country=event_data["country"],
                    event_name=event_data["event_name"],
                    importance=event_data.get("importance", "medium"),
                    currency=event_data["currency"],
                    previous=event_data.get("previous"),
                    forecast=event_data.get("forecast"),
                    actual=event_data.get("actual"),
                    impact=event_data.get("impact", "medium"),
                    source=event_data.get("source", "fxstreet"),
                    scraped_at=datetime.utcnow(),
                )
                db.add(new_event)
                created += 1
    else:
        errors.append("FXStreet scrape returned no events")

    # Try investing.com as backup
    investing_events = await scrape_investing_calendar()
    if investing_events:
        for event_data in investing_events:
            existing = db.query(EconEvent).filter(
                EconEvent.event_name == event_data["event_name"],
                EconEvent.country == event_data["country"],
                EconEvent.event_date >= event_data["event_date"].replace(hour=0, minute=0, second=0) - timedelta(hours=12),
                EconEvent.event_date <= event_data["event_date"].replace(hour=23, minute=59, second=59) + timedelta(hours=12),
            ).first()

            if not existing:
                new_event = EconEvent(
                    event_date=event_data["event_date"],
                    country=event_data["country"],
                    event_name=event_data["event_name"],
                    importance=event_data.get("importance", "medium"),
                    currency=event_data["currency"],
                    impact=event_data.get("impact", "medium"),
                    source=event_data.get("source", "investing"),
                    scraped_at=datetime.utcnow(),
                )
                db.add(new_event)
                created += 1

    # Try Alpha Vantage as tertiary
    av_events = await scrape_alpha_vantage_events()
    if av_events:
        for event_data in av_events:
            existing = db.query(EconEvent).filter(
                EconEvent.event_name == event_data["event_name"],
                EconEvent.country == event_data["country"],
            ).first()

            if not existing:
                new_event = EconEvent(
                    event_date=event_data["event_date"],
                    country=event_data["country"],
                    event_name=event_data["event_name"],
                    importance=event_data.get("importance", "medium"),
                    currency=event_data["currency"],
                    previous=event_data.get("previous"),
                    impact=event_data.get("impact", "medium"),
                    source=event_data.get("source", "alphavantage"),
                    scraped_at=datetime.utcnow(),
                )
                db.add(new_event)
                created += 1

    # If no events scraped at all, seed with known events
    total_events = db.query(EconEvent).count()
    if total_events == 0:
        seed_count = seed_known_events(db)
        created += seed_count
        errors.append("No scraped events - seeded known recurring events")

    db.commit()

    return {
        "success": created > 0 or updated > 0,
        "events_created": created,
        "events_updated": updated,
        "errors": errors if errors else [],
    }


@router.get("/impact-map", response_model=dict)
def get_impact_map():
    """
    Get the mapping of economic events to typically impacted instruments.
    """
    return {
        "mappings": EVENT_IMPACT_MAP,
        "countries": {
            "US": {"currency": "USD", "flag": "🇺🇸"},
            "EU": {"currency": "EUR", "flag": "🇪🇺"},
            "UK": {"currency": "GBP", "flag": "🇬🇧"},
            "JP": {"currency": "JPY", "flag": "🇯🇵"},
            "AU": {"currency": "AUD", "flag": "🇦🇺"},
            "CA": {"currency": "CAD", "flag": "🇨🇦"},
            "NZ": {"currency": "NZD", "flag": "🇳🇿"},
            "CH": {"currency": "CHF", "flag": "🇨🇭"},
        },
    }
