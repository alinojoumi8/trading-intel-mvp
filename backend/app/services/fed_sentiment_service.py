"""
Fed Sentiment Module (FSM)
Combines language NLP scoring of Fed communications with market-implied
rate expectations to produce a composite hawkish/dovish score and
divergence signal.

Phases implemented:
  Phase 1 — Market-Implied Score (FRED yields + futures)
  Phase 2 — Dictionary-based Language Score (Tier 1 scorer + Fed RSS)
  Phase 3 — Composite Engine + Divergence Detection
"""
import json
import logging
import math
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import xml.etree.ElementTree as ET

import httpx
import numpy as np
import yfinance as yf
from bs4 import BeautifulSoup
from fredapi import Fred

from app.core.config import settings

logger = logging.getLogger(__name__)


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _clamp(value: float, lo: float = -100.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, value))


def _get_fred() -> Optional[Fred]:
    if not settings.FRED_API_KEY:
        logger.warning("FRED_API_KEY not configured — market score will be limited")
        return None
    return Fred(api_key=settings.FRED_API_KEY)


def _fred_latest(series_id: str, days: int = 90) -> Optional[float]:
    fred = _get_fred()
    if not fred:
        return None
    try:
        end = datetime.utcnow()
        start = end - timedelta(days=days)
        df = fred.get_series(series_id, start, end)
        if df is not None and len(df) > 0:
            val = df.dropna().iloc[-1]
            return float(val) if val is not None else None
    except Exception as e:
        logger.warning(f"FRED {series_id}: {e}")
    return None


def _fred_history(series_id: str, days: int = 90) -> List[float]:
    fred = _get_fred()
    if not fred:
        return []
    try:
        end = datetime.utcnow()
        start = end - timedelta(days=days)
        df = fred.get_series(series_id, start, end)
        if df is not None:
            return [float(v) for v in df.dropna().tolist()]
    except Exception as e:
        logger.warning(f"FRED history {series_id}: {e}")
    return []


# ─── Hawkish / Dovish Dictionary ─────────────────────────────────────────────

HAWKISH_TERMS: Dict[str, float] = {
    # Rate / Policy Direction
    # NOTE: Routine action verbs ("raise rates", "increase the target range") are
    # intentionally low-weight (0.6-0.7) because they describe what the Fed JUST DID,
    # not what they signal next. The market has usually priced the action by FOMC day.
    # Forward-guidance language is what moves markets — see "further tightening" etc.
    "raise rates": 0.7, "rate increase": 0.7, "rate hike": 0.7,
    "further tightening": 2.0, "additional firming": 1.5,
    "insufficiently restrictive": 2.0, "more restrictive": 1.5,
    "premature to ease": 1.5, "not yet appropriate to reduce": 1.5,
    "hold rates": 0.5, "maintain current stance": 0.5,
    "data dependent": 0.3,
    "maintain the target range": 0.5,        # "decided to maintain" = holding/hawkish
    "decided to maintain": 0.5,
    "appropriate to maintain": 0.5,
    "increase the target range": 0.6,        # routine action — was 1.5
    "raise the target range": 0.6,           # routine action — was 1.5
    "raised the target range": 0.6,          # past-tense form (NEW)
    # Forward Guidance — Hawkish Pivot Patterns
    # NOTE: "further gradual increases" presence = hike-cycle continuation; its
    # *removal* signals a dovish pivot — handled by detect_phrase_transitions(),
    # not the dictionary. Adding it here would over-fire on routine hike statements.
    "further gradual increases": 1.0,
    # Inflation Concerns
    "inflation remains elevated": 1.5, "inflation persistent": 2.0,
    "inflation remains somewhat elevated": 1.2,
    "remains elevated": 0.8,                  # catches "inflation remains elevated"
    "somewhat elevated": 0.6,
    "price pressures": 1.0, "inflation expectations unanchored": 2.0,
    "upside risks to inflation": 1.5, "core inflation sticky": 1.5,
    "second-round effects": 1.0, "wage-price spiral": 2.0,
    "overheating": 1.5, "above target": 1.0,
    "broadening price pressures": 1.5,
    "inflation at the rate of 2 percent": 0.3,   # commitment language = hawkish resolve
    "returning inflation to its 2 percent": 0.5,
    "strongly committed": 0.5,
    # Labor Market Tightness
    "labor market tight": 1.0, "strong labor market": 0.8,
    "wage growth elevated": 1.0, "labor shortage": 0.8,
    "participation rate low": 0.5,
    "labor market remains strong": 0.8,
    "job gains": 0.3,
    # Economic Strength
    "robust growth": 0.8, "economic resilience": 0.5,
    "consumer spending strong": 0.5, "above trend growth": 1.0,
    "demand exceeds supply": 1.0,
    "expanding at a solid pace": 0.5,
    "solid pace": 0.3,
    # Balance Sheet
    "reduce balance sheet": 1.0, "quantitative tightening": 1.5,
    "accelerate runoff": 1.5, "balance sheet normalization": 1.0,
    # Directional keywords (single word)
    "hawkish": 1.5, "tightening": 1.0, "firming": 1.0,
    "restrictive": 0.8, "elevated inflation": 1.2,
    # Uncertainty (mildly hawkish — risk to not cut)
    "uncertainty about the economic outlook": 0.3,
    "economic uncertainty": 0.3,
    "attentive to the risks": 0.2,
}

DOVISH_TERMS: Dict[str, float] = {
    # Rate / Policy Direction
    # NOTE: Routine action verbs are intentionally low-weight (-0.6 to -0.7) for the
    # same reason as their hawkish counterparts — see HAWKISH_TERMS comment above.
    "cut rates": -0.7, "rate reduction": -0.7, "rate cut": -0.7,
    "further easing": -2.0, "more accommodative": -1.5,
    "reduce restrictiveness": -1.5, "appropriate to ease": -1.5,
    "lower rates": -0.7, "recalibrate": -1.0,
    "normalization of rates": -1.0,
    "lower the target range": -0.6,           # routine action — was -1.5
    "lowered the target range": -0.6,         # past-tense form (NEW)
    "reduce the target range": -0.6,          # routine action — was -1.5
    "decrease the target range": -0.6,        # routine action — was -1.5
    "preferred to lower": -1.0,               # dissent votes to cut
    "preferred to reduce": -1.0,
    # Forward Guidance — Dovish Pivot Patterns
    "any additional policy firming": -1.5,    # 2023 pivot signal — dropping commitment
    "sufficiently restrictive": -1.2,         # peak-rate language — signals pause/cut coming
    # Inflation Declining
    "inflation moderating": -1.0, "disinflation": -1.5,
    "inflation moving toward target": -1.0, "transitory": -1.5,
    "price pressures easing": -1.0, "inflation expectations anchored": -0.8,
    "below target inflation": -1.5, "deflationary": -2.0,
    "disinflationary": -1.5,
    "moving toward": -0.5,                    # "inflation moving toward 2%"
    "toward its 2 percent": -0.5,
    # Labor Market Weakness
    "labor market softening": -1.0, "rising unemployment": -1.5,
    "job losses": -1.5, "weakening employment": -1.0,
    "slack in labor market": -1.0, "cooling labor market": -0.8,
    "job gains have remained low": -0.8,       # weak jobs = dovish
    "unemployment rate has risen": -1.0,
    # Economic Weakness
    "economic slowdown": -1.5, "recession risk": -2.0,
    "downside risks": -1.0, "below trend growth": -1.0,
    "financial stress": -1.5, "credit tightening": -1.0,
    "demand weakness": -1.0, "consumer pullback": -0.8,
    "downside risks to the outlook": -1.0,
    "risks to both sides": -0.3,               # balanced = slight dovish lean
    # Balance Sheet
    "slow balance sheet runoff": -1.0, "pause qt": -1.5,
    "resume purchases": -2.0, "quantitative easing": -2.0,
    # Forward Guidance
    "patient": -0.5, "gradual": -0.5, "cautious": -0.3,
    "flexible": -0.3, "well positioned to adjust": -0.8,
    "carefully assess": -0.3,                  # signals pause/caution
    "prepared to adjust": -0.3,
    # Directional keywords
    "dovish": -1.5, "easing": -1.0, "accommodative": -1.0,
    "recession": -1.5, "slowdown": -1.0,
}

NEGATION_WORDS = {
    "not", "no", "never", "neither", "nor", "don't", "doesn't",
    "didn't", "won't", "wouldn't", "shouldn't", "cannot", "can't",
    "unlikely", "insufficient", "without", "lack", "absent",
}

POLICY_KEYWORDS = {
    "rate", "rates", "funds rate", "interest", "inflation", "employment",
    "unemployment", "labor", "growth", "gdp", "economic activity",
    "tightening", "easing", "accommodative", "restrictive", "stimulus",
    "tapering", "quantitative", "balance sheet", "forward guidance",
    "price stability", "maximum employment", "dual mandate", "target",
    "projection", "outlook", "forecast", "dot plot", "terminal rate",
    "neutral rate", "soft landing", "recession", "overheating",
    "transitory", "persistent", "entrenched", "disinflation",
    "disinflationary", "deflationary", "stagflation", "fomc", "federal reserve",
    "monetary policy", "policy rate", "hike", "cut", "pause",
}

