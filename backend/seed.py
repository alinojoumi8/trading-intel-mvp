"""
Seed script for trading-intel-mvp backend.
Seeds 10 instruments and common tags for development.
"""
from datetime import datetime, timedelta
import random

from app.core.database import SessionLocal, engine
from app.core.database import Base
from app.models.models import Instrument, Tag, ContentItem, AssetClass, ContentType, Direction, Timeframe, Confidence

# Create tables
Base.metadata.create_all(bind=engine)


def seed_instruments(db):
    """Seed 10 trading instruments."""
    instruments_data = [
        {
            "symbol": "EURUSD",
            "name": "Euro / US Dollar",
            "asset_class": AssetClass.FX,
            "description": "Most traded currency pair in the forex market.",
        },
        {
            "symbol": "GBPUSD",
            "name": "British Pound / US Dollar",
            "asset_class": AssetClass.FX,
            "description": "Cable - one of the most liquid currency pairs.",
        },
        {
            "symbol": "USDJPY",
            "name": "US Dollar / Japanese Yen",
            "asset_class": AssetClass.FX,
            "description": "The most traded Asian currency pair.",
        },
        {
            "symbol": "AUDUSD",
            "name": "Australian Dollar / US Dollar",
            "asset_class": AssetClass.FX,
            "description": "Commodity-linked currency pair.",
        },
        {
            "symbol": "XAUUSD",
            "name": "Gold / US Dollar",
            "asset_class": AssetClass.COMMODITIES,
            "description": "Gold spot price - primary precious metal.",
        },
        {
            "symbol": "XTIUSD",
            "name": "Crude Oil / US Dollar",
            "asset_class": AssetClass.COMMODITIES,
            "description": "West Texas Intermediate crude oil.",
        },
        {
            "symbol": "BTCUSD",
            "name": "Bitcoin / US Dollar",
            "asset_class": AssetClass.CRYPTO,
            "description": "Bitcoin - largest cryptocurrency by market cap.",
        },
        {
            "symbol": "ETHUSD",
            "name": "Ethereum / US Dollar",
            "asset_class": AssetClass.CRYPTO,
            "description": "Ethereum - second largest cryptocurrency.",
        },
        {
            "symbol": "SPXUSD",
            "name": "S&P 500 Index",
            "asset_class": AssetClass.INDICES,
            "description": "US equity index - 500 large-cap stocks.",
        },
        {
            "symbol": "NASUSD",
            "name": "NASDAQ 100 Index",
            "asset_class": AssetClass.INDICES,
            "description": "Tech-heavy US equity index.",
        },
    ]

    for inst_data in instruments_data:
        existing = db.query(Instrument).filter(Instrument.symbol == inst_data["symbol"]).first()
        if not existing:
            instrument = Instrument(**inst_data)
            db.add(instrument)
    
    db.commit()
    print(f"Seeded {len(instruments_data)} instruments")


def seed_tags(db):
    """Seed common trading tags."""
    tags_data = [
        "momentum",
        "breakout",
        "reversal",
        "macro-driven",
        "trend-following",
        "mean-reversion",
        "news-event",
        "technical",
        "fundamental",
        " scalp",
        "swing",
        "day-trade",
        "range-bound",
        "volatility",
        "liquidity",
    ]

    for tag_name in tags_data:
        existing = db.query(Tag).filter(Tag.name == tag_name).first()
        if not existing:
            tag = Tag(name=tag_name)
            db.add(tag)
    
    db.commit()
    print(f"Seeded {len(tags_data)} tags")


