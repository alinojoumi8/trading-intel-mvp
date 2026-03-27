"""
AI Content Generators
Uses llm_service to generate structured trading content from market context.
Each generator returns a Pydantic-serializable dict matching the ContentItem schema.
"""
import json
import logging
import re
from typing import Any, Dict, List, Optional

from app.services.llm_service import generate, generate_sync

logger = logging.getLogger(__name__)

# System prompt used for all trading AI content
TRADE_INTEL_SYSTEM = (
    "You are TradeIntel AI, a professional trading intelligence analyst. "
    "You generate well-structured, data-driven trading content. Be precise, "
    "cite specific price levels and data points, and avoid vague language. "
    "Always explain the WHY behind your analysis."
)

# Default temperature for generation
DEFAULT_TEMPERATURE = 0.7
DEFAULT_MAX_TOKENS = 2000


def _extract_json_from_response(text: str) -> Optional[dict]:
    """
    Attempt to parse a JSON object from the LLM response text.
    Tries the whole text first, then looks for markdown code blocks.
    """
    # Try whole text
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try to find JSON inside ```json ... ``` blocks
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # Try to find any {...} block
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    return None


def _normalize_direction(raw: str) -> str:
    """Normalize direction string to 'long', 'short', or 'neutral'."""
    raw = raw.lower()
    if "long" in raw or "bull" in raw or "buy" in raw:
        return "long"
    if "short" in raw or "bear" in raw or "sell" in raw:
        return "short"
    return "neutral"


def _normalize_confidence(raw: str) -> str:
    """Normalize confidence string to 'high', 'medium', or 'low'."""
    raw = raw.lower()
    if "high" in raw or "strong" in raw:
        return "high"
    if "low" in raw or "weak" in raw:
        return "low"
    return "medium"


def _normalize_timeframe(raw: str) -> str:
    """Normalize timeframe string."""
    raw = raw.lower()
    if "h4" in raw or "4h" in raw or "hour" in raw:
        return "h4"
    if "d1" in raw or "daily" in raw or "day" in raw:
        return "d1"
    if "w1" in raw or "weekly" in raw:
        return "w1"
    if "scalp" in raw or "m5" in raw or "m15" in raw or "minute" in raw:
        return "scalp"
    return "d1"


def _extract_rr_ratio(text: str) -> Optional[float]:
    """Extract R:R ratio from text like '1:2' or '2.5:1' or 'R:R = 2.0'."""
    match = re.search(r"(\d+\.?\d*)\s*:\s*1", text)
    if match:
        return float(match.group(1))
    match = re.search(r"rr?[:=\s]+(\d+\.?\d*)", text, re.IGNORECASE)
    if match:
        return float(match.group(1))
    return None


# ---------------------------------------------------------------------------
# Generator 1: Morning Briefing
# ---------------------------------------------------------------------------

