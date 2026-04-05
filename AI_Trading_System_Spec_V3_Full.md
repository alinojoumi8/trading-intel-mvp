# AI Trading System — Technical Specification V3 (Full Course Synthesis)
## Professional Macro Swing Trading Engine

**Version:** 3.0 — Full Course Synthesis
**Date:** 2026-03-30
**Courses Synthesized:**
- Transcript Folders 1–9 (Financial Markets, Economics, Central Banks, Sentiment, Fixed Income, FX, Equities, Commodities, Tools)
- Anton Kreil ITPM WISH Framework (Volatility, Gatekeeping, Discipline, Correlating Indicators)
- High Probability Day & Swing Trade Frameworks

**Markets:** Forex, Equities, Commodities (Oil, Gold, Copper), Fixed Income signals
**Time Horizon:** Day trades (hours) + Swing trades (days–weeks) + Position trades (1–3 months)
**Purpose:** Spec document for AI coding agent — build using Anthropic Claude SDK

---

## What Changed in V3 vs V2

V2 covered the ITPM WISH Framework + 3-Step Analysis + 4-Quadrant Grid + IV Ranges + Policy Divergence Engine.

V3 adds the full macro intelligence layer extracted from all transcript folders:

| New in V3 | Source |
|-----------|--------|
| Asset-class specific drivers for FX, Equities, Commodities, Bonds | Folders 5–8 |
| Currency profiles (USD, EUR, GBP, AUD, JPY, CHF, CAD, NZD) | Folder 6 |
| Equity sector rotation by economic cycle quadrant | Folder 7 |
| Bond market signals — yield curve shapes, STIR derivatives | Folder 5 |
| Commodity-specific drivers — Oil supply/demand/EIA, Gold real-rates | Folder 8 |
| Full tool set — Risk Reversals, IV Signals, CFTC, Momentum, Rebalancing Flows, OpEx | Folder 9 |
| Central bank classification — Hawks/Doves, normalization vs tightening | Folder 3 |
| News importance scoring engine — 3-step baseline/surprise/bigger-picture | Folder 2 |
| Underlying vs short-term sentiment distinction | Folder 4 |
| Asset pre-screen — floating vs pegged, tradeable volatility | Training: Regimes |
| Traffic Light system — refined 14-point technical checklist | Training: Gatekeeping |
| Hard stop / soft target / position roll framework | Training: Discipline |
| Correlating indicators — copper, oil, equity sectors as macro confirmation | Training: Correlating |

---

## Core Philosophy

**Everything is connected.** Every asset class influences every other. Never analyze one thing in isolation.

**Relatives beat absolutes.** A bad-but-improving economy beats a good-but-deteriorating one. Rate of change is what markets price — not the absolute level.

**Expectations are everything.** Markets are a forward-looking discounting mechanism. What matters is not what happened — it's whether what happened SURPRISED the market's baseline expectation.

**Professional hierarchy:**
1. Macro fundamentals → generate the directional bias (80% of effort)
2. Gatekeeping (COT + Technicals + Volatility) → time the entry (20% of effort)
3. Risk management → overlaid on everything; capital preservation first

**Underlying vs Short-Term Sentiment:**
- Underlying sentiment = determined by macro quadrant (weeks/months)
- Short-term sentiment = driven by news events and headlines (hours/days)
- Trades ALIGNED with underlying = higher probability, swing/position duration
- Trades AGAINST underlying = day trade/scalp only, tighter stops

---

## 1. Full System Architecture (6 Stages)

```
Stage 0: Asset Pre-Screen (floating? tradeable volatility? spread cost acceptable?)
Stage 1: Market Regime Classifier (Bull/Bear + VIX + Volatility Mode)
Stage 2: Growth/Inflation Grid + Underlying Sentiment (4-Quadrant)
Stage 3: Asset-Class Deep Dive + 3-Step Analysis (Baseline → Surprise → Bigger Picture)
Stage 4: Gatekeeping (COT + IV Ranges + 14-Point Technical Traffic Light)
Stage 5: Final Signal Aggregator + Trade Plan Output
```

Each stage = a separate LLM call. Output of each stage chains as JSON into the next.

---

## 2. Stage 0 — Asset Pre-Screen

### Purpose
Confirm the asset is tradeable, has meaningful volatility, and is not in a fixed/pegged regime (which suppresses volatility).

### Inputs

| Input | Source | Notes |
|-------|--------|-------|
| `asset_name` | User input | e.g. "EURUSD", "SPY", "XAUUSD" |
| `asset_type` | Classified | FX_PAIR / EQUITY_INDEX / COMMODITY / BOND |
| `currency_regime` | Static reference table | FLOATING / MANAGED_FLOAT / PEGGED |
| `atr_30d_pct` | Calculated | 30-day ATR as % of price |
| `spread_cost_pct` | Broker data | Spread as % of ATR |

### Regime Reference (Static)

| Currency | Regime | Tradeable? |
|----------|--------|------------|
| EUR, GBP, JPY, AUD, CAD, CHF, NZD, USD | FLOATING | YES |
| CNY | MANAGED CRAWLING BAND | CAUTION |
| HKD | PEGGED to USD | NO |
| Most GCC currencies (SAR, AED) | PEGGED | NO |
| DKK | PEGGED to EUR | NO |

### LLM Prompt — Stage 0

```
SYSTEM:
Pre-screen filter. REJECT if:
- Currency regime is PEGGED or FIXED
- Daily ATR as % of price < 0.3% (dead market)
- Spread cost exceeds 15% of daily ATR (too expensive)

APPROVE: Major floating FX pairs, major equity indices (S&P, FTSE, DAX, Nikkei, ASX), 
key commodities (Brent/WTI oil, Gold, Copper), bond ETF proxies (TLT, IEF).

USER:
Asset: {asset_name} | Type: {asset_type} | Regime: {currency_regime}
30d ATR %: {atr_30d_pct}% | Spread Cost %: {spread_cost_pct}%

Return JSON:
{
  "pre_screen_result": "APPROVED" | "REJECTED" | "CAUTION",
  "rejection_reason": "<if rejected>",
  "asset_class": "FX_MAJOR" | "FX_CROSS" | "EQUITY_INDEX" | "COMMODITY_ENERGY" | "COMMODITY_METAL" | "BOND_PROXY",
  "volatility_tier": "HIGH" | "MEDIUM" | "LOW",
  "note": "<one sentence>"
}
```

---

## 3. Stage 1 — Market Regime Classifier

### Professional Definitions

- **Bear Market:** Index closes below `previous_cycle_high × 0.80`
- **Bull Market:** Recovered above bear level after a prior bear
- **High Volatility:** VIX risen >25% in 30 days
- **Extreme Volatility:** VIX risen >50% in 30 days

### Trading Mode by Regime

| Trading Mode | Condition | Position Size Modifier |
|---|---|---|
| PORTFOLIO_MANAGER | Bull market, low/normal vol | 1.0× |
| SHORT_TERM_TRADER | Transitioning or high vol | 0.75× |
| REDUCE_EXPOSURE | Bear market / extreme vol | 0.5× |
| SIDELINES | Full bear + extreme vol | 0.25× |

### Inputs

