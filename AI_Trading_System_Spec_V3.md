# AI Trading System — Complete Technical Specification V3
## Professional Macro Swing Trading Engine with MT5 Execution & Web Dashboard

---

## Document Metadata

| Field | Value |
|-------|-------|
| **System Name** | WISH-AI Trading Engine |
| **Version** | 3.0 — Final Build Spec |
| **Created** | 2026-03-30 |
| **Asset Classes** | Forex, Equities, Crypto, Commodities |
| **Strategy Type** | Macro-Fundamental Swing Trading |
| **Primary Timeframe** | Daily / 4H (swing: 1–5 days) |
| **Execution** | Semi-automated — AI signals, human approval, MT5 execution |
| **Source Material** | Anton Kreil ITPM WISH Framework + Professional FX & Fundamental Masterclass |
| **Status** | Design Complete — Ready for Implementation |
| **Target Builder** | Claude Code / AI coding agent |

---

## Source Material Summary

This system is extracted and synthesised from two professional trading courses:

**Course 1 — ITPM / Anton Kreil (Professional Trading & Forex Masterclass):**
Provides the systematic process framework — the WISH Framework (Idea Generation → Gatekeeping → Risk Management → Self-Awareness). Defines market regimes using the professional bull/bear definition (previous business cycle high × 0.80), the 80/20 fundamental/technical split, the 10 macro drivers, meaningful moving averages (20/60/250 day), and volatility management via VIX.

**Course 2 — Professional FX & Fundamental Masterclass (transcript library):**
Provides the modern analytical engine — the 3-Step Analysis Process (Baseline → Surprise → Bigger Picture), the Growth/Inflation 4-Quadrant Grid (Expansion / Reflation / Disinflation / Stagflation), the principle that relatives beat absolutes (rate of change over absolute level), the policy divergence engine for FX, implied volatility ranges as dynamic support/resistance, underlying vs short-term risk sentiment, currency-specific idiosyncratic drivers, and the high-probability swing trade framework.

**Adaptations made:**
- Both frameworks merged into a single 5-stage LLM pipeline
- MT5 Python API bridge added for execution
- FastAPI + React web dashboard added for signal display and trade approval
- TradingView webhook trigger added
- Full risk management, drawdown controls, and backtesting plan added per professional trading standards

---

## 1. Strategy Overview

### 1.1 Core Thesis

Professional traders make money by predicting the *future direction* of macro fundamentals — not by reacting to price patterns. Currency, equity, commodity, and bond prices are forward-looking discounting mechanisms. When macroeconomic drivers (growth, inflation, monetary policy) are diverging between two economies or assets, and that divergence is early and widening, the market will price it in over the coming days to weeks. This system captures that divergence by identifying it before it is fully priced in, timing the entry using technical and volatility tools, and executing with defined risk parameters. The edge comes from doing more rigorous macro analysis than 90% of retail traders, combined with the discipline to only trade when all stages of the pipeline agree.

### 1.2 Strategy Summary

The system runs a 5-stage AI pipeline for any requested asset. Stage 1 classifies the global market regime. Stage 2 determines the macro Growth/Inflation quadrant and underlying risk sentiment. Stage 3 generates a fundamental trade idea using 10 macro drivers, the 3-Step Analysis Process, and relative value scoring. Stage 4 gates the entry using technical analysis and options-implied volatility levels. Stage 5 aggregates all stages into a final graded signal (A/B/C/WATCH/PASS) with full trade parameters. The trader reviews the signal in a web dashboard and approves or rejects. On approval, the system executes the trade in MetaTrader 5 automatically with stop loss and take profit set.

### 1.3 Asset Universe

**Forex (primary):**
- Major pairs: EUR/USD, GBP/USD, USD/JPY, AUD/USD, USD/CAD, NZD/USD, USD/CHF
- Cross pairs: EUR/GBP, EUR/JPY, GBP/JPY, AUD/JPY, EUR/AUD, GBP/AUD
- Excluded: all pegged/fixed regime currencies (HKD, SAR, QAR, AED, OMR, BHD)

**Equities (secondary):**
- Major indices only: S&P 500 (SPX), NASDAQ 100 (NDX), FTSE 100, DAX 40, Nikkei 225
- No individual stocks in v1.0 (indices only)

**Commodities:**
- Gold (XAU/USD), WTI Crude Oil (USOIL), Silver (XAG/USD)

**Crypto:**
- BTC/USD and ETH/USD only — treated as risk assets, driven by risk sentiment

### 1.4 Timeframe and Session

- **Primary signal timeframe:** Daily chart (macro bias) + 4H chart (entry timing)
- **Higher-timeframe filter:** Weekly chart for overall trend direction
- **Target trade duration:** 1–5 days (swing). Flexible — if a catalyst-driven setup develops into a multi-week position, hold it. If a swing closes in hours on a strong catalyst, that is acceptable.
- **Active trading sessions:** London open (08:00–12:00 GMT) and New York session (13:00–17:00 GMT) for FX. Regular market hours for equities. 24/7 for crypto but prefer entries during high-liquidity windows.
- **Avoid:** Entries in the 30 minutes before and 15 minutes after any high-impact scheduled news event (FOMC, NFP, CPI, GDP). The system flags these automatically.

---

## 2. System Architecture

### 2.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     WISH-AI TRADING ENGINE                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  TRIGGER                                                        │
│  ├── TradingView price alert webhook  → POST /webhook           │
│  └── Manual ticker entry in dashboard → POST /analyse           │
│                                                                 │
│  DATA LAYER (Python — runs before LLM pipeline)                 │
│  ├── FRED API        → GDP, CPI, unemployment, yield curve      │
│  ├── yfinance        → OHLCV, VIX, index prices                 │
│  ├── ta library      → MA20/60/250, RSI, ATR, patterns          │
│  ├── IV calculator   → Daily 1SD/2SD ranges from options data   │
│  ├── Econ calendar   → Next 5-day catalysts + consensus         │
│  └── CB tracker      → Central bank stance + language shift     │
│                                                                 │
│  AI PIPELINE (5 LLM stages — Anthropic Claude API)             │
│  ├── Stage 1: Market Regime (Bull/Bear + VIX + Vol)             │
│  ├── Stage 2: Growth/Inflation Grid + Underlying Sentiment      │
│  ├── Stage 3: Idea Generation (3-Step + Macro Drivers + Rel Val)│
│  ├── Stage 4: Gatekeeping (Technicals + IV levels + Catalyst)   │
│  └── Stage 5: Final Signal (Grade A/B/C/WATCH/PASS + params)   │
│                                                                 │
│  WEB DASHBOARD (FastAPI backend + React frontend)               │
│  ├── Signal cards with grade, confidence, reasoning             │
│  ├── Macro regime panel (live quadrant display)                 │
│  ├── Trade approval buttons: [APPROVE & EXECUTE] [WATCHLIST]    │
│  └── Open positions monitor + P&L tracker                       │
│                                                                 │
│  MT5 EXECUTION BRIDGE (MetaTrader5 Python library)              │
│  ├── On approval: send market or limit order to MT5             │
│  ├── Auto-set stop loss and take profit                         │
│  ├── Monitor open trades for invalidation conditions            │
│  └── Log all trades to SQLite database                          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 Technology Stack

| Component | Technology | Notes |
|-----------|-----------|-------|
| Backend API | Python 3.11 + FastAPI | Lightweight, async, easy to deploy |
| AI Pipeline | Anthropic SDK (`anthropic`) | Claude claude-sonnet-4-6 / claude-opus-4-6 |
| Macro Data | `fredapi` | FRED — free, reliable US macro data |
| Market Data | `yfinance` | OHLCV, VIX, index prices — free |
| Technical Analysis | `ta` library | All indicators calculated in Python, not by LLM |
| MT5 Bridge | `MetaTrader5` Python library | Official MT5 Python API — Windows only |
| Frontend Dashboard | React + Tailwind CSS | Single-page app served by FastAPI |
| Database | SQLite (→ PostgreSQL in production) | Trade log, signal history, self-awareness stats |
| Scheduling | APScheduler | Run pipeline on schedule or on webhook trigger |
| Alerting | Telegram Bot API | Push notifications for new signals and trade outcomes |
| TradingView Trigger | Webhook receiver (FastAPI endpoint) | TV alert fires the pipeline |

### 2.3 Deployment

- **Local (v1.0):** Run on Windows PC with MT5 installed. FastAPI server on `localhost:8000`. Dashboard opened in browser.
- **Cloud (v2.0):** VPS (e.g. AWS, Hetzner) running FastAPI + React. MT5 runs on a separate Windows VPS or via Wine. Dashboard accessible from any browser.

---

## 3. The 5-Stage AI Pipeline

Every stage is a separate Claude API call. Outputs are structured JSON. Each stage's output is passed as context to the next. Early exits prevent unnecessary API calls.

### Stage 1 — Market Regime Classifier

**Purpose:** Establish the global market regime and volatility state before anything else. This determines position size modifier and trading mode for all subsequent stages.

#### Inputs (fetched by Python before LLM call)

| Variable | Source | Calculation |
|----------|--------|-------------|
| `index_name` | Config | e.g. "S&P 500" |
| `index_price_current` | yfinance `^GSPC` | Latest close |
| `index_previous_cycle_high` | yfinance historical | Manually stored or auto-detected peak before last major drawdown |
| `bear_market_level` | Calculated | `index_previous_cycle_high × 0.80` |
| `vix_current` | yfinance `^VIX` | Latest close |
| `vix_30d_ago` | yfinance `^VIX` | Close 30 trading days prior |
| `vix_pct_change_30d` | Calculated | `(vix_current - vix_30d_ago) / vix_30d_ago × 100` |
| `asset_iv_1m_annualised` | Options API or CBOE | Asset-specific 1-month implied vol % |
| `iv_daily_1sd_pct` | Calculated | `asset_iv_1m_annualised / sqrt(252)` |
| `iv_daily_2sd_pct` | Calculated | `iv_daily_1sd_pct × 2` |
| `asset_hist_vol_1m` | Calculated | Rolling 20-day std dev of returns × sqrt(252) × 100 |
| `asset_hist_vol_3m` | Calculated | Rolling 60-day std dev of returns × sqrt(252) × 100 |

#### LLM System Prompt — Stage 1
```
You are a professional macro trader using the ITPM WISH Framework.
Classify the current market regime using PROFESSIONAL definitions only — not media definitions.

DEFINITIONS:
- Bear Market: Index has closed below [previous_cycle_high × 0.80] and not recovered above it
- Bull Market: Index is above [previous_cycle_high × 0.80] OR has recovered above it after a bear
- Transitioning to Bear: Index approaching bear level but not yet confirmed
- Transitioning to Bull: Index recovering toward bull confirmation level
- HIGH Volatility: VIX has risen more than 25% over the last 30 days
- EXTREME Volatility: VIX has risen more than 50% over the last 30 days
- LOW Volatility: VIX has fallen more than 25% over 30 days OR VIX absolute level below 15
- NORMAL: None of the above triggers

POSITION SIZE MODIFIER RULES (hard rules — do not deviate):
- BULL + LOW vol: modifier = 1.0 (full size)
- BULL + NORMAL vol: modifier = 1.0
- BULL + HIGH vol: modifier = 0.5 (halved)
- BULL + EXTREME vol: modifier = 0.25
- BEAR or TRANSITIONING_TO_BEAR: modifier = max 0.5 regardless of vol
- SIDELINES: modifier = 0.0

Return ONLY valid JSON. No explanation outside the JSON block.
```