def _build_briefing_prompt(market_context: dict, instrument: Optional[str] = None) -> str:
    """Build the user prompt for morning briefing generation."""
    instruments = [instrument] if instrument else ["EURUSD", "XAUUSD", "BTC"]

    forex = market_context.get("forex", {})
    crypto = market_context.get("crypto", {})
    commodities = market_context.get("commodities", {})
    cot = market_context.get("cot_data", {})
    news = market_context.get("top_news", [])
    calendar = market_context.get("economic_calendar", [])

    # Format price data
    def fmt(data):
        if not data:
            return "No data available"
        price = data.get("price") or data.get("current_price") or "N/A"
        change = data.get("change_percent") or data.get("change") or "N/A"
        return f"Price: {price}, Change: {change}%"

    forex_lines = []
    for inst in instruments:
        if inst in ["EURUSD", "GBPUSD", "USDJPY"] and inst in forex:
            forex_lines.append(f"  {inst}: {fmt(forex[inst])}")
        elif inst in ["XAUUSD", "GOLD"] and "GOLD" in commodities:
            forex_lines.append(f"  GOLD: {fmt(commodities.get('GOLD', {}))}")
        elif inst == "BTC" and "BTC" in crypto:
            forex_lines.append(f"  BTC: {fmt(crypto['BTC'])}")

    # COT data
    cot_lines = []
    for inst in ["GOLD", "EUR", "GBP", "JPY"]:
        if inst in cot and isinstance(cot[inst], dict):
            c = cot[inst]
            net = c.get("commercial_net", 0) or c.get("noncommercial_net", 0)
            if net:
                cot_lines.append(f"  {inst}: Net={net:,.0f}")

    # News headlines
    news_lines = [f"  - {n.get('headline', n.get('title', 'No title'))}" for n in news[:5]]

    # Upcoming events
    calendar_lines = []
    for ev in calendar[:3]:
        calendar_lines.append(
            f"  - {ev.get('event', 'Unknown')}: {ev.get('impact', 'medium')} impact"
        )

    prompt = f"""You are TradeIntel AI. Generate a Morning Briefing for today's trading session.

## Market Data Summary

### Forex:
{chr(10).join(forex_lines) if forex_lines else "  No forex data available"}

### Crypto:
{chr(10).join([f"  {k}: {fmt(v)}" for k, v in crypto.items()]) if crypto else "  No crypto data available"}

### Commodities:
{chr(10).join([f"  {k}: {fmt(v)}" for k, v in commodities.items()]) if commodities else "  No commodities data available"}

### COT Net Positions:
{chr(10).join(cot_lines) if cot_lines else "  No COT data available"}

### Top News:
{chr(10).join(news_lines) if news_lines else "  No news available"}

### Economic Calendar (Upcoming):
{chr(10).join(calendar_lines) if calendar_lines else "  No upcoming events"}

## Your Task

Generate a structured Morning Briefing. For each instrument provide:
- A brief one-sentence bias (Long/Short/Neutral) with key level
- 2-3 bullet points covering overnight moves and key drivers
- Risk-on / Risk-off基调 assessment

Instruments to cover: {', '.join(instruments)}

Return your response as a valid JSON object with this exact structure:
{{
  "title": "Morning Briefing - [Date]",
  "rationale": "Full analysis text (2-4 sentences) covering all instruments and key market themes",
  "direction": "neutral",
  "confidence": "high",
  "timeframe": "D1",
  "tags": ["momentum", "macro-driven"],
  "featured": false,
  "instrument": "[primary instrument or 'multi']",
  "briefings": [
    {{
      "instrument": "EURUSD",
      "direction": "long",
      "bias": "Bullish — price holding above 1.0850 support",
      "key_level": "1.0850 support, 1.0950 resistance",
      "drivers": ["ECB hawkish", "USD weakness"]
    }}
  ]
}}

Ensure the JSON is valid and parseable. Do not include any text outside the JSON structure.
"""
    return prompt


async def generate_morning_briefing(
    market_context: dict,
    instrument: Optional[str] = None,
) -> dict:
    """
    Generate a Morning Briefing content item.

    Args:
        market_context: Unified market data dict from data_aggregator.
        instrument: Optional specific instrument. If None, covers top 3.

    Returns:
        Dict matching ContentItem schema with content_type="briefing".
    """
    logger.info(f"Generating morning briefing for instrument={instrument}")

    prompt = _build_briefing_prompt(market_context, instrument)

    response = await generate(
        prompt=prompt,
        system_prompt=TRADE_INTEL_SYSTEM,
        temperature=0.7,
        max_tokens=2000,
    )

    parsed = _extract_json_from_response(response)
    if not parsed:
        raise Exception(f"Failed to parse morning briefing JSON from LLM response: {response[:300]}")

    result = {
        "content_type": "briefing",
        "title": parsed.get("title", "Morning Briefing"),
        "rationale": parsed.get("rationale", ""),
        "direction": _normalize_direction(parsed.get("direction", "neutral")),
        "confidence": _normalize_confidence(parsed.get("confidence", "high")),
        "instrument": parsed.get("instrument", instrument or "multi"),
        "timeframe": "d1",
        "tags": ["momentum", "macro-driven"],
        "featured": False,
    }

    # Include sub-briefings if present
    if "briefings" in parsed:
        result["_sub_briefings"] = parsed["briefings"]

    logger.info(f"Morning briefing generated: {result['title']}")
    return result


