"""
4-Stage Trading Signal LLM Pipeline
Implements the ITPM WISH Framework as a sequential LLM pipeline.

Stage 1: Market Regime Classification (temperature=0.0)
Stage 2: Macro Fundamental Analysis (temperature=0.2)
Stage 3: Technical Gatekeeping (temperature=0.1)
Stage 4: Final Signal Aggregator (temperature=0.0)

Each stage receives structured data inputs and outputs a JSON object.
The output of each stage chains into the next as context.
"""
import json
import logging
import re
from typing import Any, Dict, Optional

from app.services.llm_service import generate_sync

logger = logging.getLogger(__name__)

# ─── JSON Parser ─────────────────────────────────────────────────────────────

def _extract_json(text: str) -> Optional[dict]:
    """Extract first JSON object/dict from LLM response text."""
    # Try to find a code block first
    code_block_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if code_block_match:
        try:
            return json.loads(code_block_match.group(1))
        except json.JSONDecodeError:
            pass

    # Try to find raw { ... } pattern
    json_match = re.search(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass

    # Last resort: try parsing the whole text
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    return None


# ─── Prompt Templates ───────────────────────────────────────────────────────

STAGE1_SYSTEM = """You are a professional macro trader trained in the ITPM/Anton Kreil WISH framework.
Your job is to classify the current market regime with precision.
Answer ONLY with JSON. No explanation outside the JSON block."""

STAGE1_USER_TEMPLATE = """Classify the current market regime using the following data:

Index: S&P 500
Current Price: {spx_current}
Previous Business Cycle High: {spx_prev_cycle_high}
Bear Market Level (×0.80): {bear_market_level}
Bull Market Confirmation Level: {bull_market_level}

VIX Current: {vix_current}
VIX 30 Days Ago: {vix_30d_ago}
VIX % Change (30d): {vix_pct_change}%

FED SENTIMENT (FSM):{fed_context_block}

Return ONLY this JSON (no markdown, no explanation):
{{"market_regime": "...", "volatility_regime": "...", "trading_mode": "...", "position_size_modifier": ..., "regime_reasoning": "...", "vix_signal": "..."}}

Rules:
- market_regime: BULL | BEAR | TRANSITIONING_TO_BEAR | TRANSITIONING_TO_BULL
- volatility_regime: LOW (<18 or -25%) | NORMAL | HIGH (+25%) | EXTREME (>40)
- trading_mode: PORTFOLIO_MANAGER | SHORT_TERM_TRADER | REDUCE_EXPOSURE | SIDELINES
- position_size_modifier: 0.25 | 0.5 | 0.75 | 1.0 (halved for HIGH vol, quartered for EXTREME)
- If BEAR market: trading_mode = REDUCE_EXPOSURE or SIDELINES only
- If VIX % change >25%: volatility_regime = HIGH minimum
- If Fed is in active TIGHTENING cycle with HIGH conviction → add hawkish pressure to volatility regime
- If Fed pivot is in progress (is_pivot_in_progress=true) → note transition risk in regime_reasoning
- regime_reasoning: professional explanation using the specific numbers above
- vix_signal: what VIX reading implies for exposure: REDUCE_EXPOSURE | HOLD | ADD_EXPOSURE | DAY_TRADE_MODE"""


STAGE2_SYSTEM = """You are a professional macro trader. You generate trade ideas from macroeconomic fundamentals only.
You do NOT generate ideas from charts or technical indicators.
Your analysis follows the endogenous (country in isolation) then exogenous (relative comparison) approach.
Answer ONLY with JSON."""

STAGE2_USER_TEMPLATE = """Generate a macro fundamental directional bias for: {asset}

REGIME CONTEXT (from Stage 1):
Market Regime: {market_regime}
Volatility Regime: {volatility_regime}
Trading Mode: {trading_mode}

MACRO DATA (with Rate of Change):
- GDP: {gdp_latest} (prior: {gdp_prior}, RoC: {gdp_roc_pct}%, direction: {gdp_direction})
- CPI: {cpi_latest} (prior: {cpi_prior}, RoC: {cpi_roc_pct}%, direction: {cpi_direction})
- PCE: {pce_latest} (prior: {pce_prior}, RoC: {pce_roc_pct}%, direction: {pce_direction})
- Unemployment: {unemployment_latest} (direction: {unemployment_direction})
- Leading Indicator: {leading_latest} (direction: {leading_direction})
- Consumer Sentiment: {sentiment_latest} (direction: {sentiment_direction})
- Yield Curve (10Y-2Y): {yield_curve_latest} (direction: {yield_curve_direction})
- Fed Funds: {fed_funds_latest} (direction: {fed_funds_direction})

ECONOMIC QUADRANT: {economic_quadrant}
(EXPANSION=growth↑+inflation↓, REFLATION=growth↑+inflation↑, DISINFLATION=growth↓+inflation↓, STAGFLATION=growth↓+inflation↑)

ADDITIONAL DATA:
- ISM Manufacturing: {ism_manufacturing}
- Consumer Confidence: {consumer_confidence}
- NFP Change (monthly): {nfp_change}
- Core PCE: {core_pce}%
- Rate Trend: {rate_trend}
- CB Bias: {cb_bias}
- Fiscal Balance: {fiscal_deficit}
- USD Index (DXY): {dxy}
- Wage Growth: {wage_growth}%
- Retail Sales: {retail_sales}

COT POSITIONING:
- Net: {cot_net_pct}% ({cot_status})

{forex_extra}

FED MONETARY POLICY (FSM):{fed_context_block}

Return ONLY this JSON:
{{"fundamental_bias": "...", "bias_strength": "...", "economic_quadrant": "{economic_quadrant}", "driver_scores": {{"ism_pmi": "...", "consumer_confidence": "...", "employment": "...", "monetary_policy": "...", "inflation": "...", "gdp_trend": "...", "rate_differential": "...", "commodity_exposure": "...", "fiscal_policy": "...", "trade_balance": "..."}}, "top_drivers": ["...", "..."], "fundamental_reasoning": "...", "swing_trade_aligned": true|false, "swing_trade_note": "...", "relative_value_score": {{"policy_divergence_score": 0, "growth_divergence_score": 0, "rate_differential_score": 0, "composite_score": 0, "divergence_maturity": "N/A"}}}}

Rules:
- fundamental_bias: BULLISH | BEARISH | NEUTRAL
- bias_strength: STRONG | MODERATE | WEAK
- Rate of change matters more than absolute levels. ACCELERATING vs DECELERATING is the key signal.
- Use the economic quadrant to frame the overall macro environment.
- Score each driver as: BULLISH | BEARISH | NEUTRAL | N/A
- top_drivers: 2-3 strongest drivers by name (e.g. ["employment", "monetary_policy"])
- If fundamental_bias = NEUTRAL and bias_strength = WEAK → output NO_TRADE for the whole signal
- COT extremes (EXTREME_LONG or EXTREME_SHORT) are timing warnings, not directional signals
- FSM divergence: if language_score ≠ market_score direction → note as a surprise risk in fundamental_reasoning
- FSM USD_bullish signal + HAWKISH regime → strengthen BEARISH bias on risk assets; USD_bearish → weaken it
- If FSM conviction is HIGH, weight FSM signal heavily in monetary_policy driver score
- relative_value_score (FX pairs only; set all scores to 0 for non-FX):
  - policy_divergence_score: -3 (quote more hawkish) to +3 (base more hawkish)
  - growth_divergence_score: -3 to +3 based on GDP/ISM divergence between base and quote economies
  - rate_differential_score: -3 to +3 based on rate_differential_bps and trend
  - composite_score: sum of the three scores (-9 to +9); positive = bullish base currency
  - divergence_maturity: copy from POLICY DIVERGENCE input (EARLY|MID_CYCLE|LATE_CYCLE|N/A)"""


STAGE3_SYSTEM = """You are a professional trader's gatekeeping system.
Your ONLY job is to assess timing. The fundamental idea has already been generated.
You do NOT change the fundamental direction. You only decide if NOW is a good time to enter.
Answer ONLY with JSON."""

STAGE3_USER_TEMPLATE = """FUNDAMENTAL BIAS (from Stage 2): {fundamental_bias} ({bias_strength})
Top Drivers: {top_drivers}
ASSET: {asset}
CURRENT PRICE: {current_price}

TECHNICAL INPUTS:
- Price vs 20-day MA: {price_vs_20ma}
- Price vs 60-day MA: {price_vs_60ma}
- Price vs 250-day MA: {price_vs_250ma}
- 20MA vs 60MA Cross: {ma_20_vs_60_cross}
- 60MA vs 250MA Cross: {ma_60_vs_250_cross}
- RSI (14): {rsi_14}
- Trend Direction: {trend_direction}
- Chart Pattern: {price_pattern}
- Volume vs Average: {volume_vs_avg}
- ATR (14): {atr_14}
- Key Support: {key_support}
- Key Resistance: {key_resistance}
- Price Location: {at_support_resistance}

VOLATILITY RANGES (HV30 proxy):
- Daily 1SD: ±{daily_1sd} | Weekly 1SD: ±{weekly_1sd} | Monthly 1SD: ±{monthly_1sd}
- Hard Stop Distance: {hard_stop_distance}
- Soft Target Distance: {soft_target_distance}

Return ONLY this JSON:
{{"gate_signal": "...", "entry_recommendation": "...", "technical_alignment": "...", "suggested_entry_price": null|..., "stop_loss_price": null|..., "target_price": null|..., "target_2_price": null|..., "target_3_price": null|..., "risk_reward_ratio": null|..., "gate_reasoning": "...", "watch_list_trigger": "..."}}

- target_price (T1): 2R from entry (risk = |entry - stop|); for LONG: entry + (risk × 2.0), for SHORT: entry - (risk × 2.0)
- target_2_price (T2): 3R from entry; for LONG: entry + (risk × 3.0), for SHORT: entry - (risk × 3.0)
- target_3_price (T3): 4.5R stretch; for LONG: entry + (risk × 4.5), for SHORT: entry - (risk × 4.5)
- risk_reward_ratio: R:R to T1 only (target_price)

Rules:
- gate_signal: GREEN | AMBER | RED
- entry_recommendation: ENTER_FULL | ENTER_HALF | WATCH_LIST | DO_NOT_ENTER
- technical_alignment: ALIGNED | PARTIAL | CONFLICTING

LONG (BULLISH bias) rules:
- suggested_entry_price: at or below current price (limit order or current)
- stop_loss_price: BELOW entry (stop_loss_price < suggested_entry_price)
- target_price: ABOVE entry (target_price > suggested_entry_price)
- Default: stop_loss = entry - (ATR × 1.5), target = entry + (ATR × 3)
- If BULLISH and trend = DOWNTREND → WATCH_LIST (never short against bias)
- If BULLISH and pattern = HEAD_SHOULDERS → RED (wait)
- If BULLISH and pattern = INV_HEAD_SHOULDERS → GREEN
- If BULLISH and RANGING → AMBER, half position
- RSI > 70 in BULLISH = momentum confirmation (NOT overbought)
- RSI < 30 in BULLISH = possible entry (amber/green)

SHORT (BEARISH bias) rules:
- suggested_entry_price: at or above current price (limit order or current)
- stop_loss_price: ABOVE entry (stop_loss_price > suggested_entry_price)  ← CRITICAL: SHORT stops go UP
- target_price: BELOW entry (target_price < suggested_entry_price)  ← CRITICAL: SHORT targets go DOWN
- Default: stop_loss = entry + (ATR × 1.5), target = entry - (ATR × 3)
- If BEARISH and trend = UPTREND → WATCH_LIST (wait for turn)
- If BEARISH and pattern = HEAD_SHOULDERS → GREEN (distribution top)
- If BEARISH and pattern = INV_HEAD_SHOULDERS → RED (wait)
- If BEARISH and RANGING → AMBER, half position
- RSI < 30 in BEARISH = momentum confirmation (NOT oversold)
- RSI > 70 in BEARISH = possible short entry (amber/green)

VALIDATION (applies to both):
- If R:R < 2.0 → downgrade to WATCH_LIST
- If stop_loss distance > hard_stop_distance → use hard_stop_distance instead (adjust direction accordingly)
- Use soft_target_distance as validation: target should not exceed soft_target_distance from entry
- watch_list_trigger: what event would turn GREEN (e.g. "Price closes above 1.0900" for longs, "Price breaks below 1.0800" for shorts)"""


STAGE4_SYSTEM = """You are the final signal aggregator for a professional trading system.
Stage 3 has already done the gating work. Your job is to read Stage 3's verdict and translate it
into a final actionable signal with correct direction, sizing, and price levels.
You do NOT re-gate or second-guess Stage 3. You follow the decision matrix below.
Answer ONLY with JSON."""

STAGE4_USER_TEMPLATE = """STAGE 1 — REGIME:
Market Regime: {market_regime}
Volatility Regime: {volatility_regime}
Trading Mode: {trading_mode}
Position Size Modifier: {position_size_modifier}

STAGE 2 — FUNDAMENTALS:
Fundamental Bias: {fundamental_bias}
Bias Strength: {bias_strength}
Top Drivers: {top_drivers}

STAGE 3 — GATEKEEPING (the authoritative entry verdict):
Gate Signal: {gate_signal}
Entry Recommendation: {entry_recommendation}
Suggested Entry: {entry_price}
Stop Loss: {stop_loss}
Target T1 (2R): {target}
Target T2 (3R): {target_2}
Target T3 (4.5R): {target_3}
Risk/Reward: {risk_reward}

Return ONLY this JSON:
{{"final_signal": "...", "signal_grade": "...", "signal_confidence": ..., "direction": "...", "asset": "{asset}", "entry_price": null|..., "stop_loss": null|..., "target": null|..., "target_2": null|..., "target_3": null|..., "risk_reward": null|..., "recommended_position_size_pct": ..., "trade_horizon": "...", "signal_summary": "...", "key_risks": ["...", "..."], "invalidation_conditions": ["...", "..."]}}

SIGNAL GRADE RULES (determine signal_grade after final_signal):
- A: gate GREEN + strong fundamental bias + quadrant aligned + confidence ≥ 80 → full size
- B: gate GREEN or AMBER + most drivers aligned + confidence 70-79 → 75% size
- C: gate AMBER + moderate conviction + confidence 55-69 → 50% size
- WATCH: setup not ready yet → 0% (on watchlist)
- PASS: conflicting signals or confidence < 55 → 0% (no trade)
- If final_signal = NO_TRADE → signal_grade = PASS
- If final_signal = WATCH_LIST → signal_grade = WATCH
- Apply grade modifier to recommended_position_size_pct: A=1.0×, B=0.75×, C=0.50×, WATCH/PASS=0×
  Formula: recommended_position_size_pct = 100 × position_size_modifier × grade_modifier

DECISION MATRIX — follow this exactly, in order:
1. If fundamental_bias = NEUTRAL and bias_strength = WEAK → final_signal = NO_TRADE, direction = NEUTRAL
2. If gate_signal = RED and entry_recommendation = DO_NOT_ENTER → final_signal = NO_TRADE, direction = NEUTRAL
3. If gate_signal = GREEN and entry_recommendation = ENTER_FULL → final_signal = BUY (if BULLISH) or SELL (if BEARISH), confidence ≥ 80
4. If gate_signal = GREEN and entry_recommendation = ENTER_HALF → final_signal = BUY or SELL, confidence 70-79, position size × 0.5
5. If gate_signal = AMBER and entry_recommendation = ENTER_FULL → final_signal = BUY or SELL, confidence 70-79
6. If gate_signal = AMBER and entry_recommendation = ENTER_HALF → final_signal = BUY or SELL, confidence 55-69, position size × 0.5
7. If gate_signal = AMBER and entry_recommendation = WATCH_LIST → final_signal = WATCH_LIST, direction = LONG (if BULLISH) or SHORT (if BEARISH)
8. If gate_signal = RED and entry_recommendation = WATCH_LIST → final_signal = WATCH_LIST, direction = LONG or SHORT

HARD OVERRIDES (only these two justify downgrading the matrix above):
- If market_regime = BEAR (confirmed, not TRANSITIONING) AND fundamental_bias = BULLISH → downgrade one level (BUY→WATCH_LIST)
- If volatility_regime = EXTREME → downgrade one level and halve position size

TRANSITIONING regimes (TRANSITIONING_TO_BULL, TRANSITIONING_TO_BEAR) are NOT hard overrides.
Stage 3 already accounted for regime when setting gate_signal. Do not re-penalise for regime here.

Other rules:
- direction: LONG if BULLISH, SHORT if BEARISH, NEUTRAL only for NO_TRADE
- direction must match final_signal: BUY→LONG, SELL→SHORT — never BUY with NEUTRAL direction
- recommended_position_size_pct: base 100% × position_size_modifier from Stage 1 (then halve if ENTER_HALF)
- Copy entry_price, stop_loss, target, risk_reward from Stage 3 unchanged (do not recalculate)
- key_risks: 2-3 specific risks (e.g. ["NFP release in 48hrs", "Fed minutes Wednesday"])
- invalidation_conditions: what would make the trade wrong

PRICE LEVEL DIRECTION CONSTRAINT (CRITICAL — must be respected):
- For BUY/LONG: stop_loss < entry_price < target  (stop below, target above)
- For SELL/SHORT: target < entry_price < stop_loss  (target below, stop above)
- If Stage 3 prices violate this constraint for the chosen direction, correct them before outputting
- Never output a SHORT trade where stop_loss < entry_price — that is a LONG stop and will be rejected"""


# ─── Stage 1: Regime ──────────────────────────────────────────────────────────

def _build_fed_context_block_stage1(fsm: Optional[Dict[str, Any]]) -> str:
    """Build the FED SENTIMENT block for Stage 1 prompt."""
    if not fsm or not fsm.get("available"):
        return " Not available"
    pivot = "YES" if fsm.get("is_pivot_in_progress") else "NO"
    fomc_line = ""
    days = fsm.get("days_to_next_fomc")
    if days is not None:
        fomc_line = f"\n- Days to Next FOMC: {days:.1f}d {'⚠ PRE-FOMC WINDOW' if fsm.get('pre_fomc_window') else ''}"
    return (
        f"\n- Fed Regime: {fsm.get('fed_regime', 'N/A')}"
        f"\n- Composite Score: {fsm.get('composite_score', 'N/A')} (−100=dovish, +100=hawkish)"
        f"\n- Volatility Multiplier: {fsm.get('volatility_multiplier', 'N/A')}"
        f"\n- Pivot in Progress: {pivot}"
        f"{fomc_line}"
    )


def _build_fed_context_block_stage2(fsm: Optional[Dict[str, Any]]) -> str:
    """Build the FED MONETARY POLICY block for Stage 2 prompt."""
    if not fsm or not fsm.get("available"):
        return " Not available"
    return (
        f"\n- Language Score: {fsm.get('language_score', 'N/A')} | Market Score: {fsm.get('market_score', 'N/A')}"
        f"\n- Divergence: {fsm.get('divergence_category', 'N/A')}"
        f"\n- USD Signal: {fsm.get('signal_direction', 'N/A')} (conviction: {fsm.get('signal_conviction', 'N/A')})"
    )


def run_stage1(regime_data: Dict[str, Any], fsm_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Stage 1: Classify market regime."""
    logger.info("[SIGNALS] Running Stage 1: Regime Classification")

    spx = regime_data.get("spx_current", "N/A")
    prev_high = regime_data.get("spx_prev_cycle_high", "N/A")
    bear = regime_data.get("bear_market_level", "N/A")
    bull = regime_data.get("bull_market_level", "N/A")
    vix = regime_data.get("vix_current", "N/A")
    vix_ago = regime_data.get("vix_30d_ago", "N/A")
    vix_pct = regime_data.get("vix_pct_change", "N/A")

    user_prompt = STAGE1_USER_TEMPLATE.format(
        spx_current=spx,
        spx_prev_cycle_high=prev_high,
        bear_market_level=bear,
        bull_market_level=bull,
        vix_current=vix,
        vix_30d_ago=vix_ago,
        vix_pct_change=vix_pct,
        fed_context_block=_build_fed_context_block_stage1(fsm_context),
    )

    raw = generate_sync(
        prompt=user_prompt,
        system_prompt=STAGE1_SYSTEM,
        temperature=0.0,
        max_tokens=8000,
    )

    result = _extract_json(raw)
    if not result:
        logger.error(f"[SIGNALS] Stage 1: Failed to parse JSON from: {raw[:200]}")
        raise ValueError("Stage 1: LLM did not return valid JSON")

    logger.info(f"[SIGNALS] Stage 1 complete: regime={result.get('market_regime')}, vol={result.get('volatility_regime')}")
    return result


# ─── Stage 2: Macro ──────────────────────────────────────────────────────────

def run_stage2(
    macro_data: Dict[str, Any],
    stage1_output: Dict[str, Any],
    asset: str,
    fsm_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Stage 2: Macro fundamental analysis."""
    logger.info(f"[SIGNALS] Running Stage 2: Macro Analysis for {asset}")

    # Build forex extra block if FX
    forex_extra = ""
    if macro_data.get("asset_class") == "FX":
        forex_extra = f"""FOREX-SPECIFIC:
- Base Currency: {macro_data.get('base_country', 'N/A')}
- Quote Currency: {macro_data.get('quote_country', 'N/A')}
- Rate Differential: {macro_data.get('rate_differential', 'N/A')}%
- Base Commodity Dep: {macro_data.get('base_commodity_dep', 'N/A')}
- Quote Commodity Dep: {macro_data.get('quote_commodity_dep', 'N/A')}
POLICY DIVERGENCE:
- Base CB Stance: {macro_data.get('base_cb_stance', 'N/A')}
- Quote CB Stance: {macro_data.get('quote_cb_stance', 'N/A')}
- Rate Differential (bps): {macro_data.get('rate_differential_bps', 'N/A')}
- Rate Differential Trend: {macro_data.get('rate_differential_trend', 'N/A')}
- Policy Divergence Direction: {macro_data.get('policy_divergence_direction', 'N/A')}
- Divergence Maturity: {macro_data.get('divergence_maturity', 'N/A')}"""
    elif macro_data.get("asset_class") == "CRYPTO":
        forex_extra = f"""CRYPTO-SPECIFIC:
- BTC Price: {macro_data.get('btc_price', 'N/A')}
- Risk Environment: {macro_data.get('risk_environment', 'N/A')}
- Regulatory News: {macro_data.get('regulatory_news', 'N/A')}"""

    # Extract ROC-enriched indicator values
    gdp = macro_data.get("gdp", {})
    cpi = macro_data.get("cpi", {})
    pce = macro_data.get("pce", {})
    unemp = macro_data.get("unemployment", {})
    leading = macro_data.get("leading_indicator", {})
    sentiment = macro_data.get("consumer_sentiment", {})
    yc = macro_data.get("yield_curve", {})
    ff = macro_data.get("fed_funds", {})

    user_prompt = STAGE2_USER_TEMPLATE.format(
        asset=asset,
        market_regime=stage1_output.get("market_regime", "N/A"),
        volatility_regime=stage1_output.get("volatility_regime", "N/A"),
        trading_mode=stage1_output.get("trading_mode", "N/A"),
        # ROC-enriched fields
        gdp_latest=gdp.get("latest", "N/A"),
        gdp_prior=gdp.get("prior", "N/A"),
        gdp_roc_pct=gdp.get("roc_pct", "N/A"),
        gdp_direction=gdp.get("direction", "N/A"),
        cpi_latest=cpi.get("latest", "N/A"),
        cpi_prior=cpi.get("prior", "N/A"),
        cpi_roc_pct=cpi.get("roc_pct", "N/A"),
        cpi_direction=cpi.get("direction", "N/A"),
        pce_latest=pce.get("latest", "N/A"),
        pce_prior=pce.get("prior", "N/A"),
        pce_roc_pct=pce.get("roc_pct", "N/A"),
        pce_direction=pce.get("direction", "N/A"),
        unemployment_latest=unemp.get("latest", "N/A"),
        unemployment_direction=unemp.get("direction", "N/A"),
        leading_latest=leading.get("latest", "N/A"),
        leading_direction=leading.get("direction", "N/A"),
        sentiment_latest=sentiment.get("latest", "N/A"),
        sentiment_direction=sentiment.get("direction", "N/A"),
        yield_curve_latest=yc.get("latest", "N/A"),
        yield_curve_direction=yc.get("direction", "N/A"),
        fed_funds_latest=ff.get("latest", "N/A"),
        fed_funds_direction=ff.get("direction", "N/A"),
        economic_quadrant=macro_data.get("economic_quadrant", "TRANSITIONAL"),
        # Additional flat fields
        ism_manufacturing=macro_data.get("ism_manufacturing", "N/A"),
        consumer_confidence=macro_data.get("consumer_confidence", "N/A"),
        nfp_change=macro_data.get("nfp_change", "N/A"),
        core_pce=macro_data.get("core_pce", "N/A"),
        rate_trend=macro_data.get("rate_trend", "N/A"),
        cb_bias=macro_data.get("cb_bias", "N/A"),
        fiscal_deficit=macro_data.get("fiscal_deficit", "N/A"),
        dxy=macro_data.get("dxy", "N/A"),
        wage_growth=macro_data.get("wage_growth", "N/A"),
        retail_sales=macro_data.get("retail_sales", "N/A"),
        # COT
        cot_net_pct=macro_data.get("cot_net_pct", "N/A"),
        cot_status=macro_data.get("cot_status", "N/A"),
        forex_extra=forex_extra,
        fed_context_block=_build_fed_context_block_stage2(fsm_context),
    )

    raw = generate_sync(
        prompt=user_prompt,
        system_prompt=STAGE2_SYSTEM,
        temperature=0.2,
        max_tokens=12000,
    )

    result = _extract_json(raw)
    if not result:
        logger.error(f"[SIGNALS] Stage 2: Failed to parse JSON from: {raw[:200]}")
        raise ValueError("Stage 2: LLM did not return valid JSON")

    logger.info(f"[SIGNALS] Stage 2 complete: bias={result.get('fundamental_bias')}, strength={result.get('bias_strength')}")
    return result


# ─── Stage 3: Gatekeeping ──────────────────────────────────────────────────

def run_stage3(
    technicals: Dict[str, Any],
    stage1_out: Dict[str, Any],
    stage2_out: Dict[str, Any],
    asset: str,
) -> Dict[str, Any]:
    """Stage 3: Technical gatekeeping."""
    logger.info(f"[SIGNALS] Running Stage 3: Gatekeeping for {asset}")

    iv = technicals.get("iv_ranges") or {}

    user_prompt = STAGE3_USER_TEMPLATE.format(
        fundamental_bias=stage2_out.get("fundamental_bias", "NEUTRAL"),
        bias_strength=stage2_out.get("bias_strength", "WEAK"),
        top_drivers=", ".join(stage2_out.get("top_drivers", [])),
        asset=asset,
        current_price=technicals.get("current_price", "N/A"),
        price_vs_20ma=technicals.get("price_vs_20ma", "N/A"),
        price_vs_60ma=technicals.get("price_vs_60ma", "N/A"),
        price_vs_250ma=technicals.get("price_vs_250ma", "N/A"),
        ma_20_vs_60_cross=technicals.get("ma_20_vs_60_cross", "NONE"),
        ma_60_vs_250_cross=technicals.get("ma_60_vs_250_cross", "NONE"),
        rsi_14=technicals.get("rsi_14", "N/A"),
        trend_direction=technicals.get("trend_direction", "N/A"),
        price_pattern=technicals.get("price_pattern", "NONE"),
        volume_vs_avg=technicals.get("volume_vs_avg", "NORMAL"),
        atr_14=technicals.get("atr_14", "N/A"),
        key_support=technicals.get("key_support", "N/A"),
        key_resistance=technicals.get("key_resistance", "N/A"),
        at_support_resistance=technicals.get("at_support_resistance", "MID_RANGE"),
        # IV ranges
        daily_1sd=iv.get("daily_1sd", "N/A"),
        weekly_1sd=iv.get("weekly_1sd", "N/A"),
        monthly_1sd=iv.get("monthly_1sd", "N/A"),
        hard_stop_distance=iv.get("hard_stop_distance", "N/A"),
        soft_target_distance=iv.get("soft_target_distance", "N/A"),
    )

    raw = generate_sync(
        prompt=user_prompt,
        system_prompt=STAGE3_SYSTEM,
        temperature=0.1,
        max_tokens=4000,
    )

    result = _extract_json(raw)
    if not result:
        logger.error(f"[SIGNALS] Stage 3: Failed to parse JSON from: {raw[:200]}")
        raise ValueError("Stage 3: LLM did not return valid JSON")

    logger.info(f"[SIGNALS] Stage 3 complete: gate={result.get('gate_signal')}, entry={result.get('entry_recommendation')}")
    return result


# ─── Stage 4: Signal Aggregator ──────────────────────────────────────────────

def run_stage4(
    stage1_out: Dict[str, Any],
    stage2_out: Dict[str, Any],
    stage3_out: Dict[str, Any],
    asset: str,
) -> Dict[str, Any]:
    """Stage 4: Final signal output."""
    logger.info(f"[SIGNALS] Running Stage 4: Signal Aggregation for {asset}")

    user_prompt = STAGE4_USER_TEMPLATE.format(
        market_regime=stage1_out.get("market_regime", "N/A"),
        volatility_regime=stage1_out.get("volatility_regime", "N/A"),
        trading_mode=stage1_out.get("trading_mode", "N/A"),
        position_size_modifier=stage1_out.get("position_size_modifier", 1.0),
        fundamental_bias=stage2_out.get("fundamental_bias", "NEUTRAL"),
        bias_strength=stage2_out.get("bias_strength", "WEAK"),
        top_drivers=", ".join(stage2_out.get("top_drivers", [])),
        gate_signal=stage3_out.get("gate_signal", "RED"),
        entry_recommendation=stage3_out.get("entry_recommendation", "DO_NOT_ENTER"),
        entry_price=stage3_out.get("suggested_entry_price", "N/A"),
        stop_loss=stage3_out.get("stop_loss_price", "N/A"),
        target=stage3_out.get("target_price", "N/A"),
        target_2=stage3_out.get("target_2_price", "N/A"),
        target_3=stage3_out.get("target_3_price", "N/A"),
        risk_reward=stage3_out.get("risk_reward_ratio", "N/A"),
        asset=asset,
    )

    raw = generate_sync(
        prompt=user_prompt,
        system_prompt=STAGE4_SYSTEM,
        temperature=0.0,
        max_tokens=5000,
    )

    result = _extract_json(raw)
    if not result:
        logger.error(f"[SIGNALS] Stage 4: Failed to parse JSON from: {raw[:200]}")
        raise ValueError("Stage 4: LLM did not return valid JSON")

    # ── Validate & auto-correct inverted stop/target ──────────────────────────
    result = _fix_inverted_levels(result)

    logger.info(f"[SIGNALS] Stage 4 complete: final_signal={result.get('final_signal')}, confidence={result.get('signal_confidence')}")
    return result


def _fix_inverted_levels(result: dict) -> dict:
    """
    Detect and correct inverted stop/target levels produced by the LLM.
    For LONG: stop < entry < target
    For SHORT: target < entry < stop
    When an inversion is found, swap stop and target so the geometry is correct.
    """
    direction = (result.get("direction") or "").upper()
    signal = (result.get("final_signal") or "").upper()

    # Only validate actionable signals with a clear direction
    if signal not in ("BUY", "SELL") or direction not in ("LONG", "SHORT"):
        return result

    try:
        entry = float(result.get("entry_price") or 0)
        stop = float(result.get("stop_loss") or 0)
        target = float(result.get("target") or 0)
    except (TypeError, ValueError):
        return result

    if entry <= 0 or stop <= 0 or target <= 0:
        return result

    is_long = direction == "LONG"
    # Valid geometry: LONG → stop < entry < target | SHORT → target < entry < stop
    long_ok = stop < entry < target
    short_ok = target < entry < stop

    if is_long and not long_ok:
        # Could be inverted (stop above entry) — swap stop and target
        if stop > entry and target < entry:
            logger.warning(
                f"[SIGNALS] Stage 4: LONG signal has inverted levels "
                f"(entry={entry}, stop={stop}, target={target}) — swapping stop/target"
            )
            result["stop_loss"], result["target"] = result["target"], result["stop_loss"]
        else:
            logger.warning(
                f"[SIGNALS] Stage 4: LONG signal has ambiguous levels "
                f"(entry={entry}, stop={stop}, target={target}) — leaving as-is"
            )

    elif not is_long and not short_ok:
        # Could be inverted (stop below entry) — swap stop and target
        if stop < entry and target > entry:
            logger.warning(
                f"[SIGNALS] Stage 4: SHORT signal has inverted levels "
                f"(entry={entry}, stop={stop}, target={target}) — swapping stop/target"
            )
            result["stop_loss"], result["target"] = result["target"], result["stop_loss"]
        else:
            logger.warning(
                f"[SIGNALS] Stage 4: SHORT signal has ambiguous levels "
                f"(entry={entry}, stop={stop}, target={target}) — leaving as-is"
            )

    return result


# ─── Full Pipeline ───────────────────────────────────────────────────────────

def run_full_pipeline(asset: str) -> Dict[str, Any]:
    """
    Run all 4 stages sequentially and return the final signal.
    This is the main entry point for the signal generation system.
    """
    import asyncio as _asyncio
    from app.services.signals_data_fetcher import (
        get_regime_data,
        get_full_macro_data,
        classify_asset,
    )
    from app.services.signals_technicals import calculate_technicals, normalise_ticker
    from app.services.cot_service import _fetch_cot_for_instrument_async, INSTRUMENT_MAPPING
    from app.services.fed_sentiment_service import get_fsm_context_for_pipeline

    # Normalise ticker for Yahoo Finance
    ticker = normalise_ticker(asset)

    # ── Data Collection ──────────────────────────────────────────
    logger.info(f"[SIGNALS] Collecting data for {asset} (ticker: {ticker})")

    regime_data = get_regime_data()
    macro_data = get_full_macro_data(asset)
    technicals = calculate_technicals(ticker)

    # ── FSM Context (non-blocking: failure → neutral) ────────────
    try:
        from app.core.database import SessionLocal
        _db = SessionLocal()
        fsm_context = get_fsm_context_for_pipeline(db_session=_db)
        _db.close()
        logger.info(
            f"[SIGNALS] FSM context: regime={fsm_context.get('fed_regime')}, "
            f"composite={fsm_context.get('composite_score')}, "
            f"signal={fsm_context.get('signal_direction')} ({fsm_context.get('signal_conviction')})"
        )
    except Exception as _e:
        logger.warning(f"[SIGNALS] FSM context fetch failed (continuing without): {_e}")
        fsm_context = None

    # ── COT data (map asset to CFTC instrument) ─────────────────
    _COT_ASSET_MAP = {
        "EURUSD": "EUR", "GBPUSD": "GBP", "USDJPY": "JPY",
        "USDCAD": "CAD", "AUDUSD": "AUD", "USDCHF": "CHF",
        "NZDUSD": "NZD", "XAUUSD": "GOLD", "XAGUSD": "SILVER",
    }
    cot_key = _COT_ASSET_MAP.get(asset.upper())
    if cot_key and cot_key in INSTRUMENT_MAPPING:
        try:
            cot_data = _asyncio.run(_fetch_cot_for_instrument_async(cot_key))
            macro_data["cot_net_pct"] = cot_data.get("net_pct", "N/A")
            macro_data["cot_status"] = cot_data.get("position_status", "N/A")
            logger.info(f"[SIGNALS] COT for {cot_key}: {macro_data['cot_net_pct']}% ({macro_data['cot_status']})")
        except Exception as e:
            logger.warning(f"[SIGNALS] COT fetch failed for {cot_key}: {e}")
            macro_data["cot_net_pct"] = "N/A"
            macro_data["cot_status"] = "N/A"
    else:
        macro_data["cot_net_pct"] = "N/A"
        macro_data["cot_status"] = "N/A"

    if not technicals:
        raise ValueError(f"Could not fetch technical data for {asset}")

    asset_class = classify_asset(asset)

    # ── Stage 1 ──────────────────────────────────────────────────
    stage1 = run_stage1(regime_data, fsm_context=fsm_context)

    # ── Stage 2 ──────────────────────────────────────────────────
    stage2 = run_stage2(macro_data, stage1, asset, fsm_context=fsm_context)

    # Hard stop: if neutral/weak fundamentals, output NO_TRADE
    if stage2.get("fundamental_bias") == "NEUTRAL" and stage2.get("bias_strength") == "WEAK":
        logger.info(f"[SIGNALS] Stopping: NEUTRAL/WEAK fundamentals for {asset}")
        return _make_no_trade(asset, asset_class, stage1, stage2, "Weak fundamentals", fsm_context, ticker)

    # ── Stage 3 ──────────────────────────────────────────────────
    stage3 = run_stage3(technicals, stage1, stage2, asset)

    # Hard stop: if RED gate with no trigger, output NO_TRADE
    if stage3.get("gate_signal") == "RED" and not stage3.get("watch_list_trigger"):
        logger.info(f"[SIGNALS] Stopping: RED gate with no trigger for {asset}")
        return _make_no_trade(asset, asset_class, stage1, stage2, "RED gate", fsm_context, ticker)

    # ── Stage 4 ──────────────────────────────────────────────────
    stage4 = run_stage4(stage1, stage2, stage3, asset)

    # ── Apply FSM position size modifier (take the more conservative) ──
    if fsm_context and fsm_context.get("available"):
        fsm_pos_mod = fsm_context.get("position_size_modifier", 1.0)
        s1_pos_mod = stage1.get("position_size_modifier", 1.0)
        # Use the lower of the two modifiers
        if fsm_pos_mod < s1_pos_mod:
            logger.info(
                f"[SIGNALS] FSM position_size_modifier ({fsm_pos_mod}) "
                f"overrides Stage 1 ({s1_pos_mod})"
            )
            stage1["position_size_modifier"] = fsm_pos_mod
            stage1["fsm_position_override"] = True

    # ── Pre-FOMC event-risk override ─────────────────────────────────
    if fsm_context and fsm_context.get("pre_fomc_window") and stage4:
        days_fomc = fsm_context.get("days_to_next_fomc", 0)
        hours_fomc = round(days_fomc * 24) if days_fomc is not None else 0
        fomc_risk = f"FOMC meeting in ~{hours_fomc}h — reduced position sizing, elevated event risk"
        key_risks = stage4.get("key_risks") or []
        if isinstance(key_risks, list) and fomc_risk not in key_risks:
            key_risks.insert(0, fomc_risk)
            stage4["key_risks"] = key_risks
        # Halve recommended position size if ≤ 24h to FOMC
        if days_fomc is not None and days_fomc <= 1.0:
            cur_size = stage4.get("recommended_position_size_pct", 100)
            if isinstance(cur_size, (int, float)) and cur_size > 50:
                stage4["recommended_position_size_pct"] = cur_size * 0.5
                stage4["fomc_size_reduction"] = True
                logger.info(f"[SIGNALS] Pre-FOMC (<24h): position size halved to {stage4['recommended_position_size_pct']}%")
        stage4["pre_fomc_window"] = True

    # ── Assemble ────────────────────────────────────────────────
    return {
        "asset": asset,
        "asset_class": asset_class,
        "ticker_used": ticker,
        "fsm_context": fsm_context,
        "stage1": stage1,
        "stage2": stage2,
        "stage3": stage3,
        "stage4": stage4,
    }


def _make_no_trade(
    asset: str,
    asset_class: str,
    stage1: Dict,
    stage2: Dict,
    reason: str,
    fsm_context: Optional[Dict[str, Any]] = None,
    ticker: Optional[str] = None,
) -> Dict:
    return {
        "asset": asset,
        "asset_class": asset_class,
        "ticker_used": ticker,
        "fsm_context": fsm_context,
        "stage1": stage1,
        "stage2": stage2,
        "stage3": None,
        "stage4": {
            "final_signal": "NO_TRADE",
            "signal_confidence": 0,
            "direction": "NEUTRAL",
            "asset": asset,
            "signal_summary": f"No trade generated: {reason}. "
                f"Market regime is {stage1.get('market_regime', 'N/A')} with "
                f"{stage1.get('volatility_regime', 'N/A')} volatility. "
                f"Fundamental bias is {stage2.get('fundamental_bias', 'N/A')} / {stage2.get('bias_strength', 'N/A')}.",
            "key_risks": [],
            "invalidation_conditions": [],
        },
    }
