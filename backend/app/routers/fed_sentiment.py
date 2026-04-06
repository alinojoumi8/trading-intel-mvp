"""
Fed Sentiment Module API Router
Provides endpoints for Fed language sentiment, market-implied expectations,
composite score, and divergence signal.
"""
import logging
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db, Base, engine
from app.models.models import FedDocument, FedSentimentScore
from app.services.fed_sentiment_service import (
    get_current_fed_sentiment,
    get_market_score,
    sync_fed_documents,
    score_unscored_documents,
    detect_phrase_transitions,
    get_phrase_transitions,
    rescore_all_documents_tier1,
)
from app.services.fed_backtest_service import run_backtest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/fed-sentiment", tags=["fed-sentiment"])

# Ensure tables exist
Base.metadata.create_all(bind=engine)


# ─── Pydantic Schemas ─────────────────────────────────────────────────────────

class MarketExpectationsResponse(BaseModel):
    market_score: Optional[float]
    yield_2y: Optional[float]
    yield_spread_10y2y: Optional[float]
    fed_target_rate: Optional[float]
    yield_2y_30d_change: Optional[float]
    next_meeting_bps_priced: Optional[float]
    is_stale: bool
    fetched_at: str


class FedDocumentResponse(BaseModel):
    id: int
    document_type: str
    document_date: str
    speaker: Optional[str]
    title: str
    source_url: Optional[str]
    tier1_score: Optional[float]
    blended_score: Optional[float]
    importance_weight: float
    created_at: str


class CompositeResponse(BaseModel):
    composite_score: Optional[float]
    language_score: Optional[float]
    market_score: Optional[float]
    divergence_score: Optional[float]
    divergence_category: Optional[str]
    divergence_zscore: Optional[float]
    fed_regime: Optional[str]
    trading_signal: Optional[str]
    signal_conviction: Optional[str]
    signal_direction: Optional[str]
    yield_2y: Optional[float]
    yield_spread_10y2y: Optional[float]
    fed_target_rate: Optional[float]
    yield_2y_30d_change: Optional[float]
    key_phrases: Optional[List[str]]
    is_stale: bool
    generated_at: str
    days_to_next_fomc: Optional[float] = None
    next_fomc_date: Optional[str] = None


class HistoryItem(BaseModel):
    timestamp: str
    composite_score: Optional[float]
    language_score: Optional[float]
    market_score: Optional[float]
    divergence_score: Optional[float]
    fed_regime: Optional[str]
    signal_direction: Optional[str]


class SyncResponse(BaseModel):
    synced_count: int
    documents: List[FedDocumentResponse]
    message: str


# ─── GET /fed-sentiment/composite ─────────────────────────────────────────────

@router.get("/composite", response_model=CompositeResponse)
def get_composite(db: Session = Depends(get_db)) -> CompositeResponse:
    """
    Get the current Fed sentiment composite score.
    Combines language NLP score + market-implied expectations.
    Computes divergence signal and Fed regime classification.
    """
    try:
        result = get_current_fed_sentiment(db_session=db)
        return CompositeResponse(
            composite_score=result.get("composite_score"),
            language_score=result.get("language_score"),
            market_score=result.get("market_score"),
            divergence_score=result.get("divergence_score"),
            divergence_category=result.get("divergence_category"),
            divergence_zscore=result.get("divergence_zscore"),
            fed_regime=result.get("fed_regime"),
            trading_signal=result.get("trading_signal"),
            signal_conviction=result.get("signal_conviction"),
            signal_direction=result.get("signal_direction"),
            yield_2y=result.get("yield_2y"),
            yield_spread_10y2y=result.get("yield_spread_10y2y"),
            fed_target_rate=result.get("fed_target_rate"),
            yield_2y_30d_change=result.get("yield_2y_30d_change"),
            key_phrases=result.get("key_phrases", []),
            is_stale=result.get("is_stale", False),
            generated_at=datetime.utcnow().isoformat(),
            days_to_next_fomc=result.get("days_to_next_fomc"),
            next_fomc_date=result.get("next_fomc_date"),
        )
    except Exception as e:
        logger.exception("Failed to compute Fed composite score")
        raise HTTPException(status_code=500, detail=str(e))


# ─── GET /fed-sentiment/market ─────────────────────────────────────────────────