# ---------------------------------------------------------------------------
# Generator 2: Trade Setup Card
# ---------------------------------------------------------------------------

def _build_setup_prompt(market_context: dict, instrument: str) -> str:
    """Build the user prompt for trade setup generation."""
    forex = market_context.get("forex", {})
    crypto = market_context.get("crypto", {})
    commodities = market_context.get("commodities", {})
    cot = market_context.get("cot_data", {})
    news = market_context.get("top_news", [])

    # Gather data for the instrument
    inst_upper = instrument.upper()

    if inst_upper in ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "NZDUSD"]:
        data = forex.get(inst_upper, {})
    elif inst_upper in ["XAUUSD", "GOLD"]:
        data = commodities.get("GOLD", {})
    elif inst_upper in ["BTC", "ETH"]:
        data = crypto.get(inst_upper, {})
    else:
        data = {}

    price_info = f"Price: {data.get('price', data.get('current_price', 'N/A'))}"
    change_info = f"Change: {data.get('change_percent', data.get('change', 'N/A'))}%"

    # COT for the instrument
    cot_info = ""
    for inst in ["GOLD", "EUR", "GBP", "JPY"]:
        if inst in cot and isinstance(cot[inst], dict):
            c = cot[inst]
            net = c.get("commercial_net", 0) or c.get("noncommercial_net", 0)
            cot_info += f"  {inst}: Net={net:,.0f}\n"

    # News for context
    news_info = ""
    for n in news[:3]:
        news_info += f"  - {n.get('headline', n.get('title', 'No title'))}\n"

    # Technical data
    tech_info = ""
    tech = market_context.get("technicals")
    if tech:
        price = tech.get("current_price", data.get("price", "N/A"))
        trend = tech.get("trend_direction", "N/A")
        rsi = tech.get("rsi_14", "N/A")
        support = tech.get("key_support", "N/A")
        resistance = tech.get("key_resistance", "N/A")
        ma20 = tech.get("ma20", "N/A")
        ma60 = tech.get("ma60", "N/A")
        price_vs_20ma = tech.get("price_vs_20ma", "N/A")
        price_vs_60ma = tech.get("price_vs_60ma", "N/A")
        atr = tech.get("atr_14", "N/A")
        tech_info = f"""### Technical Levels:
  Price: {price}
  Trend: {trend} (MA20={ma20}, MA60={ma60})
  RSI(14): {rsi}
  ATR(14): {atr}
  Key Support: {support}
  Key Resistance: {resistance}
  Price vs MA20: {price_vs_20ma}
  Price vs MA60: {price_vs_60ma}
"""

    prompt = f"""You are TradeIntel AI. Analyze the market context below and generate a high-quality Trade Setup Card.

## Market Context for {instrument}

### Price Data:
  {price_info}, {change_info}
{tech_info}
### COT Net Positions:
{cot_info or "  No COT data available"}

### Recent News:
{news_info or "  No news available"}

## Instructions

Generate ONE trade setup based on the data above. The setup MUST meet these criteria:
- Risk:Reward ratio must be at least 1.5:1 (do NOT generate weak setups)
- Include specific entry zone, stop-loss, and take-profit levels
- Direction must be clearly justified by the data

If the current market context does not offer a clean setup with R:R >= 1.5:1, respond with:
{{"skip": true, "reason": "<brief explanation>"}}

Otherwise, return a valid JSON object with this structure:
{{
  "title": "[Instrument] [Direction] Setup — [Timeframe]",
  "instrument": "{instrument}",
  "direction": "long or short",
  "entry_zone": "e.g., 1.0850-1.0860",
  "sl": "e.g., 1.0800 (below entry)",
  "tp": "e.g., 1.0980 (R:R = 2.0:1)",
  "risk_reward_ratio": 2.0,
  "timeframe": "D1 or H4",
  "confidence": "high or medium",
  "rationale": "2-3 sentences explaining WHY this setup is valid based on the data",
  "tags": ["momentum" or "breakout" or "reversal" or "range-bound"],
  "featured": false
}}

IMPORTANT: Return ONLY valid JSON. No extra text.
"""
    return prompt


