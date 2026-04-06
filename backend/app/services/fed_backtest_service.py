"""
Fed Sentiment Backtest Service.

Validates the FSM dictionary scorer (Tier 1) and optional LLM scorer (Tier 2)
against 10 known historical FOMC events from spec Section 8.2. For each event,
we fetch the actual FOMC statement, score it, fetch DXY's 24h reaction, and
compare predicted direction vs actual market move.

Outputs accuracy metrics and a per-event breakdown.
"""
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import httpx
import yfinance as yf
from bs4 import BeautifulSoup

from app.services.fed_sentiment_service import (
    score_document_tier1,
    score_document_tier2,
    _fetch_press_conference_pdf,
)

logger = logging.getLogger(__name__)
# Suppress yfinance noise
logging.getLogger("yfinance").setLevel(logging.CRITICAL)


# ─── Historical Test Cases (spec Section 8.2) ────────────────────────────────

HISTORICAL_FOMC_EVENTS: List[Dict[str, Any]] = [
    {
        "date": "2018-01-31",
        "url": "https://www.federalreserve.gov/newsevents/pressreleases/monetary20180131a.htm",
        "event": "FOMC upgrades inflation language to 'symmetric'",
        "expected_signal": "hawkish_shift",
        "expected_direction": "USD_bullish",
        "expected_dxy_move": "rally",
        "narrative": "Symmetric inflation framing signals higher tolerance — yields rose, DXY rallied",
    },
    {
        "date": "2018-12-19",
        "url": "https://www.federalreserve.gov/newsevents/pressreleases/monetary20181219a.htm",
        "event": "Powell 'auto-pilot' QT remark at presser",
        "expected_signal": "hawkish_surprise",
        "expected_direction": "USD_bullish",
        "expected_dxy_move": "spike",
        "narrative": "QT auto-pilot rattled markets — risk-off, USD surged",
    },
    {
        "date": "2019-01-30",
        "url": "https://www.federalreserve.gov/newsevents/pressreleases/monetary20190130a.htm",
        "event": "FOMC removes 'further gradual increases' — the Pivot",
        "expected_signal": "dovish_pivot",
        "expected_direction": "USD_bearish",
        "expected_dxy_move": "drop",
        "narrative": "Major dovish pivot — DXY dropped, yields crashed",
    },
    {
        "date": "2019-07-31",
        "url": "https://www.federalreserve.gov/newsevents/pressreleases/monetary20190731a.htm",
        "event": "First cut in 10 years, 'mid-cycle adjustment'",
        "expected_signal": "hawkish_cut",
        "expected_direction": "USD_bullish",
        "expected_dxy_move": "rally",
        "narrative": "Less dovish than expected ('mid-cycle' framing) — DXY rallied on the surprise",
    },
    {
        "date": "2020-03-15",
        "url": "https://www.federalreserve.gov/newsevents/pressreleases/monetary20200315a.htm",
        "event": "Emergency Sunday cut to 0% + QE restart",
        "expected_signal": "extreme_dovish",
        "expected_direction": "USD_bearish",
        "expected_dxy_move": "drop_then_rally",
        "narrative": "Maximum dovish — DXY dropped then rallied (flight to safety)",
    },
    {
        "date": "2021-11-03",
        "url": "https://www.federalreserve.gov/newsevents/pressreleases/monetary20211103a.htm",
        "event": "Drops 'transitory' from inflation language",
        "expected_signal": "hawkish_shift",
        "expected_direction": "USD_bullish",
        "expected_dxy_move": "rally",
        "narrative": "Dropping 'transitory' = hawkish pivot signal — yields up, DXY up",
    },
    {
        "date": "2022-03-16",
        "url": "https://www.federalreserve.gov/newsevents/pressreleases/monetary20220316a.htm",
        "event": "First hike of cycle, 25bps",
        "expected_signal": "hawkish_priced_in",
        "expected_direction": "neutral",
        "expected_dxy_move": "modest",
        "narrative": "Hawkish but already priced in — modest DXY reaction",
    },
    {
        "date": "2022-06-15",
        "url": "https://www.federalreserve.gov/newsevents/pressreleases/monetary20220615a.htm",
        "event": "Surprise 75bps hike",
        "expected_signal": "hawkish_surprise",
        "expected_direction": "USD_bullish",
        "expected_dxy_move": "spike",
        "narrative": "75bps shocked the market (was pricing 50) — DXY spiked",
    },
    {
        "date": "2023-01-31",
        # 2023 FOMC was on Feb 1, statement released that day
        "url": "https://www.federalreserve.gov/newsevents/pressreleases/monetary20230201a.htm",
        "event": "'Disinflation' repeated 13 times in presser (Feb 1)",
        "expected_signal": "dovish_shift",
        "expected_direction": "USD_bearish",
        "expected_dxy_move": "drop",
        "narrative": "Powell's repeated 'disinflation' was a major dovish signal — DXY dropped",
        "actual_date": "2023-02-01",  # Statement actually released Feb 1
    },
    {
        "date": "2024-09-18",
        "url": "https://www.federalreserve.gov/newsevents/pressreleases/monetary20240918a.htm",
        "event": "First cut of cycle, 50bps",
        "expected_signal": "dovish_priced_in",
        "expected_direction": "neutral",
        "expected_dxy_move": "modest",
        "narrative": "50bps cut was partly priced in (debate between 25 and 50) — modest DXY move",
    },
]


