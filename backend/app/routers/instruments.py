from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from app.core.database import get_db
from app.models.models import Instrument, AssetClass
from app.schemas.schemas import (
    InstrumentCreate,
    InstrumentUpdate,
    InstrumentResponse,
    InstrumentWithContent,
    AssetClass,
)

router = APIRouter(prefix="/instruments", tags=["instruments"])


@router.get("/", response_model=List[InstrumentResponse])
def get_instruments(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    asset_class: Optional[AssetClass] = None,
    db: Session = Depends(get_db),
):
    """
    Get list of instruments with optional filter by asset class.
    """
    query = db.query(Instrument)

    if asset_class:
        query = query.filter(Instrument.asset_class == asset_class)

    return (
        query.order_by(Instrument.symbol)
        .offset(skip)
        .limit(limit)
        .all()
    )


@router.get("/{instrument_id}", response_model=InstrumentResponse)
def get_instrument(instrument_id: int, db: Session = Depends(get_db)):
    """
    Get a single instrument by ID.
    """
    instrument = (
        db.query(Instrument)
        .filter(Instrument.id == instrument_id)
        .first()
    )
    if not instrument:
        raise HTTPException(status_code=404, detail="Instrument not found")
    return instrument


@router.get("/symbol/{symbol}", response_model=InstrumentResponse)
def get_instrument_by_symbol(symbol: str, db: Session = Depends(get_db)):
    """
    Get instrument by symbol (e.g., EURUSD, GOLD, BTC).
    """
    instrument = (
        db.query(Instrument)
        .filter(Instrument.symbol == symbol.upper())
        .first()
    )
    if not instrument:
        raise HTTPException(status_code=404, detail="Instrument not found")
    return instrument


@router.post("/", response_model=InstrumentResponse, status_code=201)
def create_instrument(
    instrument_data: InstrumentCreate,
    db: Session = Depends(get_db),
):
    """
    Create a new instrument.
    """
    # Check if symbol already exists
    existing = (
        db.query(Instrument)
        .filter(Instrument.symbol == instrument_data.symbol.upper())
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=400, detail="Instrument with this symbol already exists"
        )

    db_instrument = Instrument(
        symbol=instrument_data.symbol.upper(),
        name=instrument_data.name,
        asset_class=instrument_data.asset_class,
        description=instrument_data.description,
    )
    db.add(db_instrument)
    db.commit()
    db.refresh(db_instrument)
    return db_instrument


@router.put("/{instrument_id}", response_model=InstrumentResponse)
def update_instrument(
    instrument_id: int,
    instrument_data: InstrumentUpdate,
    db: Session = Depends(get_db),
):
    """
    Update an existing instrument.
    """
    instrument = (
        db.query(Instrument)
        .filter(Instrument.id == instrument_id)
        .first()
    )
    if not instrument:
        raise HTTPException(status_code=404, detail="Instrument not found")

    update_data = instrument_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(instrument, field, value)

    db.commit()
    db.refresh(instrument)
    return instrument


@router.delete("/{instrument_id}", status_code=204)
def delete_instrument(instrument_id: int, db: Session = Depends(get_db)):
    """
    Delete an instrument.
    """
    instrument = (
        db.query(Instrument)
        .filter(Instrument.id == instrument_id)
        .first()
    )
    if not instrument:
        raise HTTPException(status_code=404, detail="Instrument not found")

    db.delete(instrument)
    db.commit()
    return None