async def generate_trade_setup(
    market_context: dict,
    instrument: str,
) -> Optional[dict]:
    """
    Generate a Trade Setup Card for a specific instrument.

    Args:
        market_context: Market data from data_aggregator.
        instrument: Target instrument (e.g., "EURUSD").

    Returns:
        Dict matching ContentItem schema (content_type="setup"), or None if no valid setup found.
    """
    logger.info(f"Generating trade setup for {instrument}")

    # Fetch live technicals for the instrument
    try:
        from app.services.signals_technicals import calculate_technicals, normalise_ticker
        ticker = normalise_ticker(instrument)
        tech_data = calculate_technicals(ticker, period="3mo")
        if tech_data:
            market_context = {**market_context, "technicals": tech_data}
    except Exception as e:
        logger.warning(f"Could not fetch technicals for {instrument}: {e}")

    prompt = _build_setup_prompt(market_context, instrument)

    response = await generate(
        prompt=prompt,
        system_prompt=TRADE_INTEL_SYSTEM,
        temperature=0.5,
        max_tokens=1500,
    )

    parsed = _extract_json_from_response(response)

    if not parsed:
        logger.warning(f"Could not parse trade setup JSON for {instrument}: {response[:200]}")
        return None

    # Check if we should skip
    if parsed.get("skip"):
        logger.info(f"No valid setup for {instrument}: {parsed.get('reason')}")
        return None

    rr = parsed.get("risk_reward_ratio") or _extract_rr_ratio(response)
    if rr is not None and rr < 1.5:
        logger.info(f"Skipping {instrument} setup: R:R={rr} < 1.5")
        return None

    direction = _normalize_direction(parsed.get("direction", "neutral"))
    confidence = _normalize_confidence(parsed.get("confidence", "medium"))

    # Determine tags based on content
    rationale = parsed.get("rationale", "").lower()
    tags = ["momentum"]
    if "breakout" in rationale or "resistance" in rationale:
        tags = ["breakout"]
    elif "reversal" in rationale or "divergen" in rationale:
        tags = ["reversal"]
    elif "range" in rationale or "support" in rationale:
        tags = ["range-bound"]

    result = {
        "content_type": "setup",
        "title": parsed.get("title", f"{instrument} {direction.title()} Setup"),
        "instrument": instrument.upper(),
        "direction": direction,
        "entry_zone": parsed.get("entry_zone", ""),
        "sl": parsed.get("sl", ""),
        "tp": parsed.get("tp", ""),
        "risk_reward_ratio": rr,
        "timeframe": _normalize_timeframe(parsed.get("timeframe", "d1")),
        "confidence": confidence,
        "rationale": parsed.get("rationale", ""),
        "tags": tags,
        "featured": False,
    }

    logger.info(
        f"Trade setup generated for {instrument}: {direction} @ {result['entry_zone']}, "
        f"R:R={rr}, confidence={confidence}"
    )
    return result


# ---------------------------------------------------------------------------
# Generator 3: Macro Roundup
# ---------------------------------------------------------------------------

