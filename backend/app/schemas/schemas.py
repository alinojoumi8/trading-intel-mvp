from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class ContentType(str, Enum):
    BRIEFING = "briefing"
    SETUP = "setup"
    MACRO_ROUNDUP = "macro_roundup"
    CONTRARIAN_ALERT = "contrarian_alert"


class Direction(str, Enum):
    LONG = "long"
    SHORT = "short"
    NEUTRAL = "neutral"


class Timeframe(str, Enum):
    SCALP = "scalp"
    H4 = "h4"
    D1 = "d1"
    W1 = "w1"


class Confidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class AssetClass(str, Enum):
    FX = "fx"
    COMMODITIES = "commodities"
    CRYPTO = "crypto"
    INDICES = "indices"


# Tag schemas
class TagBase(BaseModel):
    name: str = Field(..., max_length=100)


class TagCreate(TagBase):
    pass


class TagResponse(TagBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


# Instrument schemas
class InstrumentBase(BaseModel):
    symbol: str = Field(..., max_length=20)
    name: str = Field(..., max_length=100)
    asset_class: AssetClass
    description: Optional[str] = None


class InstrumentCreate(InstrumentBase):
    pass


class InstrumentUpdate(BaseModel):
    name: Optional[str] = None
    asset_class: Optional[AssetClass] = None
    description: Optional[str] = None


class InstrumentResponse(InstrumentBase):
    id: int
    symbol: str
    created_at: datetime

    class Config:
        from_attributes = True


class InstrumentWithContent(InstrumentResponse):
    content_items: List["ContentItemResponse"] = []


# Content Item schemas
class ContentItemBase(BaseModel):
    title: str = Field(..., max_length=300)
    content_type: ContentType
    rationale: str


class ContentItemCreate(ContentItemBase):
    instrument_id: Optional[int] = None
    direction: Optional[Direction] = None
    entry_zone: Optional[str] = None
    stop_loss: Optional[str] = None
    take_profit: Optional[str] = None
    risk_reward_ratio: Optional[float] = None
    timeframe: Optional[Timeframe] = None
    confidence: Optional[Confidence] = None
    featured: bool = False
    tag_ids: List[int] = []


class ContentItemUpdate(BaseModel):
    title: Optional[str] = None
    content_type: Optional[ContentType] = None
    instrument_id: Optional[int] = None
    direction: Optional[Direction] = None
    entry_zone: Optional[str] = None
    stop_loss: Optional[str] = None
    take_profit: Optional[str] = None
    risk_reward_ratio: Optional[float] = None
    timeframe: Optional[Timeframe] = None
    confidence: Optional[Confidence] = None
    rationale: Optional[str] = None
    featured: Optional[bool] = None
    tag_ids: Optional[List[int]] = None


class ContentItemResponse(ContentItemBase):
    id: int
    instrument_id: Optional[int]
    direction: Optional[Direction]
    entry_zone: Optional[str]
    stop_loss: Optional[str]
    take_profit: Optional[str]
    risk_reward_ratio: Optional[float]
    timeframe: Optional[Timeframe]
    confidence: Optional[Confidence]
    featured: bool
    published_at: datetime
    created_at: datetime
    updated_at: datetime
    tags: List[TagResponse] = []
    instrument: Optional[InstrumentResponse] = None

    class Config:
        from_attributes = True


# Content Item list response (without full instrument nested)
class ContentItemListResponse(BaseModel):
    id: int
    title: str
    content_type: ContentType
    direction: Optional[Direction]
    timeframe: Optional[Timeframe]
    confidence: Optional[Confidence]
    featured: bool
    published_at: datetime
    entry_zone: Optional[str] = None
    stop_loss: Optional[str] = None
    take_profit: Optional[str] = None
    rationale: Optional[str] = None
    tags: List[TagResponse] = []
    instrument_symbol: Optional[str] = None

    class Config:
        from_attributes = True


# Update forward references
InstrumentWithContent.model_rebuild()


# ─── News schemas ────────────────────────────────────────────────────────────

class NewsSourceBase(BaseModel):
    category: str = Field(..., max_length=50)
    name: str = Field(..., max_length=100)
    url: str = Field(..., max_length=500)


class NewsSourceCreate(NewsSourceBase):
    pass


class NewsSourceUpdate(BaseModel):
    category: Optional[str] = None
    name: Optional[str] = None
    url: Optional[str] = None
    enabled: Optional[bool] = None


class NewsSourceResponse(NewsSourceBase):
    id: int
    enabled: bool
    last_fetched_at: Optional[datetime]
    last_error: Optional[str]
    fetch_count: int
    created_at: datetime

    class Config:
        from_attributes = True


class NewsItemBase(BaseModel):
    title: str = Field(..., max_length=500)
    description: Optional[str] = None
    url: str = Field(..., max_length=1000)
    published_at: Optional[datetime] = None
    is_read: bool = False
    is_starred: bool = False
    tags: Optional[str] = None


class NewsItemCreate(NewsItemBase):
    source_id: int


class NewsItemUpdate(BaseModel):
    is_read: Optional[bool] = None
    is_starred: Optional[bool] = None


class NewsItemResponse(NewsItemBase):
    id: int
    source_id: int
    fetched_at: datetime
    source: Optional[NewsSourceResponse] = None

    class Config:
        from_attributes = True


class NewsItemListResponse(BaseModel):
    id: int
    title: str
    description: Optional[str]
    url: str
    published_at: Optional[datetime]
    is_read: bool
    is_starred: bool
    tags: Optional[str]
    source_name: str
    source_category: str

    class Config:
        from_attributes = True


class NewsFetchRequest(BaseModel):
    category: Optional[str] = None  # filter to specific category, None = all


class NewsFetchResponse(BaseModel):
    sources_updated: int
    new_items: int
    errors: int


# ─── Alert schemas ───────────────────────────────────────────────────────────

class AlertRuleBase(BaseModel):
    name: str = Field(..., max_length=100)
    instrument: Optional[str] = None
    condition_type: str  # regime_change | setup_generated | cot_change | price_cross | rsi_level
    condition_params: dict = Field(default_factory=dict)
    enabled: bool = True
    notify_via: str = "telegram"


class AlertRuleCreate(AlertRuleBase):
    pass


class AlertRuleUpdate(BaseModel):
    name: Optional[str] = None
    instrument: Optional[str] = None
    condition_type: Optional[str] = None
    condition_params: Optional[dict] = None
    enabled: Optional[bool] = None
    notify_via: Optional[str] = None


class AlertRuleResponse(AlertRuleBase):
    id: int
    last_triggered: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

    @classmethod
    def from_orm_with_params(cls, rule):
        """Create response from ORM model, parsing condition_params JSON if needed."""
        import json
        params = rule.condition_params
        if isinstance(params, str):
            try:
                params = json.loads(params)
            except (json.JSONDecodeError, TypeError):
                params = {}
        return cls(
            id=rule.id,
            name=rule.name,
            instrument=rule.instrument,
            condition_type=rule.condition_type,
            condition_params=params,
            enabled=rule.enabled,
            notify_via=rule.notify_via,
            last_triggered=rule.last_triggered,
            created_at=rule.created_at,
            updated_at=rule.updated_at,
        )


class AlertLogResponse(BaseModel):
    id: int
    alert_rule_id: int
    triggered_at: datetime
    message: str
    acknowledged: bool
    alert_rule: Optional[AlertRuleResponse] = None

    class Config:
        from_attributes = True


# ─── Correlation schemas ──────────────────────────────────────────────────────

class CorrelationResponse(BaseModel):
    instruments: List[str]
    matrix: List[List[float]]
    timeframe: str  # "1M" | "3M" | "6M"
    computed_at: datetime
    strongest_positive: tuple[str, str, float]
    strongest_negative: tuple[str, str, float]