#### LLM User Prompt — Stage 1
```
Index: {index_name}
Current Price: {index_price_current}
Previous Business Cycle High: {index_previous_cycle_high}
Bear Market Level (×0.80): {bear_market_level}

VIX Current: {vix_current}
VIX 30 Days Ago: {vix_30d_ago}
VIX % Change (30d): {vix_pct_change_30d}%

Asset Implied Vol (1m annualised): {asset_iv_1m_annualised}%
Daily 1SD Range: ±{iv_daily_1sd_pct}%
Daily 2SD Range: ±{iv_daily_2sd_pct}%
Historical Vol 1m: {asset_hist_vol_1m}%
Historical Vol 3m: {asset_hist_vol_3m}%

Return JSON with these exact fields:
{
  "market_regime": "BULL|BEAR|TRANSITIONING_TO_BEAR|TRANSITIONING_TO_BULL",
  "volatility_regime": "LOW|NORMAL|HIGH|EXTREME",
  "trading_mode": "PORTFOLIO_MANAGER|SHORT_TERM_TRADER|REDUCE_EXPOSURE|SIDELINES",
  "position_size_modifier": 0.25|0.5|0.75|1.0,
  "iv_daily_1sd_pct": number,
  "iv_daily_2sd_pct": number,
  "iv_daily_1sd_price_up": number,
  "iv_daily_1sd_price_down": number,
  "regime_reasoning": "string — 2 sentences max",
  "vix_action": "ADD_EXPOSURE|HOLD|REDUCE_50PCT|DAY_TRADE_MODE_ONLY"
}
```

#### Early Exit after Stage 1
```python
if s1["trading_mode"] == "SIDELINES":
    return {"final_signal": "NO_TRADE", "reason": "Market regime: SIDELINES. No trades."}
```

---

### Stage 2 — Growth/Inflation Grid + Underlying Sentiment

**Purpose:** Classify the macro regime quadrant (Expansion / Reflation / Disinflation / Stagflation) and determine the underlying risk sentiment and path of least resistance. This is the most important context for all asset class decisions.

#### The 4-Quadrant Grid

```
                     INFLATION DECELERATING  |  INFLATION ACCELERATING
                    __________________________|___________________________
GROWTH              |                         |                           |
ACCELERATING        |    EXPANSION            |    REFLATION              |
                    |  Risk: ON               |  Risk: ON (watch infl)    |
                    |  Best: Equities,        |  Best: Commodities,       |
                    |  high-beta FX, indices  |  EM FX, cyclical assets   |
                    |_________________________|___________________________|
GROWTH              |                         |                           |
DECELERATING        |    DISINFLATION         |    STAGFLATION            |
                    |  Risk: OFF              |  Risk: OFF                |
                    |  Best: Bonds, defensive |  Best: Gold, USD,         |
                    |  equities, JPY, CHF     |  CHF, JPY, short equities |
                    |_________________________|___________________________|
```

**Critical rule:** Use RATE OF CHANGE (direction of travel), not absolute level. Compare to 3 months prior.

#### Inputs

| Variable | Source | Description |
|----------|--------|-------------|
| `gdp_latest` | FRED `GDPC1` | Real GDP YoY % latest |
| `gdp_3m_ago` | FRED `GDPC1` | Real GDP YoY % 3 months prior |
| `gdp_direction` | Calculated | ACCELERATING / DECELERATING / FLAT |
| `cpi_latest` | FRED `CPIAUCSL` | CPI YoY % latest |
| `cpi_3m_ago` | FRED `CPIAUCSL` | CPI YoY % 3 months prior |
| `cpi_direction` | Calculated | ACCELERATING / DECELERATING / FLAT |
| `pmi_mfg` | ISM / Markit | Manufacturing PMI latest (>50 = expanding) |
| `pmi_services` | ISM / Markit | Services PMI latest |
| `leading_indicator` | FRED `USALOLITONOSTSAM` | OECD composite leading indicator |
| `leading_indicator_direction` | Calculated | vs 3m ago |
| `consumer_confidence` | FRED `UMCSENT` | University of Michigan sentiment |
| `consumer_confidence_direction` | Calculated | vs 3m ago |
| `yield_curve_spread_bps` | FRED `T10Y2YM` | 10yr - 2yr spread in basis points |
| `yield_curve_shape` | Calculated | NORMAL (>0) / FLAT (0 to -20) / INVERTED (<-20) |

#### Calculated quadrant pre-classification (Python — before LLM call)
```python
def pre_classify_quadrant(gdp_direction: str, cpi_direction: str) -> str:
    mapping = {
        ("ACCELERATING", "DECELERATING"): "EXPANSION",
        ("ACCELERATING", "ACCELERATING"): "REFLATION",
        ("DECELERATING", "DECELERATING"): "DISINFLATION",
        ("DECELERATING", "ACCELERATING"): "STAGFLATION",
    }
    key = (gdp_direction, cpi_direction)
    return mapping.get(key, "TRANSITIONAL")
```

#### LLM System Prompt — Stage 2
```
You are a global macro analyst. Classify the current macro regime using the 4-quadrant
Growth/Inflation Grid. Focus exclusively on RATE OF CHANGE — the direction of travel
for growth and inflation — not the absolute level.

RULES:
- A country with low but IMPROVING growth beats a country with high but DETERIORATING growth
- EXPANSION (growth up, inflation down) = risk ON → prefer equities, high-beta FX
- REFLATION (growth up, inflation up) = risk ON but watch for policy tightening response
- DISINFLATION (growth down, inflation down) = risk OFF → prefer bonds, JPY, CHF, defensive equities
- STAGFLATION (growth down, inflation up) = risk OFF → prefer gold, USD, short equities
- Yield curve inversion = additional recession warning — increase risk-off bias
- Path of least resistance = the direction most assets move absent a specific catalyst

Return ONLY valid JSON.
```

#### LLM User Prompt — Stage 2
```
GDP Latest: {gdp_latest}% | GDP 3m Ago: {gdp_3m_ago}% | GDP Direction: {gdp_direction}
CPI Latest: {cpi_latest}% | CPI 3m Ago: {cpi_3m_ago}% | CPI Direction: {cpi_direction}
PMI Manufacturing: {pmi_mfg} | PMI Services: {pmi_services}
Leading Indicator: {leading_indicator} | Direction: {leading_indicator_direction}
Consumer Confidence: {consumer_confidence} | Direction: {consumer_confidence_direction}
Yield Curve Spread: {yield_curve_spread_bps}bps | Shape: {yield_curve_shape}
Pre-classified Quadrant: {pre_classified_quadrant}

Return JSON:
{
  "macro_quadrant": "EXPANSION|REFLATION|DISINFLATION|STAGFLATION|TRANSITIONAL",
  "quadrant_confidence": "HIGH|MEDIUM|LOW",
  "growth_trajectory": "ACCELERATING|DECELERATING|FLAT",
  "inflation_trajectory": "ACCELERATING|DECELERATING|FLAT",
  "underlying_risk_sentiment": "RISK_ON|RISK_OFF|NEUTRAL",
  "path_of_least_resistance": "LONG_RISK|SHORT_RISK|NEUTRAL",
  "preferred_asset_classes": ["list 2-3 assets that outperform in this regime"],
  "avoid_asset_classes": ["list 1-2 assets that underperform"],
  "yield_curve_signal": "NORMAL|FLATTENING_WARNING|INVERTED_RECESSION_WARNING",
  "quadrant_reasoning": "string — 3 sentences explaining rate-of-change logic",
  "regime_inflection_risk": true|false,
  "inflection_trigger": "string — what data would signal a regime shift, or null"
}
```

#### Early Exit after Stage 2
```python
if asset_class in s2["avoid_asset_classes"] and s2["quadrant_confidence"] == "HIGH":
    return {"final_signal": "NO_TRADE",
            "reason": f"{asset_class} is in avoid list for {s2['macro_quadrant']} regime"}
```

---

### Stage 3 — Idea Generation (Macro Drivers + 3-Step Analysis + Relative Value)

**Purpose:** Generate a fundamental directional bias using the 10 macro drivers, the 3-Step Analysis Process, and relative value scoring. This is 80% of the work. No charts consulted here.

#### The 3-Step Analysis Process

Every trade idea must answer all three steps:

| Step | Question | Output |
|------|----------|--------|
| **1. Baseline** | What does the market currently expect? What is already priced in? | Current consensus / priced-in scenario |
| **2. Surprise** | What would deviate from the baseline? What would genuinely surprise? | Bullish and bearish surprise scenarios |
| **3. Bigger Picture** | Would a surprise change the underlying trajectory of growth/inflation/policy? | Trade type: position / swing / day / no trade |

#### The 10 Macro Drivers

| # | Driver | Type | Key Data Points |
|---|--------|------|-----------------|
| 1 | ISM/PMI Manufacturing | Leading | Headline, new orders, employment sub-index, inventories |
| 2 | ISM/PMI Services | Leading | Business activity, new business, employment |
| 3 | Consumer Confidence/Sentiment | Leading | UoM, Conference Board, direction vs prior month |
| 4 | Employment (NFP, unemployment, wages) | Coincident/Leading | NFP vs forecast, unemployment rate, wage growth YoY |
| 5a | Central Bank Policy | Injection/Withdrawal | Rate level, hiking/cutting/pausing, forward guidance language |
| 5b | Fiscal Policy | Injection/Withdrawal | Government spending, deficit, major stimulus announcements |
| 5c | Inflation | Coincident | CPI vs target, PCE, core vs headline, direction of travel |
| 6a | Trade Balance / Current Account | Exogenous | Surplus/deficit, direction, commodity export dependency |
| 6b | GDP / Economic Surprise Index | Leading/Coincident | GDP beat/miss, Citi surprise index, nowcast |
| 7 | Commodity Dependency | Exogenous | Relevant commodity price vs currency relationship |

#### Relative Value Scoring (FX only)

For FX, score each currency in the pair on a -3 to +3 scale across three dimensions:

| Dimension | Score +3 | Score 0 | Score -3 |
|-----------|----------|---------|----------|
| Policy divergence | Early hawkish vs dovish, widening | Neutral | Late dovish vs hawkish, narrowing |
| Growth differential | Strong improving vs weak deteriorating | Neutral | Weak improving vs strong deteriorating |
| Inflation/rate differential | Higher rates rising vs lower falling | Neutral | Lower rates falling vs higher rising |