def _build_roundup_prompt(market_context: dict) -> str:
    """Build the user prompt for macro roundup generation."""
    cot = market_context.get("cot_data", {})
    news = market_context.get("top_news", [])
    forex = market_context.get("forex", {})
    crypto = market_context.get("crypto", {})
    commodities = market_context.get("commodities", {})

    # Format COT data
    cot_lines = []
    for inst, data in cot.items():
        if isinstance(data, dict):
            net = data.get("commercial_net", 0) or data.get("noncommercial_net", 0)
            comm_long = data.get("commercial_long", 0)
            comm_short = data.get("commercial_short", 0)
            noncomm_long = data.get("noncommercial_long", 0)
            noncomm_short = data.get("noncommercial_short", 0)
            cot_lines.append(
                f"  {inst}: Commercial Net={net:,.0f} (L={comm_long:,}, S={comm_short:,}), "
                f"NonCommercial Net={data.get('noncommercial_net', 0):,.0f} (L={noncomm_long:,}, S={noncomm_short:,})"
            )

    # Format news
    news_lines = []
    for n in news[:10]:
        news_lines.append(f"  - {n.get('headline', n.get('title', 'No title'))}")

    # Price summary
    price_lines = []
    for inst, data in list(forex.items())[:5]:
        price_lines.append(f"  {inst}: {data.get('price', 'N/A')}")
    for inst, data in list(crypto.items())[:2]:
        price_lines.append(f"  {inst}: {data.get('price', 'N/A')}")
    for inst, data in list(commodities.items())[:2]:
        price_lines.append(f"  {inst}: {data.get('price', data.get('current_price', 'N/A'))}")

    prompt = f"""You are TradeIntel AI. Generate a comprehensive Weekly Macro Roundup.

## Price Summary (Week)
{chr(10).join(price_lines) if price_lines else "  No price data available"}

## COT Positioning (Latest Week)
{chr(10).join(cot_lines) if cot_lines else "  No COT data available"}

## Top News Headlines (This Week)
{chr(10).join(news_lines) if news_lines else "  No news available"}

## Your Task

Write a weekly macro roundup that includes:
1. Top 5 macro events of the week and their market impact
2. COT report analysis — are commercials positioned with or against the trend?
3. Market theme assessment — risk-on, risk-off, or mixed?
4. Week-ahead preview — key events to watch

Return a valid JSON object with this structure:
{{
  "title": "Weekly Macro Roundup — [Date Range]",
  "rationale": "Full analysis text (comprehensive, 4-6 sentences covering all themes above)",
  "direction": "neutral",
  "confidence": "high",
  "timeframe": "W1",
  "tags": ["macro-driven"],
  "featured": true,
  "instrument": "multi"
}}

IMPORTANT: Return ONLY valid JSON. No extra text.
"""
    return prompt


async def generate_macro_roundup(
    market_context: dict,
) -> dict:
    """
    Generate a Weekly Macro Roundup content item.

    Returns:
        Dict matching ContentItem schema with content_type="macro_roundup".
    """
    logger.info("Generating weekly macro roundup")

    prompt = _build_roundup_prompt(market_context)

    response = await generate(
        prompt=prompt,
        system_prompt=TRADE_INTEL_SYSTEM,
        temperature=0.5,
        max_tokens=2500,
    )

    parsed = _extract_json_from_response(response)
    if not parsed:
        raise Exception(f"Failed to parse macro roundup JSON from LLM: {response[:300]}")

    result = {
        "content_type": "macro_roundup",
        "title": parsed.get("title", "Weekly Macro Roundup"),
        "rationale": parsed.get("rationale", ""),
        "direction": "neutral",
        "confidence": "high",
        "timeframe": "w1",
        "tags": ["macro-driven"],
        "featured": True,
        "instrument": "multi",
    }

    logger.info(f"Macro roundup generated: {result['title']}")
    return result


# ---------------------------------------------------------------------------
# Generator 4: Contrarian Alert
# ---------------------------------------------------------------------------