| Input | Source |
|-------|--------|
| `index_price_current` | yfinance (SPY, EWG, EWJ, etc.) |
| `index_previous_cycle_high` | Historical max |
| `vix_current` | yfinance ^VIX |
| `vix_30d_ago` | Historical |
| `iv_1m_annualised` | Options API or yfinance |
| `iv_daily_1sd` | `iv_1m / sqrt(252)` |
| `iv_daily_2sd` | `iv_daily_1sd × 2` |

### LLM Prompt — Stage 1

```
SYSTEM:
Classify market regime using professional trader definitions only.
Bear Market: Index < [prev_high × 0.80]
High Vol: VIX +25% in 30d | Extreme: VIX +50% in 30d

USER:
Index: {name} | Price: {price} | Bear Level: {bear_level}
VIX: {vix} | VIX 30d ago: {vix_30d_ago} | Δ30d: {vix_chg}%
IV 1m annual: {iv_1m}% | Daily 1SD: ±{iv_1sd}% | Daily 2SD: ±{iv_2sd}%

Return JSON:
{
  "market_regime": "BULL" | "BEAR" | "TRANSITIONING_TO_BEAR" | "TRANSITIONING_TO_BULL",
  "volatility_regime": "LOW" | "NORMAL" | "HIGH" | "EXTREME",
  "trading_mode": "PORTFOLIO_MANAGER" | "SHORT_TERM_TRADER" | "REDUCE_EXPOSURE" | "SIDELINES",
  "position_size_modifier": 0.25 | 0.5 | 0.75 | 1.0,
  "iv_daily_1sd_pct": {number},
  "iv_daily_2sd_pct": {number},
  "regime_reasoning": "<2 sentences>",
  "vix_action": "ADD_EXPOSURE" | "HOLD" | "REDUCE_50PCT" | "DAY_TRADE_MODE"
}
```

---

## 4. Stage 2 — Growth/Inflation Grid + Underlying Sentiment

### The 4-Quadrant Framework

```
                    INFLATION DECELERATING | INFLATION ACCELERATING
                   ________________________|________________________
GROWTH             |                       |                        |
ACCELERATING       |    EXPANSION          |    REFLATION           |
                   |  Equities, Risk FX,   |  Commodities, EM,      |
                   |  cyclicals, Oil       |  cyclical FX, Oil      |
                   |  Avoid: Bonds, JPY    |  Watch: Bond yields    |
                   |_______________________|________________________|
GROWTH             |                       |                        |
DECELERATING       |    DISINFLATION       |    STAGFLATION         |
                   |  Bonds, defensives,   |  Gold, CHF, JPY,       |
                   |  USD (mild risk-off)  |  USD, short equities   |
                   |  Avoid: Cyclicals     |  Avoid: EM, cyclicals  |
                   |_______________________|________________________|
```

**CRITICAL: Always use RATE OF CHANGE — compare to 3 months ago.**

A GDP rate improving from 0.5% → 1.2% beats GDP declining from 3.0% → 2.5%.

### Key Macro Confirmation Signals

**Yield Curve:**
- Inverted (10yr < 2yr) → Recession warning; risk-off
- Every US yield curve inversion since 1970 has preceded a recession (6–18 month lead)
- Steepening from inversion → recovery beginning

**Copper:**
- Copper YoY > 0% → global growth healthy (copper = "PhD in economics")
- Copper YoY < -10% → slowdown signal

**Oil:**
- Oil +100% in 6 months → historically preceded every US recession since 1970
- Oil rising → inflation expectations rise → bonds sell off → CB more hawkish

**OECD CLI:**
- 3+ consecutive CLI increases = intermediate growth trend change (bullish)
- 3+ consecutive CLI decreases = growth trend deteriorating (bearish)

### Inputs

| Input | Source |
|-------|--------|
| `gdp_growth_latest` | FRED (GDPC1) |
| `gdp_growth_3m_ago` | FRED |
| `cpi_latest` | FRED (CPIAUCSL) |
| `cpi_3m_ago` | FRED |
| `pmi_mfg_latest` | ISM / Markit |
| `pmi_services_latest` | ISM / Markit |
| `leading_indicator` | FRED (USALOLITONOSTSAM) |
| `consumer_confidence` | FRED (UMCSENT) |
| `yield_curve_spread` | FRED (T10Y2YM) |
| `copper_yoy_pct` | yfinance (HG=F) |
| `oil_yoy_pct` | yfinance (BZ=F) |

### LLM Prompt — Stage 2

```
SYSTEM:
Classify growth/inflation regime using 4-quadrant grid.
EXPANSION: Growth↑ Inflation↓ → Risk ON
REFLATION: Growth↑ Inflation↑ → Risk ON (watch inflation)
DISINFLATION: Growth↓ Inflation↓ → Risk OFF (bonds outperform)
STAGFLATION: Growth↓ Inflation↑ → Risk OFF (gold, CHF, JPY)

RULES:
- Use RATE OF CHANGE not absolute level (compare to 3 months ago)
- Yield curve inversion = recession warning; flag prominently
- Copper YoY < -10% = growth slowdown signal
- Oil +100% over 6m = recession risk
- Assess BOTH underlying (weeks/months) AND short-term (hours/days) sentiment separately

USER:
GDP: {gdp_latest}% | 3m ago: {gdp_3m}% | Direction: {gdp_dir}
CPI: {cpi_latest}% | 3m ago: {cpi_3m}% | Direction: {cpi_dir}
PMI Mfg: {pmi_mfg} | PMI Services: {pmi_svc}
CLI: {cli} | Direction: {cli_dir}
Consumer Confidence: {cc} | Direction: {cc_dir}
Yield Curve (10yr-2yr): {yc}bps | Shape: {yc_shape}
Copper YoY: {copper_yoy}% | Oil YoY: {oil_yoy}%

Return JSON:
{
  "macro_quadrant": "EXPANSION" | "REFLATION" | "DISINFLATION" | "STAGFLATION",
  "quadrant_confidence": "HIGH" | "MEDIUM" | "LOW",
  "growth_trajectory": "ACCELERATING" | "DECELERATING" | "FLAT",
  "inflation_trajectory": "ACCELERATING" | "DECELERATING" | "FLAT",
  "underlying_risk_sentiment": "RISK_ON" | "RISK_OFF" | "NEUTRAL",
  "short_term_risk_sentiment": "RISK_ON" | "RISK_OFF" | "NEUTRAL",
  "sentiment_conflict": true | false,
  "sentiment_conflict_note": "<if conflict: what's causing short-term divergence>",
  "yield_curve_signal": "NORMAL" | "FLATTENING_RISK" | "INVERTED_RECESSION_WARNING",
  "copper_signal": "BULLISH_GROWTH" | "NEUTRAL" | "BEARISH_GROWTH",
  "oil_inflation_risk": "HIGH" | "MEDIUM" | "LOW",
  "preferred_asset_classes": ["2-3 assets that outperform in this regime"],
  "avoid_asset_classes": ["1-2 assets that underperform"],
  "path_of_least_resistance": "LONG_RISK" | "SHORT_RISK" | "NEUTRAL",
  "regime_inflection_risk": true | false,
  "inflection_note": "<what data would signal a regime change>",
  "quadrant_reasoning": "<2-3 sentences using rate-of-change logic>"
}
```