# Document importance weights (from spec Section 2.2)
DOCUMENT_WEIGHTS = {
    "statement": 1.00,
    "press_conference": 0.90,
    "dot_plot": 0.85,
    "minutes": 0.75,
    "testimony": 0.80,
    "beige_book": 0.50,
    "speech_chair": 0.75,
    "speech_vice_chair": 0.60,
    "speech_governor": 0.50,
    "speech_president_voter": 0.45,
    "speech_president_nonvoter": 0.25,
    "speech": 0.40,  # default for unclassified speeches
    "projections": 0.30,  # SEP / economic projections release
    "longer_run_goals": 0.10,  # boilerplate reaffirmation
}

# Time decay half-life: 30 days (λ = ln(2)/30)
_DECAY_LAMBDA = math.log(2) / 30


def _time_decay_weight(doc_date: datetime) -> float:
    """Exponential decay weight for a document based on age."""
    days_old = max(0, (datetime.utcnow() - doc_date).days)
    return math.exp(-_DECAY_LAMBDA * days_old)


# ─── Phase 2: Tier 1 Dictionary Scorer ───────────────────────────────────────

def _has_policy_keyword(text: str) -> bool:
    lower = text.lower()
    return any(kw in lower for kw in POLICY_KEYWORDS)


def _score_sentence(sentence: str) -> float:
    """
    Score a single sentence on [-2.0, +2.0] using hawkish/dovish dictionary.
    Handles negations within 3 tokens of a scored term.
    """
    lower = sentence.lower()
    tokens = lower.split()
    score = 0.0

    # Multi-word terms first (longest match wins)
    all_terms = {**HAWKISH_TERMS, **DOVISH_TERMS}
    sorted_terms = sorted(all_terms.keys(), key=len, reverse=True)

    for term in sorted_terms:
        pos = lower.find(term)
        if pos == -1:
            continue

        # Check for negation in 3 tokens before the term
        term_token_idx = len(lower[:pos].split())
        negated = False
        for neg_word in NEGATION_WORDS:
            check_start = max(0, term_token_idx - 3)
            window_tokens = tokens[check_start:term_token_idx]
            if neg_word in window_tokens:
                negated = True
                break

        term_score = all_terms[term]
        if negated:
            term_score = -term_score

        score += term_score

    return max(-2.0, min(2.0, score))


def score_document_tier1(text: str) -> Tuple[float, List[str]]:
    """
    Score a Fed document using Tier 1 dictionary method.
    Returns (score on [-100, +100], list of key phrases detected).

    Only sentences containing policy keywords are scored.
    Aggregation: weighted mean where weight = abs(sentence_score).
    """
    if not text or not text.strip():
        return 0.0, []

    # Split into sentences (simple sentence splitter)
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())

    scored = []
    key_phrases = []

    for sentence in sentences:
        if not _has_policy_keyword(sentence):
            continue
        s = _score_sentence(sentence)
        if abs(s) > 0.1:
            scored.append(s)
            # Capture short key phrases (first 100 chars of scored sentences)
            snippet = sentence.strip()[:100]
            if snippet:
                key_phrases.append(snippet)

    if not scored:
        return 0.0, []

    weights = [abs(s) for s in scored]
    total_weight = sum(weights)
    if total_weight == 0:
        return 0.0, []

    weighted_sum = sum(s * abs(s) for s in scored)
    raw_score = weighted_sum / total_weight  # [-2.0, +2.0]
    normalized = (raw_score / 2.0) * 100

    return _clamp(normalized), key_phrases[:10]


# ─── Phase 2: Fed RSS Scraper ─────────────────────────────────────────────────

FED_RSS_FEEDS = [
    # Monetary policy press releases (FOMC statements, minutes, Beige Book)
    "https://www.federalreserve.gov/feeds/press_monetary.xml",
    # Speeches by Fed officials
    "https://www.federalreserve.gov/feeds/speeches.xml",
    # Congressional testimony
    "https://www.federalreserve.gov/feeds/testimony.xml",
]


def _classify_doc_type(title: str, url: str) -> str:
    """Classify a Fed document type from its title and URL."""
    title_lower = title.lower()
    url_lower = url.lower()

    # Check minutes BEFORE broad "federal open market committee" match
    if "minutes" in title_lower:
        if "discount rate" in title_lower:
            return "minutes"  # Board discount rate minutes (lower importance)
        return "minutes"  # FOMC minutes
    # Economic projections release — NOT the actual FOMC statement
    if "economic projection" in title_lower or "release economic" in title_lower:
        return "projections"
    # "Statement on Longer-Run Goals" is a reaffirmation, not a policy statement
    if "longer-run goals" in title_lower or "longer run goals" in title_lower:
        return "longer_run_goals"
    # Actual FOMC policy statement
    if "fomc statement" in title_lower or (
        "federal reserve issues" in title_lower and "statement" in title_lower
    ):
        return "statement"
    if "beige book" in title_lower:
        return "beige_book"
    if "testimony" in url_lower or "testimony" in title_lower:
        return "testimony"
    if "speech" in url_lower or "speech" in title_lower:
        if any(name in title_lower for name in ["powell", "chair powell", "chairman"]):
            return "speech_chair"
        if "vice chair" in title_lower:
            return "speech_vice_chair"
        return "speech"
    return "speech"


def _extract_speaker(title: str, description: str) -> Optional[str]:
    """Attempt to extract speaker name from title or description."""
    # Common patterns: "Speech by Chair Powell", "Remarks by Governor Waller"
    patterns = [
        r'(?:by|from)\s+(?:Chair(?:man)?|Governor|President|Vice Chair)\s+([A-Z][a-z]+)',
        r'([A-Z][a-z]+)\s+(?:speaks|remarks|speech|testimony)',
    ]
    for pat in patterns:
        m = re.search(pat, title + " " + description, re.IGNORECASE)
        if m:
            return m.group(1)
    return None


def _fetch_page_text(url: str, follow_minutes_link: bool = True) -> str:
    """
    Fetch full text content from a Fed web page.

    For FOMC minutes press releases, the press release page only contains a stub
    with a link to the actual minutes. If `follow_minutes_link=True`, we detect
    this and follow the link to fetch the real minutes content.
    """
    try:
        with httpx.Client(timeout=20, follow_redirects=True) as client:
            resp = client.get(url, headers={"User-Agent": "Mozilla/5.0 (research bot)"})
            if resp.status_code != 200:
                return ""
            soup = BeautifulSoup(resp.text, "html.parser")

            # Detect FOMC minutes press release stub and follow the HTML link
            if follow_minutes_link:
                article = soup.find("div", id="article") or soup.find("div", class_="col-xs-12")
                if article:
                    for link in article.find_all("a", href=True):
                        href = link["href"]
                        if "/monetarypolicy/fomcminutes" in href and href.endswith(".htm"):
                            full_url = href if href.startswith("http") else f"https://www.federalreserve.gov{href}"
                            logger.info(f"[FSM] Following minutes link: {full_url}")
                            return _fetch_page_text(full_url, follow_minutes_link=False)

            # Fed pages wrap content in #article or .col-xs-12 divs
            article = soup.find("div", id="article") or soup.find("div", class_="col-xs-12")
            if article:
                return article.get_text(separator=" ", strip=True)
            # Fallback: get body text
            body = soup.find("body")
            return body.get_text(separator=" ", strip=True) if body else ""
    except Exception as e:
        logger.warning(f"Page fetch failed for {url}: {e}")
        return ""


def _fetch_press_conference_pdf(date_str: str) -> Tuple[str, Optional[str]]:
    """
    Fetch the FOMC press conference transcript PDF for a given meeting date.

    The Fed publishes press conference transcripts as PDFs at:
        /mediacenter/files/FOMCpresconf{YYYYMMDD}.pdf

    These transcripts are where the post-statement Q&A and Powell's verbal
    remarks live — often more informative than the written statement (e.g.,
    the famous 2023-02-01 "disinflation" repeated 13 times in the Q&A).

    Args:
        date_str: Meeting date in YYYY-MM-DD format

    Returns:
        Tuple of (extracted_text, pdf_url). Empty text on failure.
    """
    try:
        from pypdf import PdfReader
    except ImportError:
        logger.warning("[FSM] pypdf not installed — cannot extract press conference text")
        return "", None

    # Convert YYYY-MM-DD → YYYYMMDD
    yyyymmdd = date_str.replace("-", "")
    pdf_url = f"https://www.federalreserve.gov/mediacenter/files/FOMCpresconf{yyyymmdd}.pdf"

    try:
        with httpx.Client(timeout=30, follow_redirects=True) as client:
            resp = client.get(pdf_url, headers={"User-Agent": "Mozilla/5.0 (research bot)"})
            if resp.status_code != 200:
                logger.info(f"[FSM] No press conference PDF for {date_str} (HTTP {resp.status_code})")
                return "", None

        import io
        reader = PdfReader(io.BytesIO(resp.content))
        text = "\n".join((page.extract_text() or "") for page in reader.pages)

        if len(text) < 500:
            logger.warning(f"[FSM] Press conference PDF for {date_str} is too short ({len(text)} chars)")
            return "", pdf_url

        logger.info(f"[FSM] Extracted {len(text)} chars from press conference {date_str}")
        return text, pdf_url
    except Exception as e:
        logger.warning(f"[FSM] Press conference fetch failed for {date_str}: {e}")
        return "", None