**Composite score:** -9 to +9. Score above +4 = strong BUY base currency. Below -4 = strong SELL base currency.

#### Currency-Specific Idiosyncratic Drivers (injected into Stage 3 prompt)

| Currency | Primary Idiosyncratic Driver | Secondary Driver |
|----------|------------------------------|-----------------|
| USD | Global risk-off safe haven (inverse risk correlation), Fed policy | DXY strength vs all majors |
| EUR | ECB policy divergence vs Fed, Eurozone PMI composite | German industrial output, energy prices |
| GBP | Bank of England policy, UK labour market data | Brexit/trade deal developments |
| AUD | Iron ore price, China PMI manufacturing | RBA policy, commodity export terms of trade |
| NZD | Dairy prices (GDT auction), RBNZ policy | China trade relationship |
| CAD | WTI crude oil price, BoC policy | Canada employment, US-Canada trade |
| JPY | US-Japan yield differential (10yr spread), global risk sentiment | BoJ YCC policy, intervention risk |
| CHF | Safe haven demand (risk-off), SNB intervention risk | Eurozone contagion risk |

#### Inputs — Stage 3

**Universal (all assets):**
- All Stage 1 and Stage 2 outputs
- `asset_name`, `asset_class`
- `baseline_market_expectations` (from econ calendar consensus)
- `next_catalyst_name`, `next_catalyst_date`, `next_catalyst_impact` (HIGH/MEDIUM/LOW)
- `ism_mfg`, `ism_services`, `consumer_confidence`, `nfp_latest`, `unemployment_rate`
- `wage_growth_yoy`, `cpi_latest`, `cpi_target`, `gdp_surprise_index`
- `cb_current_rate`, `cb_rate_trend`, `cb_language_bias`, `fiscal_balance_pct_gdp`

**FX additional:**
- `base_currency`, `quote_currency`
- `base_cb_stance`, `quote_cb_stance` (HAWKISH / PIVOTING_HAWKISH / NEUTRAL / PIVOTING_DOVISH / DOVISH)
- `policy_divergence_direction` (BASE_FAVORED / QUOTE_FAVORED / NEUTRAL)
- `divergence_maturity` (EARLY / MID_CYCLE / LATE_CYCLE)
- `rate_differential_bps`, `rate_differential_trend` (WIDENING / NARROWING / STABLE)
- `base_growth_trajectory`, `quote_growth_trajectory`
- `currency_specific_driver_base`, `currency_specific_driver_quote`

**Equities additional:**
- `sector`, `sector_cyclicality` (CYCLICAL / DEFENSIVE)
- `earnings_revision_trend` (UPGRADING / DOWNGRADING / FLAT)
- `pe_ratio_vs_avg` (CHEAP / FAIR / EXPENSIVE)

**Commodities additional:**
- `commodity_type` (ENERGY / PRECIOUS_METAL / BASE_METAL)
- `supply_demand_balance` (SURPLUS / DEFICIT / BALANCED)
- `geopolitical_risk` (HIGH / MEDIUM / LOW)
- `dxy_direction` (STRENGTHENING / WEAKENING / FLAT)

#### LLM System Prompt — Stage 3
```
You are a professional macro swing trader. You generate trade ideas from macroeconomic
fundamentals only. You NEVER generate ideas from charts. Charts come later.

CORE RULES:
1. Relatives beat absolutes. Rate of change matters more than absolute level.
   A bad-but-improving outlook BEATS a good-but-deteriorating outlook.
2. For FX, policy divergence that is EARLY and WIDENING is the best signal.
   LATE and NARROWING means the trade is crowded — do not chase it.
3. The 3-Step Analysis is mandatory for every signal:
   - Step 1 Baseline: what has the market already priced in?
   - Step 2 Surprise: what would deviate from baseline?
   - Step 3 Bigger Picture: does that surprise change the macro trajectory?
   If Step 3 answer is NO → day trade only, not swing.
4. A trade direction that FIGHTS the macro quadrant's path of least resistance
   requires confidence > 75 and a clearly identified catalyst. Otherwise = NO_TRADE.
5. Short-term risk-on catalysts during a RISK_OFF underlying regime = day trade only.
6. Never score a driver you do not have data for. Mark it N/A.

Return ONLY valid JSON.
```

#### LLM User Prompt — Stage 3
```
REGIME CONTEXT:
Market Regime: {market_regime} | Vol Regime: {volatility_regime}
Macro Quadrant: {macro_quadrant} | Risk Sentiment: {underlying_risk_sentiment}
Path of Least Resistance: {path_of_least_resistance}
Preferred Assets: {preferred_asset_classes} | Avoid: {avoid_asset_classes}

ASSET: {asset_name} ({asset_class})
{currency_specific_context_if_fx}

3-STEP ANALYSIS INPUTS:
Baseline (market consensus): {baseline_market_expectations}
Next catalyst: {next_catalyst_name} on {next_catalyst_date} (impact: {next_catalyst_impact})

MACRO DRIVER DATA:
ISM Manufacturing: {ism_mfg} | ISM Services: {ism_services}
Consumer Confidence: {consumer_confidence} (direction: {consumer_confidence_direction})
NFP Latest: {nfp_latest}k | Unemployment: {unemployment_rate}% | Wages YoY: {wage_growth_yoy}%
CPI: {cpi_latest}% vs Target: {cpi_target}% | GDP Surprise Index: {gdp_surprise_index}
CB Rate: {cb_current_rate}% | Rate Trend: {cb_rate_trend} | CB Language: {cb_language_bias}
Fiscal Balance: {fiscal_balance_pct_gdp}% of GDP

[FX ONLY]
Base CB: {base_cb_stance} | Quote CB: {quote_cb_stance}
Divergence: {policy_divergence_direction} | Maturity: {divergence_maturity}
Rate Diff: {rate_differential_bps}bps ({rate_differential_trend})
Base Growth: {base_growth_trajectory} | Quote Growth: {quote_growth_trajectory}
Base Idiosyncratic: {currency_specific_driver_base}
Quote Idiosyncratic: {currency_specific_driver_quote}

[EQUITIES ONLY]
Sector: {sector} | Cyclicality: {sector_cyclicality}
Earnings Revision: {earnings_revision_trend} | P/E vs Avg: {pe_ratio_vs_avg}

[COMMODITIES ONLY]
Type: {commodity_type} | Supply/Demand: {supply_demand_balance}
Geopolitical Risk: {geopolitical_risk} | DXY Direction: {dxy_direction}

Return JSON:
{
  "trade_direction": "LONG|SHORT|NO_TRADE",
  "fundamental_bias": "BULLISH|BEARISH|NEUTRAL",
  "bias_strength": "STRONG|MODERATE|WEAK",
  "trade_type_recommended": "POSITION_TRADE|SWING_CATALYST|SWING_TACTICAL|DAY_TRADE_ONLY|NO_TRADE",
  "aligns_with_underlying_sentiment": true|false,
  "three_step_analysis": {
    "baseline": "string — what is currently priced in",
    "surprise_needed": "string — what would surprise markets",
    "bigger_picture_impact": "string — does surprise change macro trajectory?",
    "bigger_picture_changes": true|false
  },
  "driver_scores": {
    "ism_pmi": "BULLISH|BEARISH|NEUTRAL|N/A",
    "consumer_confidence": "BULLISH|BEARISH|NEUTRAL|N/A",
    "employment": "BULLISH|BEARISH|NEUTRAL|N/A",
    "monetary_policy": "BULLISH|BEARISH|NEUTRAL|N/A",
    "inflation": "BULLISH|BEARISH|NEUTRAL|N/A",
    "gdp_trend": "BULLISH|BEARISH|NEUTRAL|N/A",
    "fiscal_policy": "BULLISH|BEARISH|NEUTRAL|N/A",
    "trade_balance": "BULLISH|BEARISH|NEUTRAL|N/A",
    "commodity_exposure": "BULLISH|BEARISH|NEUTRAL|N/A",
    "risk_sentiment": "BULLISH|BEARISH|NEUTRAL|N/A"
  },
  "top_drivers": ["driver1", "driver2", "driver3"],
  "relative_value_score": {
    "policy_divergence_score": -3..3,
    "growth_divergence_score": -3..3,
    "rate_differential_score": -3..3,
    "composite_score": -9..9,
    "divergence_maturity": "EARLY|MID_CYCLE|LATE_CYCLE|N/A"
  },
  "catalyst_assessment": {
    "catalyst_name": "string",
    "catalyst_date": "string",
    "bullish_scenario": "string",
    "bearish_scenario": "string",
    "changes_bigger_picture": true|false,
    "implied_trade_duration": "HOURS|DAYS|WEEKS"
  },
  "fundamental_reasoning": "string — 4-5 sentences",
  "key_risks": ["risk1", "risk2", "risk3"]
}
```

#### Early Exit after Stage 3
```python
if s3["fundamental_bias"] == "NEUTRAL" and s3["bias_strength"] == "WEAK":
    return {"final_signal": "NO_TRADE", "reason": "Insufficient fundamental conviction"}
if s3["trade_direction"] == "NO_TRADE":
    return {"final_signal": "NO_TRADE", "reason": s3["fundamental_reasoning"]}
```

---

### Stage 4 — Gatekeeping (Technicals + IV Levels + Entry Quality)

**Purpose:** After a fundamental bias is established, assess whether NOW is a good time to enter. Technicals are timing tools only — they never change the fundamental direction. Output is a traffic light: GREEN / AMBER / RED.

#### Critical Rules for Stage 4
1. Fundamental bias from Stage 3 is locked. Stage 4 NEVER reverses it.
2. If fundamentals say BULLISH and chart is bearish → AMBER or RED (watch list). Never SELL.
3. Stop loss = where the trade is WRONG structurally, not where the math looks best.
4. IV-based levels (1SD, 2SD) are objective dynamic support/resistance. Prefer entries at these levels.
5. A 2SD move is statistically rare — usually mean-reverting. Trade with caution at 2SD.
6. Moving averages that matter: 20-day (1 month), 60-day (1 quarter), 250-day (1 year). Ignore 50 and 200.
7. RSI above 70 in a bullish context = momentum confirmation, NOT overbought. Same logic inverted for bearish.

#### Inputs — Stage 4

All calculated by Python `ta` library before LLM call:

| Variable | Calculation |
|----------|-------------|
| `current_price` | Latest close |
| `ma20`, `ma60`, `ma250` | Simple moving averages |
| `price_vs_20ma` | ABOVE / BELOW |
| `price_vs_60ma` | ABOVE / BELOW |
| `price_vs_250ma` | ABOVE / BELOW |
| `ma_20_60_cross` | GOLDEN / DEATH / NONE (detected on last 5 bars) |
| `ma_60_250_cross` | GOLDEN / DEATH / NONE |
| `trend_direction` | UPTREND (price > MA20 > MA60) / DOWNTREND (price < MA20 < MA60) / RANGING |
| `rsi_14` | 14-period RSI |
| `atr_14` | 14-period Average True Range |
| `volume_vs_avg` | Current volume / 20-day avg volume → HIGH (>1.5x) / NORMAL / LOW (<0.7x) |
| `price_pattern` | HEAD_SHOULDERS / INV_HEAD_SHOULDERS / DOUBLE_TOP / DOUBLE_BOTTOM / BULL_FLAG / BEAR_FLAG / PENNANT / NONE |
| `key_support` | Nearest support level (recent swing low or round number) |
| `key_resistance` | Nearest resistance level (recent swing high or round number) |
| `price_location` | AT_SUPPORT / AT_RESISTANCE / MID_RANGE |
| `iv_1sd_up` | `current_price × (1 + iv_daily_1sd_pct/100)` |
| `iv_1sd_down` | `current_price × (1 - iv_daily_1sd_pct/100)` |
| `iv_2sd_up` | `current_price × (1 + iv_daily_2sd_pct/100)` |
| `iv_2sd_down` | `current_price × (1 - iv_daily_2sd_pct/100)` |
| `price_vs_iv_levels` | AT_1SD_SUPPORT / AT_1SD_RESISTANCE / AT_2SD / BEYOND_2SD / MID_RANGE |
| `iv_trend_1w` | RISING / FALLING / FLAT (compare current IV to 5-day ago) |
| `cftc_positioning` | NET_LONG / NET_SHORT / NEUTRAL / EXTREME_LONG / EXTREME_SHORT (from CFTC COT data) |
| `opex_warning` | true if within 3 calendar days of monthly options expiry |
| `news_blackout_active` | true if within 30min of high-impact event |

#### LLM System Prompt — Stage 4
```
You are the gatekeeping system for a professional trading desk.
Your ONLY job is to assess TIMING and entry quality.

ABSOLUTE RULES — never violate these:
1. You cannot change or override the fundamental direction from Stage 3.
   If fundamental bias = BULLISH, you cannot output SHORT. You can only say GREEN/AMBER/RED.
2. If fundamentals = BULLISH and trend = DOWNTREND: output AMBER or RED. Never suggest SHORT.
3. Stop loss placement: ask WHERE IS THE TRADE WRONG structurally.
   Place the stop there — not at ATR×1.5 if that doesn't coincide with a structural level.
4. Minimum risk/reward = 2.0. If R:R < 2.0 after calculating entry/stop/target: output AMBER.
5. Entering at a 1SD IV level is better than mid-range. Flag this as IV_CONFLUENCE = true.
6. 2SD moves are statistically rare — be cautious entering at 2SD levels.
7. If opex_warning = true: flag it. Mechanical flows can distort price temporarily.
8. If news_blackout_active = true: output RED regardless of other signals. No entries in blackout.
9. RSI above 70 = momentum confirmation when bullish. NOT a reason to hold back.
10. CFTC EXTREME_LONG in a BULLISH trade = crowded. Reduce entry recommendation to HALF position.

Return ONLY valid JSON.
```

#### LLM User Prompt — Stage 4
```
FUNDAMENTAL DIRECTION (Stage 3): {trade_direction} | Bias: {fundamental_bias} ({bias_strength})
TRADE TYPE: {trade_type_recommended}
ASSET: {asset_name} | CURRENT PRICE: {current_price}

TECHNICAL DATA:
Trend: {trend_direction}
Price vs MA20: {price_vs_20ma} | vs MA60: {price_vs_60ma} | vs MA250: {price_vs_250ma}
MA Crosses: 20v60={ma_20_60_cross}, 60v250={ma_60_250_cross}
RSI(14): {rsi_14} | ATR(14): {atr_14}
Volume vs Avg: {volume_vs_avg}
Pattern: {price_pattern}
Support: {key_support} | Resistance: {key_resistance} | Location: {price_location}

IV LEVELS (Dynamic Support/Resistance):
1SD Up: {iv_1sd_up} | 1SD Down: {iv_1sd_down}
2SD Up: {iv_2sd_up} | 2SD Down: {iv_2sd_down}
Price vs IV: {price_vs_iv_levels} | IV Trend: {iv_trend_1w}

ADDITIONAL SIGNALS:
CFTC Positioning: {cftc_positioning}
OpEx Warning: {opex_warning}
News Blackout Active: {news_blackout_active}

Return JSON:
{
  "gate_signal": "GREEN|AMBER|RED",
  "entry_quality": "CATALYST_DRIVEN_HIGH_PROB|TACTICAL_MEDIUM_PROB|LOW_PROB",
  "entry_recommendation": "ENTER_FULL|ENTER_HALF|WATCH_LIST|DO_NOT_ENTER",
  "entry_zone": {
    "aggressive_entry": number,
    "conservative_entry": number,
    "entry_reasoning": "string"
  },
  "stop_loss": {
    "price": number,
    "structural_reason": "string — why this level proves the trade wrong",
    "atr_check": "string — ATR multiple for reference"
  },
  "targets": {
    "target_1": number,
    "target_2": number,
    "target_3_stretch": number,
    "partial_exit_plan": "string — e.g. close 50% at T1, trail remainder"
  },
  "risk_reward_ratio": number,
  "iv_confluence": true|false,
  "iv_note": "string — is entry zone near a 1SD or 2SD level?",
  "cftc_flag": "string or null — crowding warning if applicable",
  "opex_flag": "string or null",
  "gate_reasoning": "string — 2-3 sentences on timing",
  "watch_list_trigger": "string — price level or event that turns this GREEN, or null"
}
```

#### Early Exit after Stage 4
```python
if s4["gate_signal"] == "RED" and s4["watch_list_trigger"] is None:
    return {"final_signal": "WATCH_LIST",
            "reason": "Technical gate RED with no identifiable trigger to watch for",
            "watch_list_trigger": None}
if s4["news_blackout_active"]:
    return {"final_signal": "NO_TRADE", "reason": "News blackout active — no entries permitted"}
```

---

### Stage 5 — Final Signal Aggregator

**Purpose:** Combine all 4 prior stages into one graded, actionable swing trade signal. Enforce all hard rules. Output a complete trade card with grade, confidence, parameters, and full reasoning.

#### Signal Scoring System

| Criterion | Points |
|-----------|--------|
| Macro quadrant aligns with trade direction | +20 |
| 3-Step Analysis: surprise changes bigger picture | +15 |
| Policy/growth divergence early and widening | +15 |
| Technical gate GREEN with IV confluence | +15 |
| Catalyst-driven entry (not just tactical) | +10 |
| Underlying risk sentiment aligns | +10 |
| CFTC positioning not extreme against trade | +5 |
| **Deductions** | |
| Trade fights macro quadrant path of least resistance | -20 |
| Technical gate RED | -15 |
| CFTC extreme positioning against trade direction | -10 |
| Trade against underlying risk sentiment | -10 |
| Divergence late and narrowing | -10 |
| OpEx warning active | -5 |

#### Signal Grade Table

| Grade | Score | Action |
|-------|-------|--------|
| **A** | 85–100 | All stages aligned, catalyst-driven, early divergence. Enter FULL size. |
| **B** | 70–84 | Strong setup, minor conflicts. Enter 75% size. |
| **C** | 55–69 | Moderate setup, tactical entry. Consider 50% size. |
| **WATCH** | 40–54 | Interesting but not ready. Add to watch list with trigger. |
| **PASS** | < 40 | Conflicting signals. Do not trade. |

#### LLM System Prompt — Stage 5
```
You are the final signal aggregator for the WISH-AI trading system.
Apply the scoring system below to produce a final graded signal.
Capital preservation is the first priority. When in doubt, downgrade.
A signal below 55 is WATCH_LIST or PASS — never force a trade.

SCORING:
+20: macro quadrant aligns with trade direction
+15: 3-step bigger picture changes on surprise
+15: policy/growth divergence early and widening
+15: gate GREEN with IV confluence
+10: catalyst-driven entry
+10: underlying sentiment aligned
+5: CFTC not extreme against trade
-20: trade fights path of least resistance
-15: gate RED
-10: CFTC extreme against direction
-10: trade against underlying sentiment
-10: divergence late and narrowing
-5: opex warning active

GRADE TABLE: A=85+, B=70-84, C=55-69, WATCH=40-54, PASS=<40

Return ONLY valid JSON.
```

#### LLM User Prompt — Stage 5
```
STAGE 1: {stage1_json}
STAGE 2: {stage2_json}
STAGE 3: {stage3_json}
STAGE 4: {stage4_json}

Position Size Modifier from Stage 1: {position_size_modifier}
Account Base Risk Per Trade: {risk_per_trade_pct}% [from config]
Account Equity: {account_equity} [from MT5 bridge]

Return JSON:
{
  "final_signal": "BUY|SELL|WATCH_LIST|NO_TRADE",
  "signal_grade": "A|B|C|WATCH|PASS",
  "signal_confidence": 0-100,
  "direction": "LONG|SHORT|NEUTRAL",
  "trade_type": "SWING_CATALYST|SWING_TACTICAL|DAY_TRADE|NO_TRADE",
  "asset": "string",
  "entry_zone": {"aggressive": number, "conservative": number},
  "stop_loss": number,
  "targets": {"t1": number, "t2": number, "t3": number},
  "risk_reward": number,
  "position_size_pct": number,
  "position_size_lots": number,
  "hold_duration_expected": "string",
  "macro_regime": "string",
  "underlying_sentiment": "RISK_ON|RISK_OFF|NEUTRAL",
  "policy_divergence_quality": "EARLY_WIDENING|MID_CYCLE|LATE_NARROWING|N/A",
  "signal_summary": "string — 6-8 sentences covering: macro regime, 3-step baseline/surprise/bigger picture, relative value driver, technical timing, entry/stop/target logic, and invalidation",
  "invalidation_conditions": ["condition1", "condition2", "condition3"],
  "scoring_breakdown": {
    "quadrant_alignment": number,
    "three_step_bigger_picture": number,
    "policy_divergence": number,
    "technical_gate": number,
    "catalyst_quality": number,
    "sentiment_alignment": number,
    "cftc_score": number,
    "deductions": number,
    "total": number
  },
  "pre_trade_checklist": {
    "macro_bias_confirmed": true|false,
    "no_news_blackout": true|false,
    "rr_above_2": true|false,
    "position_size_within_limits": true|false,
    "not_in_avoid_list": true|false,
    "gate_not_red": true|false,
    "all_checks_passed": true|false
  }
}
```

---

## 4. Entry Rules

### 4.1 Primary Signal — Entry Pseudocode