---

## 5. Stage 3 — Asset-Class Deep Dive + 3-Step Analysis

### 5.1 The 3-Step Analysis Process

**Step 1 — BASELINE:** What is the market currently expecting? What is already priced in?

**Step 2 — SURPRISE:** What would deviate from the baseline and genuinely shock markets?
- The market prices expected events BEFORE they happen
- Only DEVIATIONS from expectations trigger repricing
- Ask: given the baseline, what is the biggest possible surprise (up AND down)?

**Step 3 — BIGGER PICTURE:** Would the surprise change the growth/inflation/policy trajectory?
- YES → Swing trade or position trade (days to weeks)
- NO → Day trade / scalp only (hours)

**News Importance Decision Matrix:**

| Scenario | Baseline | Surprise Impact | Trade Type |
|----------|----------|----------------|-----------|
| CB hiking strongly, data still strong | Status quo | Beat/miss won't change direction | Short-term scalp only |
| CB hiking, but data deteriorating sharply | Inflection risk building | Miss could change CB trajectory | Swing trade opportunity |
| CB explicitly data-dependent, near pause | High sensitivity to each print | Any material deviation triggers repricing | Day or Swing |

### 5.2 FX-Specific Analysis

**The Big 3 FX Drivers (in order of importance):**
1. Monetary Policy Divergence — most important single driver
2. Growth / Economic Outlook Divergence — second most important
3. Risk Sentiment — underlying determines path; short-term creates the entry

**Policy Divergence Rules:**
- EARLY + WIDENING = strongest signal, longest duration
- MID-CYCLE = good signal, moderate duration
- LATE + NARROWING = fade the trend, do not chase

**Policy Normalization ≠ Tightening:**
- Normalization = returning to neutral rate = less bullish than tightening
- Tightening = going ABOVE neutral = clearly hawkish = strongest currency support

**Hawkish vs Dovish Signals:**
- Hawkish: rate hikes, QT, higher inflation forecasts, upward GDP revisions, strong labour language
- Dovish: rate cuts, QE, lower inflation forecasts, growth concerns, data-dependent hesitancy, recession forecast
- Policy normalization = moderate hawkish

**Key FX Rule — Always Compare Two:**
Never analyze a currency alone. Always compare: currency A outlook vs currency B outlook on growth, inflation, policy.

**Currency Profiles (static LLM reference):**

| Currency | Key Drivers | Safe Haven | Commodity Link |
|----------|------------|------------|----------------|
| USD | Global reserve; Fed policy; risk-off demand | PRIMARY | Negative (commodities priced in USD) |
| EUR | ECB policy; Eurozone growth divergence; spread fragmentation risk (BTP-Bund) | PARTIAL | None |
| GBP | BOE policy; UK growth; post-Brexit trade flows | No | None |
| JPY | BOJ ultra-low rates; yield differential to US/global; risk-off safe haven | YES | None |
| AUD | RBA policy; China growth (largest partner); iron ore/base metals | No | YES (metals) |
| CAD | BOC policy; WTI oil prices; US economic relationship | No | YES (oil) |
| CHF | SNB policy; European risk proxy; safe haven demand | YES | None |
| NZD | RBNZ policy; China/Asia demand; dairy prices; AUD correlation | No | Soft (dairy) |

**Geopolitical FX Rule:**
- Geopolitical risk → risk-off → JPY, CHF, USD strengthen; EM and commodity FX weaken
- Energy supply disruptions → commodity exporters (CAD, NOK) benefit if they produce energy

### 5.3 Equity-Specific Analysis

**Sector Rotation by Quadrant:**

| Macro Quadrant | Best Sectors | Avoid |
|----------------|-------------|-------|
| EXPANSION | Technology, Consumer Discretionary, Financials | Utilities, Consumer Staples |
| REFLATION | Energy, Materials, Industrials, Financials | Technology (rate-sensitive) |
| DISINFLATION | Consumer Staples, Healthcare, Utilities | Energy, Materials, Financials |
| STAGFLATION | Energy, Gold Miners, Defensives | Technology, Consumer Discretionary, EM |

**CB Data-Dependence Reaction Function:**
- Hiking cycle (tight policy): good data = BAD for equities (more hikes); bad data = GOOD (fewer hikes)
- Cutting cycle (loose policy): good data = GOOD for equities (earnings support); bad data = BAD

**Equity Index Country Composition (matters for sector bias):**
- S&P 500: ~30% technology → rate-sensitive; underperforms in high-rate environments
- DAX: ~20% industrials/autos → more cyclical; outperforms in global growth recovery
- Nikkei: Export-heavy; weakening JPY = tailwind for Nikkei
- ASX200: 30% financials, 20% materials → China growth and commodity-sensitive

### 5.4 Bond Market Signals

**Yield Curve Shapes:**

| Shape | Meaning | Asset Implication |
|-------|---------|------------------|
| Normal (upward sloping) | Healthy growth expectations | Risk ON, equities preferred |
| Flat | Slowdown fears building | Reduce risk asset exposure |
| Inverted (short > long) | Recession signal | Risk OFF; buy bonds, gold, JPY, CHF |
| Steepening from inversion | Recovery beginning | Carefully add risk assets |

**Inflation is a bond's worst enemy:**
- Rising inflation → bond prices fall → yields rise
- CBs must hike to fight inflation → short-end yields rise fastest → curve flattens
- If market expects cuts → long-end rallies → curve steepens

**STIR Derivatives (Short-Term Interest Rate Futures):**
- Fed Funds Futures, SONIA futures, EURIBOR futures = market-implied rate path for next 12 months
- If market prices 3 cuts but CB signals only 1 → divergence = tradeable opportunity
- Track CME FedWatch Tool for US Fed path pricing

### 5.5 Commodity-Specific Analysis

**Oil Drivers:**

Demand:
- Global PMI / GDP / industrial production
- China (biggest marginal consumer)
- Seasonal patterns (summer driving, winter heating)
- Risk sentiment (risk-on = more economic activity = more oil demand)

Supply:
- OPEC+ decisions (bimonthly meetings — always calendar them)
- US rig count (EIA weekly data)
- Geopolitical disruptions in producer nations
- EIA Weekly Petroleum Status Report:
  - Inventory DRAW → price positive
  - Inventory BUILD → price negative

Futures Curve:
- Backwardation (spot > futures) → supply tight → bullish near-term
- Contango (futures > spot) → oversupply → bearish near-term, storage costs drag

**Gold Drivers:**

| Driver | Bullish Gold | Bearish Gold |
|--------|-------------|-------------|
| Real interest rates | Falling / negative | Rising |
| USD | Weakening | Strengthening |
| Risk sentiment | Risk-off / fear / crisis | Risk-on / complacency |
| Inflation expectations | Rising | Falling |
| Central bank buying | High | Low / selling |
| Geopolitical risk | High | Low |

**Gold Rule:** Gold is an inverse real-rate asset.
- Real rate = nominal rate − inflation expectation
- When nominal rates rise faster than inflation → real rates rise → gold falls
- When inflation rises faster than nominal rates → real rates fall → gold rises