def seed_sample_content(db):
    """Seed sample content items for development."""
    # Get instruments and tags
    instruments = db.query(Instrument).all()
    tags = db.query(Tag).all()
    
    if not instruments or not tags:
        print("No instruments or tags found, skipping content seed")
        return
    
    # Sample content templates
    sample_content = [
        {
            "title": "EURUSD Morning Briefing - Bullish Momentum Expected",
            "content_type": ContentType.BRIEFING,
            "instrument": "EURUSD",
            "direction": Direction.LONG,
            "timeframe": Timeframe.D1,
            "confidence": Confidence.HIGH,
            "rationale": "EUR/USD showing strong momentum after breaking above key resistance at 1.0850. Dollar weakness continues as Fed rate expectations shift lower. Key support at 1.0820 holds.",
            "featured": True,
        },
        {
            "title": "Gold Setup - Breakout Long Opportunity",
            "content_type": ContentType.SETUP,
            "instrument": "XAUUSD",
            "direction": Direction.LONG,
            "entry_zone": "2015-2025",
            "stop_loss": "1995",
            "take_profit": "2080",
            "risk_reward_ratio": 2.5,
            "timeframe": Timeframe.H4,
            "confidence": Confidence.MEDIUM,
            "rationale": "Gold breaking out of a 3-week consolidation pattern with volume confirmation. Key economic data today could catalyze the move higher.",
            "featured": True,
        },
        {
            "title": "Weekly Macro Roundup - Volatility Returns",
            "content_type": ContentType.MACRO_ROUNDUP,
            "rationale": "This week's top macro events: Fed minutes released with dovish undertones, ECB rate decision, and stronger-than-expected US jobs data. Market volatility increased significantly with VIX spiking to 20. Positioning shows crowding in short USD trades.",
            "featured": False,
        },
        {
            "title": "BTCUSD Contrarian Alert - Crowd Positioning",
            "content_type": ContentType.CONTRARIAN_ALERT,
            "instrument": "BTCUSD",
            "direction": Direction.SHORT,
            "rationale": "Retail sentiment at extreme greed levels (75%). Crowd positioning shows 65% long BTC. Contrarian view: expect a pullback to 42000-43000 zone before continuation higher.",
            "featured": False,
        },
        {
            "title": "SPX Setup - Trend Continuation",
            "content_type": ContentType.SETUP,
            "instrument": "SPXUSD",
            "direction": Direction.LONG,
            "entry_zone": "4850-4880",
            "stop_loss": "4800",
            "take_profit": "4980",
            "risk_reward_ratio": 3.2,
            "timeframe": Timeframe.D1,
            "confidence": Confidence.HIGH,
            "rationale": "S&P 500 in clear uptrend with higher highs and lows. Earnings season showing 75% beat rate. Institutional buying continues.",
            "featured": True,
        },
    ]
    
    # Get some tag names for variety
    momentum_tag = next((t for t in tags if t.name == "momentum"), tags[0])
    breakout_tag = next((t for t in tags if t.name == "breakout"), tags[1])
    macro_tag = next((t for t in tags if t.name == "macro-driven"), tags[2])
    reversal_tag = next((t for t in tags if t.name == "reversal"), tags[3])
    
    for i, content_data in enumerate(sample_content):
        instrument_symbol = content_data.pop("instrument", None)
        instrument = None
        if instrument_symbol:
            instrument = db.query(Instrument).filter(Instrument.symbol == instrument_symbol).first()
        
        # Assign tags based on content type
        assigned_tags = [momentum_tag]
        if content_data.get("content_type") == ContentType.SETUP:
            assigned_tags = [breakout_tag, momentum_tag]
        elif content_data.get("content_type") == ContentType.MACRO_ROUNDUP:
            assigned_tags = [macro_tag]
        elif content_data.get("content_type") == ContentType.CONTRARIAN_ALERT:
            assigned_tags = [reversal_tag]
        
        item = ContentItem(
            title=content_data["title"],
            content_type=content_data["content_type"],
            rationale=content_data["rationale"],
            instrument_id=instrument.id if instrument else None,
            direction=content_data.get("direction"),
            entry_zone=content_data.get("entry_zone"),
            stop_loss=content_data.get("stop_loss"),
            take_profit=content_data.get("take_profit"),
            risk_reward_ratio=content_data.get("risk_reward_ratio"),
            timeframe=content_data.get("timeframe"),
            confidence=content_data.get("confidence"),
            featured=content_data.get("featured", False),
            published_at=datetime.utcnow() - timedelta(hours=i * 3),
        )
        item.tags = assigned_tags
        
        db.add(item)
    
    db.commit()
    print(f"Seeded {len(sample_content)} sample content items")


def main():
    """Run all seed functions."""
    db = SessionLocal()
    try:
        print("Starting database seed...")
        seed_instruments(db)
        seed_tags(db)
        seed_sample_content(db)
        print("Database seeding complete!")
    finally:
        db.close()


if __name__ == "__main__":
    main()