@router.get("/market", response_model=MarketExpectationsResponse)
def get_market_expectations() -> MarketExpectationsResponse:
    """
    Get current market-implied Fed expectations from FRED + yfinance.
    Includes 2Y yield, yield curve, and bps priced for next meeting.
    """
    try:
        data = get_market_score()
        return MarketExpectationsResponse(
            market_score=data.get("market_score"),
            yield_2y=data.get("yield_2y"),
            yield_spread_10y2y=data.get("yield_spread_10y2y"),
            fed_target_rate=data.get("fed_target_rate"),
            yield_2y_30d_change=data.get("yield_2y_30d_change"),
            next_meeting_bps_priced=data.get("next_meeting_bps_priced"),
            is_stale=data.get("is_stale", False),
            fetched_at=datetime.utcnow().isoformat(),
        )
    except Exception as e:
        logger.exception("Failed to fetch market expectations")
        raise HTTPException(status_code=500, detail=str(e))


# ─── GET /fed-sentiment/documents ─────────────────────────────────────────────

@router.get("/documents", response_model=List[FedDocumentResponse])
def get_documents(
    days: int = 90,
    doc_type: Optional[str] = None,
    db: Session = Depends(get_db),
) -> List[FedDocumentResponse]:
    """
    List Fed documents stored in the database.
    Optionally filter by document type and date range.
    """
    cutoff = datetime.utcnow() - timedelta(days=days)
    query = (
        db.query(FedDocument)
        .filter(FedDocument.document_date >= cutoff)
        .order_by(FedDocument.document_date.desc())
    )
    if doc_type:
        query = query.filter(FedDocument.document_type == doc_type)

    docs = query.limit(50).all()
    return [
        FedDocumentResponse(
            id=d.id,
            document_type=d.document_type,
            document_date=d.document_date.isoformat() if d.document_date else "",
            speaker=d.speaker,
            title=d.title,
            source_url=d.source_url,
            tier1_score=d.tier1_score,
            blended_score=d.blended_score,
            importance_weight=d.importance_weight or 1.0,
            created_at=d.created_at.isoformat() if d.created_at else "",
        )
        for d in docs
    ]


# ─── POST /fed-sentiment/sync ─────────────────────────────────────────────────

@router.post("/sync", response_model=SyncResponse)
def sync_documents(
    max_docs: int = 10,
    db: Session = Depends(get_db),
) -> SyncResponse:
    """
    Scrape new Fed documents from federalreserve.gov RSS feeds,
    score them with the Tier 1 dictionary scorer, and store to DB.
    Safe to call repeatedly — deduplicates by URL.
    """
    try:
        docs = sync_fed_documents(db_session=db, max_docs=max_docs)
        new_docs = [d for d in docs if d.get("tier1_score") is not None]

        doc_responses = [
            FedDocumentResponse(
                id=d.get("id", 0),
                document_type=d.get("document_type", ""),
                document_date=d["document_date"].isoformat() if isinstance(d.get("document_date"), datetime) else str(d.get("document_date", "")),
                speaker=d.get("speaker"),
                title=d.get("title", ""),
                source_url=d.get("source_url"),
                tier1_score=d.get("tier1_score"),
                blended_score=d.get("blended_score"),
                importance_weight=d.get("importance_weight", 1.0),
                created_at=datetime.utcnow().isoformat(),
            )
            for d in docs
        ]

        return SyncResponse(
            synced_count=len(docs),
            documents=doc_responses,
            message=f"Synced {len(docs)} documents ({len(new_docs)} newly scored).",
        )
    except Exception as e:
        logger.exception("Fed document sync failed")
        raise HTTPException(status_code=500, detail=str(e))


# ─── GET /fed-sentiment/history ───────────────────────────────────────────────

@router.get("/history", response_model=List[HistoryItem])
def get_history(
    days: int = 90,
    db: Session = Depends(get_db),
) -> List[HistoryItem]:
    """
    Get historical composite scores for charting.
    Returns up to 180 data points.
    """
    cutoff = datetime.utcnow() - timedelta(days=days)
    scores = (
        db.query(FedSentimentScore)
        .filter(FedSentimentScore.timestamp >= cutoff)
        .order_by(FedSentimentScore.timestamp.asc())
        .limit(180)
        .all()
    )
    return [
        HistoryItem(
            timestamp=s.timestamp.isoformat() if s.timestamp else "",
            composite_score=s.composite_score,
            language_score=s.language_score,
            market_score=s.market_score,
            divergence_score=s.divergence_score,
            fed_regime=s.fed_regime,
            signal_direction=s.signal_direction,
        )
        for s in scores
    ]


