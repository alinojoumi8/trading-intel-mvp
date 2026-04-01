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

Return ONLY this JSON (no markdown, no explanation):
{{"market_regime": "...", "volatility_regime": "...", "trading_mode": "...", "position_size_modifier": ..., "regime_reasoning": "...", "vix_signal": "..."}}

Rules:
- market_regime: BULL | BEAR | TRANSITIONING_TO_BEAR | TRANSITIONING_TO_BULL
- volatility_regime: LOW (<18 or -25%) | NORMAL | HIGH (+25%) | EXTREME (>40)
- trading_mode: PORTFOLIO_MANAGER | SHORT_TERM_TRADER | REDUCE_EXPOSURE | SIDELINES
- position_size_modifier: 0.25 | 0.5 | 0.75 | 1.0 (halved for HIGH vol, quartered for EXTREME)
- If BEAR market: trading_mode = REDUCE_EXPOSURE or SIDELINES only
- If VIX % change >25%: volatility_regime = HIGH minimum
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

Return ONLY this JSON:
{{"fundamental_bias": "...", "bias_strength": "...", "economic_quadrant": "{economic_quadrant}", "driver_scores": {{"ism_pmi": "...", "consumer_confidence": "...", "employment": "...", "monetary_policy": "...", "inflation": "...", "gdp_trend": "...", "rate_differential": "...", "commodity_exposure": "...", "fiscal_policy": "...", "trade_balance": "..."}}, "top_drivers": ["...", "..."], "fundamental_reasoning": "...", "swing_trade_aligned": true|false, "swing_trade_note": "..."}}

Rules:
- fundamental_bias: BULLISH | BEARISH | NEUTRAL
- bias_strength: STRONG | MODERATE | WEAK
- Rate of change matters more than absolute levels. ACCELERATING vs DECELERATING is the key signal.
- Use the economic quadrant to frame the overall macro environment.
- Score each driver as: BULLISH | BEARISH | NEUTRAL | N/A
- top_drivers: 2-3 strongest drivers by name (e.g. ["employment", "monetary_policy"])
- If fundamental_bias = NEUTRAL and bias_strength = WEAK → output NO_TRADE for the whole signal
- COT extremes (EXTREME_LONG or EXTREME_SHORT) are timing warnings, not directional signals"""


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
{{"gate_signal": "...", "entry_recommendation": "...", "technical_alignment": "...", "suggested_entry_price": null|..., "stop_loss_price": null|..., "target_price": null|..., "risk_reward_ratio": null|..., "gate_reasoning": "...", "watch_list_trigger": "..."}}

Rules:
- gate_signal: GREEN | AMBER | RED
- entry_recommendation: ENTER_FULL | ENTER_HALF | WATCH_LIST | DO_NOT_ENTER
- technical_alignment: ALIGNED | PARTIAL | CONFLICTING
- If fundamental_bias = BULLISH and trend = DOWNTREND → WATCH_LIST (never short)
- If BULLISH and pattern = HEAD_SHOULDERS → RED (wait)
- If BULLISH and pattern = INV_HEAD_SHOULDERS → GREEN
- If BULLISH and RANGING → AMBER, half position
- RSI > 70 in BULLISH = momentum confirmation (NOT overbought)
- RSI < 30 in BULLISH = possible entry (amber/green)
- If R:R < 2.0 → downgrade to WATCH_LIST
- Default stop_loss = entry - (ATR × 1.5), target = entry + (ATR × 3)
- If stop_loss distance > hard_stop_distance → flag OVERSIZED_STOP, use hard_stop_distance instead
- Use soft_target_distance as validation: target should not exceed soft_target_distance from entry
- watch_list_trigger: what event would turn GREEN (e.g. "Price closes above 1.0900")"""