def scrape_fed_rss(max_per_feed: int = 50) -> List[Dict[str, Any]]:
    """
    Scrape Fed RSS feeds and return a list of document metadata dicts.
    Does NOT fetch full page text (that's done selectively later).
    """
    documents = []

    for feed_url in FED_RSS_FEEDS:
        try:
            with httpx.Client(timeout=15, follow_redirects=True) as client:
                resp = client.get(feed_url, headers={"User-Agent": "Mozilla/5.0"})
                if resp.status_code != 200:
                    logger.warning(f"RSS feed returned {resp.status_code}: {feed_url}")
                    continue

            root = ET.fromstring(resp.text)
            # Handle both RSS 2.0 (<rss><channel><item>) and Atom (<feed><entry>)
            ns = {"dc": "http://purl.org/dc/elements/1.1/"}
            channel = root.find("channel") or root
            items = channel.findall("item")[:max_per_feed]

            for item in items:
                def _text(tag: str) -> str:
                    el = item.find(tag)
                    return el.text.strip() if el is not None and el.text else ""

                title_text = _text("title") or "Untitled"
                link_url = _text("link") or ""
                pub_text = _text("pubDate") or item.findtext("{http://purl.org/dc/elements/1.1/}date", "")
                desc_text = _text("description")
                doc_date = _parse_rss_date(pub_text)

                doc_type = _classify_doc_type(title_text, link_url)
                speaker = _extract_speaker(title_text, desc_text)

                documents.append({
                    "title": title_text,
                    "source_url": link_url,
                    "document_date": doc_date or datetime.utcnow(),
                    "document_type": doc_type,
                    "speaker": speaker,
                    "description": desc_text,
                })

        except Exception as e:
            logger.warning(f"RSS scrape failed for {feed_url}: {e}")

    return documents