# ─── GET /fed-sentiment/stage1-output ─────────────────────────────────────────

@router.get("/stage1-output")
def get_stage1_output(db: Session = Depends(get_db)) -> dict:
    """
    Output formatted for Stage 1 (Regime Detection) consumption.
    Returns Fed regime + volatility/directional adjustments.
    """
    result = get_current_fed_sentiment(db_session=db)

    composite = result.get("composite_score") or 0.0
    regime = result.get("fed_regime", "neutral_hold")

    adjustments = {
        "volatility_multiplier": 1.0,
        "directional_bias": "none",
        "position_size_modifier": 1.0,
        "breakout_probability_boost": 0.0,
    }

    # During aggressive regimes, add directional bias
    if abs(composite) > 50:
        adjustments["directional_bias"] = "bullish_usd" if composite > 0 else "bearish_usd"

    # If divergence category is confusion → reduce position size
    if result.get("divergence_category") == "confusion":
        adjustments["position_size_modifier"] = 0.75
        adjustments["volatility_multiplier"] = 1.5

    return {
        "fed_regime": regime,
        "composite_score": composite,
        "regime_confidence": min(1.0, abs(composite) / 100),
        "is_pivot_in_progress": result.get("divergence_category") in (
            "hawkish_surprise", "dovish_surprise"
        ),
        "adjustments": adjustments,
        "generated_at": datetime.utcnow().isoformat(),
    }


# ─── POST /fed-sentiment/score-tier2 ──────────────────────────────────────────

class Tier2Response(BaseModel):
    scored_count: int
    message: str
    documents: List[FedDocumentResponse]


@router.post("/score-tier2", response_model=Tier2Response)
def score_tier2(
    max_docs: int = 5,
    db: Session = Depends(get_db),
) -> Tier2Response:
    """
    Run Tier 2 LLM scoring (MiniMax) on documents that only have Tier 1 scores.
    Priority order: FOMC statements → minutes → speeches.
    Blends Tier 1 (30%) + Tier 2 (70%) into blended_score.
    Safe to call repeatedly — skips already-scored documents.
    """
    try:
        scored_count = score_unscored_documents(db_session=db, max_docs=max_docs)

        # Return the freshly scored documents
        from app.models.models import FedDocument as FedDoc
        recent = (
            db.query(FedDoc)
            .filter(FedDoc.tier2_score.isnot(None))
            .order_by(FedDoc.document_date.desc())
            .limit(20)
            .all()
        )

        docs = [
            FedDocumentResponse(
                id=d.id,
                document_type=d.document_type,
                document_date=d.document_date.isoformat() if d.document_date else "",
                speaker=d.speaker,
                title=d.title,
                source_url=d.source_url,
                tier1_score=d.tier1_score,
                blended_score=d.blended_score,
                importance_weight=d.importance_weight or 1.0,
                created_at=d.created_at.isoformat() if d.created_at else "",
            )
            for d in recent
        ]

        return Tier2Response(
            scored_count=scored_count,
            message=f"Tier 2 LLM scored {scored_count} new document(s). {len(docs)} total with Tier 2 scores.",
            documents=docs,
        )
    except Exception as e:
        logger.exception("Tier 2 scoring failed")
        raise HTTPException(status_code=500, detail=str(e))


# ─── GET /fed-sentiment/phrase-transitions ────────────────────────────────────

class PhraseTransitionItem(BaseModel):
    id: int
    phrase_from: str
    phrase_to: str
    signal_type: Optional[str]
    description: Optional[str]
    doc_from_date: Optional[str]
    doc_to_date: Optional[str]
    detected_at: Optional[str]


@router.get("/phrase-transitions", response_model=List[PhraseTransitionItem])
def list_phrase_transitions(
    limit: int = 20,
    db: Session = Depends(get_db),
) -> List[PhraseTransitionItem]:
    """
    List detected key phrase transitions between consecutive FOMC statements.
    These are historically significant language changes that precede policy pivots.
    """
    items = get_phrase_transitions(db_session=db, limit=limit)
    return [PhraseTransitionItem(**item) for item in items]