```python
def should_enter_trade(signal: dict, portfolio: dict, config: dict) -> tuple[bool, str]:
    """
    Returns (True, reason) if trade should be entered, (False, reason) if not.
    All checks must pass. First failure = no trade.
    """

    # Hard block 1: Signal grade
    if signal["signal_grade"] in ["WATCH", "PASS"]:
        return False, f"Signal grade {signal['signal_grade']} — insufficient confluence"

    # Hard block 2: Pre-trade checklist
    checklist = signal["pre_trade_checklist"]
    if not checklist["all_checks_passed"]:
        failed = [k for k, v in checklist.items() if v is False and k != "all_checks_passed"]
        return False, f"Pre-trade checklist failed: {failed}"

    # Hard block 3: Risk/reward
    if signal["risk_reward"] < 2.0:
        return False, f"R:R {signal['risk_reward']} below minimum 2.0"

    # Hard block 4: Daily drawdown limit
    if portfolio["daily_pnl_pct"] <= -config["max_daily_loss_pct"]:
        return False, "Daily loss limit reached — no new entries today"

    # Hard block 5: Max concurrent positions
    if portfolio["open_positions"] >= config["max_concurrent_positions"]:
        return False, f"Max concurrent positions ({config['max_concurrent_positions']}) reached"

    # Hard block 6: Max portfolio risk
    if portfolio["total_open_risk_pct"] + signal["position_size_pct"] > config["max_total_portfolio_risk_pct"]:
        return False, "Adding this trade would exceed max total portfolio risk"

    # Hard block 7: Consecutive losses
    if portfolio["consecutive_losses"] >= config["max_consecutive_losses"]:
        return False, f"Consecutive loss limit ({config['max_consecutive_losses']}) reached — cooldown active"

    # Hard block 8: Correlated positions
    correlated = get_correlated_open_positions(signal["asset"], portfolio, threshold=0.70)
    if len(correlated) >= config["max_correlated_positions"]:
        return False, f"Max correlated positions reached: {correlated}"

    # Hard block 9: Market regime
    if signal["market_regime"] == "BEAR" and signal["direction"] == "LONG":
        if signal["signal_confidence"] < 75:
            return False, "LONG trade in BEAR regime requires confidence >= 75"

    # Hard block 10: Pegged currency check
    if is_pegged_currency(signal["asset"]):
        return False, "Pegged/fixed currency regime — not tradeable"

    return True, "All entry checks passed"
```

### 4.2 Entry Execution

```python
def execute_entry(signal: dict, config: dict, mt5_bridge) -> dict:
    """Execute the approved trade in MT5."""

    # Determine order type
    price_diff_from_aggressive = abs(signal["entry_zone"]["aggressive"] - mt5_bridge.get_current_price(signal["asset"]))
    atr = signal["atr_14"]

    if price_diff_from_aggressive < atr * 0.1:
        order_type = "MARKET"
        entry_price = mt5_bridge.get_current_price(signal["asset"])
    else:
        order_type = "LIMIT"
        entry_price = signal["entry_zone"]["aggressive"]

    # Calculate lot size
    lot_size = calculate_lot_size(
        account_equity=mt5_bridge.get_equity(),
        risk_pct=config["risk_per_trade_pct"] * signal["position_size_modifier"],
        entry_price=entry_price,
        stop_loss=signal["stop_loss"],
        pip_value=mt5_bridge.get_pip_value(signal["asset"])
    )

    # Send order to MT5
    result = mt5_bridge.send_order(
        symbol=signal["asset"],
        direction=signal["direction"],
        order_type=order_type,
        price=entry_price,
        lot_size=lot_size,
        stop_loss=signal["stop_loss"],
        take_profit=signal["targets"]["t1"],
        comment=f"WISH-AI {signal['signal_grade']} {signal['signal_confidence']}"
    )

    return result
```

### 4.3 Missed Entry Rule

```python
# If a LIMIT order is not filled within the session, cancel and reassess
MAX_LIMIT_ORDER_AGE_HOURS = 24  # [DEFAULT]

def check_stale_orders(mt5_bridge, max_age_hours: int = MAX_LIMIT_ORDER_AGE_HOURS):
    for order in mt5_bridge.get_pending_orders():
        if order.age_hours > max_age_hours:
            mt5_bridge.cancel_order(order.ticket)
            log_event(f"Cancelled stale limit order {order.ticket} for {order.symbol}")
```

---

## 5. Exit Rules

### 5.1 Stop Loss

- **Method:** Structural — place where the trade is proven wrong, confirmed by ATR check
- **Structural stop logic:**
  - For LONG: below the most recent significant swing low, or below key support level, or below 1SD IV level — whichever is closest to a key structural level
  - For SHORT: above the most recent significant swing high, or above key resistance, or above 1SD IV level
- **ATR check:** Stop distance should be between 1.0× and 2.5× ATR(14). If structural stop is > 2.5× ATR, reduce position size, do not widen the stop arbitrarily.
- **Stop formula (fallback if no structural level):**
  ```
  LONG stop  = entry_price - (1.5 × ATR_14)
  SHORT stop = entry_price + (1.5 × ATR_14)
  ```
- **Stop adjustment:** Stop is NEVER moved against the trade. It may only be moved in the direction of profit (trail) once 1R has been achieved.

### 5.2 Take Profit — Partial Exit Plan

```python
# Default partial exit structure for swing trades
PARTIAL_EXIT_PLAN = {
    "t1_pct_close": 0.50,   # Close 50% of position at Target 1
    "t1_action": "move_stop_to_breakeven",
    "t2_pct_close": 0.30,   # Close 30% at Target 2
    "t2_action": "trail_stop_by_atr",
    "t3_pct_close": 0.20,   # Let 20% run to stretch target
    "t3_action": "trail_stop_by_structure"
}

# Target calculation
def calculate_targets(entry: float, stop: float, direction: str) -> dict:
    risk = abs(entry - stop)
    if direction == "LONG":
        return {
            "t1": entry + (risk * 2.0),   # 2R
            "t2": entry + (risk * 3.0),   # 3R
            "t3": entry + (risk * 4.5),   # 4.5R stretch
        }
    else:  # SHORT
        return {
            "t1": entry - (risk * 2.0),
            "t2": entry - (risk * 3.0),
            "t3": entry - (risk * 4.5),
        }
```

### 5.3 Trailing Stop

```python
def update_trailing_stop(trade: dict, mt5_bridge) -> None:
    """
    Activate trailing stop once 1R profit achieved.
    Trail by 1× ATR below price (for longs) or above price (for shorts).
    """
    current_price = mt5_bridge.get_current_price(trade["symbol"])
    entry = trade["entry_price"]
    stop = trade["current_stop"]
    atr = trade["atr_14"]
    risk = abs(entry - stop)

    if trade["direction"] == "LONG":
        unrealised_r = (current_price - entry) / risk
        if unrealised_r >= 1.0:  # Trailing activates at 1R
            new_trail_stop = current_price - (1.0 * atr)
            if new_trail_stop > stop:
                mt5_bridge.modify_stop(trade["ticket"], new_trail_stop)

    elif trade["direction"] == "SHORT":
        unrealised_r = (entry - current_price) / risk
        if unrealised_r >= 1.0:
            new_trail_stop = current_price + (1.0 * atr)
            if new_trail_stop < stop:
                mt5_bridge.modify_stop(trade["ticket"], new_trail_stop)
```

### 5.4 Time-Based Exit

```python
MAX_HOLD_DAYS = 7           # [DEFAULT] — swing trades max 7 calendar days
SESSION_CLOSE_BUFFER_MINS = 15  # Close open day trades 15 min before session end

def check_time_exits(trade: dict, mt5_bridge) -> None:
    days_held = (datetime.now() - trade["open_time"]).days

    # Max hold period
    if days_held >= MAX_HOLD_DAYS:
        mt5_bridge.close_trade(trade["ticket"], reason="MAX_HOLD_PERIOD")
        log_event(f"Time exit: {trade['symbol']} held {days_held} days")

    # Day trade session close (if trade was tagged as DAY_TRADE)
    if trade["trade_type"] == "DAY_TRADE":
        if is_within_minutes_of_session_close(SESSION_CLOSE_BUFFER_MINS):
            mt5_bridge.close_trade(trade["ticket"], reason="SESSION_CLOSE")
```

### 5.5 Invalidation-Based Exit

```python
def check_invalidation_conditions(trade: dict, live_data: dict, mt5_bridge) -> None:
    """
    Check if any of the trade's invalidation conditions have been triggered.
    These are AI-generated conditions stored with each trade at signal time.
    """
    for condition in trade["invalidation_conditions"]:
        # Run each condition through a lightweight LLM check
        # or pre-programmed rule if condition is price-based
        if is_price_based_condition(condition):
            if evaluate_price_condition(condition, live_data["current_price"]):
                mt5_bridge.close_trade(trade["ticket"], reason=f"INVALIDATION: {condition}")
                send_telegram_alert(f"⚠️ Trade invalidated: {trade['symbol']} — {condition}")
```

### 5.6 Complete Exit Pseudocode

```python
def on_each_bar(trade: dict, mt5_bridge, live_data: dict) -> None:
    """Called on every new bar for each open trade."""
    current_price = live_data["current_price"]

    # 1. Stop loss hit
    if trade["direction"] == "LONG" and current_price <= trade["stop_loss"]:
        mt5_bridge.close_trade(trade["ticket"], reason="STOP_LOSS")
        return

    if trade["direction"] == "SHORT" and current_price >= trade["stop_loss"]:
        mt5_bridge.close_trade(trade["ticket"], reason="STOP_LOSS")
        return

    # 2. Target 1 hit — partial close
    if not trade["t1_closed"]:
        if (trade["direction"] == "LONG" and current_price >= trade["targets"]["t1"]) or \
           (trade["direction"] == "SHORT" and current_price <= trade["targets"]["t1"]):
            mt5_bridge.partial_close(trade["ticket"], pct=0.50)
            mt5_bridge.modify_stop(trade["ticket"], trade["entry_price"])  # Move to BE
            trade["t1_closed"] = True

    # 3. Target 2 hit — partial close
    if trade["t1_closed"] and not trade["t2_closed"]:
        if (trade["direction"] == "LONG" and current_price >= trade["targets"]["t2"]) or \
           (trade["direction"] == "SHORT" and current_price <= trade["targets"]["t2"]):
            mt5_bridge.partial_close(trade["ticket"], pct=0.30)
            trade["t2_closed"] = True

    # 4. Trailing stop (activates after T1)
    if trade["t1_closed"]:
        update_trailing_stop(trade, mt5_bridge)

    # 5. Time-based exit
    check_time_exits(trade, mt5_bridge)

    # 6. Invalidation conditions
    check_invalidation_conditions(trade, live_data, mt5_bridge)
```

---

## 6. Position Sizing

### 6.1 Sizing Model — Fixed Fractional (Risk-Based)

Risk a fixed percentage of current account equity per trade, adjusted by the position size modifier from Stage 1.