def _build_contrarian_prompt(market_context: dict, instrument: str) -> str:
    """Build the user prompt for contrarian alert generation."""
    inst_upper = instrument.upper()
    cot = market_context.get("cot_data", {})
    news = market_context.get("top_news", [])

    # Find COT data for instrument
    cot_data = None
    for key in [inst_upper, instrument.upper()]:
        if key in cot and isinstance(cot[key], dict):
            cot_data = cot[key]
            break

    # Find related news
    related_news = []
    for n in news:
        headline = n.get("headline", n.get("title", "")).lower()
        if any(x in headline for x in [instrument.lower(), inst_upper.lower()]):
            related_news.append(n)
    if not related_news:
        related_news = news[:3]

    cot_info = "No COT data available"
    if cot_data:
        net = cot_data.get("commercial_net", 0) or cot_data.get("noncommercial_net", 0)
        comm_long = cot_data.get("commercial_long", 0)
        comm_short = cot_data.get("commercial_short", 0)
        noncomm_long = cot_data.get("noncommercial_long", 0)
        noncomm_short = cot_data.get("noncommercial_short", 0)
        total_long = comm_long + noncomm_long
        total_short = comm_short + noncomm_short
        if total_long + total_short > 0:
            net_pct = (net / (total_long + total_short)) * 100
            cot_info = (
                f"Commercial: Net={net:,.0f} (L={comm_long:,}, S={comm_short:,})\n"
                f"NonCommercial: Net={cot_data.get('noncommercial_net', 0):,.0f} (L={noncomm_long:,}, S={noncomm_short:,})\n"
                f"Net as % of total: {net_pct:.1f}%"
            )

    news_info = "\n".join([f"  - {n.get('headline', n.get('title', 'No title'))}" for n in related_news])

    prompt = f"""You are TradeIntel AI. Analyze whether current positioning is EXTREME (crowded) enough to warrant a contrarian alert for {instrument}.

## COT Positioning Data:
{cot_info}

## Relevant News (sentiment check):
{news_info}

## Your Analysis Task

Step 1: Assess if positioning is EXTREME:
- Is the net position (commercial or noncommercial) very one-sided (e.g., >70% of total positions on one side)?
- Is sentiment in the news uniformly bullish or bearish?
- Are positioning ratios at historical extremes?

Step 2: If EXTREME, generate a contrarian alert explaining:
- What the crowd is positioned for
- Why the crowded trade could be wrong
- What would invalidate the crowd's thesis

Step 3: If NOT extreme, respond with:
{{"skip": true, "reason": "Positioning is not at an extreme level"}}

## Output Format

If extreme positioning found, return:
{{
  "title": "Contrarian Alert: [Instrument] — [Crowd positioning summary]",
  "instrument": "{instrument}",
  "direction": "long or short (opposite of crowd)",
  "rationale": "2-3 sentences explaining why the crowd is likely wrong and what could go right for the contrarian view",
  "confidence": "high or medium",
  "tags": ["contrarian"],
  "featured": false,
  "crowd_position": "description of what the crowd is positioned for",
  "crowd_reason": "why this positioning is likely wrong"
}}

If NOT extreme, return:
{{"skip": true, "reason": "..."}}

IMPORTANT: Return ONLY valid JSON. No extra text.
"""
    return prompt


async def generate_contrarian_alert(
    market_context: dict,
    instrument: str,
) -> Optional[dict]:
    """
    Generate a Contrarian Alert — only when COT or sentiment shows extreme positioning.

    Args:
        market_context: Market data from data_aggregator.
        instrument: Target instrument.

    Returns:
        Dict matching ContentItem schema (content_type="contrarian_alert"), or None if not extreme.
    """
    logger.info(f"Checking contrarian alert for {instrument}")

    prompt = _build_contrarian_prompt(market_context, instrument)

    response = await generate(
        prompt=prompt,
        system_prompt=TRADE_INTEL_SYSTEM,
        temperature=0.6,
        max_tokens=1500,
    )

    parsed = _extract_json_from_response(response)

    if not parsed:
        logger.warning(f"Could not parse contrarian alert JSON for {instrument}: {response[:200]}")
        return None

    if parsed.get("skip"):
        logger.info(f"No contrarian alert for {instrument}: {parsed.get('reason')}")
        return None

    direction = _normalize_direction(parsed.get("direction", "neutral"))
    confidence = _normalize_confidence(parsed.get("confidence", "medium"))

    result = {
        "content_type": "contrarian_alert",
        "title": parsed.get("title", f"Contrarian Alert: {instrument}"),
        "instrument": instrument.upper(),
        "direction": direction,
        "rationale": parsed.get("rationale", ""),
        "confidence": confidence,
        "tags": ["contrarian"],
        "featured": False,
    }

    logger.info(f"Contrarian alert generated for {instrument}: {direction}")
    return result