### 5.6 Stage 3 Inputs

**All assets:**
| Input | Description |
|-------|-------------|
| `baseline_market_expectations` | Consensus expectation for next catalyst |
| `next_catalyst` | Next scheduled data release or CB event (within 5 days) |
| `catalyst_type` | BIGGER_PICTURE_CHANGER / SHORT_TERM_CATALYST / LOW_IMPACT |
| `recent_data_trend` | Last 3 data points: direction |
| `surprise_probability` | HIGH / MEDIUM / LOW |

**FX additional:**
| Input | Description |
|-------|-------------|
| `base_cb_stance` | HAWKISH / DOVISH / NEUTRAL / PIVOTING_HAWKISH / PIVOTING_DOVISH |
| `quote_cb_stance` | Same for opposing currency |
| `policy_divergence_direction` | BASE_FAVORED / QUOTE_FAVORED / NEUTRAL |
| `divergence_maturity` | EARLY / MID_CYCLE / LATE_CYCLE |
| `rate_differential_bps` | Base minus quote rate |
| `rate_differential_direction` | WIDENING / NARROWING / STABLE |
| `base_growth_vs_quote_growth` | BASE_IMPROVING / QUOTE_IMPROVING / NEUTRAL |
| `base_inflation_vs_quote_inflation` | Same |
| `risk_reversals_skew` | CALLS_PREMIUM / PUTS_PREMIUM / NEUTRAL |
| `cftc_net_pct` | Net non-commercial position % |
| `cftc_status` | EXTREME_LONG / NET_LONG / NEUTRAL / NET_SHORT / EXTREME_SHORT |

**Equities additional:**
| Input | Description |
|-------|-------------|
| `sector_cyclicality` | CYCLICAL / DEFENSIVE |
| `sector_regime_fit` | Does sector outperform in current macro quadrant? |
| `earnings_revision_trend` | UPGRADING / DOWNGRADING / FLAT |
| `pe_vs_historical_avg` | CHEAP / FAIR / EXPENSIVE |
| `cb_data_dependence` | Is CB in data-dependent mode? (affects cyclical reaction) |

**Commodities additional:**
| Input | Description |
|-------|-------------|
| `commodity_type` | ENERGY / PRECIOUS_METAL / BASE_METAL |
| `supply_demand_balance` | SURPLUS / DEFICIT / BALANCED |
| `usd_direction` | STRENGTHENING / WEAKENING / FLAT |
| `real_rates_direction` | RISING / FALLING (critical for gold) |
| `opec_stance` | CUTTING / HOLDING / INCREASING |
| `eia_inventory_trend` | DRAWING / BUILDING / NEUTRAL |
| `curve_structure` | BACKWARDATION / CONTANGO / FLAT |
| `geopolitical_risk` | HIGH / MEDIUM / LOW |

### 5.7 LLM Prompt — Stage 3

```
SYSTEM:
You are a professional macro swing trader using the 3-Step Analysis Process.

RULE 1: RELATIVES beat ABSOLUTES. Bad-but-improving beats good-but-deteriorating.
RULE 2: FX policy divergence — EARLY + WIDENING = strongest signal. LATE + NARROWING = fade.
RULE 3: Catalyst changes BIGGER PICTURE = swing/position trade. Doesn't change it = day trade only.
RULE 4: Trade direction must align with underlying risk sentiment from Stage 2.
RULE 5: Never trade against macro quadrant path of least resistance without explicit strong reason.
RULE 6: Equity in data-dependent CB environment — know cyclical reaction function direction.
RULE 7: For FX — always compare TWO currencies; never analyze one in isolation.
RULE 8: For commodities — separate supply shock from demand shock.
RULE 9: CFTC extreme positioning = WARNING on timing, NOT a direction reversal signal.
RULE 10: Against underlying sentiment = day trade / scalp only, tighter stop.

USER:
STAGE 1: {regime_json}
STAGE 2: {grid_json}

ASSET: {asset_name} | TYPE: {asset_type} | PRICE: {current_price}

3-STEP ANALYSIS:
BASELINE: {baseline} | Rate cycle: {rate_cycle} | Recent data trend: {recent_trend}
SURPRISE: Next catalyst: {catalyst} on {date} | Type: {catalyst_type}
  Bullish surprise: {bullish_surprise}
  Bearish surprise: {bearish_surprise}
  Surprise probability: {surprise_prob}
BIGGER PICTURE: Bullish changes outlook: {bull_big_pic} | Bearish: {bear_big_pic}

[FX ONLY:]
Base CB: {base_cb} | Quote CB: {quote_cb}
Divergence: {div_direction} | Maturity: {div_maturity}
Rate Differential: {rate_diff}bps | Direction: {rate_diff_dir}
Growth Comparison: {growth_comp} | Inflation Comparison: {inflation_comp}
Risk Reversals: {risk_rev} | CFTC Net: {cftc_net}% | Status: {cftc_status}

[EQUITIES ONLY:]
Sector: {sector} | Cyclicality: {cyclicality}
Regime Fit: {regime_fit} | Earnings: {earnings} | P/E: {pe}
CB Data Dependence: {cb_dep}

[COMMODITIES ONLY:]
Type: {type} | Supply/Demand: {sup_dem} | USD: {usd_dir}
Real Rates: {real_rates} | OPEC: {opec} | EIA: {eia} | Curve: {curve}
Geopolitical Risk: {geo_risk}

Return JSON:
{
  "trade_direction": "LONG" | "SHORT" | "NO_TRADE",
  "fundamental_bias": "BULLISH" | "BEARISH" | "NEUTRAL",
  "bias_strength": "STRONG" | "MODERATE" | "WEAK",
  "trade_type": "SWING_CATALYST" | "SWING_TACTICAL" | "DAY_TRADE_ONLY" | "POSITION_TRADE" | "NO_TRADE",
  "aligns_with_underlying_sentiment": true | false,
  "3step_summary": {
    "baseline": "<what is priced in>",
    "surprise_needed": "<what would surprise markets>",
    "bigger_picture_impact": "<does surprise change the trajectory?>"
  },
  "relative_value_score": {
    "rate_of_change_advantage": "BASE" | "QUOTE" | "LONG" | "NEUTRAL",
    "policy_divergence_score": -3 to 3,
    "growth_divergence_score": -3 to 3,
    "inflation_divergence_score": -3 to 3,
    "composite_relative_score": -9 to 9
  },
  "catalyst_assessment": {
    "next_catalyst": "{name}",
    "catalyst_date": "{date}",
    "bullish_scenario": "<outcome and market reaction>",
    "bearish_scenario": "<outcome and market reaction>",
    "trade_duration_implied": "HOURS" | "DAYS" | "WEEKS"
  },
  "asset_class_drivers": {
    "primary_driver": "<most important driver right now>",
    "secondary_driver": "<second most important>",
    "key_risk": "<what could invalidate the bias>"
  },
  "fundamental_reasoning": "<4-6 sentences: macro regime, asset drivers, divergence, catalyst outlook>",
  "key_risks": ["<risk 1>", "<risk 2>", "<risk 3>"]
}
```

---

## 6. Stage 4 — Gatekeeping (COT + IV Ranges + Technical Traffic Light)