# ─── Fetch helpers ───────────────────────────────────────────────────────────

def _fetch_statement_text(url: str) -> str:
    """Fetch the text content of a historical FOMC statement page."""
    try:
        with httpx.Client(timeout=20, follow_redirects=True) as client:
            resp = client.get(url, headers={"User-Agent": "Mozilla/5.0 (research bot)"})
            if resp.status_code != 200:
                logger.warning(f"[BACKTEST] Statement fetch {url}: HTTP {resp.status_code}")
                return ""
        soup = BeautifulSoup(resp.text, "html.parser")
        article = soup.find("div", id="article") or soup.find("div", class_="col-xs-12")
        if article:
            return article.get_text(separator=" ", strip=True)
        body = soup.find("body")
        return body.get_text(separator=" ", strip=True) if body else ""
    except Exception as e:
        logger.warning(f"[BACKTEST] Statement fetch failed for {url}: {e}")
        return ""


def _fetch_dxy_reaction(event_date: str) -> Dict[str, Any]:
    """
    Fetch DXY price action around an FOMC event.

    Primary path: Use Dukascopy 1-minute intraday data to compute multiple
    reaction windows from the exact 2:00 PM ET FOMC release time.

    Fallback: yfinance daily close-to-close (noisy, used only if intraday
    data is unavailable for this date).
    """
    # Try intraday first (best ground truth)
    try:
        from app.services.dxy_intraday_loader import compute_fomc_reaction_windows
        intraday = compute_fomc_reaction_windows(event_date)
        if intraday.get("available"):
            windows = intraday["windows"]

            # Extract the headline metrics for backwards compatibility
            pct_30m = windows.get("30m", {}).get("pct_move")  # Statement-only reaction
            pct_90m = windows.get("90m", {}).get("pct_move")  # Statement + press conf
            pct_120m = windows.get("120m", {}).get("pct_move")  # Full reaction window

            # Use 90m as the composite measure (captures press conference too)
            composite = pct_90m if pct_90m is not None else pct_30m

            return {
                "available": True,
                "source": "dukascopy_1m",
                "event_date_actual": event_date,
                "release_time_utc": intraday["release_time_utc"],
                "baseline_close": intraday["baseline_close"],
                "intraday_pct": round(pct_30m, 3) if pct_30m is not None else None,
                "composite_24h_pct": round(composite, 3) if composite is not None else None,
                # Full window detail for analysis
                "pct_1m": windows.get("1m", {}).get("pct_move"),
                "pct_10m": windows.get("10m", {}).get("pct_move"),
                "pct_30m": pct_30m,
                "pct_90m": pct_90m,
                "pct_120m": pct_120m,
                "direction_30m": intraday.get("direction_30m"),
            }
    except Exception as e:
        logger.warning(f"[BACKTEST] Intraday DXY fetch failed for {event_date}: {e}")

    # Fallback to yfinance daily
    try:
        ed = datetime.strptime(event_date, "%Y-%m-%d")
        start = ed - timedelta(days=2)
        end = ed + timedelta(days=7)
        ticker = yf.Ticker("DX-Y.NYB")
        hist = ticker.history(start=start.strftime("%Y-%m-%d"), end=end.strftime("%Y-%m-%d"))
        if hist.empty:
            return {"available": False}

        event_idx = None
        for i, idx in enumerate(hist.index):
            if idx.strftime("%Y-%m-%d") >= event_date:
                event_idx = i
                break
        if event_idx is None or event_idx + 1 >= len(hist):
            return {"available": False}

        event_open = float(hist.iloc[event_idx]["Open"])
        event_close = float(hist.iloc[event_idx]["Close"])
        intraday_pct = (event_close - event_open) / event_open * 100
        next_close = float(hist.iloc[event_idx + 1]["Close"]) if event_idx + 1 < len(hist) else None
        next_day_pct = (next_close - event_close) / event_close * 100 if next_close else None
        composite_24h = intraday_pct + (next_day_pct or 0)

        return {
            "available": True,
            "source": "yfinance_daily",
            "event_date_actual": hist.index[event_idx].strftime("%Y-%m-%d"),
            "event_open": round(event_open, 3),
            "event_close": round(event_close, 3),
            "intraday_pct": round(intraday_pct, 3),
            "next_day_pct": round(next_day_pct, 3) if next_day_pct is not None else None,
            "composite_24h_pct": round(composite_24h, 3),
        }
    except Exception as e:
        logger.warning(f"[BACKTEST] DXY fetch failed for {event_date}: {e}")
        return {"available": False, "error": str(e)}