# ---------------------------------------------------------------------------
# Synchronous wrappers for testing
# ---------------------------------------------------------------------------

def generate_morning_briefing_sync(
    market_context: dict,
    instrument: Optional[str] = None,
) -> dict:
    """Sync wrapper for generate_morning_briefing."""
    return generate_sync(
        prompt=_build_briefing_prompt(market_context, instrument),
        system_prompt=TRADE_INTEL_SYSTEM,
        temperature=0.7,
        max_tokens=2000,
    )


def generate_trade_setup_sync(
    market_context: dict,
    instrument: str,
) -> Optional[dict]:
    """Sync wrapper for generate_trade_setup."""
    import json
    response = generate_sync(
        prompt=_build_setup_prompt(market_context, instrument),
        system_prompt=TRADE_INTEL_SYSTEM,
        temperature=0.5,
        max_tokens=1500,
    )
    parsed = _extract_json_from_response(response)
    if not parsed or parsed.get("skip"):
        return None
    rr = parsed.get("risk_reward_ratio") or _extract_rr_ratio(response)
    if rr is not None and rr < 1.5:
        return None
    direction = _normalize_direction(parsed.get("direction", "neutral"))
    confidence = _normalize_confidence(parsed.get("confidence", "medium"))
    rationale = parsed.get("rationale", "").lower()
    tags = ["momentum"]
    if "breakout" in rationale or "resistance" in rationale:
        tags = ["breakout"]
    elif "reversal" in rationale or "divergen" in rationale:
        tags = ["reversal"]
    elif "range" in rationale or "support" in rationale:
        tags = ["range-bound"]
    return {
        "content_type": "setup",
        "title": parsed.get("title", f"{instrument} {direction.title()} Setup"),
        "instrument": instrument.upper(),
        "direction": direction,
        "entry_zone": parsed.get("entry_zone", ""),
        "sl": parsed.get("sl", ""),
        "tp": parsed.get("tp", ""),
        "risk_reward_ratio": rr,
        "timeframe": _normalize_timeframe(parsed.get("timeframe", "d1")),
        "confidence": confidence,
        "rationale": parsed.get("rationale", ""),
        "tags": tags,
        "featured": False,
    }


def generate_macro_roundup_sync(market_context: dict) -> dict:
    """Sync wrapper for generate_macro_roundup."""
    response = generate_sync(
        prompt=_build_roundup_prompt(market_context),
        system_prompt=TRADE_INTEL_SYSTEM,
        temperature=0.5,
        max_tokens=2500,
    )
    parsed = _extract_json_from_response(response)
    if not parsed:
        raise Exception(f"Failed to parse macro roundup JSON: {response[:300]}")
    return {
        "content_type": "macro_roundup",
        "title": parsed.get("title", "Weekly Macro Roundup"),
        "rationale": parsed.get("rationale", ""),
        "direction": "neutral",
        "confidence": "high",
        "timeframe": "w1",
        "tags": ["macro-driven"],
        "featured": True,
        "instrument": "multi",
    }


def generate_contrarian_alert_sync(
    market_context: dict,
    instrument: str,
) -> Optional[dict]:
    """Sync wrapper for generate_contrarian_alert."""
    response = generate_sync(
        prompt=_build_contrarian_prompt(market_context, instrument),
        system_prompt=TRADE_INTEL_SYSTEM,
        temperature=0.6,
        max_tokens=1500,
    )
    parsed = _extract_json_from_response(response)
    if not parsed or parsed.get("skip"):
        return None
    direction = _normalize_direction(parsed.get("direction", "neutral"))
    confidence = _normalize_confidence(parsed.get("confidence", "medium"))
    return {
        "content_type": "contrarian_alert",
        "title": parsed.get("title", f"Contrarian Alert: {instrument}"),
        "instrument": instrument.upper(),
        "direction": direction,
        "rationale": parsed.get("rationale", ""),
        "confidence": confidence,
        "tags": ["contrarian"],
        "featured": False,
    }