### 6.1 Philosophy

Gatekeeping does NOT change the fundamental direction. It only determines WHEN and HOW MUCH to deploy.
- GREEN → Full starter position
- AMBER → Half starter position / watchlist
- RED → Do not deploy; wait for technical alignment

### 6.2 COT / CFTC Positioning

**Source:** CFTC.gov (free CSV), released Fridays
**Track:** Non-commercial (leveraged money) positions only

**Net Position Calculation:**
```
Net Position % = % Leveraged Long - % Leveraged Short
Flip = zero-line crossover = positioning change signal
Extreme Long > +50% = late to trade long (timing caution)
Extreme Short < -40% = late to trade short (timing caution)
```

**COT Decision Matrix:**

| COT Status | Bias LONG | Bias SHORT |
|-----------|-----------|-----------|
| Extreme Long (>+50%) | CAUTION — late | AMBER — good timing |
| Flip (short→long) | GREEN — confirms | AMBER — early reversal |
| Neutral / balanced | GREEN | GREEN |
| Flip (long→short) | AMBER — early reversal | GREEN — confirms |
| Extreme Short (<-40%) | AMBER — good timing | CAUTION — late |

**WARNING:** NEVER reverse fundamental direction based on COT alone. It is TIMING only.

### 6.3 Implied Volatility Tools

**IV Ranges as Dynamic Support/Resistance:**
- Daily 1SD = `IV_annualised / sqrt(252)` → expected ±move with 68% probability
- Daily 2SD = 1SD × 2 → expected ±move with 95% probability; tends to mean-revert
- Entering at 1SD support (longs) or 1SD resistance (shorts) = optimal entry zone
- Price at 2SD extreme = contrarian / mean-reversion signal; caution on momentum

**FX Risk Reversals:**
- Calls at premium (positive RR) → options market pricing upside → bullish confirmation
- Puts at premium (negative RR) → options market pricing downside → bearish confirmation
- Risk reversals diverging from price = early warning of reversal

**Volatility Momentum Signal:**
- HV30 > HV90 → volatility expanding → momentum in direction of recent move
- HV30 < HV90 → volatility contracting → consolidation; breakout may be near

**IV Rising from Low Levels:**
- Low IV then rising sharply = anticipates big directional move ahead
- Very high IV then falling = move may be exhausted; consider fading

### 6.4 Technical Traffic Light (14-Point Checklist)

| # | Check | Confirms LONG | Confirms SHORT |
|---|-------|--------------|----------------|
| 1 | Trend direction | Uptrend (HH, HL) | Downtrend (LH, LL) |
| 2 | Price vs 20MA | Price > 20MA | Price < 20MA |
| 3 | Price vs 60MA | Price > 60MA | Price < 60MA |
| 4 | Price vs 200/250MA | Price > 200MA | Price < 200MA |
| 5 | 20/60 MA cross | Golden cross | Death cross |
| 6 | RSI(14) level | RSI 40–70 (momentum healthy) | RSI 30–60 (momentum weak) |
| 7 | RSI divergence | Price falling, RSI rising | Price rising, RSI falling |
| 8 | Key support/resistance | At key support | At key resistance |
| 9 | IV 1SD level | Price at 1SD support | Price at 1SD resistance |
| 10 | IV 2SD extreme | At 2SD low (mean-reversion) | At 2SD high (mean-reversion) |
| 11 | FX risk reversals | Calls at premium | Puts at premium |
| 12 | CFTC positioning | Flip to long or neutral | Flip to short or neutral |
| 13 | Volume / momentum | Volume expanding on up moves | Volume expanding on down moves |
| 14 | Pattern (ranging) | At support in range | At resistance in range |

**Decision:**
- 10–14 CONFIRMING → GREEN (full starter)
- 6–9 CONFIRMING → AMBER (half starter / watchlist)
- 0–5 CONFIRMING → RED (do not deploy)

### 6.5 Stop Loss & Target Framework

**Hard Stop Loss (place where trade is WRONG, not where R:R looks pretty):**
```
stop_distance = monthly_ATR × 1.3
hard_stop_long = entry_price − stop_distance
hard_stop_short = entry_price + stop_distance
```
Use IV 1SD or 2SD levels as additional reference for stop placement when they coincide with structure.

**Soft Target (review point — NOT automatic exit):**
```
target_distance = stop_distance × 3   (minimum 1:3 R:R)
soft_target_long = entry_price + target_distance
soft_target_short = entry_price − target_distance
```

**When Soft Target Hit — Two Options:**
1. **Roll Stop:** Move hard stop to breakeven or above average price → creates a free trade
2. **Add to Position:** Double size at soft target; roll new stop above average → only if thesis intact

### 6.6 LLM Prompt — Stage 4

```
SYSTEM:
You are the timing/gatekeeping system. You NEVER change the fundamental direction from Stage 3.
Assess: Is now a good time to enter? GREEN / AMBER / RED.
Stop = where trade is WRONG. Not where R:R looks best.
IV 1SD levels = dynamic support/resistance. 2SD = mean-reversion caution.
COT extreme = warning on timing, not direction reversal.
Run 14-point technical checklist. Count confirming vs conflicting.

USER:
FUNDAMENTAL DIRECTION: {direction} | {bias} | {strength} | {trade_type}
ASSET: {asset} | PRICE: {price}

TECHNICALS:
vs 20MA: {v20} | vs 60MA: {v60} | vs 250MA: {v250} | MA Cross: {cross}
RSI: {rsi} | Trend: {trend}
Support: {support} | Resistance: {resistance} | ATR14: {atr}

IV LEVELS:
1SD daily: {1sd_dn} to {1sd_up} | 2SD daily: {2sd_dn} to {2sd_up}
IV Trend: {iv_trend} | HV30 vs HV90: {hv_comp}
Risk Reversals (FX): {risk_rev}

COT: Net %: {cftc_net}% | Status: {cftc_status}

Return JSON:
{
  "gate_signal": "GREEN" | "AMBER" | "RED",
  "entry_quality": "CATALYST_DRIVEN_HIGH_PROB" | "TACTICAL_MEDIUM_PROB" | "LOW_PROB",
  "entry_recommendation": "ENTER_FULL_STARTER" | "ENTER_HALF_STARTER" | "WATCH_LIST" | "DO_NOT_ENTER",
  "checklist_score": {
    "confirming": {0-14},
    "conflicting": {0-14},
    "key_confirming": ["signal1", "signal2"],
    "key_conflicting": ["signal1"]
  },
  "entry_zone": {
    "aggressive": {price},
    "conservative": {price},
    "reasoning": "<why>"
  },
  "stop_loss": {
    "price": {price},
    "reasoning": "<where trade is WRONG>"
  },
  "targets": {
    "t1_soft": {price},
    "t2": {price},
    "t3_stretch": {price}
  },
  "risk_reward_ratio": {number},
  "iv_confluence": true | false,
  "iv_note": "<is entry at a 1SD or 2SD level?>",
  "cot_timing_quality": "IDEAL" | "GOOD" | "CAUTION" | "WAIT",
  "gate_reasoning": "<2-3 sentences on timing>",
  "watch_list_trigger": "<price/event that makes AMBER/RED → GREEN>",
  "soft_target_management": {
    "recommended_action": "ROLL_STOP" | "ADD_TO_POSITION" | "TAKE_PARTIAL_PROFIT",
    "roll_stop_to": {price},
    "add_size_pct": "<% of original to add if adding>"
  }
}
```