def _parse_rss_date(date_str: str) -> Optional[datetime]:
    """Parse RSS date string into datetime."""
    if not date_str:
        return None
    formats = [
        "%a, %d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S GMT",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%d",
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(date_str.strip(), fmt)
            # Strip timezone for naive datetime storage
            return dt.replace(tzinfo=None)
        except ValueError:
            continue
    return None


# ─── Phase 2: Language Score Aggregation ─────────────────────────────────────

def get_language_score(
    documents: List[Dict[str, Any]]
) -> Tuple[float, List[str]]:
    """
    Aggregate language scores from multiple Fed documents into a single
    language score on [-100, +100].

    Each document's score is weighted by:
      - document importance (DOCUMENT_WEIGHTS)
      - time decay (30-day half-life)

    Returns (aggregated_score, combined_key_phrases).
    """
    if not documents:
        return 0.0, []

    weighted_scores = []
    total_weight = 0.0
    all_phrases = []

    for doc in documents:
        # Prefer blended (Tier 1 + Tier 2) over Tier 1 alone
        score = doc.get("blended_score") or doc.get("tier1_score")
        if score is None:
            continue

        doc_type = doc.get("document_type", "speech")
        doc_date = doc.get("document_date")
        if isinstance(doc_date, str):
            try:
                doc_date = datetime.fromisoformat(doc_date)
            except Exception:
                doc_date = datetime.utcnow()
        if not doc_date:
            doc_date = datetime.utcnow()

        importance = DOCUMENT_WEIGHTS.get(doc_type, 0.40)
        decay = _time_decay_weight(doc_date)
        effective_weight = importance * decay

        weighted_scores.append(score * effective_weight)
        total_weight += effective_weight

        phrases = doc.get("key_phrases", [])
        if isinstance(phrases, str):
            try:
                phrases = json.loads(phrases)
            except Exception:
                phrases = []
        all_phrases.extend(phrases)

    if total_weight == 0:
        return 0.0, []

    language_score = sum(weighted_scores) / total_weight
    return _clamp(language_score), all_phrases[:15]


# ─── Phase 4: Tier 2 LLM Scorer ─────────────────────────────────────────────

TIER2_SYSTEM_PROMPT = """You are an expert Federal Reserve communications analyst.
Your job is to score Fed documents on a hawkish/dovish scale for each dimension.
Respond ONLY with a valid JSON object — no markdown, no explanation."""

TIER2_PROMPT_TEMPLATE = """# Fed Communication Sentiment Analysis

## Document
- Type: {document_type}
- Date: {document_date}
- Speaker: {speaker}
- Previous composite score: {prev_score}

## Full Text
{document_text}

## Scoring Instructions

Analyze this Federal Reserve communication and score it on the following dimensions.
For each dimension, provide a score from -10 (extremely dovish) to +10 (extremely hawkish), with 0 being neutral.

### Dimension 1: Rate Path Signal (-10 to +10)
What does this communication signal about the future direction of the federal funds rate?
- Negative = rate cuts likely, easing cycle
- Positive = rate hikes likely or extended hold, tightening bias

### Dimension 2: Inflation Assessment (-10 to +10)
How does the communication characterize inflation?
- Negative = inflation under control, transitory, declining toward target
- Positive = inflation persistent, elevated, above target, concerning

### Dimension 3: Growth/Employment Assessment (-10 to +10)
How does the communication characterize economic activity and the labor market?
- Negative = weakness, softening, rising unemployment, downside risks
- Positive = strength, tightness, overheating concerns, solid growth

### Dimension 4: Forward Guidance Tone (-10 to +10)
What is the overall lean of any forward-looking language?
- Negative = dovish pivot, patience, flexibility, recalibrating lower
- Positive = hawkish resolve, data dependence in tightening context, holding firm

### Dimension 5: Language Shift (-10 to +10)
Compared to the previous score context provided, has the tone shifted?
- Negative = more dovish vs recent baseline
- Positive = more hawkish vs recent baseline
- 0 = no meaningful shift or insufficient context

Return ONLY this JSON object (no markdown, no extra text):
{{
  "rate_path_signal": <integer from -10 to 10>,
  "inflation_assessment": <integer from -10 to 10>,
  "growth_employment": <integer from -10 to 10>,
  "forward_guidance_tone": <integer from -10 to 10>,
  "language_shift": <integer from -10 to 10>,
  "key_phrases": ["<short phrase 1>", "<short phrase 2>", "<short phrase 3>"],
  "shift_description": "<one sentence describing the tone or any notable shift>",
  "confidence": <float from 0.0 to 1.0>
}}"""

# Dimension weights for Tier 2 aggregation (from spec Section 2.3.2)
TIER2_WEIGHTS = {
    "rate_path_signal": 0.30,
    "inflation_assessment": 0.25,
    "growth_employment": 0.15,
    "forward_guidance_tone": 0.20,
    "language_shift": 0.10,
}


def _aggregate_tier2_scores(llm_output: Dict[str, Any]) -> float:
    """
    Aggregate 5-dimension LLM scores into a single [-100, +100] value.
    Raw range is [-10, +10] per dimension → normalize to [-100, +100].
    """
    weighted_sum = sum(
        float(llm_output.get(dim, 0)) * weight
        for dim, weight in TIER2_WEIGHTS.items()
    )
    # Raw range [-10, +10] → scale to [-100, +100]
    normalized = weighted_sum * 10
    return _clamp(normalized)


def score_document_tier2(
    text: str,
    document_type: str = "speech",
    document_date: Optional[datetime] = None,
    speaker: Optional[str] = None,
    prev_score: Optional[float] = None,
) -> Tuple[Optional[float], List[str], Optional[Dict[str, Any]]]:
    """
    Score a Fed document using Tier 2 LLM (MiniMax).
    Returns (score on [-100, +100], key_phrases, raw_dimensions_dict).
    Returns (None, [], None) on failure so caller can fall back to Tier 1.
    """
    if not settings.MINIMAX_API_KEY:
        logger.warning("MINIMAX_API_KEY not set — Tier 2 scoring unavailable")
        return None, [], None

    if not text or len(text.strip()) < 100:
        return None, [], None

    # Truncate very long documents to keep within token limits (~8k chars)
    truncated_text = text[:8000] if len(text) > 8000 else text

    date_str = document_date.strftime("%Y-%m-%d") if document_date else "unknown"
    prev_str = f"{prev_score:.1f}" if prev_score is not None else "no prior score"

    prompt = TIER2_PROMPT_TEMPLATE.format(
        document_type=document_type,
        document_date=date_str,
        speaker=speaker or "Federal Reserve Official",
        prev_score=prev_str,
        document_text=truncated_text,
    )

    try:
        from app.services.llm_service import generate_sync
        raw_response = generate_sync(
            prompt=prompt,
            system_prompt=TIER2_SYSTEM_PROMPT,
            temperature=0.1,   # low temperature for consistent scoring
            max_tokens=1500,   # enough room for thinking + JSON output
        )
    except Exception as e:
        logger.warning(f"Tier 2 LLM call failed: {e}")
        return None, [], None

    # Parse JSON from response — try multiple strategies
    dimensions = None
    raw = raw_response.strip()

    # Strategy 1: direct JSON parse after stripping markdown fences
    try:
        if raw.startswith("```"):
            raw = re.sub(r"^```[a-z]*\n?", "", raw)
            raw = re.sub(r"\n?```$", "", raw).strip()
        dimensions = json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Strategy 2: find outermost {...} block
    if dimensions is None:
        brace_match = re.search(r"(\{[\s\S]*\})", raw_response)
        if brace_match:
            try:
                dimensions = json.loads(brace_match.group(1))
            except Exception:
                pass

    # Strategy 3: extract key-value pairs manually if JSON is malformed
    if dimensions is None:
        logger.warning(f"Tier 2 JSON parse failed — raw: {raw_response[:300]}")
        return None, [], None

    score = _aggregate_tier2_scores(dimensions)
    key_phrases = dimensions.get("key_phrases", [])
    if not isinstance(key_phrases, list):
        key_phrases = []

    logger.info(
        f"Tier 2 scored [{document_type}] {date_str}: {score:.1f} "
        f"(conf={dimensions.get('confidence', '?')})"
    )
    return score, key_phrases, dimensions


def blend_tier_scores(tier1_score: float, tier2_score: float) -> float:
    """
    Blend Tier 1 (dictionary) and Tier 2 (LLM) scores.
    LLM is more accurate but slower — weight it more heavily when available.
    """
    return _clamp(0.30 * tier1_score + 0.70 * tier2_score)


def score_unscored_documents(db_session, max_docs: int = 5) -> int:
    """
    Find FedDocuments with no Tier 2 score and score them in batch.
    Respects max_docs to avoid hammering the LLM API.
    Returns count of documents newly scored.
    """
    from app.models.models import FedDocument

    # Priority order: statements and minutes first, then speeches
    priority_types = ["statement", "minutes", "press_conference", "testimony", "speech"]

    candidates = []
    for doc_type in priority_types:
        batch = (
            db_session.query(FedDocument)
            .filter(FedDocument.tier2_score.is_(None))
            .filter(FedDocument.document_type == doc_type)
            .filter(FedDocument.full_text.isnot(None))
            .order_by(FedDocument.document_date.desc())
            .limit(max_docs - len(candidates))
            .all()
        )
        candidates.extend(batch)
        if len(candidates) >= max_docs:
            break

    scored_count = 0
    for doc in candidates:
        tier2_score, tier2_phrases, dimensions = score_document_tier2(
            text=doc.full_text or "",
            document_type=doc.document_type,
            document_date=doc.document_date,
            speaker=doc.speaker,
            prev_score=doc.tier1_score,
        )

        if tier2_score is not None:
            doc.tier2_score = tier2_score
            doc.blended_score = blend_tier_scores(
                doc.tier1_score or 0.0,
                tier2_score,
            )
            # Merge key phrases
            existing_phrases = []
            if doc.key_phrases:
                try:
                    existing_phrases = json.loads(doc.key_phrases)
                except Exception:
                    pass
            all_phrases = list(dict.fromkeys(existing_phrases + tier2_phrases))[:15]
            doc.key_phrases = json.dumps(all_phrases)

            try:
                db_session.commit()
                scored_count += 1
            except Exception as e:
                db_session.rollback()
                logger.warning(f"Failed to save Tier 2 score for doc {doc.id}: {e}")

    return scored_count


# ─── Phase 1: Market-Implied Expectations Score ───────────────────────────────

def get_market_score() -> Dict[str, Any]:
    """
    Compute the market-implied Fed expectations score from:
      1. 2Y Treasury yield + 30-day change (FRED: DGS2)
      2. 10Y-2Y yield spread (FRED: T10Y2Y)
      3. Current Fed Funds target rate (FRED: FEDFUNDS)
      4. Fed Funds futures approximation via yfinance (ZQ contracts)

    Returns a dict with score [-100, +100] and component values.
    """
    result: Dict[str, Any] = {
        "market_score": None,
        "yield_2y": None,
        "yield_spread_10y2y": None,
        "fed_target_rate": None,
        "yield_2y_30d_change": None,
        "next_meeting_bps_priced": None,
        "is_stale": False,
    }

    # ── FRED Data ──────────────────────────────────────────────────────────────
    yield_2y = _fred_latest("DGS2", days=10)
    yield_spread = _fred_latest("T10Y2Y", days=10)
    fed_target = _fred_latest("FEDFUNDS", days=60)

    # 30-day change in 2Y yield
    yield_2y_history = _fred_history("DGS2", days=45)
    yield_2y_30d_change = None
    if len(yield_2y_history) >= 20:
        yield_2y_30d_change = round(yield_2y_history[-1] - yield_2y_history[-20], 3)

    result["yield_2y"] = yield_2y
    result["yield_spread_10y2y"] = yield_spread
    result["fed_target_rate"] = fed_target
    result["yield_2y_30d_change"] = yield_2y_30d_change

    if yield_2y is None and yield_spread is None:
        result["is_stale"] = True
        return result

    # ── Fed Funds Futures (yfinance fallback) ──────────────────────────────────
    next_meeting_bps = _estimate_bps_priced_from_yf(fed_target)
    result["next_meeting_bps_priced"] = next_meeting_bps

    # ── Compute Score Components ───────────────────────────────────────────────
    components: Dict[str, float] = {}

    # 1. Near-term expectations (weight 0.35)
    # Use next_meeting_bps if available, else estimate from 2Y vs target
    if next_meeting_bps is not None:
        components["near_term"] = _clamp(next_meeting_bps * 2.0)
    elif yield_2y is not None and fed_target is not None:
        # If 2Y yield > target, market expects hikes; if below, expects cuts
        diff_bps = (yield_2y - fed_target) * 100
        components["near_term"] = _clamp(diff_bps * 1.0)
    else:
        components["near_term"] = 0.0

    # 2. 12-month rate path (weight 0.30) — approximate from 2Y yield level
    if yield_2y is not None and fed_target is not None:
        path_bps = (yield_2y - fed_target) * 100  # total priced
        components["rate_path_12m"] = _clamp(path_bps * 0.5)
    else:
        components["rate_path_12m"] = 0.0

    # 3. 2Y yield momentum (weight 0.20)
    if yield_2y_30d_change is not None:
        # ±50bps change → ±100 score
        components["yield_momentum"] = _clamp(yield_2y_30d_change * 200)
    else:
        components["yield_momentum"] = 0.0

    # 4. Curve shape signal (weight 0.15)
    # Inverted = market expects cuts. Steep positive = expect hikes or no cuts
    if yield_spread is not None:
        components["curve_shape"] = _clamp(yield_spread * 50)
    else:
        components["curve_shape"] = 0.0

    weights = {
        "near_term": 0.35,
        "rate_path_12m": 0.30,
        "yield_momentum": 0.20,
        "curve_shape": 0.15,
    }

    market_score = sum(components[k] * weights[k] for k in weights)
    result["market_score"] = round(_clamp(market_score), 2)
    result["components"] = {k: round(v, 2) for k, v in components.items()}

    return result


def _estimate_bps_priced_from_yf(fed_target: Optional[float]) -> Optional[float]:
    """
    Try to get Fed Funds futures implied rate from yfinance (ZQ ticker).
    ZQ contracts are monthly; use nearest month available.
    Returns bps difference from current target (positive = hike, negative = cut).
    """
    if fed_target is None:
        return None

    # Try the front-month Fed Funds futures (ZQ format varies)
    now = datetime.utcnow()
    # Try current and next month contract codes
    month_codes = ["F", "G", "H", "J", "K", "M", "N", "Q", "U", "V", "X", "Z"]
    year_suffix = str(now.year)[-2:]
    ticker_candidates = [
        f"ZQ={month_codes[now.month - 1]}{year_suffix}.CBT",
        f"30DFF={month_codes[now.month - 1]}{year_suffix}.CBT",
    ]

    for ticker in ticker_candidates:
        try:
            import logging as _logging
            _yf_logger = _logging.getLogger("yfinance")
            _prev_level = _yf_logger.level
            _yf_logger.setLevel(_logging.CRITICAL)  # suppress 404 noise
            t = yf.Ticker(ticker)
            hist = t.history(period="5d")
            _yf_logger.setLevel(_prev_level)
            if hist is not None and not hist.empty:
                price = float(hist["Close"].iloc[-1])
                implied_rate = 100.0 - price  # ZQ quoted as 100 - rate
                diff_bps = (implied_rate - fed_target) * 100
                return round(diff_bps, 1)
        except Exception:
            pass

    return None


# ─── Phase 3: Composite Engine ────────────────────────────────────────────────

def _categorize_divergence(
    divergence: float,
    zscore: float,
    language_score: float,
    market_score: float,
) -> str:
    """Classify the divergence between language and market scores."""
    if zscore > 1.5 and divergence > 20:
        return "hawkish_surprise"
    if zscore < -1.5 and divergence < -20:
        return "dovish_surprise"
    if language_score > 20 and market_score > 20 and abs(divergence) < 15:
        return "hawkish_consensus"
    if language_score < -20 and market_score < -20 and abs(divergence) < 15:
        return "dovish_consensus"
    if abs(language_score) < 10 and market_score > 30:
        return "market_leads_hawk"
    if abs(language_score) < 10 and market_score < -30:
        return "market_leads_dove"
    if (language_score > 20 and market_score < -20) or (language_score < -20 and market_score > 20):
        return "confusion"
    return "neutral"


def _classify_fed_regime(composite: float, language_score: float, market_score: float) -> str:
    """Map composite score to a named Fed regime."""
    if composite >= 60:
        return "aggressive_tightening"
    if composite >= 25:
        return "moderate_tightening"
    if composite >= -25:
        return "neutral_hold"
    if composite >= -60:
        return "moderate_easing"
    return "aggressive_easing"


def _generate_trading_signal(
    language_score: float,
    market_score: float,
    divergence: float,
    div_zscore: float,
) -> Tuple[str, str, str]:
    """
    Generate a trading signal from the divergence between language and market.
    Returns (signal_text, conviction, direction).
    """
    lang_bucket = "hawkish" if language_score > 25 else "dovish" if language_score < -25 else "neutral"
    mkt_bucket = "hawkish" if market_score > 25 else "dovish" if market_score < -25 else "neutral"

    if abs(div_zscore) > 2.0:
        div_bucket = "extreme"
    elif abs(divergence) > 30:
        div_bucket = "large_positive" if divergence > 0 else "large_negative"
    else:
        div_bucket = "small"

    SIGNAL_MATRIX = {
        ("hawkish", "neutral", "large_positive"): (
            "Fed hawkish, market hasn't priced it. USD bullish opportunity.", "high", "USD_bullish"
        ),
        ("hawkish", "neutral", "extreme"): (
            "Extreme hawkish divergence — Fed well ahead of market. Strong USD bullish.", "high", "USD_bullish"
        ),
        ("hawkish", "hawkish", "small"): (
            "Fed hawkish, already priced in. Limited additional USD upside.", "low", "neutral"
        ),
        ("hawkish", "dovish", "extreme"): (
            "Maximum divergence: Fed hawkish, market pricing cuts. Reduce sizing — high uncertainty.", "low", "neutral"
        ),
        ("dovish", "neutral", "large_negative"): (
            "Fed dovish pivot, market hasn't priced it. USD bearish opportunity.", "high", "USD_bearish"
        ),
        ("dovish", "neutral", "extreme"): (
            "Extreme dovish divergence — Fed well ahead of market. Strong USD bearish.", "high", "USD_bearish"
        ),
        ("dovish", "dovish", "small"): (
            "Fed dovish, already priced in. Limited additional USD downside.", "low", "neutral"
        ),
        ("neutral", "hawkish", "large_negative"): (
            "Market pricing hikes Fed hasn't signaled. Correction risk — watch for Fed catch-up.", "medium", "USD_bearish"
        ),
        ("neutral", "dovish", "large_positive"): (
            "Market pricing cuts Fed hasn't signaled. Correction risk — watch for Fed catch-up.", "medium", "USD_bullish"
        ),
    }

    key = (lang_bucket, mkt_bucket, div_bucket)
    if key in SIGNAL_MATRIX:
        return SIGNAL_MATRIX[key]

    # Fallback by bucket
    if lang_bucket == "hawkish" and mkt_bucket == "neutral":
        return ("Fed leans hawkish vs neutral market pricing. Mild USD bullish lean.", "medium", "USD_bullish")
    if lang_bucket == "dovish" and mkt_bucket == "neutral":
        return ("Fed leans dovish vs neutral market pricing. Mild USD bearish lean.", "medium", "USD_bearish")
    if lang_bucket == "neutral" and mkt_bucket == "neutral":
        return ("Fed neutral, markets neutral. No clear Fed-driven signal.", "low", "neutral")

    return ("No clear signal from Fed sentiment module.", "low", "neutral")


def compute_composite(
    language_score: Optional[float],
    market_data: Dict[str, Any],
    divergence_history: Optional[List[float]] = None,
) -> Dict[str, Any]:
    """
    Blend language and market scores into composite output with divergence signal.
    """
    market_score = market_data.get("market_score")

    # Handle missing components gracefully
    if language_score is None and market_score is None:
        return {
            "composite_score": None,
            "language_score": None,
            "market_score": None,
            "divergence_score": None,
            "divergence_category": "neutral",
            "divergence_zscore": None,
            "fed_regime": "neutral_hold",
            "trading_signal": "Insufficient data for Fed sentiment signal.",
            "signal_conviction": "low",
            "signal_direction": "neutral",
            "is_stale": True,
        }

    # If only one component available, use it directly
    if language_score is None:
        composite = market_score
        language_score = 0.0
    elif market_score is None:
        composite = language_score
        market_score = 0.0
    else:
        # Base composite: 45% language, 55% market (market has skin in the game)
        composite = 0.45 * language_score + 0.55 * market_score

    composite = _clamp(composite)

    # Divergence: language minus market
    # Positive = Fed more hawkish than market prices
    divergence = language_score - market_score

    # Z-score vs history
    hist = divergence_history or []
    div_std = float(np.std(hist)) if len(hist) >= 5 else 20.0
    div_zscore = divergence / div_std if div_std > 0 else 0.0

    div_category = _categorize_divergence(divergence, div_zscore, language_score, market_score)
    fed_regime = _classify_fed_regime(composite, language_score, market_score)
    signal_text, conviction, direction = _generate_trading_signal(
        language_score, market_score, divergence, div_zscore
    )

    return {
        "composite_score": round(composite, 2),
        "language_score": round(language_score, 2),
        "market_score": round(market_score, 2),
        "divergence_score": round(divergence, 2),
        "divergence_category": div_category,
        "divergence_zscore": round(div_zscore, 2),
        "fed_regime": fed_regime,
        "trading_signal": signal_text,
        "signal_conviction": conviction,
        "signal_direction": direction,
        "is_stale": market_data.get("is_stale", False),
        # Pass through market detail
        "yield_2y": market_data.get("yield_2y"),
        "yield_spread_10y2y": market_data.get("yield_spread_10y2y"),
        "fed_target_rate": market_data.get("fed_target_rate"),
        "yield_2y_30d_change": market_data.get("yield_2y_30d_change"),
    }


# ─── Main Pipeline Function ───────────────────────────────────────────────────

def sync_fed_documents(db_session=None, max_docs: int = 10) -> List[Dict[str, Any]]:
    """
    Scrape new Fed documents, score them with Tier 1, and return the list.
    If db_session is provided, new documents are stored in the database.
    Deduplicates by source_url.
    """
    from app.models.models import FedDocument

    # Seed FOMC calendar (idempotent — only adds new dates)
    if db_session:
        try:
            seed_fomc_calendar(db_session)
        except Exception as e:
            logger.warning(f"[FSM] FOMC calendar seed skipped: {e}")

    raw_docs = scrape_fed_rss(max_per_feed=max_docs)
    processed = []

    for doc in raw_docs:
        url = doc.get("source_url", "")

        # Skip docs with obviously bad dates (e.g., 1899 from RSS feed bugs)
        doc_date = doc.get("document_date")
        if doc_date and isinstance(doc_date, datetime) and doc_date.year < 2020:
            logger.info(f"[FSM] Skipping doc with bad date ({doc_date}): {doc.get('title', '')[:60]}")
            continue

        # Skip if already in DB
        if db_session and url:
            existing = db_session.query(FedDocument).filter(
                FedDocument.source_url == url
            ).first()
            if existing:
                # Return existing doc data
                processed.append({
                    "id": existing.id,
                    "document_type": existing.document_type,
                    "document_date": existing.document_date,
                    "speaker": existing.speaker,
                    "title": existing.title,
                    "source_url": existing.source_url,
                    "tier1_score": existing.tier1_score,
                    "blended_score": existing.blended_score,
                    "importance_weight": existing.importance_weight,
                    "key_phrases": existing.key_phrases,
                })
                continue

        # Fetch full text for all relevant doc types
        full_text = ""
        doc_type = doc.get("document_type", "speech")
        if url and doc_type in (
            "statement", "minutes", "testimony", "beige_book",
            "projections", "longer_run_goals", "press_conference",
        ):
            full_text = _fetch_page_text(url)
        elif doc_type.startswith("speech") and url:
            full_text = _fetch_page_text(url)

        # Score with Tier 1
        text_to_score = full_text or doc.get("description", "")
        tier1_score, key_phrases = score_document_tier1(text_to_score)

        importance = DOCUMENT_WEIGHTS.get(doc_type, 0.40)

        doc_record = {
            "document_type": doc_type,
            "document_date": doc.get("document_date"),
            "speaker": doc.get("speaker"),
            "title": doc.get("title", ""),
            "source_url": url,
            "full_text": full_text[:50000] if full_text else None,
            "tier1_score": tier1_score,
            "tier2_score": None,
            "blended_score": tier1_score,
            "importance_weight": importance,
            "key_phrases": json.dumps(key_phrases),
        }

        # Store to DB
        if db_session:
            try:
                fed_doc = FedDocument(**doc_record)
                db_session.add(fed_doc)
                db_session.commit()
                db_session.refresh(fed_doc)
                doc_record["id"] = fed_doc.id
            except Exception as e:
                db_session.rollback()
                logger.warning(f"Failed to store FedDocument: {e}")

        processed.append(doc_record)

        # ── Sidecar: fetch the press conference transcript for FOMC statements ──
        # Released as a PDF at /mediacenter/files/FOMCpresconf{YYYYMMDD}.pdf.
        # Powell's verbal Q&A often carries more signal than the written statement.
        if doc_type == "statement" and doc_date and isinstance(doc_date, datetime):
            _ingest_press_conference_for_date(db_session, doc_date, processed)

    return processed


def _ingest_press_conference_for_date(
    db_session,
    statement_date: datetime,
    processed: List[Dict[str, Any]],
) -> None:
    """
    Fetch the press conference transcript PDF associated with an FOMC statement
    date. Stores as a separate FedDocument with document_type='press_conference'.
    Idempotent: skips if already in DB.
    """
    if not db_session:
        return

    from app.models.models import FedDocument

    date_str = statement_date.strftime("%Y-%m-%d")
    yyyymmdd = statement_date.strftime("%Y%m%d")
    pdf_url = f"https://www.federalreserve.gov/mediacenter/files/FOMCpresconf{yyyymmdd}.pdf"

    # Skip if already in DB
    existing = (
        db_session.query(FedDocument)
        .filter(FedDocument.source_url == pdf_url)
        .first()
    )
    if existing:
        return

    text, url_used = _fetch_press_conference_pdf(date_str)
    if not text or not url_used:
        return

    tier1_score, key_phrases = score_document_tier1(text)
    pc_record = {
        "document_type": "press_conference",
        "document_date": statement_date,
        "speaker": "Powell",  # All recent press conferences are Powell-led
        "title": f"FOMC Press Conference Transcript — {date_str}",
        "source_url": url_used,
        "full_text": text[:50000],
        "tier1_score": tier1_score,
        "tier2_score": None,
        "blended_score": tier1_score,
        "importance_weight": DOCUMENT_WEIGHTS.get("press_conference", 0.90),
        "key_phrases": json.dumps(key_phrases),
    }
    try:
        pc_doc = FedDocument(**pc_record)
        db_session.add(pc_doc)
        db_session.commit()
        db_session.refresh(pc_doc)
        pc_record["id"] = pc_doc.id
        processed.append(pc_record)
        logger.info(f"[FSM] Ingested press conference for {date_str}: T1={tier1_score:.1f}")
    except Exception as e:
        db_session.rollback()
        logger.warning(f"[FSM] Failed to store press conference for {date_str}: {e}")


def get_current_fed_sentiment(db_session=None) -> Dict[str, Any]:
    """
    Main entry point: compute the current Fed sentiment composite.

    1. Get market score from FRED
    2. Load recent documents from DB (or scrape if db_session provided)
    3. Compute language score
    4. Compute composite + divergence
    5. Optionally store to fed_sentiment_scores table

    Returns the full composite output dict.
    """
    from app.models.models import FedDocument, FedSentimentScore

    # Phase 1: Market score
    market_data = get_market_score()

    # Phase 2: Language score from recent documents
    recent_docs = []
    if db_session:
        # Load documents from last 90 days
        cutoff = datetime.utcnow() - timedelta(days=90)
        db_docs = (
            db_session.query(FedDocument)
            .filter(FedDocument.document_date >= cutoff)
            .filter(FedDocument.tier1_score.isnot(None))
            .order_by(FedDocument.document_date.desc())
            .limit(30)
            .all()
        )
        # Auto-sync if no recent documents in DB
        if not db_docs:
            logger.info("No recent Fed documents in DB — triggering auto-sync")
            sync_fed_documents(db_session=db_session, max_docs=10)
            db_docs = (
                db_session.query(FedDocument)
                .filter(FedDocument.document_date >= cutoff)
                .filter(FedDocument.tier1_score.isnot(None))
                .order_by(FedDocument.document_date.desc())
                .limit(30)
                .all()
            )

        recent_docs = [
            {
                "document_type": d.document_type,
                "document_date": d.document_date,
                "tier1_score": d.tier1_score,
                "blended_score": d.blended_score,
                "key_phrases": d.key_phrases,
            }
            for d in db_docs
        ]

    language_score, key_phrases = get_language_score(recent_docs) if recent_docs else (None, [])

    # Load divergence history for z-score
    divergence_history = []
    if db_session:
        hist_scores = (
            db_session.query(FedSentimentScore.divergence_score)
            .filter(FedSentimentScore.divergence_score.isnot(None))
            .order_by(FedSentimentScore.timestamp.desc())
            .limit(60)
            .all()
        )
        divergence_history = [float(r[0]) for r in hist_scores]

    # Phase 3: Composite
    composite = compute_composite(language_score, market_data, divergence_history)
    composite["key_phrases"] = key_phrases

    # FOMC Calendar: next meeting date + days countdown
    if db_session:
        fomc_info = get_next_fomc_date(db_session)
        composite["days_to_next_fomc"] = fomc_info.get("days_to_next_fomc")
        composite["next_fomc_date"] = fomc_info.get("next_fomc_date")
    else:
        composite["days_to_next_fomc"] = None
        composite["next_fomc_date"] = None

    # Store to DB
    if db_session:
        try:
            score_record = FedSentimentScore(
                timestamp=datetime.utcnow(),
                language_score=composite.get("language_score"),
                market_score=composite.get("market_score"),
                composite_score=composite.get("composite_score"),
                divergence_score=composite.get("divergence_score"),
                divergence_category=composite.get("divergence_category"),
                divergence_zscore=composite.get("divergence_zscore"),
                fed_regime=composite.get("fed_regime"),
                trading_signal=composite.get("trading_signal"),
                signal_conviction=composite.get("signal_conviction"),
                signal_direction=composite.get("signal_direction"),
                yield_2y=composite.get("yield_2y"),
                yield_spread_10y2y=composite.get("yield_spread_10y2y"),
                fed_target_rate=composite.get("fed_target_rate"),
                yield_2y_30d_change=composite.get("yield_2y_30d_change"),
                is_stale=composite.get("is_stale", False),
            )
            db_session.add(score_record)
            db_session.commit()
        except Exception as e:
            db_session.rollback()
            logger.warning(f"Failed to store FedSentimentScore: {e}")

    return composite


# ─── Phrase Transition Tracker ───────────────────────────────────────────────

# Known phrase transitions with their signal types (spec Section 2.5)
PHRASE_TRANSITION_PATTERNS: List[Dict[str, str]] = [
    {
        "from": "transitory",
        "to": "persistent",
        "signal": "hawkish_pivot",
        "description": "Inflation characterization hardening — historically precedes tightening cycle",
    },
    {
        "from": "patient",
        "to": "data dependent",
        "signal": "hawkish_lean",
        "description": "Removing commitment to wait — signals readiness to move sooner",
    },
    {
        "from": "further tightening",
        "to": "well positioned",
        "signal": "dovish_pivot",
        "description": "Dropping hiking bias — signals rate peak reached",
    },
    {
        "from": "ongoing increases",
        "to": "extent of future increases",
        "signal": "dovish_shift",
        "description": "Signaling a pause in hiking — language shift toward flexibility",
    },
    {
        "from": "some further policy firming",
        "to": "any additional policy firming",
        "signal": "dovish_shift",
        "description": "Reducing commitment magnitude — 'any' vs 'some' signals dovish pivot",
    },
    {
        "from": "restrictive enough",
        "to": "sufficiently restrictive",
        "signal": "dovish_pivot",
        "description": "Signaling peak rates — 'sufficiently restrictive' is classic peak language",
    },
    {
        "from": "inflation expectations anchored",
        "to": "unanchored",
        "signal": "extremely_hawkish",
        "description": "Inflation credibility at risk — extreme hawkish escalation",
    },
    {
        "from": "maintain the target range",
        "to": "reduce the target range",
        "signal": "dovish_pivot",
        "description": "Switching from hold to cut language — easing cycle beginning",
    },
    {
        "from": "reduce the target range",
        "to": "maintain the target range",
        "signal": "hawkish_shift",
        "description": "Pausing cuts — hawkish shift within easing cycle",
    },
    {
        "from": "elevated",
        "to": "remains somewhat elevated",
        "signal": "dovish_shift",
        "description": "Softening inflation language — progress toward target acknowledged",
    },
]


def detect_phrase_transitions(db_session, max_pairs: int = 3) -> List[Dict[str, Any]]:
    """
    Compare consecutive FOMC statements for key phrase transitions.
    Stores detected transitions in PhraseTransition table.
    Returns list of newly detected transitions.

    Only compares FOMC statements (document_type='statement') ordered by date.
    """
    from app.models.models import FedDocument, PhraseTransition

    # Auto-create table if needed
    from app.core.database import Base, engine
    Base.metadata.create_all(bind=engine)

    # Load last N+1 FOMC statements (need pairs to compare)
    statements = (
        db_session.query(FedDocument)
        .filter(FedDocument.document_type == "statement")
        .filter(FedDocument.full_text.isnot(None))
        .order_by(FedDocument.document_date.desc())
        .limit(max_pairs + 1)
        .all()
    )

    if len(statements) < 2:
        logger.info("[FSM] Not enough FOMC statements to detect transitions (need ≥2 with full_text)")
        return []

    # statements[0] = newest, statements[1] = prior, etc.
    # We compare each adjacent pair: (new, old)
    newly_detected = []

    for i in range(len(statements) - 1):
        doc_new = statements[i]
        doc_old = statements[i + 1]

        text_new = (doc_new.full_text or "").lower()
        text_old = (doc_old.full_text or "").lower()

        if not text_new or not text_old:
            continue

        for pattern in PHRASE_TRANSITION_PATTERNS:
            phrase_from = pattern["from"].lower()
            phrase_to = pattern["to"].lower()

            # Transition detected if:
            # - "from" phrase appears in older doc AND "to" phrase appears in newer doc
            # OR
            # - "from" phrase appears in older doc AND is absent in newer doc (phrase dropped = signal)
            from_in_old = phrase_from in text_old
            to_in_new = phrase_to in text_new
            from_in_new = phrase_from in text_new

            if not from_in_old:
                continue  # Pattern doesn't apply if "from" phrase wasn't in old doc

            if not (to_in_new or not from_in_new):
                continue  # No transition occurred

            # Check if already stored to avoid duplicates
            existing = (
                db_session.query(PhraseTransition)
                .filter(
                    PhraseTransition.doc_from_id == doc_old.id,
                    PhraseTransition.doc_to_id == doc_new.id,
                    PhraseTransition.phrase_from == pattern["from"],
                    PhraseTransition.phrase_to == pattern["to"],
                )
                .first()
            )
            if existing:
                continue

            transition = PhraseTransition(
                phrase_from=pattern["from"],
                phrase_to=pattern["to"],
                doc_from_id=doc_old.id,
                doc_to_id=doc_new.id,
                doc_from_date=doc_old.document_date,
                doc_to_date=doc_new.document_date,
                signal_type=pattern["signal"],
                description=pattern["description"],
                detected_at=datetime.utcnow(),
            )
            db_session.add(transition)
            newly_detected.append({
                "phrase_from": pattern["from"],
                "phrase_to": pattern["to"],
                "signal_type": pattern["signal"],
                "description": pattern["description"],
                "doc_from_date": doc_old.document_date.isoformat() if doc_old.document_date else None,
                "doc_to_date": doc_new.document_date.isoformat() if doc_new.document_date else None,
            })
            logger.info(
                f"[FSM] Phrase transition detected: '{pattern['from']}' → '{pattern['to']}' "
                f"({pattern['signal']}) between {doc_old.document_date} and {doc_new.document_date}"
            )

    if newly_detected:
        try:
            db_session.commit()
        except Exception as e:
            db_session.rollback()
            logger.warning(f"[FSM] Failed to store phrase transitions: {e}")

    return newly_detected


def get_phrase_transitions(db_session, limit: int = 20) -> List[Dict[str, Any]]:
    """Return stored phrase transitions from DB, most recent first."""
    from app.models.models import PhraseTransition

    from app.core.database import Base, engine
    Base.metadata.create_all(bind=engine)

    try:
        rows = (
            db_session.query(PhraseTransition)
            .order_by(PhraseTransition.doc_to_date.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "id": r.id,
                "phrase_from": r.phrase_from,
                "phrase_to": r.phrase_to,
                "signal_type": r.signal_type,
                "description": r.description,
                "doc_from_date": r.doc_from_date.isoformat() if r.doc_from_date else None,
                "doc_to_date": r.doc_to_date.isoformat() if r.doc_to_date else None,
                "detected_at": r.detected_at.isoformat() if r.detected_at else None,
            }
            for r in rows
        ]
    except Exception as e:
        logger.warning(f"[FSM] Could not load phrase transitions: {e}")
        return []


# ─── FOMC Calendar Seeder ────────────────────────────────────────────────────

# Known FOMC meeting dates. Each meeting spans 2 days; the policy statement is
# released at 2:00 PM ET on the second (last) day.
# Reference: https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm
# Stored in UTC: 2:00 PM ET = 18:00 UTC (EST) or 19:00 UTC (EDT/DST).
FOMC_MEETING_DATES = [
    # 2025
    ("2025-01-29", 19),
    ("2025-03-19", 18),
    ("2025-05-07", 18),
    ("2025-06-18", 18),
    ("2025-07-30", 18),
    ("2025-09-17", 18),
    ("2025-10-29", 18),
    ("2025-12-10", 19),
    # 2026
    ("2026-01-28", 19),
    ("2026-03-18", 18),
    ("2026-04-29", 18),
    ("2026-06-17", 18),
    ("2026-07-29", 18),
    ("2026-09-16", 18),
    ("2026-10-28", 18),
    ("2026-12-09", 19),
]


def seed_fomc_calendar(db_session) -> int:
    """
    Seed the EconEvent table with known FOMC meeting dates.
    Idempotent: skips dates that already exist.
    Returns the number of new events added.
    """
    from app.models.models import EconEvent

    added = 0
    for date_str, hour_utc in FOMC_MEETING_DATES:
        try:
            event_date = datetime.strptime(date_str, "%Y-%m-%d").replace(hour=hour_utc, minute=0)
        except Exception:
            continue

        # Check if this FOMC event already exists for this date
        existing = (
            db_session.query(EconEvent)
            .filter(
                EconEvent.event_name.ilike("%FOMC%"),
                EconEvent.event_date >= event_date.replace(hour=0, minute=0),
                EconEvent.event_date < event_date.replace(hour=23, minute=59),
            )
            .first()
        )
        if existing:
            continue

        event = EconEvent(
            event_date=event_date,
            country="US",
            currency="USD",
            event_name="FOMC Meeting / Rate Decision",
            importance="high",
            impact="high",
            source="manual_fomc_seed",
        )
        db_session.add(event)
        added += 1

    if added > 0:
        try:
            db_session.commit()
            logger.info(f"[FSM] Seeded {added} FOMC meeting events")
        except Exception as e:
            db_session.rollback()
            logger.warning(f"[FSM] Failed to seed FOMC calendar: {e}")
            return 0
    return added


def get_next_fomc_date(db_session) -> Dict[str, Any]:
    """
    Query EconEvent table for the next FOMC meeting date.
    Returns dict with days_to_next_fomc and next_fomc_date (ISO string).
    """
    from app.models.models import EconEvent
    try:
        now = datetime.utcnow()
        event = (
            db_session.query(EconEvent)
            .filter(
                EconEvent.event_name.ilike("%FOMC%"),
                EconEvent.event_date > now,
            )
            .order_by(EconEvent.event_date.asc())
            .first()
        )
        if event:
            delta = event.event_date - now
            days = delta.total_seconds() / 86400
            return {
                "days_to_next_fomc": round(days, 1),
                "next_fomc_date": event.event_date.isoformat(),
            }
    except Exception as e:
        logger.warning(f"[FSM] Could not query next FOMC date: {e}")
    return {"days_to_next_fomc": None, "next_fomc_date": None}


def backfill_historical_fed_documents(
    db_session,
    start_year: int = 2010,
    end_year: Optional[int] = None,
    max_per_year: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Walk the Fed's per-year FOMC historical archive pages and ingest all
    statements, minutes, and press conferences in date range.

    URL pattern: https://www.federalreserve.gov/monetarypolicy/fomchistorical{year}.htm

    For each year, extracts links to:
      - /newsevents/pressreleases/monetary{YYYYMMDD}*.htm  (statements)
      - /monetarypolicy/fomcminutes{YYYYMMDD}.htm          (minutes — full text page)
      - /monetarypolicy/fomcpresconf{YYYYMMDD}.htm         (press conference landing,
        triggers PDF transcript ingestion)

    Idempotent: skips URLs already in DB. Tier 1 scoring only (free).
    Use score_unscored_documents() afterward to add Tier 2 LLM scoring.
    """
    from app.models.models import FedDocument
    from datetime import date as date_cls

    end_year = end_year or datetime.utcnow().year
    current_year = datetime.utcnow().year

    stats = {
        "years_processed": [],
        "statements_added": 0,
        "minutes_added": 0,
        "press_conferences_added": 0,
        "skipped_existing": 0,
        "errors": 0,
    }

    # The Fed splits FOMC archives into two locations:
    #   - fomchistorical{year}.htm  for older years (~5+ years old, e.g. 2010-2020)
    #   - fomccalendars.htm         for the current rolling 5-year window (2021+)
    # Fetch the calendar page once and reuse for all recent years
    calendar_links: List[str] = []
    try:
        with httpx.Client(timeout=20, follow_redirects=True) as client:
            resp = client.get(
                "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm",
                headers={"User-Agent": "Mozilla/5.0 (research bot)"},
            )
            if resp.status_code == 200:
                soup_cal = BeautifulSoup(resp.text, "html.parser")
                calendar_links = [a["href"] for a in soup_cal.find_all("a", href=True)]
    except Exception as e:
        logger.warning(f"[FSM] Failed to load fomccalendars.htm: {e}")

    for year in range(start_year, end_year + 1):
        try:
            # Pick the right source for this year
            historical_url = f"https://www.federalreserve.gov/monetarypolicy/fomchistorical{year}.htm"
            try:
                with httpx.Client(timeout=20, follow_redirects=True) as client:
                    resp = client.get(historical_url, headers={"User-Agent": "Mozilla/5.0 (research bot)"})
                    if resp.status_code == 200:
                        soup = BeautifulSoup(resp.text, "html.parser")
                        all_links = [a for a in soup.find_all("a", href=True)]
                        source = "historical"
                    else:
                        # Fall back to calendar page links
                        all_links = [{"href": h} for h in calendar_links]
                        source = "calendar"
            except Exception:
                all_links = [{"href": h} for h in calendar_links]
                source = "calendar"

            # Collect unique URLs by category, filtered to this year
            stmt_urls = set()
            minutes_urls = set()
            presconf_dates = set()
            year_str = str(year)

            for a in all_links:
                href = a["href"]
                # Filter URLs by year — extract YYYYMMDD from path and match
                year_match = re.search(r"(20\d{2})\d{4}", href)
                if not year_match or year_match.group(1) != year_str:
                    continue

                if "/newsevents/pressreleases/monetary" in href and href.endswith(".htm"):
                    full = href if href.startswith("http") else f"https://www.federalreserve.gov{href}"
                    stmt_urls.add(full)
                elif "fomcminutes" in href and href.endswith(".htm"):
                    full = href if href.startswith("http") else f"https://www.federalreserve.gov{href}"
                    minutes_urls.add(full)
                elif "fomcpresconf" in href and href.endswith(".htm"):
                    m = re.search(r"fomcpresconf(\d{8})", href)
                    if m:
                        date_str = m.group(1)
                        presconf_dates.add(date_str)

            year_added = {"statements": 0, "minutes": 0, "press_conferences": 0}

            # Process statements
            for stmt_url in sorted(stmt_urls):
                if max_per_year and year_added["statements"] >= max_per_year:
                    break
                if _ingest_historical_doc(db_session, stmt_url, expected_year=year, stats=stats):
                    year_added["statements"] += 1

            # Process minutes
            for min_url in sorted(minutes_urls):
                if _ingest_historical_doc(db_session, min_url, expected_year=year, stats=stats, doc_type_hint="minutes"):
                    year_added["minutes"] += 1

            # Process press conferences (PDFs by date)
            for date_str in sorted(presconf_dates):
                try:
                    pc_dt = datetime.strptime(date_str, "%Y%m%d")
                except ValueError:
                    continue
                # Check if already in DB
                pdf_url = f"https://www.federalreserve.gov/mediacenter/files/FOMCpresconf{date_str}.pdf"
                existing = (
                    db_session.query(FedDocument)
                    .filter(FedDocument.source_url == pdf_url)
                    .first()
                )
                if existing:
                    stats["skipped_existing"] += 1
                    continue
                processed_pc = []
                _ingest_press_conference_for_date(db_session, pc_dt, processed_pc)
                if processed_pc:
                    year_added["press_conferences"] += 1
                    stats["press_conferences_added"] += 1

            stats["years_processed"].append({
                "year": year,
                "statements": year_added["statements"],
                "minutes": year_added["minutes"],
                "press_conferences": year_added["press_conferences"],
            })
            logger.info(
                f"[FSM] Year {year}: +{year_added['statements']} stmts, "
                f"+{year_added['minutes']} minutes, +{year_added['press_conferences']} press confs"
            )
        except Exception as e:
            logger.exception(f"[FSM] Year {year} backfill failed: {e}")
            stats["errors"] += 1

    return stats


def _ingest_historical_doc(
    db_session,
    url: str,
    expected_year: int,
    stats: Dict[str, int],
    doc_type_hint: Optional[str] = None,
) -> bool:
    """
    Fetch a single historical Fed document by URL, classify, score with Tier 1,
    store in DB. Returns True if newly added, False if skipped.
    """
    from app.models.models import FedDocument

    # Skip if already in DB
    existing = db_session.query(FedDocument).filter(FedDocument.source_url == url).first()
    if existing:
        stats["skipped_existing"] += 1
        return False

    # Extract date from URL
    date_match = re.search(r"(\d{8})", url)
    doc_date = None
    if date_match:
        try:
            doc_date = datetime.strptime(date_match.group(1), "%Y%m%d")
        except ValueError:
            pass

    if not doc_date or doc_date.year != expected_year:
        # Date sanity check failed; skip
        return False

    # Fetch the page
    full_text = _fetch_page_text(url)
    if not full_text or len(full_text) < 200:
        return False

    # Classify
    title = ""
    try:
        with httpx.Client(timeout=15, follow_redirects=True) as client:
            resp = client.get(url, headers={"User-Agent": "Mozilla/5.0 (research bot)"})
            soup = BeautifulSoup(resp.text, "html.parser")
            title_el = soup.find("title")
            if title_el and title_el.text:
                title = title_el.text.strip().split("|")[0].strip()
    except Exception:
        pass

    if not title:
        title = f"Fed document {doc_date.date()}"

    # Use doc_type_hint if provided (for minutes URLs that are unambiguous)
    if doc_type_hint:
        doc_type = doc_type_hint
    else:
        doc_type = _classify_doc_type(title, url)

    # Only keep policy-relevant types
    if doc_type not in ("statement", "minutes", "press_conference", "projections", "longer_run_goals"):
        return False

    # Score with Tier 1
    tier1_score, key_phrases = score_document_tier1(full_text)

    record = {
        "document_type": doc_type,
        "document_date": doc_date,
        "speaker": None,
        "title": title[:200],
        "source_url": url,
        "full_text": full_text[:50000],
        "tier1_score": tier1_score,
        "tier2_score": None,
        "blended_score": tier1_score,
        "importance_weight": DOCUMENT_WEIGHTS.get(doc_type, 0.40),
        "key_phrases": json.dumps(key_phrases),
    }
    try:
        doc = FedDocument(**record)
        db_session.add(doc)
        db_session.commit()
        if doc_type == "statement":
            stats["statements_added"] += 1
        elif doc_type == "minutes":
            stats["minutes_added"] += 1
        return True
    except Exception as e:
        db_session.rollback()
        logger.warning(f"[FSM] Failed to store {url}: {e}")
        return False


def rescore_all_documents_tier1(db_session) -> Dict[str, int]:
    """
    Re-score all FedDocument rows that have full_text using the current
    Tier 1 dictionary. Updates tier1_score, blended_score (recomputed if
    tier2_score exists), and key_phrases. Use after dictionary recalibration.

    Returns counts: {processed, updated, skipped}.
    """
    from app.models.models import FedDocument

    docs = (
        db_session.query(FedDocument)
        .filter(FedDocument.full_text.isnot(None))
        .all()
    )

    processed = 0
    updated = 0
    skipped = 0

    for doc in docs:
        processed += 1
        if not doc.full_text or len(doc.full_text) < 100:
            skipped += 1
            continue

        new_t1, new_phrases = score_document_tier1(doc.full_text)
        old_t1 = doc.tier1_score

        # Recompute blended score: 30% T1 + 70% T2 if T2 exists, else T1 only
        if doc.tier2_score is not None:
            new_blended = 0.30 * new_t1 + 0.70 * doc.tier2_score
        else:
            new_blended = new_t1

        doc.tier1_score = new_t1
        doc.blended_score = new_blended
        doc.key_phrases = json.dumps(new_phrases)
        updated += 1
        logger.info(
            f"[FSM] Rescored {doc.document_type} {doc.document_date.date() if doc.document_date else '?'}: "
            f"T1 {old_t1:.1f} → {new_t1:.1f} (blended: {new_blended:.1f})"
        )

    try:
        db_session.commit()
    except Exception as e:
        db_session.rollback()
        logger.warning(f"[FSM] Rescore commit failed: {e}")
        return {"processed": processed, "updated": 0, "skipped": skipped, "error": str(e)}

    return {"processed": processed, "updated": updated, "skipped": skipped}


def get_fsm_context_for_pipeline(db_session=None) -> Dict[str, Any]:
    """
    Compact FSM snapshot for the 4-stage signal pipeline.
    Returns a dict with the key Fed sentiment fields needed by Stage 1 + Stage 2.
    Falls back to neutral/zero values if FSM data is unavailable.
    """
    defaults: Dict[str, Any] = {
        "available": False,
        "fed_regime": "NEUTRAL",
        "composite_score": 0.0,
        "language_score": 0.0,
        "market_score": 0.0,
        "is_pivot_in_progress": False,
        "volatility_multiplier": 1.0,
        "divergence_category": "NEUTRAL",
        "signal_direction": "NEUTRAL",
        "signal_conviction": "LOW",
        "position_size_modifier": 1.0,
        "days_to_next_fomc": None,
        "next_fomc_date": None,
        "pre_fomc_window": False,
    }

    try:
        composite = get_current_fed_sentiment(db_session=db_session)

        # Derive position_size_modifier from conviction + divergence
        conviction = composite.get("signal_conviction", "LOW")
        divergence = composite.get("divergence_category", "NEUTRAL")
        if divergence in ("HAWKISH_SURPRISE", "DOVISH_SURPRISE"):
            # Strong divergence signals warrant higher confidence
            pos_modifier = 1.0 if conviction == "HIGH" else 0.75
        else:
            pos_modifier = 1.0

        days_fomc = composite.get("days_to_next_fomc")
        pre_fomc = days_fomc is not None and days_fomc <= 2.0

        return {
            "available": True,
            "fed_regime": composite.get("fed_regime", "NEUTRAL"),
            "composite_score": round(composite.get("composite_score") or 0.0, 1),
            "language_score": round(composite.get("language_score") or 0.0, 1),
            "market_score": round(composite.get("market_score") or 0.0, 1),
            "is_pivot_in_progress": composite.get("is_pivot_in_progress", False),
            "volatility_multiplier": composite.get("volatility_multiplier", 1.0),
            "divergence_category": composite.get("divergence_category", "NEUTRAL"),
            "signal_direction": composite.get("signal_direction", "NEUTRAL"),
            "signal_conviction": conviction,
            "position_size_modifier": pos_modifier,
            "days_to_next_fomc": days_fomc,
            "next_fomc_date": composite.get("next_fomc_date"),
            "pre_fomc_window": pre_fomc,
        }
    except Exception as e:
        logger.warning(f"[FSM] Could not fetch FSM context for pipeline: {e}")
        return defaults