# ─── Scoring + Direction inference ───────────────────────────────────────────

def _score_to_direction(score: float, threshold: float = 5.0) -> str:
    """Convert a hawkish/dovish score to predicted USD direction."""
    if score > threshold:
        return "USD_bullish"
    if score < -threshold:
        return "USD_bearish"
    return "neutral"


def _dxy_move_to_direction(pct_move: float, threshold: float = 0.10) -> str:
    """
    Convert a DXY % move to actual USD direction.

    Threshold is 0.10% (tighter than the previous 0.15%) because intraday windows
    have less noise than 24h close-to-close. A 0.10% move in 30 minutes is a clear
    directional signal; below that is essentially flat for FOMC events.
    """
    if pct_move > threshold:
        return "USD_bullish"
    if pct_move < -threshold:
        return "USD_bearish"
    return "neutral"


# ─── Main Backtest ───────────────────────────────────────────────────────────

def run_backtest(use_tier2: bool = False, max_events: Optional[int] = None) -> Dict[str, Any]:
    """
    Run the FSM backtest against historical FOMC events.

    Args:
        use_tier2: If True, also runs Tier 2 LLM scoring (slower, more accurate).
        max_events: Limit the number of events tested (None = all 10).

    Returns a dict with per-event results and aggregate accuracy metrics.
    """
    events = HISTORICAL_FOMC_EVENTS[:max_events] if max_events else HISTORICAL_FOMC_EVENTS
    logger.info(f"[BACKTEST] Running FSM backtest on {len(events)} events (tier2={use_tier2})")

    results = []
    direction_correct = 0
    direction_evaluated = 0
    surprise_detected = 0
    surprise_total = 0
    priced_in_correct = 0
    priced_in_total = 0

    for event in events:
        event_date = event.get("actual_date") or event["date"]
        logger.info(f"[BACKTEST] Processing {event_date}: {event['event']}")

        # 1. Fetch statement
        text = _fetch_statement_text(event["url"])
        if not text:
            results.append({
                **event,
                "status": "failed",
                "error": "Could not fetch statement",
            })
            continue

        # 2. Score statement with Tier 1
        statement_t1, key_phrases = score_document_tier1(text)

        # 2b. Try to fetch + score the press conference transcript (where Powell's
        # verbal Q&A often carries the real signal — see 2023-02-01 "disinflation")
        pc_text, pc_url = _fetch_press_conference_pdf(event_date)
        pc_t1 = None
        pc_t2 = None
        if pc_text:
            pc_t1, _ = score_document_tier1(pc_text)
            logger.info(f"[BACKTEST] Press conference for {event_date}: T1={pc_t1:.1f}")

        # Combine T1: statement (0.4) + press conference (0.6) when both available
        # Press conference gets higher weight because Q&A reveals true bias
        if pc_t1 is not None:
            tier1_score = 0.40 * statement_t1 + 0.60 * pc_t1
        else:
            tier1_score = statement_t1

        # 3. Optionally score with Tier 2 LLM
        tier2_score = None
        tier2_dimensions = None
        if use_tier2:
            try:
                doc_dt = datetime.strptime(event_date, "%Y-%m-%d")
                t2_stmt, _, t2_dims = score_document_tier2(
                    text=text,
                    document_type="statement",
                    document_date=doc_dt,
                    speaker=None,
                    prev_score=None,
                )
                tier2_dimensions = t2_dims

                # Also score press conference with T2 if available
                if pc_text:
                    try:
                        t2_pc, _, _ = score_document_tier2(
                            text=pc_text,
                            document_type="press_conference",
                            document_date=doc_dt,
                            speaker="Powell",
                            prev_score=None,
                        )
                        pc_t2 = t2_pc
                        tier2_score = 0.40 * t2_stmt + 0.60 * t2_pc
                    except Exception as e:
                        logger.warning(f"[BACKTEST] Tier 2 press conference scoring failed: {e}")
                        tier2_score = t2_stmt
                else:
                    tier2_score = t2_stmt
            except Exception as e:
                logger.warning(f"[BACKTEST] Tier 2 scoring failed for {event_date}: {e}")

        # Final score: blend if T2 available, else T1 only
        if tier2_score is not None:
            final_score = 0.30 * tier1_score + 0.70 * tier2_score
        else:
            final_score = tier1_score

        # 4. Fetch DXY reaction
        dxy = _fetch_dxy_reaction(event_date)

        # 5. Compute predicted vs actual direction
        predicted_direction = _score_to_direction(final_score)
        actual_direction = None
        is_correct = None

        if dxy.get("available"):
            actual_direction = _dxy_move_to_direction(dxy["composite_24h_pct"])
            direction_evaluated += 1

            expected = event["expected_direction"]
            # Direction is correct if predicted matches actual (regardless of expected)
            if predicted_direction == actual_direction:
                direction_correct += 1
                is_correct = True
            else:
                is_correct = False

            # Surprise detection: hawkish_surprise / extreme_dovish events should
            # produce a strong score (|score| > 20)
            if "surprise" in event["expected_signal"] or "extreme" in event["expected_signal"]:
                surprise_total += 1
                if abs(final_score) > 20:
                    surprise_detected += 1

            # Priced-in detection: priced_in events should produce neutral predictions
            if "priced_in" in event["expected_signal"]:
                priced_in_total += 1
                if predicted_direction == "neutral":
                    priced_in_correct += 1

        results.append({
            **event,
            "status": "ok",
            "tier1_score": round(tier1_score, 2),
            "tier2_score": round(tier2_score, 2) if tier2_score is not None else None,
            "tier2_dimensions": tier2_dimensions,
            "final_score": round(final_score, 2),
            "predicted_direction": predicted_direction,
            "key_phrases_count": len(key_phrases),
            "key_phrases_sample": key_phrases[:5],
            "dxy_reaction": dxy,
            "actual_direction": actual_direction,
            "direction_correct": is_correct,
            "text_length": len(text),
            # Press conference detail (sourced from PDF transcript when available)
            "press_conference_available": pc_text is not None and len(pc_text) > 0,
            "press_conference_t1": round(pc_t1, 2) if pc_t1 is not None else None,
            "press_conference_t2": round(pc_t2, 2) if pc_t2 is not None else None,
            "statement_only_t1": round(statement_t1, 2),
        })

    # ─── Aggregate metrics ──────────────────────────────────────────
    direction_accuracy = (
        direction_correct / direction_evaluated if direction_evaluated > 0 else None
    )
    surprise_rate = (
        surprise_detected / surprise_total if surprise_total > 0 else None
    )
    priced_in_rate = (
        priced_in_correct / priced_in_total if priced_in_total > 0 else None
    )

    return {
        "ran_at": datetime.utcnow().isoformat(),
        "use_tier2": use_tier2,
        "total_events": len(events),
        "events_processed": len([r for r in results if r["status"] == "ok"]),
        "metrics": {
            "direction_accuracy": round(direction_accuracy, 3) if direction_accuracy is not None else None,
            "direction_correct": direction_correct,
            "direction_evaluated": direction_evaluated,
            "surprise_detection_rate": round(surprise_rate, 3) if surprise_rate is not None else None,
            "surprise_detected": surprise_detected,
            "surprise_total": surprise_total,
            "priced_in_accuracy": round(priced_in_rate, 3) if priced_in_rate is not None else None,
            "priced_in_correct": priced_in_correct,
            "priced_in_total": priced_in_total,
        },
        "events": results,
    }