---

## 7. Stage 5 — Final Signal Aggregator + Trade Plan

### 7.1 Scoring System

| Criteria | Points |
|----------|--------|
| Macro quadrant aligns with trade direction | +20 |
| 3-Step: surprise would change bigger picture | +15 |
| Policy/growth divergence early and widening | +15 |
| Technical gate GREEN with IV confluence | +15 |
| Trade is catalyst-driven (not just tactical) | +10 |
| Underlying risk sentiment aligns | +10 |
| Trade against underlying sentiment | −10 |
| Technical gate RED | −15 |
| Trade fights macro quadrant path of least resistance | −20 |
| Each major conflicting stage | −5 each |
| CFTC extreme in opposite direction | −5 |
| Purely tactical, no clear catalyst | −5 |

### 7.2 Grade Reference

| Grade | Score | Action |
|-------|-------|--------|
| A | 85–100 | All stages aligned, catalyst-driven, early divergence → Enter full starter |
| B | 70–84 | Strong, minor conflicts → Enter 75% starter |
| C | 55–69 | Moderate, tactical → Half starter, tight stop |
| WATCH | 40–54 | Not ready → Watchlist with trigger price |
| PASS | <40 | Conflicting signals → Do not trade |

### 7.3 Position Sizing Framework

```python
# Position size calculation
def calculate_position_size(
    account_equity: float,
    position_limit_pct: float,   # e.g. 0.33 for forex-only, 0.10 for multi-asset
    stage1_modifier: float,       # 0.25 / 0.5 / 0.75 / 1.0
    signal_grade: str             # A / B / C
) -> dict:
    grade_multiplier = {"A": 1.0, "B": 0.75, "C": 0.50, "WATCH": 0, "PASS": 0}[signal_grade]
    max_position = account_equity * position_limit_pct
    starter_position = max_position * 0.50  # Always start at 50% of max
    adjusted = starter_position * stage1_modifier * grade_multiplier
    return {
        "max_position": max_position,
        "starter_position": starter_position,
        "adjusted_position": adjusted,
        "max_risk_pct": 0.02  # Never risk more than 2% of equity per trade
    }

# Stop loss calculation
def calculate_stop(entry_price: float, monthly_atr: float, direction: str) -> float:
    stop_distance = monthly_atr * 1.3
    return entry_price - stop_distance if direction == "LONG" else entry_price + stop_distance

# Soft target calculation (3:1 R:R minimum)
def calculate_soft_target(entry_price: float, stop_loss: float, direction: str) -> float:
    risk = abs(entry_price - stop_loss)
    return entry_price + (risk * 3) if direction == "LONG" else entry_price - (risk * 3)
```

**Portfolio-Level Risk Controls:**
- Max leverage: 8× for forex; 6× for combined portfolios
- Portfolio stop loss: 20% of total margin → halt all trading, reassess everything
- Single asset limit: 33% (forex-only) / 10–15% (multi-asset)
- Minimum positions: 3 (forex-only) / 8–10 (multi-asset)
- Never add to a losing position

### 7.4 LLM Prompt — Stage 5

```
SYSTEM:
Final signal aggregator. Combine all stages. Capital preservation = first priority.
Minimum score for a trade: 55 (Grade C). Below 55 = NO_TRADE.
When stages conflict: default to WATCH_LIST.

USER:
STAGE 1 (Regime): {s1_json}
STAGE 2 (Grid): {s2_json}
STAGE 3 (Idea): {s3_json}
STAGE 4 (Gate): {s4_json}

Return JSON:
{
  "final_signal": "BUY" | "SELL" | "WATCH_LIST" | "NO_TRADE",
  "signal_confidence": 0-100,
  "signal_grade": "A" | "B" | "C" | "WATCH" | "PASS",
  "direction": "LONG" | "SHORT" | "NEUTRAL",
  "trade_type": "SWING_CATALYST" | "SWING_TACTICAL" | "DAY_TRADE" | "POSITION_TRADE" | "NO_TRADE",
  "asset": "{name}",
  "entry_zone": {"aggressive": {price}, "conservative": {price}},
  "stop_loss": {price},
  "targets": {"t1_soft": {price}, "t2": {price}, "t3_stretch": {price}},
  "risk_reward_ratio": {number},
  "position_size_pct_of_max": {1-100},
  "adjusted_for_vol_modifier": {1-100},
  "hold_duration": "1-4 hours" | "1-2 days" | "2-5 days" | "1-3 weeks",
  "macro_regime": "{quadrant}",
  "underlying_sentiment": "RISK_ON" | "RISK_OFF" | "NEUTRAL",
  "policy_divergence_quality": "EARLY_WIDENING" | "MID_CYCLE" | "LATE_NARROWING" | "N/A",
  "signal_summary": "<6-10 sentence paragraph: macro regime → 3-step baseline/surprise/bigger picture → relative value driver → technical timing → entry/stop/target logic → invalidation>",
  "invalidation_conditions": ["<condition 1>", "<condition 2>", "<condition 3>"],
  "watch_list_trigger": "<if WATCH: what makes this tradeable>",
  "scoring_breakdown": {
    "macro_quadrant_alignment": {score},
    "3step_bigger_picture": {score},
    "policy_divergence": {score},
    "technical_gate": {score},
    "catalyst_quality": {score},
    "sentiment_alignment": {score},
    "deductions": {score},
    "total": {score}
  }
}
```

---

## 8. Special Event Frameworks

### 8.1 Trading Central Bank Decisions

**Type A — Clear Policy Shift:**
- CB clearly signals change in direction (from hiking to pausing, pausing to cutting, etc.)
- Size surprise: 50bps vs expected 25bps = big; 25bps as expected = no surprise
- Action: Trade surprise direction immediately; evaluate if bigger picture changer

**Type B — Status Quo / Data-Dependent:**
- CB holds rates, maintains vague guidance
- Focus on LANGUAGE: slightly more hawkish or dovish vs prior meeting?
- Hawkish language cues: "remain vigilant", "not yet confident", "data dependent but willing"
- Dovish language cues: "meeting by meeting", "balanced risks", growth concerns
- Action: Day trade on language deviation only; not a bigger picture changer

**Quarterly CB Projections (dot plots / MPR / SMP):**
- GDP forecast revisions + inflation forecast revisions + rate path dots
- Upward inflation revision + higher rate path = hawkish surprise
- Downward growth revision + lower rate path = dovish surprise
- Forward guidance revisions matter MORE than the current rate decision

### 8.2 Rebalancing Flows

**Month-end / Quarter-end institutional portfolio rebalancing:**
- Large portfolios rebalance to maintain target allocations (e.g. 60/40)
- If equities rallied strongly → equity weight > target → must sell equities, buy bonds
- Creates predictable calendar-driven FX and equity flows (typically 3–5 days before month-end)
- Japan-specific: if JPY fell vs USD this month → Japanese institutional investors (with large USD holdings) → month-end USD selling / JPY buying expected
- Track direction of equity/bond moves during month to anticipate rebalancing direction

