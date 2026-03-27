"""
COT History API Router
Manages historical COT (Commitment of Traders) data.
"""
import asyncio
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.models import COTSnapshot
from app.services.cot_service import get_cot_summary_async, _fetch_cot_for_instrument_async

router = APIRouter(prefix="/cot-history", tags=["cot-history"])


# ─── Schemas ──────────────────────────────────────────────────────────────────

class COTSnapshotResponse(BaseModel):
    id: int
    report_date: datetime
    instrument: str
    commercial_net: int
    noncommercial_net: int
    open_interest: int
    created_at: datetime

    class Config:
        from_attributes = True


class COTSnapshotListResponse(BaseModel):
    items: List[COTSnapshotResponse]
    total: int
    limit: int
    offset: int


class COTLatestResponse(BaseModel):
    instrument: str
    report_date: Optional[str]
    commercial_net: int
    noncommercial_net: int
    open_interest: int


class COTScrapeResponse(BaseModel):
    success: bool
    instruments_updated: List[str]
    errors: List[str]


# ─── GET /cot-history/ ────────────────────────────────────────────────────────

@router.get("/", response_model=dict)
def list_cot_snapshots(
    instrument: Optional[str] = Query(None, description="Filter by instrument: GOLD, EUR, GBP, JPY, OIL"),
    date_from: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """
    List COT snapshots with optional filters.
    Returns commercial_net, noncommercial_net, and open_interest for each snapshot.
    """
    query = db.query(COTSnapshot)

    if instrument:
        query = query.filter(COTSnapshot.instrument == instrument.upper())

    if date_from:
        try:
            dt_from = datetime.strptime(date_from, "%Y-%m-%d")
            query = query.filter(COTSnapshot.report_date >= dt_from)
        except ValueError:
            pass

    if date_to:
        try:
            dt_to = datetime.strptime(date_to, "%Y-%m-%d")
            # Include the entire day
            dt_to = dt_to.replace(hour=23, minute=59, second=59)
            query = query.filter(COTSnapshot.report_date <= dt_to)
        except ValueError:
            pass

    total = query.count()
    snapshots = query.order_by(desc(COTSnapshot.report_date)).offset(offset).limit(limit).all()

    return {
        "items": [
            {
                "id": s.id,
                "report_date": s.report_date.isoformat(),
                "instrument": s.instrument,
                "commercial_net": s.commercial_net,
                "noncommercial_net": s.noncommercial_net,
                "open_interest": s.open_interest,
                "created_at": s.created_at.isoformat() if s.created_at else None,
            }
            for s in snapshots
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


# ─── GET /cot-history/latest ──────────────────────────────────────────────────

@router.get("/latest", response_model=dict)
def get_latest_cot(db: Session = Depends(get_db)):
    """
    Get the most recent COT snapshot for each tracked instrument.
    """
    instruments = ["GOLD", "EUR", "GBP", "JPY", "OIL"]
    result = []

    for inst in instruments:
        snapshot = (
            db.query(COTSnapshot)
            .filter(COTSnapshot.instrument == inst)
            .order_by(desc(COTSnapshot.report_date))
            .first()
        )
        if snapshot:
            result.append({
                "instrument": inst,
                "report_date": snapshot.report_date.strftime("%Y-%m-%d"),
                "commercial_net": snapshot.commercial_net,
                "noncommercial_net": snapshot.noncommercial_net,
                "open_interest": snapshot.open_interest,
            })
        else:
            result.append({
                "instrument": inst,
                "report_date": None,
                "commercial_net": 0,
                "noncommercial_net": 0,
                "open_interest": 0,
            })

    return {"instruments": result}


# ─── POST /cot-history/scrape ───────────────────────────────────────────────

@router.post("/scrape", response_model=dict)
async def scrape_cot_data(db: Session = Depends(get_db)):
    """
    Scrape current COT data from the CFTC Socrata API and store in the database.
    Fetches for GOLD, EUR, GBP, JPY, OIL instruments.
    """
    instruments = ["GOLD", "EUR", "GBP", "JPY", "OIL"]
    errors = []
    updated = []

    async def fetch_and_store(inst: str):
        try:
            data = await _fetch_cot_for_instrument_async(inst)
            if "error" in data or not data.get("report_date"):
                return inst, False, data.get("error", "No data returned")

            report_date = datetime.strptime(data["report_date"][:10], "%Y-%m-%d")

            # Check if we already have this exact snapshot
            existing = (
                db.query(COTSnapshot)
                .filter(
                    COTSnapshot.instrument == inst,
                    COTSnapshot.report_date == report_date,
                )
                .first()
            )

            if existing:
                # Update existing
                existing.commercial_net = data.get("commercial_net", 0)
                existing.noncommercial_net = data.get("noncommercial_net", 0)
                existing.open_interest = data.get("open_interest", 0)
            else:
                # Insert new
                snapshot = COTSnapshot(
                    report_date=report_date,
                    instrument=inst,
                    commercial_net=data.get("commercial_net", 0),
                    noncommercial_net=data.get("noncommercial_net", 0),
                    open_interest=data.get("open_interest", 0),
                )
                db.add(snapshot)

            return inst, True, None
        except Exception as e:
            return inst, False, str(e)

    results = await asyncio.gather(*[fetch_and_store(i) for i in instruments])

    for inst, success, err in results:
        if success:
            updated.append(inst)
        else:
            errors.append(f"{inst}: {err}")

    db.commit()

    return {
        "success": len(updated) > 0,
        "instruments_updated": updated,
        "errors": errors,
    }