```python
def calculate_lot_size(
    account_equity: float,
    risk_pct: float,           # e.g. 0.01 for 1%
    position_size_modifier: float,  # from Stage 1: 0.25 / 0.5 / 0.75 / 1.0
    entry_price: float,
    stop_loss: float,
    pip_value: float,           # value per pip per standard lot in account currency
    min_lot: float = 0.01,
    max_lot: float = 10.0
) -> float:
    """
    Formula:
    risk_amount = account_equity × risk_pct × position_size_modifier
    stop_distance_pips = abs(entry_price - stop_loss) / pip_size
    lot_size = risk_amount / (stop_distance_pips × pip_value)
    """
    adjusted_risk_pct = risk_pct * position_size_modifier
    risk_amount = account_equity * adjusted_risk_pct
    stop_distance_pips = abs(entry_price - stop_loss) / get_pip_size(symbol)
    raw_lot_size = risk_amount / (stop_distance_pips * pip_value)
    lot_size = round(raw_lot_size, 2)
    return max(min_lot, min(lot_size, max_lot))
```

### 6.2 Signal Grade Size Modifier

In addition to the regime-based modifier from Stage 1, apply a grade-based modifier:

| Signal Grade | Grade Modifier | Combined Example (Bull Normal + Grade B) |
|--------------|---------------|------------------------------------------|
| A | 1.0× | 1.0 × 1.0 = 100% of base risk |
| B | 0.75× | 1.0 × 0.75 = 75% of base risk |
| C | 0.50× | 1.0 × 0.5 = 50% of base risk |
| WATCH | 0× | No trade |
| PASS | 0× | No trade |

```python
GRADE_MODIFIER = {"A": 1.0, "B": 0.75, "C": 0.50, "WATCH": 0.0, "PASS": 0.0}

final_modifier = stage1_position_size_modifier * GRADE_MODIFIER[signal_grade]
```

### 6.3 Position Size Config Defaults

```python
# config.py
RISK_PER_TRADE_PCT = 0.01       # 1% of equity per trade [DEFAULT — adjust to your comfort]
MAX_CONCURRENT_POSITIONS = 5    # [DEFAULT]
MAX_TOTAL_PORTFOLIO_RISK_PCT = 0.06  # 6% total open risk [DEFAULT]
MAX_CORRELATED_POSITIONS = 2    # Max positions with correlation > 0.70 [DEFAULT]
MIN_LOT_SIZE = 0.01
MAX_LOT_SIZE = 10.0
```

---

## 7. Risk Management & Drawdown Controls

### 7.1 Per-Trade Risk

- **Risk per trade:** 1% of account equity [DEFAULT — configurable in `config.py`]
- **Adjusted by:** Stage 1 regime modifier × Signal grade modifier
- **Maximum risk on any single trade:** 2% of equity (hard cap regardless of modifiers)
- **Stop loss:** Always set at order entry. No trade without a stop.

### 7.2 Portfolio-Level Risk Rules

```python
PORTFOLIO_RISK_RULES = {
    "max_concurrent_positions": 5,
    "max_total_open_risk_pct": 6.0,      # 6% of equity across all open trades
    "max_correlated_positions": 2,        # max 2 positions with r > 0.70
    "correlation_threshold": 0.70,
    "max_single_currency_exposure": 3,    # max 3 trades involving the same currency
    "max_same_direction_positions": 4,    # max 4 longs or 4 shorts simultaneously
}
```

### 7.3 Drawdown Controls

```python
DRAWDOWN_CONTROLS = {
    "max_daily_loss_pct": 3.0,    # Stop all trading after 3% daily drawdown [DEFAULT]
    "max_weekly_loss_pct": 6.0,   # Reduce all position sizes 50% after 6% weekly DD [DEFAULT]
    "max_total_drawdown_pct": 15.0,  # HALT system completely at 15% total DD [DEFAULT]
    "daily_loss_action": "STOP_TRADING_TODAY",
    "weekly_loss_action": "HALVE_ALL_POSITION_SIZES",
    "total_dd_action": "HALT_SYSTEM_MANUAL_REVIEW_REQUIRED",
}

def check_drawdown_limits(portfolio: dict, config: dict) -> tuple[bool, str]:
    """Returns (can_trade, reason). Called before every new entry."""

    if portfolio["daily_pnl_pct"] <= -config["max_daily_loss_pct"]:
        return False, f"Daily loss limit hit ({portfolio['daily_pnl_pct']:.1f}%) — no new trades today"

    if portfolio["weekly_pnl_pct"] <= -config["max_weekly_loss_pct"]:
        # Don't stop trading but halve position sizes
        portfolio["emergency_size_modifier"] = 0.5
        log_event("Weekly loss limit hit — position sizes halved for remainder of week")

    if portfolio["total_drawdown_pct"] <= -config["max_total_drawdown_pct"]:
        halt_system("MAX_TOTAL_DRAWDOWN_EXCEEDED")
        send_telegram_alert("🚨 SYSTEM HALTED: Total drawdown limit reached. Manual review required.")
        return False, "System halted — total drawdown limit exceeded"

    return True, "Drawdown within limits"
```

### 7.4 Loss Streak Controls

```python
LOSS_STREAK_RULES = {
    "max_consecutive_losses": 5,        # Pause after 5 consecutive losses [DEFAULT]
    "cooldown_hours": 24,               # 24-hour pause before resuming [DEFAULT]
    "post_cooldown_size_reduction": 0.5,  # Trade at 50% size for next 10 trades
    "full_size_resume_after_wins": 3,   # Return to full size after 3 consecutive wins
}

def check_loss_streak(portfolio: dict, config: dict) -> tuple[bool, str]:
    if portfolio["consecutive_losses"] >= config["max_consecutive_losses"]:
        hours_since_last_loss = get_hours_since_last_trade()
        if hours_since_last_loss < config["cooldown_hours"]:
            remaining = config["cooldown_hours"] - hours_since_last_loss
            return False, f"Loss streak cooldown: {remaining:.0f} hours remaining"
    return True, "Loss streak within limits"
```

---

## 8. Market Context Filters

### 8.1 Regime Filter

```python
def regime_filter(stage1: dict, stage2: dict, signal: dict) -> tuple[bool, str]:
    """Block or warn based on macro regime."""

    # Block: asset in avoid list for current quadrant
    if signal["asset_class"] in stage2["avoid_asset_classes"]:
        return False, f"{signal['asset_class']} avoid-listed in {stage2['macro_quadrant']} regime"

    # Warn: trading against path of least resistance
    trade_against_pol = (
        stage2["path_of_least_resistance"] == "LONG_RISK" and signal["direction"] == "SHORT" or
        stage2["path_of_least_resistance"] == "SHORT_RISK" and signal["direction"] == "LONG"
    )
    if trade_against_pol and signal["signal_confidence"] < 75:
        return False, "Trade against path of least resistance requires confidence >= 75"

    return True, "Regime filter passed"
```

### 8.2 Volatility Filter

```python
def volatility_filter(stage1: dict, signal: dict) -> tuple[bool, str]:
    """Filter based on volatility regime."""
    if stage1["volatility_regime"] == "EXTREME":
        if signal["signal_grade"] not in ["A"]:
            return False, "EXTREME volatility — only Grade A signals permitted"
    return True, "Volatility filter passed"
```

### 8.3 News/Event Filter (Blackout Window)

```python
def news_blackout_filter(econ_calendar: list, minutes_before: int = 30, minutes_after: int = 15) -> tuple[bool, str]:
    """Block new entries within [minutes_before] of a HIGH impact event."""
    now = datetime.utcnow()
    for event in econ_calendar:
        if event["impact"] == "HIGH":
            event_time = event["datetime_utc"]
            minutes_to_event = (event_time - now).total_seconds() / 60
            minutes_since_event = (now - event_time).total_seconds() / 60
            if -minutes_after <= minutes_since_event <= minutes_before:
                return False, f"News blackout: {event['name']} at {event_time.strftime('%H:%M')} UTC"
    return True, "No news blackout active"
```

### 8.4 Session Filter

```python
ACTIVE_SESSIONS = {
    "FOREX": [
        {"name": "London", "start_utc": "08:00", "end_utc": "17:00"},
        {"name": "New York", "start_utc": "13:00", "end_utc": "22:00"},
    ],
    "EQUITIES": [
        {"name": "US Market Hours", "start_utc": "14:30", "end_utc": "21:00"},
    ],
    "CRYPTO": [],  # 24/7 — no session filter
}

def session_filter(asset_class: str) -> tuple[bool, str]:
    sessions = ACTIVE_SESSIONS.get(asset_class, [])
    if not sessions:
        return True, "No session restriction"
    now_utc = datetime.utcnow().strftime("%H:%M")
    for session in sessions:
        if session["start_utc"] <= now_utc <= session["end_utc"]:
            return True, f"Active session: {session['name']}"
    return False, "Outside active trading session"
```

### 8.5 OpEx / Quad Witching Filter

```python
def opex_filter(days_to_expiry: int, warning_days: int = 3) -> tuple[bool, str]:
    """Warn (don't block) when within 3 days of monthly options expiry."""
    if days_to_expiry <= warning_days:
        # Don't block — just flag. Mechanical flows can distort but also create opportunities.
        return True, f"⚠️ OpEx warning: {days_to_expiry} days to expiry — mechanical flows possible"
    return True, "No OpEx warning"
```

---

## 9. Psychology & Discipline Framework

### 9.1 Pre-Trade Checklist

The system auto-generates this and embeds it in the Stage 5 output. The trader reviews it in the dashboard before approving execution.

```
PRE-TRADE CHECKLIST — must all be TRUE before [APPROVE & EXECUTE] button is active:
[ ] Signal grade is A, B, or C (not WATCH or PASS)
[ ] All 5 pipeline stages completed without early exit
[ ] No news blackout within 30 minutes
[ ] R:R ratio >= 2.0
[ ] Position size within portfolio risk limits
[ ] Daily drawdown limit not hit today
[ ] Consecutive loss cooldown not active
[ ] Asset not in macro regime avoid list
[ ] Technical gate is not RED (GREEN or AMBER only)
[ ] Trade direction consistent with fundamental bias
```

### 9.2 Trading Schedule

```python
MAX_SIGNALS_PER_DAY = 10        # System will not generate more than 10 signals per day [DEFAULT]
MAX_APPROVED_TRADES_PER_DAY = 3  # Trader can approve max 3 trades per day [DEFAULT]
MAX_TRADES_PER_WEEK = 10        # [DEFAULT]
REQUIRED_WEEKLY_REVIEW = "Sunday 18:00 local time"  # Review all trades and update CB tracker
```

### 9.3 Revenge Trading Prevention