@router.post("/detect-transitions")
def run_detect_transitions(db: Session = Depends(get_db)) -> dict:
    """
    Run phrase transition detection against the last 3 pairs of FOMC statements.
    Safe to call repeatedly — deduplicates by document pair + phrase pair.
    """
    try:
        new_transitions = detect_phrase_transitions(db_session=db, max_pairs=3)
        return {
            "detected": len(new_transitions),
            "transitions": new_transitions,
            "message": (
                f"Detected {len(new_transitions)} new phrase transition(s)."
                if new_transitions else "No new transitions detected."
            ),
        }
    except Exception as e:
        logger.exception("Phrase transition detection failed")
        raise HTTPException(status_code=500, detail=str(e))


# ─── POST /fed-sentiment/rescore-tier1 ────────────────────────────────────────

@router.post("/rescore-tier1")
def rescore_tier1(db: Session = Depends(get_db)) -> dict:
    """
    Re-score all FedDocument rows with the current Tier 1 dictionary.
    Use this after dictionary recalibration to update existing scores.
    Updates both tier1_score and blended_score (recomputing the blend if T2 exists).
    """
    try:
        result = rescore_all_documents_tier1(db_session=db)
        return {
            **result,
            "message": f"Re-scored {result['updated']}/{result['processed']} documents.",
        }
    except Exception as e:
        logger.exception("Tier 1 rescore failed")
        raise HTTPException(status_code=500, detail=str(e))


# ─── POST /fed-sentiment/backtest ─────────────────────────────────────────────

# In-memory cache for the latest backtest result (so the UI doesn't have to
# re-run a 1-2 minute computation on every page load).
_backtest_cache: dict = {}


@router.post("/backtest")
def run_fsm_backtest(
    use_tier2: bool = False,
    max_events: Optional[int] = None,
) -> dict:
    """
    Run the FSM backtest against 10 known historical FOMC events (spec Section 8.2).
    Compares Tier 1 (and optionally Tier 2 LLM) scores against actual DXY 24h reactions.

    Set use_tier2=True to also run the LLM scorer (slower, more accurate).
    """
    try:
        result = run_backtest(use_tier2=use_tier2, max_events=max_events)
        cache_key = "tier2" if use_tier2 else "tier1"
        _backtest_cache[cache_key] = result
        return result
    except Exception as e:
        logger.exception("FSM backtest failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/backtest")
def get_fsm_backtest(use_tier2: bool = False) -> dict:
    """
    Return the cached backtest result. Returns empty/null if not yet run.
    Use POST /backtest to trigger a fresh run.
    """
    cache_key = "tier2" if use_tier2 else "tier1"
    cached = _backtest_cache.get(cache_key)
    if not cached:
        return {
            "ran_at": None,
            "use_tier2": use_tier2,
            "events": [],
            "metrics": {},
            "message": "No backtest run yet. POST /fed-sentiment/backtest to run.",
        }
    return cached


# ─── GET /fed-sentiment/documents/{id} ────────────────────────────────────────

class FedDocumentDetailResponse(FedDocumentResponse):
    tier2_score: Optional[float]
    full_text_preview: Optional[str]


@router.get("/documents/{doc_id}", response_model=FedDocumentDetailResponse)
def get_document(doc_id: int, db: Session = Depends(get_db)) -> FedDocumentDetailResponse:
    """Get a single Fed document with full detail including Tier 2 score."""
    doc = db.query(FedDocument).filter(FedDocument.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    return FedDocumentDetailResponse(
        id=doc.id,
        document_type=doc.document_type,
        document_date=doc.document_date.isoformat() if doc.document_date else "",
        speaker=doc.speaker,
        title=doc.title,
        source_url=doc.source_url,
        tier1_score=doc.tier1_score,
        tier2_score=doc.tier2_score,
        blended_score=doc.blended_score,
        importance_weight=doc.importance_weight or 1.0,
        created_at=doc.created_at.isoformat() if doc.created_at else "",
        full_text_preview=(doc.full_text or "")[:500] if doc.full_text else None,
    )
