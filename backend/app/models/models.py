from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Enum, ForeignKey, Table, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from app.core.database import Base


class User(Base):
    """User accounts for authentication and subscription management."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    name = Column(String(100), nullable=True)
    subscription_tier = Column(String(20), default="free", nullable=False)  # free | pro
    stripe_customer_id = Column(String(100), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class ContentType(str, enum.Enum):
    BRIEFING = "briefing"
    SETUP = "setup"
    MACRO_ROUNDUP = "macro_roundup"
    CONTRARIAN_ALERT = "contrarian_alert"


class Direction(str, enum.Enum):
    LONG = "long"
    SHORT = "short"
    NEUTRAL = "neutral"


class Timeframe(str, enum.Enum):
    SCALP = "scalp"
    H4 = "h4"
    D1 = "d1"
    W1 = "w1"


class Confidence(str, enum.Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class AssetClass(str, enum.Enum):
    FX = "fx"
    COMMODITIES = "commodities"
    CRYPTO = "crypto"
    INDICES = "indices"


# Join table for content and tags
content_tags = Table(
    "content_tags",
    Base.metadata,
    Column("content_item_id", Integer, ForeignKey("content_items.id"), primary_key=True),
    Column("tag_id", Integer, ForeignKey("tags.id"), primary_key=True),
)


class Tag(Base):
    __tablename__ = "tags"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    content_items = relationship("ContentItem", secondary=content_tags, back_populates="tags")


class Instrument(Base):
    __tablename__ = "instruments"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(20), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    asset_class = Column(Enum(AssetClass), nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    content_items = relationship("ContentItem", back_populates="instrument")


class ContentItem(Base):
    __tablename__ = "content_items"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(300), nullable=False)
    content_type = Column(Enum(ContentType), nullable=False)
    instrument_id = Column(Integer, ForeignKey("instruments.id"), nullable=True)
    direction = Column(Enum(Direction), nullable=True)
    entry_zone = Column(String(100), nullable=True)
    stop_loss = Column(String(100), nullable=True)
    take_profit = Column(String(100), nullable=True)
    risk_reward_ratio = Column(Float, nullable=True)
    timeframe = Column(Enum(Timeframe), nullable=True)
    confidence = Column(Enum(Confidence), nullable=True)
    rationale = Column(Text, nullable=False)
    featured = Column(Boolean, default=False)
    published_at = Column(DateTime, default=datetime.utcnow, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    instrument = relationship("Instrument", back_populates="content_items")
    tags = relationship("Tag", secondary=content_tags, back_populates="content_items")
    trade_outcome = relationship("TradeOutcome", back_populates="content_item", uselist=False)


class NewsSource(Base):
    __tablename__ = "news_sources"

    id = Column(Integer, primary_key=True, index=True)
    category = Column(String(50), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    url = Column(String(500), nullable=False, unique=True)
    enabled = Column(Boolean, default=True)
    last_fetched_at = Column(DateTime, nullable=True)
    last_error = Column(String(500), nullable=True)
    fetch_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    items = relationship("NewsItem", back_populates="source", cascade="all, delete-orphan")


class NewsItem(Base):
    __tablename__ = "news_items"

    id = Column(Integer, primary_key=True, index=True)
    source_id = Column(Integer, ForeignKey("news_sources.id"), nullable=False)
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    url = Column(String(1000), nullable=False)
    published_at = Column(DateTime, nullable=True, index=True)
    fetched_at = Column(DateTime, default=datetime.utcnow)
    is_read = Column(Boolean, default=False)
    is_starred = Column(Boolean, default=False)
    tags = Column(String(200), nullable=True)  # comma-separated, derived from source category

    __table_args__ = (
        UniqueConstraint("source_id", "url", name="uq_news_source_url"),
    )

    source = relationship("NewsSource", back_populates="items")


class TradingSignal(Base):
    __tablename__ = "trading_signals"

    id = Column(Integer, primary_key=True, index=True)
    asset = Column(String(20), nullable=False, index=True)
    asset_class = Column(String(20), nullable=True)  # FX, CRYPTO, EQUITY, COMMODITY

    # Stage 1 — Regime
    market_regime = Column(String(30), nullable=True)
    volatility_regime = Column(String(20), nullable=True)
    trading_mode = Column(String(30), nullable=True)
    position_size_modifier = Column(Float, nullable=True)

    # Stage 2 — Fundamentals
    fundamental_bias = Column(String(20), nullable=True)
    bias_strength = Column(String(20), nullable=True)
    top_drivers = Column(String(300), nullable=True)  # JSON array as string

    # Stage 3 — Gatekeeping
    gate_signal = Column(String(10), nullable=True)
    entry_recommendation = Column(String(20), nullable=True)
    technical_alignment = Column(String(20), nullable=True)

    # Trade parameters
    entry_price = Column(Float, nullable=True)
    stop_loss = Column(Float, nullable=True)
    target_price = Column(Float, nullable=True)
    risk_reward_ratio = Column(Float, nullable=True)

    # Stage 4 — Final output
    final_signal = Column(String(20), nullable=True)
    signal_grade = Column(String(10), nullable=True)   # A | B | C | WATCH | PASS
    signal_confidence = Column(Integer, nullable=True)
    direction = Column(String(10), nullable=True)
    recommended_position_size_pct = Column(Integer, nullable=True)
    trade_horizon = Column(String(20), nullable=True)
    signal_summary = Column(Text, nullable=True)
    key_risks = Column(Text, nullable=True)  # JSON array as string
    invalidation_conditions = Column(Text, nullable=True)  # JSON array as string

    # Stage outputs raw (full JSON blobs for debugging)
    stage1_output = Column(Text, nullable=True)
    stage2_output = Column(Text, nullable=True)
    stage3_output = Column(Text, nullable=True)
    stage4_output = Column(Text, nullable=True)

    # Fed Sentiment Module context snapshot at signal generation time
    fsm_context_json = Column(Text, nullable=True)

    # Outcome tracking (filled later when signal resolves)
    outcome = Column(String(20), nullable=True)  # WIN, LOSS, BREAKEVEN, ACTIVE
    outcome_notes = Column(Text, nullable=True)
    generated_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)


class TradeOutcome(Base):
    """Tracks the outcome of a trade setup."""
    __tablename__ = "trade_outcomes"

    id = Column(Integer, primary_key=True, index=True)
    content_item_id = Column(Integer, ForeignKey("content_items.id"), nullable=False, index=True)
    status = Column(String(20), default="open", nullable=False)  # open | won | lost | breakeven | cancelled
    result_note = Column(Text, nullable=True)
    actual_entry = Column(String(100), nullable=True)
    actual_sl = Column(String(100), nullable=True)
    actual_tp = Column(String(100), nullable=True)
    pnl_pips = Column(Float, nullable=True)
    outcome_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    content_item = relationship("ContentItem", back_populates="trade_outcome")


class COTSnapshot(Base):
    """Stores historical COT (Commitment of Traders) data for instruments."""
    __tablename__ = "cot_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    report_date = Column(DateTime, nullable=False, index=True)
    instrument = Column(String(20), nullable=False, index=True)  # GOLD, EUR, GBP, JPY, OIL
    commercial_long = Column(Integer, default=0)
    commercial_short = Column(Integer, default=0)
    commercial_net = Column(Integer, default=0)
    noncommercial_long = Column(Integer, default=0)
    noncommercial_short = Column(Integer, default=0)
    noncommercial_net = Column(Integer, default=0)
    open_interest = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)


class RegimeSnapshot(Base):
    """Stores daily market regime snapshots for tracked instruments."""
    __tablename__ = "regime_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    instrument = Column(String(20), nullable=False, index=True)
    trend = Column(String(30), nullable=False)
    rsi_14 = Column(Float, nullable=False)
    atr_percent = Column(Float, nullable=False)
    regime = Column(String(30), nullable=False)  # TRENDING_UP | TRENDING_DOWN | RANGING
    recorded_at = Column(DateTime, default=datetime.utcnow)


class AlertRule(Base):
    """User-defined alert rules for market events."""
    __tablename__ = "alert_rules"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    instrument = Column(String(20), nullable=True)  # NULL = all instruments
    condition_type = Column(String(50), nullable=False)  # regime_change | setup_generated | cot_change | price_cross | rsi_level
    condition_params = Column(Text, nullable=False, default="{}")  # JSON params
    enabled = Column(Boolean, default=True)
    last_triggered = Column(DateTime, nullable=True)
    notify_via = Column(String(20), default="telegram")  # telegram | both
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    logs = relationship("AlertLog", back_populates="alert_rule", cascade="all, delete-orphan")


class AlertLog(Base):
    """Log of triggered alert events."""
    __tablename__ = "alert_logs"

    id = Column(Integer, primary_key=True, index=True)
    alert_rule_id = Column(Integer, ForeignKey("alert_rules.id"), nullable=False, index=True)
    triggered_at = Column(DateTime, default=datetime.utcnow)
    message = Column(Text, nullable=False)
    acknowledged = Column(Boolean, default=False)

    alert_rule = relationship("AlertRule", back_populates="logs")


class FedDocument(Base):
    """Stores Federal Reserve communications with sentiment scores."""
    __tablename__ = "fed_documents"

    id = Column(Integer, primary_key=True, index=True)
    document_type = Column(String(50), nullable=False, index=True)  # statement | minutes | speech | beige_book | testimony | press_conference
    document_date = Column(DateTime, nullable=False, index=True)
    speaker = Column(String(100), nullable=True)       # Chair Powell, Governor Waller, etc.
    title = Column(String(500), nullable=False)
    source_url = Column(String(1000), nullable=True)
    full_text = Column(Text, nullable=True)
    tier1_score = Column(Float, nullable=True)          # dictionary scorer [-100, +100]
    tier2_score = Column(Float, nullable=True)          # LLM scorer (Phase 4)
    blended_score = Column(Float, nullable=True)        # final language score
    importance_weight = Column(Float, default=1.0)      # document hierarchy weight
    key_phrases = Column(Text, nullable=True)           # JSON array of notable phrases
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("source_url", name="uq_fed_doc_url"),
    )


class FedSentimentScore(Base):
    """Stores composite Fed sentiment scores (language + market)."""
    __tablename__ = "fed_sentiment_scores"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Component scores
    language_score = Column(Float, nullable=True)        # [-100, +100]
    market_score = Column(Float, nullable=True)          # [-100, +100]
    composite_score = Column(Float, nullable=True)       # [-100, +100]

    # Divergence
    divergence_score = Column(Float, nullable=True)      # language - market
    divergence_category = Column(String(50), nullable=True)  # hawkish_surprise | dovish_surprise | etc.
    divergence_zscore = Column(Float, nullable=True)

    # Fed regime + trading signal
    fed_regime = Column(String(50), nullable=True)       # aggressive_tightening | neutral_hold | etc.
    trading_signal = Column(Text, nullable=True)
    signal_conviction = Column(String(10), nullable=True)    # high | medium | low
    signal_direction = Column(String(20), nullable=True)     # USD_bullish | USD_bearish | neutral

    # Market component breakdown (for transparency)
    yield_2y = Column(Float, nullable=True)
    yield_spread_10y2y = Column(Float, nullable=True)
    fed_target_rate = Column(Float, nullable=True)
    yield_2y_30d_change = Column(Float, nullable=True)

    # Meta
    is_stale = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class BacktestSignal(Base):
    """A historical signal generated by the V3 backtest runner."""
    __tablename__ = "backtest_signals"

    id = Column(Integer, primary_key=True, index=True)
    backtest_run_id = Column(String(50), nullable=False, index=True)  # Group signals by run
    asset = Column(String(20), nullable=False, index=True)
    as_of_date = Column(DateTime, nullable=False, index=True)  # When the signal would have been generated

    # Signal output (mirrors TradingSignal)
    final_signal = Column(String(20), nullable=True)  # BUY | SELL | WATCH_LIST | NO_TRADE
    signal_grade = Column(String(10), nullable=True)   # A | B | C | WATCH | PASS
    direction = Column(String(10), nullable=True)
    signal_confidence = Column(Integer, nullable=True)
    market_regime = Column(String(30), nullable=True)
    fundamental_bias = Column(String(20), nullable=True)
    gate_signal = Column(String(10), nullable=True)
    entry_price = Column(Float, nullable=True)
    stop_loss = Column(Float, nullable=True)
    target_price = Column(Float, nullable=True)   # T1 at 2R
    target_2_price = Column(Float, nullable=True)  # T2 at 3R
    target_3_price = Column(Float, nullable=True)  # T3 at 4.5R
    risk_reward_ratio = Column(Float, nullable=True)
    recommended_position_size_pct = Column(Float, nullable=True)

    # FSM context at signal time
    fsm_composite_score = Column(Float, nullable=True)
    fsm_divergence_category = Column(String(30), nullable=True)

    # Outcome (filled by simulator after generation)
    outcome = Column(String(30), nullable=True)  # WIN | LOSS | ENTRY_NOT_TRIGGERED | OPEN | NO_DATA
    t1_hit = Column(Boolean, default=False)   # T1 (2R) target reached
    t2_hit = Column(Boolean, default=False)   # T2 (3R) target reached
    t3_hit = Column(Boolean, default=False)   # T3 (4.5R) target reached
    entry_triggered = Column(Boolean, default=False)
    entry_actual_price = Column(Float, nullable=True)
    exit_price = Column(Float, nullable=True)
    entry_time = Column(DateTime, nullable=True)
    exit_time = Column(DateTime, nullable=True)
    pnl_pct = Column(Float, nullable=True)
    r_multiple = Column(Float, nullable=True)
    bars_in_trade = Column(Integer, nullable=True)
    max_favorable_excursion_pct = Column(Float, nullable=True)
    max_adverse_excursion_pct = Column(Float, nullable=True)

    # Raw stage outputs (JSON)
    stage1_output = Column(Text, nullable=True)
    stage2_output = Column(Text, nullable=True)
    stage3_output = Column(Text, nullable=True)
    stage4_output = Column(Text, nullable=True)
    fsm_context_json = Column(Text, nullable=True)

    generated_at = Column(DateTime, default=datetime.utcnow)
    notes = Column(Text, nullable=True)


class PhraseTransition(Base):
    """Tracks key phrase transitions between consecutive FOMC statements."""
    __tablename__ = "phrase_transitions"

    id = Column(Integer, primary_key=True, index=True)
    phrase_from = Column(String(500), nullable=False)
    phrase_to = Column(String(500), nullable=False)
    doc_from_id = Column(Integer, nullable=True)
    doc_to_id = Column(Integer, nullable=True)
    doc_from_date = Column(DateTime, nullable=True)
    doc_to_date = Column(DateTime, nullable=True)
    signal_type = Column(String(30), nullable=True)   # hawkish_pivot | dovish_pivot | hawkish_lean | dovish_shift
    description = Column(String(300), nullable=True)
    detected_at = Column(DateTime, default=datetime.utcnow)


class EconEvent(Base):
    """Economic events that impact market trading (FOMC, NFP, CPI, GDP, etc.)."""
    __tablename__ = "econ_events"

    id = Column(Integer, primary_key=True, index=True)
    event_date = Column(DateTime, nullable=False, index=True)
    country = Column(String(10), nullable=False)  # US, EU, UK, JP, AU, CA, etc.
    event_name = Column(String(200), nullable=False)
    importance = Column(String(20), default="medium")  # low | medium | high
    currency = Column(String(10), nullable=False)  # USD, EUR, GBP, JPY, AUD, CAD
    previous = Column(String(50), nullable=True)
    forecast = Column(String(50), nullable=True)
    actual = Column(String(50), nullable=True)
    impact = Column(String(20), default="medium")  # low | medium | high (how much it moves markets)
    source = Column(String(50), default="manual")  # "manual" | "finnhub" | "alphavantage" | "news"
    scraped_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