```python
def revenge_trade_prevention(portfolio: dict, config: dict) -> tuple[bool, str]:
    """
    Prevents escalating position sizes after a loss.
    Position size CANNOT increase after a losing trade.
    """
    last_trade = portfolio["last_closed_trade"]
    if last_trade and last_trade["outcome"] == "LOSS":
        if portfolio["consecutive_losses"] >= 2:
            # Force 50% size reduction after 2nd consecutive loss
            portfolio["temp_size_modifier"] = 0.5
            return True, "⚠️ 2+ consecutive losses — position size reduced 50%"
    return True, "No revenge trade risk detected"
```

### 9.4 Post-Trade Journal — Auto-Logged Fields

Every closed trade is automatically logged to the database with:

| Field | Source |
|-------|--------|
| `trade_id` | Auto-generated UUID |
| `asset` | Signal data |
| `direction` | Signal data |
| `entry_price`, `exit_price` | MT5 bridge |
| `stop_loss`, `take_profit` | Signal data |
| `lot_size` | Position sizing calculation |
| `entry_time`, `exit_time` | MT5 broker timestamps |
| `exit_reason` | STOP_LOSS / TP1 / TP2 / TP3 / TIME / INVALIDATION / MANUAL |
| `r_multiple_achieved` | Calculated: `(exit - entry) / (entry - stop)` |
| `signal_grade` | Stage 5 output |
| `signal_confidence` | Stage 5 output |
| `macro_quadrant` | Stage 2 output |
| `trade_type` | Stage 3 output |
| `policy_divergence_quality` | Stage 3 output |
| `stage1_json` | Full JSON archived |
| `stage2_json` | Full JSON archived |
| `stage3_json` | Full JSON archived |
| `stage4_json` | Full JSON archived |
| `stage5_json` | Full JSON archived |
| `invalidation_hit` | Boolean — did an invalidation condition trigger? |
| `account_equity_at_entry` | MT5 bridge |
| `daily_pnl_at_entry` | Portfolio tracker |

---

## 10. MT5 Execution Bridge

### 10.1 MT5 Python Library Setup

```python
# mt5_bridge.py
import MetaTrader5 as mt5
from datetime import datetime
import logging

class MT5Bridge:
    def __init__(self, login: int, password: str, server: str):
        if not mt5.initialize(login=login, password=password, server=server):
            raise ConnectionError(f"MT5 init failed: {mt5.last_error()}")
        self.account_info = mt5.account_info()
        logging.info(f"MT5 connected: {self.account_info.name} | Balance: {self.account_info.balance}")

    def get_equity(self) -> float:
        return mt5.account_info().equity

    def get_current_price(self, symbol: str, side: str = "ask") -> float:
        tick = mt5.symbol_info_tick(symbol)
        return tick.ask if side == "ask" else tick.bid

    def get_pip_value(self, symbol: str) -> float:
        info = mt5.symbol_info(symbol)
        return info.trade_tick_value / info.trade_tick_size * info.point

    def send_order(self, symbol: str, direction: str, order_type: str,
                   price: float, lot_size: float, stop_loss: float,
                   take_profit: float, comment: str = "") -> dict:

        order_type_map = {
            ("LONG", "MARKET"): mt5.ORDER_TYPE_BUY,
            ("SHORT", "MARKET"): mt5.ORDER_TYPE_SELL,
            ("LONG", "LIMIT"): mt5.ORDER_TYPE_BUY_LIMIT,
            ("SHORT", "LIMIT"): mt5.ORDER_TYPE_SELL_LIMIT,
        }

        request = {
            "action": mt5.TRADE_ACTION_DEAL if order_type == "MARKET" else mt5.TRADE_ACTION_PENDING,
            "symbol": symbol,
            "volume": lot_size,
            "type": order_type_map[(direction, order_type)],
            "price": price,
            "sl": stop_loss,
            "tp": take_profit,
            "comment": comment,
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        result = mt5.order_send(request)
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            raise RuntimeError(f"MT5 order failed: {result.retcode} — {result.comment}")

        return {"ticket": result.order, "price": result.price, "volume": result.volume}

    def partial_close(self, ticket: int, pct: float) -> None:
        position = mt5.positions_get(ticket=ticket)[0]
        close_volume = round(position.volume * pct, 2)
        close_type = mt5.ORDER_TYPE_SELL if position.type == 0 else mt5.ORDER_TYPE_BUY
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": position.symbol,
            "volume": close_volume,
            "type": close_type,
            "position": ticket,
            "comment": f"Partial close {pct*100:.0f}%",
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        mt5.order_send(request)

    def modify_stop(self, ticket: int, new_stop: float) -> None:
        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "position": ticket,
            "sl": new_stop,
        }
        mt5.order_send(request)

    def close_trade(self, ticket: int, reason: str = "") -> None:
        position = mt5.positions_get(ticket=ticket)[0]
        close_type = mt5.ORDER_TYPE_SELL if position.type == 0 else mt5.ORDER_TYPE_BUY
        price = self.get_current_price(position.symbol, "bid" if position.type == 0 else "ask")
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": position.symbol,
            "volume": position.volume,
            "type": close_type,
            "position": ticket,
            "price": price,
            "comment": reason,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        mt5.order_send(request)

    def get_open_positions(self) -> list:
        return mt5.positions_get() or []

    def get_pending_orders(self) -> list:
        return mt5.orders_get() or []
```

### 10.2 TradingView Webhook Receiver

```python
# In main FastAPI app
from fastapi import FastAPI, Request
import asyncio

app = FastAPI()

@app.post("/webhook/tradingview")
async def tradingview_webhook(request: Request):
    """
    TradingView sends a POST with JSON body when a price alert fires.
    Configure TradingView alert message as:
    {"asset": "EURUSD", "trigger": "price_alert", "price": {{close}}}
    """
    body = await request.json()
    asset = body.get("asset")
    if not asset:
        return {"status": "error", "message": "No asset in webhook payload"}

    # Trigger the full pipeline asynchronously
    asyncio.create_task(run_pipeline_and_notify(asset))
    return {"status": "ok", "message": f"Pipeline triggered for {asset}"}

@app.post("/analyse")
async def manual_analyse(request: Request):
    """Manual trigger from dashboard."""
    body = await request.json()
    asset = body.get("asset")
    asyncio.create_task(run_pipeline_and_notify(asset))
    return {"status": "ok", "message": f"Analysis started for {asset}"}

@app.post("/approve")
async def approve_trade(request: Request):
    """Called when trader clicks APPROVE & EXECUTE in dashboard."""
    body = await request.json()
    signal_id = body.get("signal_id")
    signal = get_signal_from_db(signal_id)
    can_enter, reason = should_enter_trade(signal, get_portfolio(), config)
    if can_enter:
        result = execute_entry(signal, config, mt5_bridge)
        return {"status": "executed", "ticket": result["ticket"]}
    return {"status": "blocked", "reason": reason}
```

---

## 11. Web Dashboard

### 11.1 Dashboard Pages

| Page | Description |
|------|-------------|
| **/ (Home)** | Live macro regime panel + latest signals feed |
| **/signals** | All signals with grade badges, expand to see full analysis |
| **/signal/:id** | Full signal detail: all 5 stage outputs, pre-trade checklist, approve button |
| **/positions** | Open positions in MT5: P&L, time in trade, invalidation monitor |
| **/stats** | Self-awareness statistics: win rate by grade/regime/asset/trade type |
| **/settings** | Config: risk%, max positions, MT5 credentials, Telegram token |

### 11.2 Signal Card UI (React Component)

Each signal card shows:
```
┌─────────────────────────────────────────────────┐
│  [A] EUR/USD  ▲ LONG     Confidence: 87/100      │
│  Macro: EXPANSION | Risk ON | Policy: Early↑     │
│  Entry: 1.0842–1.0855  Stop: 1.0782  T1: 1.0962 │
│  R:R: 2.0  Size: 0.8 lots  Hold: 2–4 days        │
│  ─────────────────────────────────────────────── │
│  Fed pivoting hawkish vs ECB pausing. EUR rate   │
│  differential widening. ISM beat + NFP strong.   │
│  Price at 1SD IV support, uptrend confirmed...   │
│  ─────────────────────────────────────────────── │
│  Invalidation: Close below 1.0782 | ECB surprise │
│  [▶ APPROVE & EXECUTE]  [👁 WATCH LIST]  [✕ SKIP]│
└─────────────────────────────────────────────────┘
```

### 11.3 Macro Regime Panel (always visible in header)

```
┌─────────────────────────────────────────────────┐
│  REGIME: EXPANSION  |  Risk: ON  |  Mode: PORT  │
│  Growth: ↑ ACCEL    |  Inflation: ↓ DECEL       │
│  VIX: 18.2 (+2.1%)  |  Position Modifier: 1.0x  │
│  Quadrant Confidence: HIGH  |  Updated: 09:45    │
└─────────────────────────────────────────────────┘
```

---

## 12. Backtesting Plan

### 12.1 Backtesting Checklist

| # | Task | Status |
|---|------|--------|
| 1 | Collect 5 years of daily OHLCV for all instruments | ☐ |
| 2 | Collect 5 years of FRED macro data (GDP, CPI, PMI, etc.) | ☐ |
| 3 | Build macro regime classifier backtest (Stage 1 + 2 using historical data) | ☐ |
| 4 | Build fundamental scorer backtest (Stage 3 — score historical driver data) | ☐ |
| 5 | Implement entry logic exactly as per Section 4 | ☐ |
| 6 | Implement exit logic exactly as per Section 5 | ☐ |
| 7 | Implement position sizing as per Section 6 | ☐ |
| 8 | Apply all filters from Section 8 | ☐ |
| 9 | Run in-sample backtest (Jan 2018 – Dec 2022) | ☐ |
| 10 | Run out-of-sample validation (Jan 2023 – Dec 2024) | ☐ |
| 11 | Run Monte Carlo simulation (min 1,000 iterations) | ☐ |
| 12 | Sensitivity test: vary each parameter ±20% | ☐ |
| 13 | Stress test: 2020 COVID crash, 2022 rate spike | ☐ |
| 14 | Paper trade on MT5 demo for minimum 30 days / 30 signals | ☐ |
| 15 | Compare paper trade results vs backtest — variance < 30% | ☐ |
| 16 | Go live at 25% normal position size for 30 days | ☐ |

### 12.2 Target Performance Metrics

| Metric | Minimum | Ideal | Description |
|--------|---------|-------|-------------|
| Net Profit Factor | > 1.4 | > 2.0 | Gross profit / Gross loss |
| Win Rate | > 42% | > 55% | % of trades reaching T1 |
| Average R:R Achieved | > 1.5 | > 2.5 | Actual avg win / avg loss |
| Max Drawdown | < 20% | < 10% | Peak-to-trough |
| Sharpe Ratio | > 1.0 | > 1.8 | Risk-adjusted annual return |
| Sortino Ratio | > 1.5 | > 2.5 | Downside risk-adjusted |
| Recovery Factor | > 3.0 | > 5.0 | Net profit / Max drawdown |
| Expectancy (R) | > 0.25R | > 0.5R | Per trade expected value |
| Max Consecutive Losses | < 8 | < 5 | Longest losing streak |
| Grade A Win Rate | > 60% | > 70% | Grade A signals specifically |
| Grade B Win Rate | > 50% | > 60% | Grade B signals |
| Grade C Win Rate | > 40% | > 50% | Grade C signals |

