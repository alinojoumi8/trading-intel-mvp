# Fed Sentiment Module — Design Specification

## Document Metadata
- **Module Name**: Fed Sentiment Module (FSM)
- **Version**: 1.0
- **Created**: 2026-04-05
- **Parent System**: V3 AI Trading System
- **Integration Points**: Stage 1 (Regime Detection), Stage 3 (Fundamental Analysis)
- **Status**: Design Phase — Ready for Implementation

---

## 1. Module Overview

### 1.1 Core Thesis

Federal Reserve communications move markets — but the *highest-value signals* come not from the Fed's words alone, but from the **divergence between what the Fed says and what the market prices in**. When the Fed shifts hawkish but futures markets haven't adjusted, USD-bullish opportunities emerge. When the Fed pivots dovish but it's already priced in, the move is exhausted. This module quantifies both sides and detects the gap.

### 1.2 Module Summary

The Fed Sentiment Module produces a single composite score (`fed_composite_score`) on a scale of -100 (extremely dovish) to +100 (extremely hawkish), updated in near-real-time. It combines two independent components:

1. **Language Sentiment Score** — NLP analysis of all Fed communications scored on a hawkish/dovish scale
2. **Market-Implied Expectations Score** — derived from Fed Funds futures, OIS curves, and Treasury yields

The module's primary output is the **divergence signal** between these two components. When the Fed's language diverges materially from what markets are pricing, the module flags a high-conviction trading opportunity.

### 1.3 Architecture Position

```
┌─────────────────────────────────────────────────────────┐
│                   V3 Trading System                      │
│                                                          │
│  ┌──────────────────────────────────────────────────┐   │
│  │         Fed Sentiment Module (FSM)                │   │
│  │                                                    │   │
│  │  ┌─────────────┐     ┌──────────────────┐        │   │
│  │  │ Component 1  │     │  Component 2      │        │   │
│  │  │ Language NLP  │     │  Market-Implied   │        │   │
│  │  │ Score         │     │  Expectations     │        │   │
│  │  │ [-100,+100]   │     │  Score [-100,+100]│        │   │
│  │  └──────┬────────┘     └────────┬──────────┘        │   │
│  │         │                       │                    │   │
│  │         └───────┬───────────────┘                    │   │
│  │                 ▼                                    │   │
│  │  ┌──────────────────────────────────┐               │   │
│  │  │  Component 3: Composite Engine   │               │   │
│  │  │  • Blended Score [-100,+100]     │               │   │
│  │  │  • Divergence Signal             │               │   │
│  │  │  • Regime Classification         │               │   │
│  │  └──────────────┬───────────────────┘               │   │
│  │                 │                                    │   │
│  └─────────────────┼────────────────────────────────┘   │
│                    │                                     │
│       ┌────────────┴────────────┐                       │
│       ▼                         ▼                       │
│  ┌──────────┐           ┌──────────────┐                │
│  │ Stage 1   │           │  Stage 3      │                │
│  │ Regime    │           │  Fundamental  │                │
│  │ Detection │           │  Analysis     │                │
│  └──────────┘           └──────────────┘                │
└─────────────────────────────────────────────────────────┘
```

---

## 2. Component 1: FOMC Language Sentiment Analysis

### 2.1 Data Sources

#### 2.1.1 Primary Sources (Free)

| Source | URL / Access | Content | Update Frequency | Lag |
|--------|-------------|---------|-------------------|-----|
| **FOMC Statements** | federalreserve.gov/monetarypolicy | Post-meeting policy statements | 8x/year (per meeting) | Real-time |
| **FOMC Meeting Minutes** | federalreserve.gov/monetarypolicy | Detailed meeting discussions | 8x/year | ~3 weeks after meeting |
| **Press Conference Transcripts** | federalreserve.gov/monetarypolicy | Chair Q&A transcripts | 8x/year (post-meeting) | ~2-4 weeks |
| **Beige Book** | federalreserve.gov/monetarypolicy/beige-book | Regional economic conditions | 8x/year | Real-time on release |
| **Fed Governor Speeches** | federalreserve.gov/newsevents/speeches | Individual FOMC member remarks | Irregular, ~50-100/year | Real-time |
| **Congressional Testimony** | federalreserve.gov/newsevents/testimony | Semi-annual and ad hoc | ~2-4x/year | Real-time |
| **FRED API** | fred.stlouisfed.org/docs/api | Economic data + some text series | Continuous | Real-time |

#### 2.1.2 Pre-Built Datasets (Free, for Training/Backtesting)

| Dataset | Source | Content | Use |
|---------|--------|---------|-----|
| **Trillion Dollar Words (FOMC-NLP)** | `gtfintechlab/fomc_communication` on HuggingFace | ~40,000 time-stamped sentences from FOMC minutes, press conferences, and speeches (1996-2022), with ~2,500 manually annotated as hawkish/dovish/neutral | Fine-tuning training data |
| **FOMC Statements & Minutes (Kaggle)** | `drlexus/fed-statements-and-minutes` | Scraped full-text FOMC statements and minutes in CSV | Historical analysis corpus |
| **Parsed FOMC Minutes (Acosta)** | acostamiguel.com/data/fomc_data.html | Pre-parsed FOMC transcripts split by speaker and section since 1976 | Speaker-level analysis |
| **FOMC Scraper (GitHub)** | `vtasca/fed-statement-scraping` | Auto-scraper for FOMC statements and minutes with change tracking | Automated data pipeline |

#### 2.1.3 Premium Data Sources (Optional Enhancements)

| Source | Provider | Content | Cost |
|--------|----------|---------|------|
| **MNLPFEDS** | Morgan Stanley | Proprietary NLP-based Fed sentiment index | Institutional subscription |
| **Permutable AI Fed Tracker** | Permutable | Real-time Fed sentiment scoring | API subscription |
| **FXStreet Fed Sentiment Index** | FXStreet | Composite Fed sentiment measure | Free (basic) / Premium |

### 2.2 Document Type Hierarchy & Weights

Not all Fed communications carry equal weight. The module assigns a **document importance weight** that scales the sentiment score's influence on the composite:

| Document Type | Importance Weight | Rationale |
|--------------|-------------------|-----------|
| FOMC Post-Meeting Statement | 1.00 | Consensus view, most market-moving |
| Press Conference (Chair) | 0.90 | Chair's framing and forward guidance |
| Dot Plot Summary of Economic Projections (SEP) | 0.85 | Quantified rate path expectations |
| FOMC Meeting Minutes | 0.75 | Detailed but lagged (~3 weeks) |
| Beige Book | 0.50 | Qualitative regional data, pre-meeting context |
| Chair Congressional Testimony | 0.80 | Policy signals outside FOMC cycle |
| Vice Chair Speeches | 0.60 | Influential but individual view |
| Governor Speeches (Voters) | 0.50 | Individual views, but they vote |
| Regional Fed President Speeches (Voters) | 0.45 | Vote at meetings they rotate into |
| Regional Fed President Speeches (Non-Voters) | 0.25 | Influence debate, but don't vote |

**Weight decay**: Document scores decay over time. A 30-day exponential decay factor is applied:

```
effective_weight = base_weight × exp(-λ × days_since_publication)
λ = ln(2) / 30   # half-life of 30 days
```

This means an FOMC statement's influence halves every 30 days, naturally fading as new information arrives.

### 2.3 Scoring Methodology

The module uses a **two-tier scoring architecture**: a fast dictionary-based scorer for real-time processing, and an LLM-based scorer for deeper analysis.

#### 2.3.1 Tier 1: Dictionary-Based Sentence Scoring (Real-Time)

**Scale**: Each sentence receives a score from -2.0 (strongly dovish) to +2.0 (strongly hawkish), with 0.0 = neutral.