### 8.3 Options Expiry (OpEx) and Quad Witching

**Monthly OpEx (US: 3rd Friday each month):**
- Large open interest at specific strikes creates "pinning" effect
- Price gravitates toward max pain (highest open interest strike)
- After expiry: suppressed vol can be released → monitor for breakout

**Quad Witching (US: 3rd Friday of March, June, Sept, Dec):**
- Simultaneous expiry of stock futures, stock options, index futures, index options
- Creates elevated volatility and volume → can distort price action
- Wait for expiry to pass before reading trend signals from equity markets

---

## 9. Python Data Pipeline

```python
import yfinance as yf
import pandas as pd
import numpy as np
from fredapi import Fred
import ta

# ─── FRED macro data with rate-of-change ─────────────────────────────────────
def get_macro_data(fred_api_key: str) -> dict:
    fred = Fred(api_key=fred_api_key)

    def series_roc(series_id: str, periods: int = 3):
        data = fred.get_series(series_id).dropna()
        latest = float(data.iloc[-1])
        prior = float(data.iloc[-1 - periods])
        roc = ((latest - prior) / abs(prior)) * 100
        direction = "ACCELERATING" if roc > 0.5 else ("DECELERATING" if roc < -0.5 else "FLAT")
        return {"latest": round(latest, 4), "prior": round(prior, 4),
                "roc_pct": round(roc, 2), "direction": direction}

    return {
        "gdp":               series_roc("GDPC1"),
        "cpi":               series_roc("CPIAUCSL"),
        "pce":               series_roc("PCEPI"),
        "unemployment":      series_roc("UNRATE"),
        "leading_indicator": series_roc("USALOLITONOSTSAM"),
        "consumer_sentiment":series_roc("UMCSENT"),
        "yield_curve_spread":series_roc("T10Y2YM"),
        "fed_funds_rate":    series_roc("FEDFUNDS"),
    }


# ─── Implied Volatility ranges ────────────────────────────────────────────────
def calculate_iv_ranges(price: float, iv_annual_pct: float) -> dict:
    iv = iv_annual_pct / 100
    d1sd = iv / np.sqrt(252)
    w1sd = iv / np.sqrt(52)
    m1sd = iv / np.sqrt(12)
    return {
        "daily_1sd_pct":    round(d1sd * 100, 4),
        "daily_2sd_pct":    round(d1sd * 2 * 100, 4),
        "weekly_1sd_pct":   round(w1sd * 100, 4),
        "monthly_1sd_pct":  round(m1sd * 100, 4),
        "monthly_stop":     round(price * m1sd * 1.3, 5),       # hard stop distance
        "monthly_target":   round(price * m1sd * 3 * 1.3, 5),   # 3:1 soft target distance
        "daily_1sd_up":     round(price * (1 + d1sd), 5),
        "daily_1sd_down":   round(price * (1 - d1sd), 5),
        "daily_2sd_up":     round(price * (1 + d1sd * 2), 5),
        "daily_2sd_down":   round(price * (1 - d1sd * 2), 5),
    }


# ─── Technical indicators ─────────────────────────────────────────────────────
def calculate_technicals(ticker: str, period: str = "1y") -> dict:
    df = yf.download(ticker, period=period, auto_adjust=True)
    df['MA20']   = df['Close'].rolling(20).mean()
    df['MA60']   = df['Close'].rolling(60).mean()
    df['MA250']  = df['Close'].rolling(250).mean()
    df['ATR']    = ta.volatility.AverageTrueRange(df['High'], df['Low'], df['Close']).average_true_range()
    df['ATR_M']  = df['ATR'].rolling(21).mean()  # monthly ATR
    df['RSI']    = ta.momentum.RSIIndicator(df['Close']).rsi()
    df['ret']    = df['Close'].pct_change()
    hv30 = df['ret'].tail(20).std() * np.sqrt(252) * 100
    hv90 = df['ret'].tail(60).std() * np.sqrt(252) * 100

    r = df.iloc[-1]; p = df.iloc[-2]

    cross = "NONE"
    if p['MA20'] < p['MA60'] and r['MA20'] > r['MA60']: cross = "GOLDEN"
    elif p['MA20'] > p['MA60'] and r['MA20'] < r['MA60']: cross = "DEATH"

    if r['Close'] > r['MA20'] > r['MA60']:   trend = "UPTREND"
    elif r['Close'] < r['MA20'] < r['MA60']: trend = "DOWNTREND"
    else:                                     trend = "RANGING"

    return {
        "price":         float(r['Close']),
        "ma20":          float(r['MA20']),
        "ma60":          float(r['MA60']),
        "ma250":         float(r['MA250']),
        "rsi_14":        round(float(r['RSI']), 1),
        "atr_14":        round(float(r['ATR']), 5),
        "atr_monthly":   round(float(r['ATR_M']), 5),
        "hv30":          round(hv30, 2),
        "hv90":          round(hv90, 2),
        "hv_comparison": "EXPANDING" if hv30 > hv90 else "CONTRACTING",
        "vs_20ma":       "ABOVE" if r['Close'] > r['MA20'] else "BELOW",
        "vs_60ma":       "ABOVE" if r['Close'] > r['MA60'] else "BELOW",
        "vs_250ma":      "ABOVE" if r['Close'] > r['MA250'] else "BELOW",
        "ma_cross":      cross,
        "trend":         trend,
    }


# ─── Macro quadrant pre-classifier ───────────────────────────────────────────
def classify_quadrant(gdp_dir: str, cpi_dir: str) -> str:
    return {
        ("ACCELERATING", "DECELERATING"): "EXPANSION",
        ("ACCELERATING", "ACCELERATING"): "REFLATION",
        ("DECELERATING", "DECELERATING"): "DISINFLATION",
        ("DECELERATING", "ACCELERATING"): "STAGFLATION",
    }.get((gdp_dir, cpi_dir), "TRANSITIONAL")


# ─── COT CFTC net position ────────────────────────────────────────────────────
def get_cot_position(cot_csv_path: str, currency_name: str) -> dict:
    df = pd.read_csv(cot_csv_path)
    row = df[df['Market_and_Exchange_Names'].str.contains(currency_name, case=False)]
    if row.empty:
        return {"error": "not found"}
    ll = float(row['Lev_Money_Positions_Long_All'].values[0])
    ls = float(row['Lev_Money_Positions_Short_All'].values[0])
    oi = float(row['Open_Interest_All'].values[0])
    net = round(((ll - ls) / oi) * 100, 2)
    status = ("EXTREME_LONG" if net > 50 else
              "NET_LONG"    if net > 25 else
              "EXTREME_SHORT" if net < -40 else
              "NET_SHORT"   if net < -20 else "NEUTRAL")
    return {"net_pct": net, "status": status}
```

---

## 10. LLM Configuration