### 12.3 Go / No-Go Criteria

The system goes live ONLY if ALL of the following are satisfied on **out-of-sample data**:

- [ ] Net Profit Factor > 1.4
- [ ] Max Drawdown < 20%
- [ ] Sharpe Ratio > 1.0
- [ ] Grade A signals outperform Grade B, Grade B outperforms Grade C (signal grading working)
- [ ] Monte Carlo: < 5% probability of ruin at max tested drawdown
- [ ] Parameter sensitivity: no cliff edges within ±20% of any parameter
- [ ] Paper trade results within 30% variance of backtest results

---

## 13. Self-Awareness Statistics Module

### 13.1 Key Metrics (auto-calculated from trade log)

| Metric | Query |
|--------|-------|
| `overall_win_rate` | % trades where exit_reason IN ('TP1', 'TP2', 'TP3') |
| `avg_r_multiple` | AVG(r_multiple_achieved) |
| `win_rate_by_grade` | GROUP BY signal_grade |
| `win_rate_by_quadrant` | GROUP BY macro_quadrant |
| `win_rate_by_asset_class` | GROUP BY asset_class |
| `win_rate_by_trade_type` | GROUP BY trade_type (SWING_CATALYST vs SWING_TACTICAL) |
| `win_rate_by_divergence_quality` | GROUP BY policy_divergence_quality |
| `regime_classifier_accuracy` | Did predicted regime match next 30-day market behaviour? |
| `grade_discrimination_index` | Is Grade A actually outperforming Grade B? |
| `best_performing_session` | GROUP BY session (London / NY) |
| `catalyst_vs_tactical_delta` | Win rate diff between SWING_CATALYST and SWING_TACTICAL |
| `monthly_r_multiple` | Monthly sum of R multiples — should be positive and consistent |

### 13.2 Feedback Loop to Pipeline

Every 30 trades, the system calculates performance by grade and by regime and updates the Stage 5 prompt with a performance note:

```python
PERFORMANCE_CONTEXT = f"""
SYSTEM PERFORMANCE FEEDBACK (last 30 trades):
- Grade A win rate: {grade_a_wr:.0%} | Avg R: {grade_a_r:.2f}
- Grade B win rate: {grade_b_wr:.0%} | Avg R: {grade_b_r:.2f}
- Grade C win rate: {grade_c_wr:.0%} | Avg R: {grade_c_r:.2f}
- Best performing regime: {best_regime}
- Best trade type: {best_trade_type}
- Worst performing asset class: {worst_asset_class}
Use this context to calibrate scoring thresholds if Grade discrimination is collapsing.
"""
```

---

## 14. Complete File Structure

```
/wish-ai-trading/
│
├── main.py                        # FastAPI app — entry point, all routes
├── config.py                      # All configurable parameters (risk %, MT5 creds, etc.)
├── requirements.txt               # All Python dependencies
│
├── /pipeline/                     # AI pipeline stages
│   ├── orchestrator.py            # run_full_pipeline() — chains all 5 stages
│   ├── stage1_regime.py           # Market regime classifier
│   ├── stage2_grid.py             # Growth/Inflation grid
│   ├── stage3_idea.py             # Macro drivers + 3-Step + Relative value
│   ├── stage4_gate.py             # Technicals + IV + gatekeeping
│   └── stage5_signal.py           # Final signal aggregator + scoring
│
├── /prompts/                      # All LLM prompt templates (string files)
│   ├── stage1_system.txt
│   ├── stage1_user.txt
│   ├── stage2_system.txt
│   ├── stage2_user.txt
│   ├── stage3_system.txt
│   ├── stage3_user.txt
│   ├── stage4_system.txt
│   ├── stage4_user.txt
│   ├── stage5_system.txt
│   └── stage5_user.txt
│
├── /data/                         # Data fetching and calculation
│   ├── fetcher_fred.py            # FRED API — GDP, CPI, yield curve, etc.
│   ├── fetcher_market.py          # yfinance — OHLCV, VIX, index prices
│   ├── fetcher_iv.py              # Implied volatility + daily 1SD/2SD calculator
│   ├── fetcher_calendar.py        # Economic calendar (investing.com scrape)
│   ├── fetcher_cot.py             # CFTC COT positioning data
│   ├── fetcher_cb.py              # Central bank stance tracker (stored + updated)
│   ├── technicals.py              # All TA: MA, RSI, ATR, patterns, volume
│   └── macro_grid.py              # Pre-classifier for Growth/Inflation quadrant
│
├── /execution/                    # Trade execution layer
│   ├── mt5_bridge.py              # Full MT5 Python API wrapper
│   ├── order_manager.py           # Entry, partial close, trail, time exit
│   ├── position_sizer.py          # Lot size calculator
│   └── trade_monitor.py           # Monitors open trades for invalidation
│
├── /risk/                         # Risk management
│   ├── portfolio_risk.py          # Portfolio-level risk checks
│   ├── drawdown_controller.py     # Daily/weekly/total DD controls
│   ├── loss_streak.py             # Consecutive loss rules
│   └── filters.py                 # Regime, session, news blackout, OpEx filters
│
├── /database/                     # Persistence layer
│   ├── schema.sql                 # Full SQLite schema
│   ├── db.py                      # DB connection + query helpers
│   └── trade_logger.py            # Auto-log all trades + signal JSONs
│
├── /stats/                        # Self-awareness statistics
│   ├── performance_tracker.py     # All metrics from Section 13
│   └── feedback_builder.py        # Builds performance context for Stage 5 prompt
│
├── /alerts/                       # Notifications
│   └── telegram_bot.py            # Send signal alerts + trade outcomes to Telegram
│
└── /frontend/                     # React web dashboard
    ├── package.json
    ├── /src/
    │   ├── App.jsx
    │   ├── /components/
    │   │   ├── MacroRegimeHeader.jsx    # Always-visible regime panel
    │   │   ├── SignalCard.jsx           # Signal display + approve/reject buttons
    │   │   ├── SignalDetail.jsx         # Full 5-stage breakdown
    │   │   ├── PositionsTable.jsx       # Open MT5 positions
    │   │   ├── StatsPanel.jsx           # Self-awareness metrics
    │   │   └── PreTradeChecklist.jsx    # Checklist before approve button activates
    │   └── /pages/
    │       ├── Home.jsx
    │       ├── Signals.jsx
    │       ├── Positions.jsx
    │       ├── Stats.jsx
    │       └── Settings.jsx
    └── /public/
```

---

## 15. Complete Hard Rules Reference

These are non-negotiable constraints enforced in code, not delegated to the LLM:

| # | Rule | Where Enforced |
|---|------|---------------|
| 1 | Fundamentals generate ideas. Technicals only time entries. | Stage 3 / Stage 4 separation |
| 2 | LLM cannot reverse fundamental direction using technicals | Stage 4 system prompt + code validation |
| 3 | Bear market → position_size_modifier max 0.50 | Stage 1 hard rule |
| 4 | VIX rise >25% → halve position size | Stage 1 hard rule |
| 5 | Use 20/60/250-day MAs only. Never 50 or 200. | Stage 4 prompt + technicals.py |
| 6 | RSI >70 = momentum confirmation when bullish. Not overbought. | Stage 4 prompt |
| 7 | Minimum R:R = 2.0. Below 2.0 → WATCH_LIST | Stage 4 + Stage 5 validation |
| 8 | Stop loss = where trade is wrong structurally | Stage 4 prompt |
| 9 | Stop never moved against the trade | order_manager.py |
| 10 | No entry within 30 min of HIGH impact event | news_blackout_filter() |
| 11 | Pegged/fixed currencies not tradeable | regime filter + asset universe list |
| 12 | Rate of change beats absolute level in all scoring | Stage 3 prompt |
| 13 | Policy divergence: EARLY+WIDENING best. LATE+NARROWING = do not chase | Stage 3 scoring |
| 14 | Short-term risk-on catalyst in RISK_OFF regime = day trade only | Stage 3 trade_type logic |
| 15 | Max daily loss 3% → no new trades that day | drawdown_controller.py |
| 16 | Max total drawdown 15% → halt system | drawdown_controller.py |
| 17 | After 5 consecutive losses → 24hr cooldown | loss_streak.py |
| 18 | Max 5 concurrent open positions | portfolio_risk.py |
| 19 | Max 2 correlated positions (r > 0.70) | portfolio_risk.py |
| 20 | It's never just one thing — if no identifiable reason for move, NO_TRADE | Stage 3 prompt |

---

## 16. Instructions for Claude Code

Hand this entire document to Claude Code and say:

> "Build the WISH-AI Trading Engine exactly as specified in `AI_Trading_System_Spec_V3.md`. This is a Python application with a FastAPI backend, React frontend, Anthropic Claude API integration, and MetaTrader 5 execution bridge.
>
> Build in this order:
> 1. Project scaffold — create all folders and empty files per the file structure in Section 14
> 2. `config.py` — all configurable parameters with the defaults specified in the document
> 3. `requirements.txt` — all dependencies: anthropic, fastapi, uvicorn, yfinance, fredapi, ta, MetaTrader5, pandas, numpy, requests, beautifulsoup4, apscheduler, python-telegram-bot, sqlite3
> 4. `/data/` layer — all fetchers and calculators, fully working with real APIs
> 5. `/pipeline/` — all 5 stage modules, using the exact LLM prompts from Section 3 (stored in `/prompts/` as text files and loaded at runtime, not hardcoded)
> 6. `/execution/` — MT5 bridge using the MetaTrader5 Python library as specified in Section 10
> 7. `/risk/` — all risk management modules as specified in Sections 6 and 7
> 8. `main.py` — FastAPI app with all routes: `/webhook/tradingview`, `/analyse`, `/approve`, `/positions`, `/stats`
> 9. `/database/schema.sql` and `db.py` — SQLite schema logging all fields from Section 9.4
> 10. `/frontend/` — React + Tailwind dashboard with signal cards, regime header, and approve/reject buttons as described in Section 11
> 11. `/stats/` — self-awareness metrics from Section 13
> 12. `/alerts/telegram_bot.py` — Telegram notifications
>
> Every function must match the pseudocode in the spec exactly. Every LLM prompt must be loaded from its `/prompts/` text file. Every hard rule in Section 15 must be enforced in code, not left to the LLM. All configurable values must come from `config.py`, not be hardcoded.
>
> After building, create a `README.md` with: installation steps, environment variable setup, how to connect MT5, how to configure TradingView webhooks, and how to run the app locally."

---

*End of WISH-AI Trading Engine — Technical Specification V3*
*Version 3.0 | Built from ITPM WISH Framework + Professional FX & Fundamental Masterclass*