**Methodology** (adapted from the Kansas City Fed's approach and ECB research):

1. **Tokenize** the document into sentences
2. **Filter** out sentences without monetary policy keywords (reduces noise)
3. **Score** each sentence using the hawkish/dovish dictionary
4. **Handle negations** — a negation word within 3 tokens of a scored keyword flips the polarity
5. **Aggregate** sentence scores into a document-level score

**Monetary Policy Keyword Filter** (sentences must contain at least one to be scored):

```python
POLICY_KEYWORDS = {
    "rate", "rates", "funds rate", "interest", "inflation", "employment",
    "unemployment", "labor", "growth", "GDP", "economic activity",
    "tightening", "easing", "accommodative", "restrictive", "stimulus",
    "tapering", "quantitative", "balance sheet", "forward guidance",
    "price stability", "maximum employment", "dual mandate", "target",
    "projection", "outlook", "forecast", "dot plot", "terminal rate",
    "neutral rate", "soft landing", "recession", "overheating",
    "transitory", "persistent", "entrenched", "disinflation",
    "disinflationary", "deflationary", "stagflation"
}
```

**Hawkish Dictionary** (score = +1.0 each, or +2.0 if marked with *):

```python
HAWKISH_TERMS = {
    # Rate/Policy Direction
    "raise rates": 1.5, "rate increase": 1.5, "rate hike": 1.5,
    "further tightening": 2.0, "additional firming": 1.5,
    "insufficiently restrictive": 2.0, "more restrictive": 1.5,
    "premature to ease": 1.5, "not yet appropriate to reduce": 1.5,
    "hold rates": 0.5, "maintain current stance": 0.5,
    "data dependent": 0.3,  # mild hawkish lean in tightening cycle

    # Inflation Concerns
    "inflation remains elevated": 1.5, "inflation persistent": 2.0,
    "price pressures": 1.0, "inflation expectations unanchored": 2.0,
    "upside risks to inflation": 1.5, "core inflation sticky": 1.5,
    "second-round effects": 1.0, "wage-price spiral": 2.0,
    "overheating": 1.5, "above target": 1.0,
    "broadening price pressures": 1.5,

    # Labor Market Tightness
    "labor market tight": 1.0, "strong labor market": 0.8,
    "wage growth elevated": 1.0, "labor shortage": 0.8,
    "participation rate low": 0.5,

    # Economic Strength
    "robust growth": 0.8, "economic resilience": 0.5,
    "consumer spending strong": 0.5, "above trend growth": 1.0,
    "demand exceeds supply": 1.0,

    # Balance Sheet
    "reduce balance sheet": 1.0, "quantitative tightening": 1.5,
    "accelerate runoff": 1.5, "balance sheet normalization": 1.0
}

DOVISH_TERMS = {
    # Rate/Policy Direction
    "cut rates": -1.5, "rate reduction": -1.5, "rate cut": -1.5,
    "further easing": -2.0, "more accommodative": -1.5,
    "reduce restrictiveness": -1.5, "appropriate to ease": -1.5,
    "lower rates": -1.5, "recalibrate": -1.0,
    "normalization of rates": -1.0,

    # Inflation Declining
    "inflation moderating": -1.0, "disinflation": -1.5,
    "inflation moving toward target": -1.0, "transitory": -1.5,
    "price pressures easing": -1.0, "inflation expectations anchored": -0.8,
    "below target inflation": -1.5, "deflationary": -2.0,

    # Labor Market Weakness
    "labor market softening": -1.0, "rising unemployment": -1.5,
    "job losses": -1.5, "weakening employment": -1.0,
    "slack in labor market": -1.0, "cooling labor market": -0.8,

    # Economic Weakness
    "economic slowdown": -1.5, "recession risk": -2.0,
    "downside risks": -1.0, "below trend growth": -1.0,
    "financial stress": -1.5, "credit tightening": -1.0,
    "demand weakness": -1.0, "consumer pullback": -0.8,

    # Balance Sheet
    "slow balance sheet runoff": -1.0, "pause QT": -1.5,
    "resume purchases": -2.0, "quantitative easing": -2.0,

    # Forward Guidance (Dovish)
    "patient": -0.5, "gradual": -0.5, "cautious": -0.3,
    "flexible": -0.3, "well positioned to adjust": -0.3
}
```

**Negation Handling**:

```python
NEGATION_WORDS = {
    "not", "no", "never", "neither", "nor", "don't", "doesn't",
    "didn't", "won't", "wouldn't", "shouldn't", "cannot", "can't",
    "unlikely", "insufficient", "without", "lack", "absent"
}

# If a negation word appears within 3 tokens before a scored term,
# flip the sign: hawkish becomes dovish and vice versa
# "not yet appropriate to ease" → hawkish (negation of dovish)
# "no longer restrictive enough" → dovish (negation of hawkish)
```

**Document-Level Aggregation**:

```python
def score_document(sentences, scored_sentences):
    """
    document_score = weighted mean of sentence scores
    weight = abs(sentence_score)  # stronger sentences count more
    """
    if not scored_sentences:
        return 0.0

    weights = [abs(s.score) for s in scored_sentences]
    total_weight = sum(weights)
    if total_weight == 0:
        return 0.0

    weighted_sum = sum(s.score * abs(s.score) for s in scored_sentences)
    raw_score = weighted_sum / total_weight  # range: [-2.0, +2.0]

    # Normalize to [-100, +100] scale
    normalized = (raw_score / 2.0) * 100
    return clamp(normalized, -100, 100)
```

#### 2.3.2 Tier 2: LLM-Based Deep Scoring (Batch Processing)

For deeper analysis — especially for press conferences, minutes, and speeches where context and nuance matter — the module uses Claude API calls.

**Prompt Template** (stored in an editable rubric file — see Section 7):

```markdown
# Fed Communication Sentiment Analysis

## Document
- Type: {document_type}
- Date: {date}
- Speaker: {speaker}
- Context: Previous meeting score was {prev_score}

## Full Text
{document_text}

## Scoring Instructions

Analyze this Federal Reserve communication and score it on the following dimensions.
For each dimension, provide a score from -10 (extremely dovish) to +10 (extremely hawkish),
with 0 being perfectly neutral.

### Dimension 1: Rate Path Signal (-10 to +10)
What does this communication signal about the future direction of the federal funds rate?
- Negative = rate cuts likely, easing cycle
- Positive = rate hikes likely or extended hold, tightening bias

### Dimension 2: Inflation Assessment (-10 to +10)
How does the communication characterize inflation?
- Negative = inflation under control, transitory, declining
- Positive = inflation persistent, elevated, concerning

### Dimension 3: Growth/Employment Assessment (-10 to +10)
How does the communication characterize economic activity and the labor market?
- Negative = weakness, softening, downside risks
- Positive = strength, tightness, overheating concerns

### Dimension 4: Forward Guidance Tone (-10 to +10)
What is the overall lean of any forward-looking language?
- Negative = dovish pivot, flexibility, patience
- Positive = hawkish resolve, data dependence in tightening context

### Dimension 5: Language Shift (-10 to +10)
Compared to recent communications, has the tone shifted?
- Negative = shifted more dovish vs. recent baseline
- Positive = shifted more hawkish vs. recent baseline
- 0 = no meaningful shift

## Output Format
Return a JSON object:
{
  "rate_path_signal": <score>,
  "inflation_assessment": <score>,
  "growth_employment": <score>,
  "forward_guidance_tone": <score>,
  "language_shift": <score>,
  "key_phrases": ["<phrase1>", "<phrase2>", ...],
  "shift_description": "<one-sentence description of any tone change>",
  "confidence": <0.0-1.0>
}
```

**LLM Score Aggregation**:

```python
def aggregate_llm_scores(llm_output: dict) -> float:
    """
    Weighted average of the 5 dimensions, normalized to [-100, +100].
    """
    weights = {
        "rate_path_signal": 0.30,
        "inflation_assessment": 0.25,
        "growth_employment": 0.15,
        "forward_guidance_tone": 0.20,
        "language_shift": 0.10,
    }

    weighted_sum = sum(
        llm_output[dim] * w for dim, w in weights.items()
    )
    # Raw range: [-10, +10] → normalize to [-100, +100]
    normalized = weighted_sum * 10
    return clamp(normalized, -100, 100)
```

#### 2.3.3 Tier Selection Logic

```python
def select_scoring_tier(document_type: str, is_realtime: bool) -> str:
    """
    Tier 1 (dictionary) for speed; Tier 2 (LLM) for depth.
    Use both and blend when time permits.
    """
    if is_realtime and document_type == "statement":
        # Statements drop during market hours — need instant score
        return "tier1_only"
    elif is_realtime and document_type in ("press_conference_live", "speech"):
        # Live events — use Tier 1, queue Tier 2 for post-event refinement
        return "tier1_then_tier2"
    else:
        # Batch processing (minutes, historical analysis)
        return "tier2_with_tier1_fallback"
```

**Blending (when both tiers run)**:

```python
def blend_tier_scores(tier1_score: float, tier2_score: float) -> float:
    """
    LLM score is more accurate, but dictionary is faster.
    When both are available, weight LLM more heavily.
    """
    return 0.30 * tier1_score + 0.70 * tier2_score
```

### 2.4 Language Shift Detection

One of the most valuable signals is not the absolute stance but the *change* between consecutive communications. The module tracks this explicitly.

```python
@dataclass
class LanguageShiftSignal:
    current_score: float       # latest document score
    previous_score: float      # prior comparable document score
    delta: float               # current - previous
    delta_zscore: float        # delta / std_dev(historical_deltas)
    shift_category: str        # "hawkish_shift" | "dovish_shift" | "neutral"
    significance: str          # "major" | "minor" | "noise"

def detect_language_shift(
    current_score: float,
    previous_score: float,
    historical_deltas: list[float]
) -> LanguageShiftSignal:
    delta = current_score - previous_score
    std = np.std(historical_deltas) if historical_deltas else 10.0
    zscore = delta / std if std > 0 else 0.0

    if abs(zscore) > 2.0:
        significance = "major"
    elif abs(zscore) > 1.0:
        significance = "minor"
    else:
        significance = "noise"

    if delta > 5.0:
        category = "hawkish_shift"
    elif delta < -5.0:
        category = "dovish_shift"
    else:
        category = "neutral"

    return LanguageShiftSignal(
        current_score=current_score,
        previous_score=previous_score,
        delta=delta,
        delta_zscore=zscore,
        shift_category=category,
        significance=significance,
    )
```

### 2.5 Specific Language Trackers

Beyond the composite score, the module tracks specific **phrase-level transitions** that historically precede policy pivots:

| Phrase Pattern | Transition | Signal |
|---------------|------------|--------|
| "transitory" → "persistent" | Inflation characterization hardening | Hawkish pivot |
| "patient" → "data dependent" | Removing commitment to wait | Hawkish lean |
| "further tightening" → "well positioned" | Dropping bias to hike | Dovish pivot |
| "ongoing increases" → "extent of future increases" | Signaling pause | Dovish shift |
| "some further" → "any additional" | Reducing commitment magnitude | Dovish shift |
| "restrictive enough" → "sufficiently restrictive" | Signaling peak rates | Dovish pivot |
| "inflation expectations anchored" → "unanchored" | Inflation credibility at risk | Extremely hawkish |

**Implementation**: Store each FOMC statement's key phrases in a database. On each new statement, compare against the prior statement's phrases to detect transitions. Flag transitions from the table above as high-priority alerts.

```python
@dataclass
class PhraseTransition:
    phrase_from: str
    phrase_to: str
    document_from_date: str
    document_to_date: str
    signal_type: str         # "hawkish_pivot" | "dovish_pivot"
    historical_significance: str  # narrative from backtesting
```

---

## 3. Component 2: Market-Implied Fed Expectations

### 3.1 Data Sources

| Instrument | Data Source | Access | Update Frequency |
|-----------|------------|--------|------------------|
| **Fed Funds Futures (ZQ)** | CME via yfinance / FRED | Free (delayed) | Daily close / EOD |
| **CME FedWatch Probabilities** | CME FedWatch API | Paid API (EOD + intraday) | Intraday (paid) / EOD (free scrape) |
| **2-Year Treasury Yield** | FRED (`DGS2`) / yfinance (`^IRX`, `^FVX`) | Free | Daily |
| **10Y-2Y Spread** | FRED (`T10Y2Y`) | Free | Daily |
| **SOFR Futures** | CME via yfinance | Free (delayed) | Daily |
| **OIS Swap Rates** | QuantLib construction from SOFR futures | Free (computed) | Daily |
| **Atlanta Fed Market Probability Tracker** | atlantafed.org/cenfis/market-probability-tracker | Free (web) | Meeting-cycle |
| **Minneapolis Fed Probability Tracker** | minneapolisfed.org | Free (web) | Daily |

#### 3.1.1 CME FedWatch API (Preferred for Probabilities)

The CME FedWatch API provides the industry-standard rate probability calculations.

- **Base URL**: `https://markets.api.cmegroup.com/fedwatch/v1`
- **Auth**: OAuth2 Bearer token
- **Endpoints**: `/forecasts` (meeting-by-meeting probabilities), meeting date history/future
- **EOD Update**: Business days at 01:45 UTC
- **Cost**: Paid subscription (contact CME for pricing)

**Free Alternative**: Scrape probabilities from the Atlanta Fed Market Probability Tracker or compute them directly from Fed Funds Futures prices via FRED.

### 3.2 Implied Probability Calculation (Self-Computed)

When the CME FedWatch API is unavailable, the module computes implied probabilities from Fed Funds futures prices using the standard methodology.

#### 3.2.1 Core Formula

```python
def implied_rate_from_futures(futures_price: float) -> float:
    """
    Fed Funds futures are quoted as 100 - implied_rate.
    e.g., price of 95.025 implies rate of 4.975%
    """
    return 100.0 - futures_price

def meeting_probability(
    implied_rate_meeting_month: float,
    current_target_rate: float,
    rate_increment: float = 0.25
) -> dict:
    """
    Calculate probability of rate change at a given meeting.

    CME methodology assumes:
    - Rate changes always in multiples of 25 bps
    - EFFR reacts proportionally to the change

    Example:
    implied_rate = 5.125, current_rate = 5.00, increment = 0.25
    P(hike) = (5.125 - 5.00) / 0.25 = 0.50 → 50% chance of 25bp hike
    P(hold) = 1 - P(hike) = 0.50 → 50% chance of hold
    """
    rate_diff = implied_rate_meeting_month - current_target_rate
    hike_probability = rate_diff / rate_increment

    # Clamp to [0, 1] and handle multiple moves
    if abs(hike_probability) > 1.0:
        # Multiple moves are priced in
        n_moves = int(abs(hike_probability))
        residual = abs(hike_probability) - n_moves
        return {
            "n_full_moves": n_moves,
            "partial_probability": residual,
            "direction": "hike" if hike_probability > 0 else "cut",
            "total_bps_priced": rate_diff * 100,
        }

    return {
        "n_full_moves": 0,
        "partial_probability": abs(hike_probability),
        "direction": "hike" if hike_probability > 0 else "cut",
        "total_bps_priced": rate_diff * 100,
    }
```

#### 3.2.2 Full Meeting-Month Calculation (Handling Split Months)

When an FOMC meeting occurs mid-month, the implied rate must be decomposed:

```python
def decompose_meeting_month(
    futures_implied_rate: float,
    pre_meeting_rate: float,
    meeting_day: int,
    days_in_month: int
) -> float:
    """
    Decompose monthly average into pre- and post-meeting rates.

    The futures contract prices the AVERAGE rate for the month.
    If the meeting is on day M of N total days:

    avg_rate = (M/N) × pre_meeting_rate + ((N-M)/N) × post_meeting_rate

    Solving for post_meeting_rate:
    post_meeting_rate = (avg_rate - (M/N) × pre_meeting_rate) / ((N-M)/N)
    """
    pre_weight = meeting_day / days_in_month
    post_weight = (days_in_month - meeting_day) / days_in_month

    post_meeting_rate = (
        (futures_implied_rate - pre_weight * pre_meeting_rate) / post_weight
    )
    return post_meeting_rate
```

### 3.3 Multi-Instrument Market Expectations Score

The module combines multiple market instruments into a single market expectations score.

#### 3.3.1 Component Signals

```python
@dataclass
class MarketExpectationsSnapshot:
    timestamp: datetime

    # Fed Funds Futures
    next_meeting_implied_rate: float
    next_meeting_probability_hike: float
    next_meeting_probability_cut: float
    next_meeting_probability_hold: float
    meetings_out_12m_total_bps: float  # total cuts/hikes priced over next 12 months

    # Treasury Yields
    yield_2y: float
    yield_2y_30d_change: float  # 30-day change in 2Y yield
    yield_10y_2y_spread: float  # curve steepness

    # SOFR/OIS
    sofr_3m_implied: float
    sofr_12m_implied: float
    ois_term_spread: float  # 12m OIS - 3m OIS

    # Derived
    rate_path_slope: float  # are markets pricing tightening or easing over 12m?
    curve_signal: str       # "steepening" | "flattening" | "inverting" | "normalizing"
```

#### 3.3.2 Market Expectations Score Calculation

```python
def calculate_market_expectations_score(
    snapshot: MarketExpectationsSnapshot,
    current_fed_target: float
) -> float:
    """
    Convert market-implied expectations into a single score [-100, +100].
    Positive = markets expect hawkish (hikes/hold), negative = expect dovish (cuts).
    """
    components = {}

    # 1. Near-term rate expectations (weight: 0.35)
    # How many bps of cuts/hikes are priced for next meeting?
    next_meeting_bps = (snapshot.next_meeting_implied_rate - current_fed_target) * 100
    # Normalize: ±50bps → ±100 score
    components["near_term"] = clamp(next_meeting_bps * 2.0, -100, 100)

    # 2. 12-month cumulative path (weight: 0.30)
    # Total bps priced over next 12 months. ±200bps → ±100 score
    components["rate_path_12m"] = clamp(
        snapshot.meetings_out_12m_total_bps * 0.5, -100, 100
    )

    # 3. 2-Year yield momentum (weight: 0.20)
    # 30-day change in 2Y yield. ±50bps change → ±100 score
    components["yield_momentum"] = clamp(
        snapshot.yield_2y_30d_change * 200, -100, 100
    )

    # 4. Curve shape signal (weight: 0.15)
    # 10Y-2Y spread. Positive spread = normal curve (neutral/hawkish ok).
    # Negative spread = inverted curve (market expects cuts).
    # Range: -200bps to +200bps → -100 to +100
    components["curve_shape"] = clamp(
        snapshot.yield_10y_2y_spread * 50, -100, 100
    )

    weights = {
        "near_term": 0.35,
        "rate_path_12m": 0.30,
        "yield_momentum": 0.20,
        "curve_shape": 0.15,
    }

    score = sum(components[k] * weights[k] for k in weights)
    return clamp(score, -100, 100)
```

### 3.4 "Priced In" Assessment

A critical question: **is the Fed's current stance already reflected in market prices?**

```python
@dataclass
class PricedInAssessment:
    language_score: float      # Component 1 output
    market_score: float        # Component 2 output
    alignment: float           # correlation between the two
    priced_in_pct: float       # 0-100%, how much of Fed's stance is priced in
    category: str              # "fully_priced" | "partially_priced" | "not_priced"

def assess_priced_in(
    language_score: float,
    market_score: float
) -> PricedInAssessment:
    """
    Compare the direction and magnitude of both scores.
    If both are hawkish (positive) and of similar magnitude,
    the market has priced in the Fed's stance.
    """
    # Same direction?
    same_direction = (language_score > 0 and market_score > 0) or \
                     (language_score < 0 and market_score < 0)

    if not same_direction and abs(language_score) > 20 and abs(market_score) > 20:
        return PricedInAssessment(
            language_score=language_score,
            market_score=market_score,
            alignment=-1.0,
            priced_in_pct=0.0,
            category="not_priced",
        )

    # Magnitude comparison — how much of the language score
    # is reflected in the market score?
    if abs(language_score) < 5:
        priced_in_pct = 100.0  # neutral stance, nothing to price in
    else:
        ratio = market_score / language_score if language_score != 0 else 1.0
        priced_in_pct = clamp(ratio * 100, 0, 150)
        # >100% means market is pricing MORE than what Fed is saying

    if priced_in_pct > 80:
        category = "fully_priced"
    elif priced_in_pct > 40:
        category = "partially_priced"
    else:
        category = "not_priced"

    return PricedInAssessment(
        language_score=language_score,
        market_score=market_score,
        alignment=1.0 if same_direction else -1.0,
        priced_in_pct=priced_in_pct,
        category=category,
    )
```

---

## 4. Component 3: Composite Score & Divergence Detection

### 4.1 Composite Score Calculation

```python
@dataclass
class FedCompositeOutput:
    timestamp: datetime

    # Component scores
    language_score: float       # [-100, +100]
    market_score: float         # [-100, +100]

    # Composite
    composite_score: float      # [-100, +100]

    # Divergence
    divergence_score: float     # [-100, +100], signed
    divergence_magnitude: float # [0, 200], unsigned
    divergence_category: str    # see Section 4.2
    divergence_zscore: float    # how unusual is this divergence?

    # Priced-in assessment
    priced_in: PricedInAssessment

    # Regime classification
    fed_regime: str             # see Section 4.3

    # Actionable signal
    trading_signal: str         # see Section 4.4
    signal_conviction: str      # "high" | "medium" | "low"
    signal_direction: str       # "USD_bullish" | "USD_bearish" | "neutral"


def calculate_composite(
    language_score: float,
    market_score: float,
    divergence_history: list[float],
) -> FedCompositeOutput:
    """
    Blend language and market scores. The composite gives slightly
    more weight to market prices (they have skin in the game),
    but language leads — shifts in language precede market repricing.
    """
    # Base composite: weighted blend
    composite = 0.45 * language_score + 0.55 * market_score

    # Divergence: language minus market
    # Positive divergence = Fed MORE hawkish than market prices
    # Negative divergence = Fed MORE dovish than market prices
    divergence = language_score - market_score
    div_magnitude = abs(divergence)

    # Z-score of divergence vs. history
    div_std = np.std(divergence_history) if divergence_history else 20.0
    div_zscore = divergence / div_std if div_std > 0 else 0.0

    # Categorize divergence
    div_category = categorize_divergence(divergence, div_zscore)

    # Priced-in assessment
    priced_in = assess_priced_in(language_score, market_score)

    # Fed regime
    fed_regime = classify_fed_regime(composite, language_score, market_score)

    # Trading signal
    signal, conviction, direction = generate_trading_signal(
        language_score, market_score, divergence, div_zscore, priced_in
    )

    return FedCompositeOutput(
        timestamp=datetime.utcnow(),
        language_score=language_score,
        market_score=market_score,
        composite_score=clamp(composite, -100, 100),
        divergence_score=divergence,
        divergence_magnitude=div_magnitude,
        divergence_category=div_category,
        divergence_zscore=div_zscore,
        priced_in=priced_in,
        fed_regime=fed_regime,
        trading_signal=signal,
        signal_conviction=conviction,
        signal_direction=direction,
    )
```

### 4.2 Divergence Categories

| Category | Condition | Interpretation |
|----------|-----------|----------------|
| `hawkish_surprise` | language > +30, market < +10, divergence z > +1.5 | Fed more hawkish than market expects — USD bullish opportunity |
| `dovish_surprise` | language < -30, market > -10, divergence z < -1.5 | Fed more dovish than market expects — USD bearish opportunity |
| `hawkish_consensus` | language > +20, market > +20, abs(divergence) < 15 | Fed hawkish AND market has priced it — limited move |
| `dovish_consensus` | language < -20, market < -20, abs(divergence) < 15 | Fed dovish AND market has priced it — limited move |
| `market_leads_hawk` | language near 0, market > +30 | Market pricing hikes before Fed signals — watch for Fed catch-up or market correction |
| `market_leads_dove` | language near 0, market < -30 | Market pricing cuts before Fed signals — watch for Fed catch-up or market correction |
| `confusion` | language and market in opposite directions, both > ±20 | Maximum uncertainty — reduce position sizing |
| `neutral` | both scores near 0, low divergence | No actionable signal |

```python
def categorize_divergence(divergence: float, zscore: float) -> str:
    if zscore > 1.5 and divergence > 20:
        return "hawkish_surprise"
    elif zscore < -1.5 and divergence < -20:
        return "dovish_surprise"
    # ... (implement full table above)
```

### 4.3 Fed Regime Classification

The module outputs a regime classification for Stage 1 integration:

```python
FED_REGIMES = {
    "aggressive_tightening": {
        "composite_range": (60, 100),
        "description": "Fed actively raising rates, hawkish language + market pricing hikes",
        "fx_implication": "Strong USD bullish bias",
    },
    "moderate_tightening": {
        "composite_range": (25, 60),
        "description": "Fed leaning hawkish, gradual tightening expected",
        "fx_implication": "Mild USD bullish",
    },
    "neutral_hold": {
        "composite_range": (-25, 25),
        "description": "Fed on pause, balanced language, market pricing stability",
        "fx_implication": "Range-bound, trade other factors",
    },
    "moderate_easing": {
        "composite_range": (-60, -25),
        "description": "Fed leaning dovish, gradual cuts expected",
        "fx_implication": "Mild USD bearish",
    },
    "aggressive_easing": {
        "composite_range": (-100, -60),
        "description": "Fed actively cutting, crisis-mode easing",
        "fx_implication": "Strong USD bearish bias",
    },
    "pivot_in_progress": {
        "condition": "abs(language_shift.delta) > 30 in last 2 meetings",
        "description": "Fed is changing direction — highest volatility regime",
        "fx_implication": "Major trend change forming, high conviction signals",
    },
}
```

### 4.4 Trading Signal Generation

```python
SIGNAL_MATRIX = {
    # (language_bucket, market_bucket, divergence_bucket) → signal
    ("hawkish", "neutral", "large_positive"): {
        "signal": "Fed hawkish, market hasn't priced it. USD bullish opportunity.",
        "conviction": "high",
        "direction": "USD_bullish",
    },
    ("hawkish", "hawkish", "small"): {
        "signal": "Fed hawkish, already priced in. Limited upside for USD.",
        "conviction": "low",
        "direction": "neutral",
    },
    ("dovish", "neutral", "large_negative"): {
        "signal": "Fed dovish pivot, market hasn't priced it. USD bearish opportunity.",
        "conviction": "high",
        "direction": "USD_bearish",
    },
    ("dovish", "dovish", "small"): {
        "signal": "Fed dovish, already priced in. Limited downside for USD.",
        "conviction": "low",
        "direction": "neutral",
    },
    ("neutral", "hawkish", "large_negative"): {
        "signal": "Market pricing hikes Fed hasn't signaled. Potential correction risk.",
        "conviction": "medium",
        "direction": "USD_bearish",
    },
    ("neutral", "dovish", "large_positive"): {
        "signal": "Market pricing cuts Fed hasn't signaled. Potential correction risk.",
        "conviction": "medium",
        "direction": "USD_bullish",
    },
    ("hawkish", "dovish", "extreme"): {
        "signal": "Maximum divergence: Fed hawkish, market pricing cuts. CONFUSION — reduce sizing.",
        "conviction": "low",
        "direction": "neutral",
    },
}

def generate_trading_signal(
    language_score: float,
    market_score: float,
    divergence: float,
    div_zscore: float,
    priced_in: PricedInAssessment,
) -> tuple[str, str, str]:
    lang_bucket = "hawkish" if language_score > 25 else "dovish" if language_score < -25 else "neutral"
    mkt_bucket = "hawkish" if market_score > 25 else "dovish" if market_score < -25 else "neutral"

    if abs(div_zscore) > 2.0:
        div_bucket = "extreme"
    elif abs(divergence) > 30:
        div_bucket = "large_positive" if divergence > 0 else "large_negative"
    else:
        div_bucket = "small"

    key = (lang_bucket, mkt_bucket, div_bucket)
    result = SIGNAL_MATRIX.get(key, {
        "signal": "No clear signal from Fed sentiment module.",
        "conviction": "low",
        "direction": "neutral",
    })
    return result["signal"], result["conviction"], result["direction"]
```

---

## 5. Integration with V3 Trading System

### 5.1 Stage 1 (Regime Detection) Integration

The FSM provides a **Fed Policy Regime** that overlays the existing technical regime detection:

```python
# V3 Stage 1 receives this from FSM
@dataclass
class FSM_Stage1_Output:
    fed_regime: str                 # from Section 4.3
    composite_score: float          # [-100, +100]
    regime_confidence: float        # [0, 1]
    is_pivot_in_progress: bool      # major shift detected
    regime_duration_days: int       # how long in current regime

    # Regime modifiers for Stage 1
    volatility_adjustment: float    # multiplier for expected volatility
    trend_bias: str                 # "bullish_usd" | "bearish_usd" | "none"

# Stage 1 integration logic
def apply_fed_regime_to_stage1(
    technical_regime: str,
    fsm_output: FSM_Stage1_Output,
) -> dict:
    """
    The Fed regime modifies Stage 1's technical regime classification.
    """
    adjustments = {
        "volatility_multiplier": 1.0,
        "directional_bias": "none",
        "position_size_modifier": 1.0,
    }

    # During pivot, increase expected volatility
    if fsm_output.is_pivot_in_progress:
        adjustments["volatility_multiplier"] = 1.5
        adjustments["position_size_modifier"] = 0.75  # reduce size during uncertainty

    # Strong directional regime → add bias
    if abs(fsm_output.composite_score) > 50:
        if fsm_output.composite_score > 0:
            adjustments["directional_bias"] = "bullish_usd"
        else:
            adjustments["directional_bias"] = "bearish_usd"

    # If technical says range-bound but Fed is in aggressive mode,
    # expect breakout — widen stops, reduce counter-trend trades
    if technical_regime == "ranging" and abs(fsm_output.composite_score) > 60:
        adjustments["breakout_probability_boost"] = 0.3

    return adjustments
```

### 5.2 Stage 3 (Fundamental Analysis) Integration

The FSM feeds directly into Stage 3's fundamental scoring:

```python
# V3 Stage 3 receives the full composite output
@dataclass
class FSM_Stage3_Output:
    composite_score: float          # [-100, +100]
    language_score: float           # [-100, +100]
    market_score: float             # [-100, +100]
    divergence_category: str        # from Section 4.2
    divergence_magnitude: float     # [0, 200]
    trading_signal: str             # human-readable signal
    signal_conviction: str          # "high" | "medium" | "low"
    signal_direction: str           # "USD_bullish" | "USD_bearish" | "neutral"
    priced_in_category: str         # "fully_priced" | "partially_priced" | "not_priced"
    key_phrases: list[str]          # notable phrases from latest Fed comm
    next_fomc_date: str             # for event-risk awareness
    days_to_next_fomc: int

# Stage 3 integration
def apply_fed_to_stage3(
    existing_fundamental_score: float,
    fsm_output: FSM_Stage3_Output,
    pair: str,  # e.g., "EURUSD"
) -> float:
    """
    The FSM adjusts the fundamental score for USD pairs.
    For non-USD pairs, this module has reduced influence.
    """
    # Determine USD relevance
    usd_is_base = pair.endswith("USD") or pair.startswith("USD")
    usd_weight = 0.30 if usd_is_base else 0.10

    # Conviction multiplier
    conviction_map = {"high": 1.0, "medium": 0.6, "low": 0.3}
    conviction = conviction_map.get(fsm_output.signal_conviction, 0.3)

    # Direction adjustment
    if fsm_output.signal_direction == "USD_bullish":
        fed_adjustment = fsm_output.composite_score * usd_weight * conviction
        # If USD is quote currency (EURUSD), USD bullish = pair bearish
        if pair.endswith("USD"):
            fed_adjustment = -fed_adjustment
    elif fsm_output.signal_direction == "USD_bearish":
        fed_adjustment = -fsm_output.composite_score * usd_weight * conviction
        if pair.endswith("USD"):
            fed_adjustment = -fed_adjustment
    else:
        fed_adjustment = 0.0

    # Near-FOMC caution: reduce signal weight 48h before meeting
    if fsm_output.days_to_next_fomc <= 2:
        fed_adjustment *= 0.5  # reduce — about to get new data

    adjusted_score = existing_fundamental_score + fed_adjustment
    return clamp(adjusted_score, -100, 100)
```

### 5.3 API Endpoint Specification

```python
# FastAPI endpoint for the V3 system to query FSM
from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/fed-sentiment", tags=["fed-sentiment"])

@router.get("/composite")
async def get_composite_score() -> FedCompositeOutput:
    """Current composite score with all components."""
    pass

@router.get("/language")
async def get_language_score() -> dict:
    """Current language sentiment score with document breakdown."""
    pass

@router.get("/market-expectations")
async def get_market_expectations() -> MarketExpectationsSnapshot:
    """Current market-implied expectations snapshot."""
    pass

@router.get("/divergence")
async def get_divergence() -> dict:
    """Current divergence analysis."""
    pass

@router.get("/history")
async def get_history(days: int = 90) -> list[FedCompositeOutput]:
    """Historical composite scores for charting."""
    pass

@router.get("/stage1-output")
async def get_stage1_output() -> FSM_Stage1_Output:
    """Output formatted for Stage 1 consumption."""
    pass

@router.get("/stage3-output")
async def get_stage3_output() -> FSM_Stage3_Output:
    """Output formatted for Stage 3 consumption."""
    pass

@router.post("/analyze-document")
async def analyze_document(document: FedDocument) -> dict:
    """Ad-hoc analysis of a Fed communication document."""
    pass
```

### 5.4 React Dashboard Components

The V3 dashboard should include:

1. **Fed Sentiment Gauge** — circular gauge showing composite score (-100 to +100), color-coded (red = hawkish, blue = dovish)
2. **Divergence Indicator** — bar chart showing language score vs market score side-by-side, with divergence arrow
3. **Language Trend Chart** — time series of language scores across last 12 months, with FOMC meeting markers
4. **Rate Expectations Curve** — chart of implied rates for each future FOMC meeting (from futures)
5. **Signal Card** — prominent card showing the current trading signal text, conviction, and direction
6. **Phrase Tracker Table** — table of key phrase transitions detected between meetings
7. **Calendar Sidebar** — next FOMC meeting date, days remaining, and countdown

---

## 6. Data Pipeline & Update Schedule

### 6.1 Pipeline Architecture

```
┌─────────────────────────────────────────────────────┐
│                  DATA INGESTION                      │
├──────────────────┬──────────────────────────────────┤
│  Fed Comms       │  Market Data                      │
│  ┌────────────┐  │  ┌──────────────────────────┐    │
│  │ RSS/Scraper │  │  │ FRED API (daily)         │    │
│  │ Fed Website │  │  │ - DFF (fed funds rate)    │    │
│  │ (hourly)    │  │  │ - DGS2 (2Y yield)        │    │
│  └──────┬─────┘  │  │ - T10Y2Y (spread)         │    │
│         │        │  └──────────┬───────────────┘    │
│  ┌──────▼─────┐  │  ┌──────────▼───────────────┐    │
│  │ Tier 1:    │  │  │ yfinance (15-min delay)   │    │
│  │ Dictionary │  │  │ - Fed Funds Futures (ZQ)   │    │
│  │ Scorer     │  │  │ - SOFR Futures             │    │
│  │ (instant)  │  │  │ - Treasury ETFs            │    │
│  └──────┬─────┘  │  └──────────┬───────────────┘    │
│         │        │             │                     │
│  ┌──────▼─────┐  │  ┌──────────▼───────────────┐    │
│  │ Tier 2:    │  │  │ Probability Calculator    │    │
│  │ Claude LLM │  │  │ (from futures prices)      │    │
│  │ (queued)   │  │  │                            │    │
│  └──────┬─────┘  │  └──────────┬───────────────┘    │
│         │        │             │                     │
├─────────┼────────┴─────────────┼────────────────────┤
│         ▼                      ▼                     │
│  ┌──────────────────────────────────────────┐       │
│  │         COMPOSITE ENGINE                  │       │
│  │  Language Score + Market Score → Blend     │       │
│  │  Divergence Detection                     │       │
│  │  Signal Generation                        │       │
│  └───────────────────┬──────────────────────┘       │
│                      │                               │
│                      ▼                               │
│  ┌──────────────────────────────────────────┐       │
│  │         OUTPUT LAYER                      │       │
│  │  → PostgreSQL (history)                   │       │
│  │  → FastAPI endpoints (V3 stages)          │       │
│  │  → WebSocket (React dashboard)            │       │
│  │  → Alert system (divergence triggers)     │       │
│  └──────────────────────────────────────────┘       │
└─────────────────────────────────────────────────────┘
```

### 6.2 Update Schedule

| Data Type | Update Frequency | Trigger |
|-----------|-----------------|---------|
| Market expectations score | Every 15 minutes during market hours | Cron scheduler |
| Language score (new document) | Within 60 seconds of detection | RSS/scraper detection |
| Language score (Tier 2 LLM) | Within 10 minutes of new document | Queued after Tier 1 |
| Composite score | On every component update | Event-driven |
| Divergence history | Daily snapshot at 17:00 EST | Cron |
| Full recalculation | Daily at 01:00 EST | Cron |

### 6.3 Database Schema

```sql
-- Core scores table
CREATE TABLE fed_sentiment_scores (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL,
    language_score FLOAT NOT NULL,
    market_score FLOAT NOT NULL,
    composite_score FLOAT NOT NULL,
    divergence_score FLOAT NOT NULL,
    divergence_category VARCHAR(50),
    fed_regime VARCHAR(50),
    trading_signal TEXT,
    signal_conviction VARCHAR(10),
    signal_direction VARCHAR(20),
    metadata JSONB
);

-- Document analysis results
CREATE TABLE fed_documents (
    id SERIAL PRIMARY KEY,
    document_type VARCHAR(50) NOT NULL,
    document_date DATE NOT NULL,
    speaker VARCHAR(100),
    source_url TEXT,
    full_text TEXT,
    tier1_score FLOAT,
    tier2_score FLOAT,
    blended_score FLOAT,
    tier2_dimensions JSONB,  -- the 5-dimension LLM scores
    key_phrases JSONB,
    importance_weight FLOAT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Phrase transition tracking
CREATE TABLE phrase_transitions (
    id SERIAL PRIMARY KEY,
    phrase_from TEXT NOT NULL,
    phrase_to TEXT NOT NULL,
    doc_from_id INT REFERENCES fed_documents(id),
    doc_to_id INT REFERENCES fed_documents(id),
    signal_type VARCHAR(30),
    detected_at TIMESTAMPTZ DEFAULT NOW()
);

-- Market expectations snapshots
CREATE TABLE market_expectations (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL,
    fed_target_rate FLOAT,
    next_meeting_implied_rate FLOAT,
    prob_hike FLOAT,
    prob_cut FLOAT,
    prob_hold FLOAT,
    total_bps_12m FLOAT,
    yield_2y FLOAT,
    yield_spread_10y2y FLOAT,
    market_score FLOAT,
    raw_data JSONB
);

-- Indexes
CREATE INDEX idx_scores_timestamp ON fed_sentiment_scores(timestamp);
CREATE INDEX idx_documents_date ON fed_documents(document_date);
CREATE INDEX idx_market_timestamp ON market_expectations(timestamp);
```

---

## 7. Autoresearch Optimization Pattern

Following the Karpathy autoresearch pattern, the FSM's scoring rubric is stored in an editable markdown file that can be iteratively optimized against historical FOMC outcomes.

### 7.1 Rubric File Structure

```
fed_sentiment_module/
├── config/
│   ├── scoring_rubric.md           # THE editable rubric — human-written
│   ├── hawkish_dovish_dictionary.json  # term weights, editable
│   ├── document_weights.json       # importance weights, editable
│   └── signal_matrix.json          # trading signal mapping, editable
├── optimization/
│   ├── program.md                  # autoresearch agent instructions
│   ├── eval_dataset.json           # historical FOMC events + known outcomes
│   ├── scoring_function.py         # automated evaluation scorer
│   └── optimization_log.json       # results of each iteration
```

### 7.2 Evaluation Dataset Format

```json
{
  "events": [
    {
      "date": "2022-03-16",
      "event_type": "fomc_meeting",
      "statement_text": "...",
      "actual_decision": "hike_25",
      "actual_dot_plot_shift": "+50bps_median",
      "dxy_reaction_1h": "+0.8%",
      "dxy_reaction_24h": "+1.2%",
      "eurusd_reaction_1h": "-0.7%",
      "treasury_2y_reaction": "+12bps",
      "was_surprise": true,
      "correct_signal": "USD_bullish",
      "correct_conviction": "high"
    }
  ]
}
```

### 7.3 Scoring Function (for Autoresearch)

The optimizer evaluates the rubric against historical events using these binary criteria:

```python
def evaluate_rubric(rubric_config: dict, eval_dataset: list) -> dict:
    """
    Binary scoring criteria (Karpathy pattern: yes/no, add up yeses).
    """
    results = {
        "direction_accuracy": 0,       # Did signal direction match actual FX move?
        "conviction_calibration": 0,    # Did high-conviction signals produce larger moves?
        "divergence_detection": 0,      # Were surprise events flagged as divergences?
        "priced_in_accuracy": 0,        # Did "priced in" events produce smaller moves?
        "regime_accuracy": 0,           # Was regime classification correct?
        "total_events": len(eval_dataset),
    }

    for event in eval_dataset:
        # Recompute scores using current rubric
        language_score = score_with_rubric(event["statement_text"], rubric_config)
        # ... compute full signal
        signal = generate_signal(language_score, market_score)

        # Criterion 1: Direction correct?
        actual_direction = "USD_bullish" if event["dxy_reaction_24h"] > 0.1 else \
                          "USD_bearish" if event["dxy_reaction_24h"] < -0.1 else "neutral"
        if signal.direction == actual_direction:
            results["direction_accuracy"] += 1

        # Criterion 2: High conviction → bigger move?
        if signal.conviction == "high" and abs(event["dxy_reaction_24h"]) > 0.5:
            results["conviction_calibration"] += 1
        elif signal.conviction == "low" and abs(event["dxy_reaction_24h"]) < 0.3:
            results["conviction_calibration"] += 1

        # Criterion 3: Surprise events flagged?
        if event["was_surprise"] and signal.divergence_category in (
            "hawkish_surprise", "dovish_surprise"
        ):
            results["divergence_detection"] += 1
        elif not event["was_surprise"]:
            results["divergence_detection"] += 1  # correctly not flagging

        # Criterion 4: Priced-in events → small moves?
        if signal.priced_in_category == "fully_priced" and \
           abs(event["dxy_reaction_24h"]) < 0.3:
            results["priced_in_accuracy"] += 1
        elif signal.priced_in_category == "not_priced" and \
             abs(event["dxy_reaction_24h"]) > 0.3:
            results["priced_in_accuracy"] += 1

    # Calculate percentages
    n = results["total_events"]
    results["direction_accuracy_pct"] = results["direction_accuracy"] / n * 100
    results["conviction_calibration_pct"] = results["conviction_calibration"] / n * 100
    results["divergence_detection_pct"] = results["divergence_detection"] / n * 100
    results["priced_in_accuracy_pct"] = results["priced_in_accuracy"] / n * 100

    results["composite_score"] = (
        results["direction_accuracy_pct"] * 0.35 +
        results["conviction_calibration_pct"] * 0.25 +
        results["divergence_detection_pct"] * 0.25 +
        results["priced_in_accuracy_pct"] * 0.15
    )

    return results
```

### 7.4 Optimization Loop

```python
# program.md instructions for the autoresearch agent:
"""
## Objective
Optimize the Fed Sentiment Module's scoring rubric to maximize composite
accuracy score against the historical evaluation dataset.

## What You Can Modify
1. config/hawkish_dovish_dictionary.json — term weights
2. config/document_weights.json — document importance weights
3. config/signal_matrix.json — signal generation thresholds
4. The LLM prompt template in scoring_rubric.md — dimension weights, instructions

## What You Cannot Modify
1. The evaluation dataset (eval_dataset.json)
2. The scoring function (scoring_function.py)
3. The core architecture (composite calculation structure)

## Process
1. Run the current rubric through scoring_function.py
2. Record the baseline score
3. Make ONE focused change to a config file
4. Re-run the scorer
5. If score improved: keep the change, log it
6. If score decreased: revert, try a different change
7. Repeat for up to 50 iterations

## Constraints
- Each iteration must complete in under 2 minutes
- Log every change and its impact in optimization_log.json
- Never change more than one config file per iteration
"""
```

---

## 8. Historical Validation & Backtesting

### 8.1 Backtesting Approach

| # | Task | Status |
|---|------|--------|
| 1 | Collect all FOMC statements 2015-2025 (10 years, ~80 meetings) | ☐ |
| 2 | Collect DXY, EURUSD, 2Y yield, Fed Funds futures data for same period | ☐ |
| 3 | Score all historical statements with Tier 1 + Tier 2 | ☐ |
| 4 | Reconstruct market expectations at each meeting from futures prices | ☐ |
| 5 | Compute divergence scores for all meetings | ☐ |
| 6 | Correlate divergence signals with 1h, 24h, 1w FX moves | ☐ |
| 7 | Evaluate direction accuracy across full sample | ☐ |
| 8 | Test across known regime changes (2018 pause, 2019 cuts, 2020 emergency, 2022-23 hikes, 2024 cuts) | ☐ |
| 9 | Run walk-forward optimization: train on 2015-2020, validate on 2021-2025 | ☐ |
| 10 | Sensitivity test: vary dictionary weights ±30%, recompute accuracy | ☐ |
| 11 | Compare against baseline: does FSM improve V3 performance vs. V3 without FSM? | ☐ |

### 8.2 Key Historical Test Cases

These are the critical FOMC events the module must handle correctly to be credible:

| Date | Event | Expected Signal | Expected Market Reaction |
|------|-------|-----------------|--------------------------|
| 2018-01-31 | FOMC upgrades inflation language to "symmetric" | Hawkish shift | DXY rally, yields up |
| 2018-12-19 | Powell "auto-pilot" QT remark at presser | Hawkish surprise | Risk-off, USD spike |
| 2019-01-30 | FOMC removes "further gradual increases" — the Pivot | Major dovish shift | DXY drops, yields crash |
| 2019-07-31 | First cut in 10 years, "mid-cycle adjustment" | Hawkish cut (less dovish than expected) | DXY rallied (surprise) |
| 2020-03-15 | Emergency Sunday cut to 0% + QE restart | Maximum dovish | DXY dropped then rallied (flight to safety) |
| 2021-11-03 | Drops "transitory" from inflation language | Hawkish shift | Yields up, DXY up |
| 2022-03-16 | First hike of cycle, 25bps | Hawkish, market already pricing it | Modest DXY move (priced in) |
| 2022-06-15 | Surprise 75bps hike (market expected 50 two weeks prior) | Hawkish surprise | DXY spike |
| 2023-01-31 | "Disinflation" repeated 13 times in presser | Major dovish shift signal | DXY dropped |
| 2024-09-18 | First cut of cycle, 50bps (debate between 25 and 50) | Dovish, partially priced | Modest DXY move |

### 8.3 Target Performance Metrics

| Metric | Minimum | Ideal | Description |
|--------|---------|-------|-------------|
| Direction accuracy (24h) | > 60% | > 70% | Signal direction matches DXY move |
| Conviction calibration | > 55% | > 65% | High conviction → larger moves, low conviction → smaller |
| Surprise detection rate | > 70% | > 85% | Correctly flags surprise events as divergences |
| Priced-in accuracy | > 60% | > 75% | Correctly identifies when moves are already priced in |
| False positive rate (divergence) | < 30% | < 15% | Flagging divergence when none exists |
| Walk-forward consistency | > 55% direction accuracy out-of-sample | > 65% | Rubric generalizes beyond training data |

### 8.4 Comparison Benchmarks

Compare FSM performance against:

1. **Naive baseline**: always predict same direction as composite score sign
2. **Market-only baseline**: trade based on futures probabilities alone (no language)
3. **Language-only baseline**: trade based on NLP score alone (no market data)
4. **FXStreet Fed Sentiment Index**: if available, compare direction calls

The FSM should **outperform both individual components** — the value comes from the divergence detection, not from either score alone.

---

## 9. Technical Implementation Details

### 9.1 Technology Stack

| Component | Technology | Notes |
|-----------|-----------|-------|
| **Language** | Python 3.11+ | Match V3 system |
| **Web Framework** | FastAPI | Match V3, add FSM endpoints |
| **NLP — Tier 1** | Custom dictionary scorer + spaCy for tokenization | Fast, no GPU needed |
| **NLP — Tier 2** | Claude API (`claude-sonnet-4-6`) | Balance quality and cost; upgrade to Opus for backtesting |
| **Pre-trained model** | `gtfintechlab/FOMC-RoBERTa` via HuggingFace | Optional Tier 1.5 — fine-tuned BERT for hawkish/dovish |
| **Market Data** | FRED API (`fredapi` package) + `yfinance` | Free, already in V3 |
| **OIS Curve** | QuantLib Python | For SOFR curve construction |
| **Database** | PostgreSQL (match V3) | Store all scores and documents |
| **Scheduler** | APScheduler | For periodic data pulls |
| **Scraper** | `httpx` + `BeautifulSoup` | For Fed website RSS/HTML |
| **Dashboard** | React (match V3) + Recharts | For visualization components |

### 9.2 File/Module Structure

```
v3_trading_system/
├── modules/
│   └── fed_sentiment/
│       ├── __init__.py
│       ├── config/
│       │   ├── scoring_rubric.md
│       │   ├── hawkish_dovish_dictionary.json
│       │   ├── document_weights.json
│       │   └── signal_matrix.json
│       ├── ingestion/
│       │   ├── fed_scraper.py          # Scrapes Fed website for new docs
│       │   ├── fred_client.py          # FRED API wrapper
│       │   ├── market_data.py          # yfinance + futures data
│       │   └── document_store.py       # Saves raw docs to DB
│       ├── scoring/
│       │   ├── dictionary_scorer.py    # Tier 1 scorer
│       │   ├── llm_scorer.py           # Tier 2 Claude scorer
│       │   ├── roberta_scorer.py       # Optional Tier 1.5
│       │   └── score_blender.py        # Blends tier scores
│       ├── market_expectations/
│       │   ├── futures_probability.py  # Fed Funds futures → probabilities
│       │   ├── ois_curve.py            # QuantLib OIS curve construction
│       │   ├── yield_tracker.py        # 2Y yield momentum
│       │   └── market_score.py         # Composite market expectations score
│       ├── composite/
│       │   ├── composite_engine.py     # Blends language + market scores
│       │   ├── divergence_detector.py  # Divergence classification
│       │   ├── regime_classifier.py    # Fed regime classification
│       │   └── signal_generator.py     # Trading signal output
│       ├── api/
│       │   └── routes.py              # FastAPI endpoints
│       ├── optimization/
│       │   ├── program.md             # Autoresearch instructions
│       │   ├── eval_dataset.json      # Historical events for optimization
│       │   └── scoring_function.py    # Evaluation scorer
│       └── tests/
│           ├── test_dictionary_scorer.py
│           ├── test_futures_probability.py
│           ├── test_composite_engine.py
│           └── test_historical_cases.py
```

### 9.3 Implementation Phases

1. **Phase 1 — Data Pipeline** (Week 1-2): Build Fed document scraper, FRED/yfinance data pulls, database schema. Verify data collection for all sources.

2. **Phase 2 — Language Scoring** (Week 2-3): Implement Tier 1 dictionary scorer. Test against known hawkish/dovish statements. Implement Tier 2 LLM scorer with Claude API. Optionally integrate FOMC-RoBERTa as Tier 1.5.

3. **Phase 3 — Market Expectations** (Week 3-4): Implement futures probability calculator. Build 2Y yield and curve shape trackers. Compute market expectations score.

4. **Phase 4 — Composite Engine** (Week 4-5): Blend scores. Implement divergence detection. Implement signal generation. Connect to V3 Stage 1 and Stage 3.

5. **Phase 5 — Historical Validation** (Week 5-7): Score all historical FOMC events. Run backtesting against DXY/EURUSD. Compute accuracy metrics. Run autoresearch optimization loop to refine rubric.

6. **Phase 6 — Dashboard & Live Deployment** (Week 7-8): Build React dashboard components. Deploy with live data feeds. Monitor and refine.

### 9.4 Coding Agent Instructions

When implementing this module, pay attention to these non-obvious requirements:

1. **FOMC calendar awareness**: The module must know the FOMC meeting schedule. Hardcode the current year's dates and scrape the Fed's website for future years. The blackout period (10 days before each meeting when Fed officials can't speak publicly) is important context.

2. **Rate regime sensitivity**: The dictionary's "data dependent" phrase is mildly hawkish *during a tightening cycle* but mildly dovish *during an easing cycle*. The scorer needs to know the current regime to correctly score context-dependent phrases.

3. **Dot plot handling**: The Summary of Economic Projections (SEP) is released quarterly (March, June, September, December meetings). The dot plot's median rate path for year-end is a quantitative signal that should override NLP scoring for those meetings.

4. **Press conference lag**: The Fed posts the press conference transcript days after the event. During the live press conference, only wire headlines are available. The module should ingest headlines in real-time (via RSS/news API) and queue the full transcript for Tier 2 analysis when posted.

5. **Split-month futures edge case**: If an FOMC meeting falls on the first or last day of a month, the decomposition formula in Section 3.2.2 can produce unstable results. Add bounds checking and fall back to the adjacent month's contract.

6. **Claude API rate limits**: Batch Tier 2 scoring. Don't send every sentence individually — send the full document in one call. For backtesting 80+ historical meetings, implement exponential backoff and respect rate limits.

7. **Error handling**: If the FRED API is down, use yfinance as fallback for yield data. If yfinance is down, use the last known values with a staleness flag. Never output a composite score based on stale data without flagging it.

---

## 10. Research References & Data Sources

### 10.1 Academic Papers

- **"Trillion Dollar Words"** (Shah et al., ACL 2023) — The foundational dataset and classification benchmark. Code at `gtfintechlab/fomc-hawkish-dovish`, pre-trained model at `gtfintechlab/FOMC-RoBERTa` on HuggingFace.
- **"Gauging the Sentiment of FOMC Communications"** (Federal Reserve FEDS 2025-048) — The Fed's own research on sentiment extraction from FOMC texts.
- **"Deciphering Federal Reserve Communication"** (Kansas City Fed Working Paper RWP 20-14) — Dictionary-based approach with negation handling.
- **"CB-LMs: Language Models for Central Banking"** (BIS Working Paper 1215) — Foundation models fine-tuned for central bank text classification.
- **"FOMC Minutes Sentiments and Their Impact on Financial Markets"** (Journal of International Financial Markets, 2021) — Empirical evidence that FOMC sentiment scores predict market returns.
- **"Modeling Hawkish-Dovish Latent Beliefs in Multi-Agent Debate-Based LLMs"** (arXiv:2511.02469) — Multi-agent LLM framework for monetary policy classification.
- **ECB Working Paper 2085** — "Between Hawks and Doves: Measuring Central Bank Communication" — Cross-applicable methodology from ECB research.

### 10.2 Data Sources Summary

| Source | Type | URL | Cost |
|--------|------|-----|------|
| Federal Reserve Website | FOMC statements, minutes, transcripts | federalreserve.gov/monetarypolicy | Free |
| FRED API | Economic data, yields, rates | fred.stlouisfed.org/docs/api | Free (API key required) |
| gtfintechlab/fomc_communication | 40k annotated FOMC sentences | huggingface.co/datasets/gtfintechlab/fomc_communication | Free |
| gtfintechlab/FOMC-RoBERTa | Pre-trained hawkish/dovish classifier | huggingface.co/gtfintechlab/FOMC-RoBERTa | Free |
| Kaggle FOMC Dataset | Historical statements and minutes CSV | kaggle.com/datasets/drlexus/fed-statements-and-minutes | Free |
| vtasca/fed-statement-scraping | Auto-scraper for Fed documents | github.com/vtasca/fed-statement-scraping | Free |
| CME FedWatch API | Rate probabilities | cmegroup.com/market-data/market-data-api/fedwatch-api.html | Paid |
| Atlanta Fed Probability Tracker | Meeting-by-meeting rate probabilities | atlantafed.org/cenfis/market-probability-tracker | Free |
| Minneapolis Fed Probability Tracker | Historical probability data | minneapolisfed.org | Free |
| yfinance | Treasury yields, futures prices | pypi.org/project/yfinance | Free |
| Parsed FOMC Data (Acosta) | Pre-parsed transcripts since 1976 | acostamiguel.com/data/fomc_data.html | Free |

### 10.3 Tools & Libraries

| Tool | Purpose | License |
|------|---------|---------|
| `fredapi` | Python wrapper for FRED API | Apache 2.0 |
| `yfinance` | Market data (yields, futures) | Apache 2.0 |
| `spaCy` | Sentence tokenization, NLP pipeline | MIT |
| `transformers` (HuggingFace) | Load FOMC-RoBERTa model | Apache 2.0 |
| `QuantLib` (Python bindings) | OIS curve construction | Modified BSD |
| `anthropic` | Claude API for Tier 2 scoring | Proprietary (API) |
| `httpx` + `BeautifulSoup` | Fed website scraping | BSD / MIT |
| `APScheduler` | Cron-like job scheduling | MIT |

---

## 11. Revision Log

| Version | Date | Changes | Reason |
|---------|------|---------|--------|
| 1.0 | 2026-04-05 | Initial design specification | — |