```python
import anthropic, json, re

client = anthropic.Anthropic()

STAGE_CONFIG = {
    "stage0_prescreen": {"model": "claude-haiku-4-5-20251001", "max_tokens": 400,  "temperature": 0.0},
    "stage1_regime":    {"model": "claude-sonnet-4-6",         "max_tokens": 800,  "temperature": 0.0},
    "stage2_grid":      {"model": "claude-sonnet-4-6",         "max_tokens": 1200, "temperature": 0.1},
    "stage3_idea":      {"model": "claude-opus-4-6",           "max_tokens": 2500, "temperature": 0.2},
    "stage4_gate":      {"model": "claude-sonnet-4-6",         "max_tokens": 1500, "temperature": 0.1},
    "stage5_signal":    {"model": "claude-sonnet-4-6",         "max_tokens": 2500, "temperature": 0.0},
}
# Use claude-opus-4-6 for Stage 3 only — the reasoning-heavy analytical core
# Use claude-haiku-4-5-20251001 for Stage 0 — simple filtering, cost-efficient
# Use claude-sonnet-4-6 for all other stages — classification/rule-following

def run_stage(stage_name: str, system_prompt: str, user_content: str) -> dict:
    cfg = STAGE_CONFIG[stage_name]
    resp = client.messages.create(
        model=cfg["model"], max_tokens=cfg["max_tokens"],
        temperature=cfg["temperature"],
        system=system_prompt,
        messages=[{"role": "user", "content": user_content}]
    )
    text = resp.content[0].text
    match = re.search(r'\{[\s\S]*\}', text)
    if match:
        return json.loads(match.group())
    raise ValueError(f"Stage {stage_name} returned no valid JSON")


def run_full_analysis(asset: str, macro: dict, tech: dict, iv: dict,
                      cot: dict, asset_specific: dict) -> dict:
    s0 = run_stage("stage0_prescreen", S0_SYSTEM, build_s0(asset, tech))
    if s0["pre_screen_result"] == "REJECTED":
        return {"final_signal": "NO_TRADE", "reason": s0["rejection_reason"]}

    s1 = run_stage("stage1_regime", S1_SYSTEM, build_s1(tech, iv))
    s2 = run_stage("stage2_grid",   S2_SYSTEM, build_s2(macro))
    s3 = run_stage("stage3_idea",   S3_SYSTEM, build_s3(s1, s2, asset, asset_specific))

    if s3["trade_direction"] == "NO_TRADE":
        return {"final_signal": "NO_TRADE", "reasoning": s3["fundamental_reasoning"]}

    s4 = run_stage("stage4_gate",   S4_SYSTEM, build_s4(s3, tech, iv, cot))
    s5 = run_stage("stage5_signal", S5_SYSTEM, build_s5(s1, s2, s3, s4))
    return s5
```

---

## 11. Data Sources Reference

| Data Point | Free Source | Better Source |
|------------|------------|---------------|
| GDP (real, QoQ, YoY) | FRED (GDPC1) | Bloomberg |
| CPI / PCE | FRED (CPIAUCSL, PCEPI) | Bloomberg |
| ISM Manufacturing | ismworld.org | Bloomberg |
| ISM Services | ismworld.org | Bloomberg |
| PMI (non-US) | S&P Global / Markit | Bloomberg |
| OECD CLI | FRED (USALOLITONOSTSAM) | OECD |
| Consumer Confidence | FRED (UMCSENT, CSCICP03) | Conference Board |
| Yield Curve (10yr–2yr) | FRED (T10Y2YM) | Bloomberg |
| Fed Funds Rate | FRED (FEDFUNDS) | |
| CB Statements (NLP) | Central bank websites (scrape) | |
| VIX | yfinance (^VIX) | CBOE |
| FX Implied Vol (1m) | Bloomberg / Refinitiv | |
| FX Risk Reversals | Bloomberg | Refinitiv |
| OHLCV (all assets) | yfinance | Bloomberg |
| Economic Calendar | investing.com / Trading Economics API | Bloomberg |
| CFTC COT Report | CFTC.gov (free CSV weekly) | |
| EIA Petroleum Weekly | EIA.gov (free) | |
| OPEC meetings calendar | OPEC.org | |
| Copper spot | yfinance (HG=F) | |
| Gold spot | yfinance (GC=F) | |
| Brent Oil | yfinance (BZ=F) | |
| STIR futures / Fed rate path | CME FedWatch Tool | Bloomberg |

---

## 12. Implementation Phases

| Phase | Description | Deliverable |
|-------|------------|-------------|
| 1 | Data pipeline: FRED, yfinance, COT CSV parser, IV calculator | Working data fetchers for all inputs |
| 2 | Stage 0 + 1 + 2: Pre-screen, regime classifier, macro grid | JSON output for any asset |
| 3 | Stage 3: 3-Step analysis + asset-class logic (FX, equities, commodities, bonds) | Fundamental bias with full reasoning |
| 4 | Stage 4: Gatekeeping — IV ranges, COT traffic light, 14-point technical checklist | Entry zone, stop, targets, R:R |
| 5 | Stage 5: Final aggregator, scoring, trade plan | Grade A–Pass signal with full trade plan |
| 6 | UI / Dashboard: signal summary, invalidation conditions, watchlist management | Web dashboard or CLI output |
| 7 | Backtesting harness: replay historical data through all 6 stages | Performance metrics (win rate, R:R, drawdown) |

---

## 13. Key Rules Summary (Developer Reference)

1. **Fundamentals generate direction. Technicals time entry.** Never let TA override macro direction.
2. **Rate of change, not absolute level.** Always compare to 3 months ago.
3. **Relatives, not absolutes.** Always compare two currencies/assets — never analyze one in isolation.
4. **3-Step for every trade.** Baseline → Surprise → Bigger Picture determines trade type and duration.
5. **Catalyst-driven > tactical.** Prefer trading out of events that create clear market surprises.
6. **Underlying > short-term sentiment.** Trades against underlying = day trade with tight stop only.
7. **Hard stop is automatic. Soft target is a review point.** Roll stop or add to position at target.
8. **1:3 minimum R:R.** Only need 33% win rate to break even. Never force lower R:R.
9. **Starter position first.** Enter at 50% of max. Add when thesis confirmed at soft target.
10. **COT is timing only.** Extreme positioning = warning on timing; never a reason to reverse direction.
11. **Capital preservation first.** Portfolio stop = 20% of margin. When hit, stop all trading, reassess.
12. **Leverage discipline.** Never exceed 8× for forex; 6× combined portfolios.
13. **News importance screen.** Before every data event: run 3-step to assess if it can change the bigger picture. If not — day trade/scalp only, no swing.
14. **CB decisions: language matters as much as rate.** Track forward guidance, dot plots, inflation forecasts — not just the decision.
15. **Correlating indicators confirm.** Use equity sectors, copper, oil, yield curve, CFTC as confirmation — never as standalone signals.

---

## 14. Revision Log

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | Prior | Anton Kreil ITPM WISH Framework only |
| 2.0 | Prior | Added 3-Step, 4-Quadrant Grid, IV ranges, policy divergence engine, signal scoring |
| 3.0 | 2026-03-30 | Full transcript synthesis: FX profiles, equity sector rotation, bond signals, commodity rules (oil + gold), CB decision frameworks, rebalancing flows, OpEx, CFTC deep detail, news importance engine, underlying vs short-term sentiment, Stage 0 pre-screen, hard stop / soft target / roll framework, 14-point technical checklist |