STAGE4_SYSTEM = """You are the final signal aggregator for a professional trading system.
Your job is to combine regime, fundamental, and technical signals into one actionable output.
You must be conservative. When signals conflict, default to WATCH_LIST.
You always prioritise capital preservation over opportunity.
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

STAGE 3 — GATEKEEPING:
Gate Signal: {gate_signal}
Entry Recommendation: {entry_recommendation}
Suggested Entry: {entry_price}
Stop Loss: {stop_loss}
Target: {target}
Risk/Reward: {risk_reward}

Return ONLY this JSON:
{{"final_signal": "...", "signal_confidence": ..., "direction": "...", "asset": "{asset}", "entry_price": null|..., "stop_loss": null|..., "target": null|..., "risk_reward": null|..., "recommended_position_size_pct": ..., "trade_horizon": "...", "signal_summary": "...", "key_risks": ["...", "..."], "invalidation_conditions": ["...", "..."]}}

Rules:
- final_signal: BUY | SELL | WATCH_LIST | NO_TRADE
- direction: LONG | SHORT | NEUTRAL
- confidence: 0-100 (90-100=all aligned, 70-89=2/3 aligned, 50-69=partial, <50=no trade)
- recommended_position_size_pct: base 100%, multiplied by position_size_modifier from Stage 1
- If any stage says NO_TRADE → final_signal = NO_TRADE
- If gate_signal = RED with no watch_list_trigger → final_signal = NO_TRADE
- key_risks: 2-3 specific risks (e.g. ["NFP release in 48hrs", "Fed minutes Wednesday"])
- invalidation_conditions: what would make the trade wrong (e.g. ["Price closes below stop loss", "CB turns dovish"])"""


# ─── Stage 1: Regime ──────────────────────────────────────────────────────────

def run_stage1(regime_data: Dict[str, Any]) -> Dict[str, Any]:
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
    )

    raw = generate_sync(
        prompt=user_prompt,
        system_prompt=STAGE1_SYSTEM,
        temperature=0.0,
        max_tokens=4000,
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
- Quote Commodity Dep: {macro_data.get('quote_commodity_dep', 'N/A')}"""
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
    )

    raw = generate_sync(
        prompt=user_prompt,
        system_prompt=STAGE2_SYSTEM,
        temperature=0.2,
        max_tokens=5000,
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

    logger.info(f"[SIGNALS] Stage 4 complete: final_signal={result.get('final_signal')}, confidence={result.get('signal_confidence')}")
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

    # Normalise ticker for Yahoo Finance
    ticker = normalise_ticker(asset)

    # ── Data Collection ──────────────────────────────────────────
    logger.info(f"[SIGNALS] Collecting data for {asset} (ticker: {ticker})")

    regime_data = get_regime_data()
    macro_data = get_full_macro_data(asset)
    technicals = calculate_technicals(ticker)

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
    stage1 = run_stage1(regime_data)

    # ── Stage 2 ──────────────────────────────────────────────────
    stage2 = run_stage2(macro_data, stage1, asset)

    # Hard stop: if neutral/weak fundamentals, output NO_TRADE
    if stage2.get("fundamental_bias") == "NEUTRAL" and stage2.get("bias_strength") == "WEAK":
        logger.info(f"[SIGNALS] Stopping: NEUTRAL/WEAK fundamentals for {asset}")
        return _make_no_trade(asset, asset_class, stage1, stage2, "Weak fundamentals")

    # ── Stage 3 ──────────────────────────────────────────────────
    stage3 = run_stage3(technicals, stage1, stage2, asset)

    # Hard stop: if RED gate with no trigger, output NO_TRADE
    if stage3.get("gate_signal") == "RED" and not stage3.get("watch_list_trigger"):
        logger.info(f"[SIGNALS] Stopping: RED gate with no trigger for {asset}")
        return _make_no_trade(asset, asset_class, stage1, stage2, "RED gate")

    # ── Stage 4 ──────────────────────────────────────────────────
    stage4 = run_stage4(stage1, stage2, stage3, asset)

    # ── Assemble ────────────────────────────────────────────────
    return {
        "asset": asset,
        "asset_class": asset_class,
        "ticker_used": ticker,
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
) -> Dict:
    return {
        "asset": asset,
        "asset_class": asset_class,
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
