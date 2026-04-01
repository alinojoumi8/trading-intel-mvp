"""
News Analysis Router
AI-powered news analysis and Q&A using MiniMax LLM with market context.
"""
import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.llm_service import generate

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/news", tags=["news-analysis"])


# ─── Request / Response Models ───────────────────────────────────────────────

class AnalyzeRequest(BaseModel):
    title: str
    description: str
    source: str = ""
    sentiment_score: Optional[float] = None
    sentiment_label: Optional[str] = None


class InstrumentImpact(BaseModel):
    instrument: str
    direction: str  # "Bullish" | "Bearish" | "Neutral"


class AnalyzeResponse(BaseModel):
    summary: str
    instruments: List[InstrumentImpact]
    regime_note: str


class AskRequest(BaseModel):
    title: str
    description: str
    question: str
    analysis_summary: str = ""
    conversation: List[dict] = []  # [{"role": "user"|"ai", "text": "..."}]


class AskResponse(BaseModel):
    answer: str


# ─── Helpers ─────────────────────────────────────────────────────────────────

async def _get_market_context_summary() -> str:
    """Build a short market context string from current data."""
    try:
        from app.services.signals_data_fetcher import get_regime_data, get_macro_data

        regime = get_regime_data()
        macro = get_macro_data()

        gdp = macro.get("gdp", {})
        cpi = macro.get("cpi", {})
        quadrant = macro.get("economic_quadrant", "UNKNOWN")

        return (
            f"Market regime: SPX at {regime.get('spx_current', 'N/A')}, "
            f"VIX at {regime.get('vix_current', 'N/A')}. "
            f"Economic quadrant: {quadrant}. "
            f"GDP direction: {gdp.get('direction', 'N/A')}, "
            f"CPI direction: {cpi.get('direction', 'N/A')}. "
            f"Fed funds rate: {macro.get('fed_funds_rate', 'N/A')}. "
            f"Rate trend: {macro.get('rate_trend', 'N/A')}."
        )
    except Exception as e:
        logger.warning(f"Failed to get market context: {e}")
        return "Market context unavailable."


ANALYZE_SYSTEM = """You are a professional macro trading analyst. You analyze news articles and explain their trading impact.
You MUST respond with EXACTLY this format — no markdown, no code blocks, just plain text sections:

SUMMARY: <2-3 sentence trading impact analysis>
INSTRUMENTS: <comma-separated list in format TICKER:DIRECTION, e.g. EUR/USD:Bearish, GBP/USD:Neutral, SPY:Bullish>
REGIME: <one sentence connecting this to the current market regime>

Rules:
- Direction must be exactly: Bullish, Bearish, or Neutral
- Only include instruments that are meaningfully affected
- Keep summary focused on actionable trading implications
- Reference the market context provided"""

ASK_SYSTEM = """You are a professional macro trading analyst helping a trader understand news and its market implications.
Answer questions concisely (2-4 sentences max). Be specific about instruments, directions, and timeframes.
Use the article context and market data provided. If you don't know, say so — don't speculate."""


# ─── Endpoints ───────────────────────────────────────────────────────────────

@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_news(req: AnalyzeRequest):
    """Generate AI trading analysis for a news article."""
    market_ctx = await _get_market_context_summary()

    sentiment_info = ""
    if req.sentiment_label:
        sentiment_info = f"\nSentiment: {req.sentiment_label} ({req.sentiment_score})"

    prompt = f"""Analyze this news article for trading implications:

HEADLINE: {req.title}
SOURCE: {req.source}{sentiment_info}

ARTICLE:
{req.description[:1500]}

CURRENT MARKET CONTEXT:
{market_ctx}

Respond in the exact format specified."""

    try:
        raw = await generate(
            prompt=prompt,
            system_prompt=ANALYZE_SYSTEM,
            temperature=0.2,
            max_tokens=500,
        )

        return _parse_analysis(raw)
    except Exception as e:
        logger.error(f"News analysis failed: {e}")
        raise HTTPException(status_code=500, detail="Analysis generation failed")


@router.post("/ask", response_model=AskResponse)
async def ask_about_news(req: AskRequest):
    """Ask a follow-up question about a news article."""
    market_ctx = await _get_market_context_summary()

    # Build conversation history
    history = ""
    if req.analysis_summary:
        history += f"\nPREVIOUS AI ANALYSIS: {req.analysis_summary}\n"
    for msg in req.conversation[-6:]:  # Keep last 6 messages for context
        role = "Trader" if msg.get("role") == "user" else "Analyst"
        history += f"\n{role}: {msg.get('text', '')}"

    prompt = f"""NEWS ARTICLE: {req.title}
{req.description[:1000]}

MARKET CONTEXT:
{market_ctx}
{history}

Trader: {req.question}

Respond as the analyst. Be concise (2-4 sentences)."""

    try:
        raw = await generate(
            prompt=prompt,
            system_prompt=ASK_SYSTEM,
            temperature=0.3,
            max_tokens=300,
        )
        # Clean up the response
        answer = raw.strip()
        if answer.startswith("Analyst:"):
            answer = answer[8:].strip()
        return AskResponse(answer=answer)
    except Exception as e:
        logger.error(f"News Q&A failed: {e}")
        raise HTTPException(status_code=500, detail="Q&A generation failed")


# ─── Response Parser ─────────────────────────────────────────────────────────

def _parse_analysis(raw: str) -> AnalyzeResponse:
    """Parse the structured LLM response into AnalyzeResponse."""
    summary = ""
    instruments = []
    regime = ""

    for line in raw.strip().split("\n"):
        line = line.strip()
        if line.upper().startswith("SUMMARY:"):
            summary = line[8:].strip()
        elif line.upper().startswith("INSTRUMENTS:"):
            parts = line[12:].strip().split(",")
            for part in parts:
                part = part.strip()
                if ":" in part:
                    ticker, direction = part.rsplit(":", 1)
                    direction = direction.strip().capitalize()
                    if direction not in ("Bullish", "Bearish", "Neutral"):
                        direction = "Neutral"
                    instruments.append(InstrumentImpact(
                        instrument=ticker.strip(),
                        direction=direction,
                    ))
        elif line.upper().startswith("REGIME:"):
            regime = line[7:].strip()

    if not summary:
        summary = raw.strip()[:200]
    if not regime:
        regime = "Unable to determine regime alignment."

    return AnalyzeResponse(
        summary=summary,
        instruments=instruments,
        regime_note=regime,
    )
