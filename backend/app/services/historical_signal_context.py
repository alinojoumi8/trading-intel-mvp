"""
Historical signal context assembler.

Builds the exact `{regime_data, macro_data, technicals, fsm_context}` dict
that the V3 4-stage LLM pipeline needs, but using only data publicly known
as of an arbitrary historical date. No look-ahead bias.

The output of `build_context()` is shaped identically to what
`signals_data_fetcher.get_regime_data() / get_full_macro_data() /
calculate_technicals()` returns at runtime — so the existing
`run_full_pipeline()` can be called with these injected.
"""
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from app.services.intraday_loader import get_window, load_year
from app.services.vix_history_loader import get_vix_at, get_vix_change_pct
from app.services.historical_macro_loader import get_value_as_of, get_value_with_roc

logger = logging.getLogger(__name__)


# ─── Asset → intraday symbol mapping ─────────────────────────────────────────

# V3 asset name → our intraday Parquet symbol
ASSET_TO_INTRADAY = {
    "EURUSD": "EURUSD",
    "GBPUSD": "GBPUSD",
    "USDJPY": "USDJPY",
    "XAUUSD": "XAUUSD",
    "USA500": "USA500",
    "SPX": "USA500",
    "SPY": "USA500",
    "NAS100": "NAS100",
    "DXY": "DXY",
}


# ─── Stage 1 — Historical Regime Data ────────────────────────────────────────

def build_historical_regime(as_of: datetime) -> Dict[str, Any]:
    """
    Build the regime_data dict for Stage 1 prompt at a historical date.

    Inputs (point-in-time):
      - SPX from USA500 intraday
      - VIX from VIX history Parquet
      - SPX previous business cycle high computed from price history
    """
    if as_of.tzinfo is None:
        as_of = pd.Timestamp(as_of, tz="UTC").to_pydatetime()

    # ── SPX current price (USA500 intraday) ──────────────────────────
    spx_year_df = load_year("USA500", as_of.year)
    if spx_year_df is None:
        logger.warning(f"[CTX] No USA500 data for year {as_of.year}")
        return {}

    target_ts = pd.Timestamp(as_of).tz_convert("UTC") if as_of.tzinfo else pd.Timestamp(as_of, tz="UTC")
    in_window = spx_year_df[spx_year_df.index <= target_ts]
    if in_window.empty:
        return {}
    spx_current = float(in_window.iloc[-1]["close"])

    # ── SPX previous business cycle high (look back ~5 years) ────────
    five_years_ago = as_of - timedelta(days=365 * 5)
    historical_spx = get_window("USA500", five_years_ago, as_of)
    if historical_spx.empty:
        spx_prev_high = spx_current
    else:
        # Resample to daily, find rolling-max high
        daily = historical_spx["high"].resample("1D").max().dropna()
        spx_prev_high = float(daily.max()) if len(daily) > 0 else spx_current

    bear_market_level = spx_prev_high * 0.80 if spx_prev_high else None
    bull_market_level = spx_prev_high

    # ── VIX (current + 30d ago + % change) ───────────────────────────
    vix_data = get_vix_change_pct(as_of, days_back=30)
    vix_current = vix_data["current"] if vix_data else None
    vix_30d_ago = vix_data["prior"] if vix_data else None
    vix_pct_change = vix_data["pct_change"] if vix_data else None

    return {
        "spx_current": round(spx_current, 2),
        "spx_prev_cycle_high": round(spx_prev_high, 2) if spx_prev_high else None,
        "bear_market_level": round(bear_market_level, 2) if bear_market_level else None,
        "bull_market_level": round(bull_market_level, 2) if bull_market_level else None,
        "vix_current": vix_current,
        "vix_30d_ago": vix_30d_ago,
        "vix_pct_change": vix_pct_change,
    }


# ─── Stage 2 — Historical Macro Data ─────────────────────────────────────────

def _classify_quadrant(gdp_dir: str, cpi_dir: str) -> str:
    """Match the live pipeline's quadrant classifier."""
    is_growth_up = gdp_dir in ("RISING", "ACCELERATING")
    is_inflation_up = cpi_dir in ("RISING", "ACCELERATING")
    if is_growth_up and not is_inflation_up:
        return "EXPANSION"
    if is_growth_up and is_inflation_up:
        return "REFLATION"
    if not is_growth_up and not is_inflation_up:
        return "DISINFLATION"
    if not is_growth_up and is_inflation_up:
        return "STAGFLATION"
    return "TRANSITIONAL"


def build_historical_macro(as_of: datetime, asset: str = "EURUSD") -> Dict[str, Any]:
    """
    Build the macro_data dict for Stage 2 prompt at a historical date.
    Mirrors the shape of `signals_data_fetcher.get_macro_data()`.
    """
    result: Dict[str, Any] = {}

    # ROC-enriched indicators (matches the live pipeline shape)
    result["gdp"] = get_value_with_roc("GDPC1", as_of)
    result["cpi"] = get_value_with_roc("CPIAUCSL", as_of)
    result["pce"] = get_value_with_roc("PCEPI", as_of)
    result["unemployment"] = get_value_with_roc("UNRATE", as_of)
    result["leading_indicator"] = get_value_with_roc("USSLIND", as_of)
    result["consumer_sentiment"] = get_value_with_roc("UMCSENT", as_of)
    result["yield_curve"] = get_value_with_roc("T10Y2Y", as_of)
    result["fed_funds"] = get_value_with_roc("DFF", as_of)

    # Economic quadrant
    gdp_dir = result["gdp"].get("direction", "UNKNOWN")
    cpi_dir = result["cpi"].get("direction", "UNKNOWN")
    result["economic_quadrant"] = _classify_quadrant(gdp_dir, cpi_dir)

    # Flat shortcuts (the live pipeline uses these too)
    pce_val = get_value_as_of("PCEPILFE", as_of)
    nfp = get_value_as_of("PAYEMS", as_of)
    nfp_prior = None
    if nfp:
        # Get prior month for NFP delta
        from app.services.historical_macro_loader import get_series_history_as_of
        history = get_series_history_as_of("PAYEMS", as_of, limit=2)
        if len(history) >= 2:
            nfp_prior = history[-2]["value"]

    result["consumer_confidence"] = get_value_as_of("UMCSENT", as_of)
    result["consumer_confidence"] = result["consumer_confidence"]["value"] if result["consumer_confidence"] else None
    result["nfp_change"] = round(nfp["value"] - nfp_prior, 1) if nfp and nfp_prior else None
    result["core_pce"] = pce_val["value"] if pce_val else None

    from app.services.mql5_loader import get_mql5_value_as_of
    ism_mfg = get_mql5_value_as_of("ism-manufacturing-pmi", as_of)
    ism_svc = get_mql5_value_as_of("ism-non-manufacturing-pmi", as_of)
    result["ism_manufacturing"] = round(ism_mfg["value"], 1) if ism_mfg else "N/A"
    result["ism_services"] = round(ism_svc["value"], 1) if ism_svc else "N/A"
    result["surprise_index"] = None

    # DXY snapshot
    dxy_val = get_value_as_of("DTWEXBGS", as_of)
    result["dxy"] = round(dxy_val["value"], 2) if dxy_val else None

    # Wage growth (Avg Hourly Earnings)
    wage_val = get_value_as_of("CES0500000003", as_of)
    result["wage_growth"] = round(wage_val["value"], 2) if wage_val else None

    # Retail sales
    rs_val = get_value_as_of("RSAFS", as_of)
    result["retail_sales"] = round(rs_val["value"], 1) if rs_val else None

    # Fiscal balance — proxy with the leading index for now (FYFSD vintage history is sparse)
    result["fiscal_deficit"] = None

    # Rate trend & CB bias from Fed Funds history
    from app.services.historical_macro_loader import get_series_history_as_of
    ff_history = get_series_history_as_of("FEDFUNDS", as_of, limit=6)
    if len(ff_history) >= 3:
        latest_rate = ff_history[-1]["value"]
        prev_rate = ff_history[-3]["value"]
        if latest_rate > prev_rate + 0.1:
            result["rate_trend"] = "HIKING"
        elif latest_rate < prev_rate - 0.1:
            result["rate_trend"] = "CUTTING"
        else:
            result["rate_trend"] = "PAUSING"
    else:
        result["rate_trend"] = "UNKNOWN"

    # CB bias
    if len(ff_history) >= 6:
        recent = [h["value"] for h in ff_history[-6:]]
        if all(recent[i] > recent[i-1] for i in range(1, len(recent))):
            result["cb_bias"] = "HAWKISH"
        elif all(recent[i] < recent[i-1] for i in range(1, len(recent))):
            result["cb_bias"] = "DOVISH"
        else:
            result["cb_bias"] = "NEUTRAL"
    else:
        result["cb_bias"] = "NEUTRAL"

    result["fed_funds_rate"] = result["fed_funds"].get("latest")
    result["unemployment_rate"] = result["unemployment"].get("latest")
    result["gdp_growth"] = result["gdp"].get("latest")
    result["cb_inflation_target"] = 2.0

    # COT — use most-recent value we have in DB or N/A (full historical COT
    # backfill is a separate task; for the backtest we'll pull from cot_service
    # if available, otherwise N/A)
    result["cot_net_pct"] = "N/A"
    result["cot_status"] = "N/A"

    # Asset class detection (matches signals_data_fetcher.classify_asset)
    result["asset_class"] = _classify_asset(asset)

    return result


def _classify_asset(asset: str) -> str:
    """Match signals_data_fetcher.classify_asset."""
    upper = asset.upper().replace("=X", "").replace("/", "")
    if upper in ("XAUUSD", "GOLD", "XAGUSD", "SILVER"):
        return "COMMODITY"  # Note: the live pipeline treats XAU/XAG as FX in some places
    if upper in ("EURUSD", "GBPUSD", "USDJPY", "USDCAD", "AUDUSD", "USDCHF", "NZDUSD"):
        return "FX"
    if upper in ("BTCUSD", "ETHUSD", "BTC", "ETH"):
        return "CRYPTO"
    if upper in ("USA500", "USATECH", "SPY", "QQQ", "SPX", "NAS100"):
        return "EQUITY"
    return "FX"  # default


# ─── Stage 3 — Historical Technicals ─────────────────────────────────────────

def build_historical_technicals(asset: str, as_of: datetime) -> Optional[Dict[str, Any]]:
    """
    Compute technical indicators (MA20/60/250, RSI, ATR, etc.) from intraday
    Parquet data, resampled to daily bars, as of a historical date.

    Returns same shape as signals_technicals.calculate_technicals().
    """
    symbol = ASSET_TO_INTRADAY.get(asset.upper())
    if not symbol:
        logger.warning(f"[CTX] No intraday symbol for asset {asset}")
        return None

    if as_of.tzinfo is None:
        as_of = pd.Timestamp(as_of, tz="UTC").to_pydatetime()

    # Pull ~1 year of intraday data ending at as_of
    one_year_ago = as_of - timedelta(days=400)
    intraday = get_window(symbol, one_year_ago, as_of)
    if intraday.empty or len(intraday) < 1000:
        logger.warning(f"[CTX] Insufficient intraday data for {symbol} as of {as_of}")
        return None

    # Resample to daily OHLCV (UTC midnight closes)
    daily = intraday.resample("1D").agg({
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
    }).dropna()

    if len(daily) < 60:
        return None

    close = daily["close"]
    high = daily["high"]
    low = daily["low"]
    volume = daily["volume"]

    # Moving averages
    ma20 = close.rolling(20).mean()
    ma60 = close.rolling(60).mean()
    ma250 = close.rolling(250).mean() if len(close) >= 250 else close.rolling(min(len(close), 250)).mean()

    latest = float(close.iloc[-1])
    latest_ma20 = float(ma20.iloc[-1]) if not np.isnan(ma20.iloc[-1]) else None
    latest_ma60 = float(ma60.iloc[-1]) if not np.isnan(ma60.iloc[-1]) else None
    latest_ma250 = float(ma250.iloc[-1]) if not np.isnan(ma250.iloc[-1]) else None

    # Cross detection
    def _cross(series_a: pd.Series, series_b: pd.Series) -> str:
        if len(series_a) < 2 or len(series_b) < 2:
            return "NONE"
        a_now, a_prev = float(series_a.iloc[-1]), float(series_a.iloc[-2])
        b_now, b_prev = float(series_b.iloc[-1]), float(series_b.iloc[-2])
        if a_prev < b_prev and a_now > b_now:
            return "GOLDEN"
        if a_prev > b_prev and a_now < b_now:
            return "DEATH"
        return "NONE"

    ma_20_vs_60_cross = _cross(ma20, ma60)
    ma_60_vs_250_cross = _cross(ma60, ma250)

    # RSI (14)
    delta = close.diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = -delta.where(delta < 0, 0).rolling(14).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    rsi_14 = float(rsi.iloc[-1]) if not np.isnan(rsi.iloc[-1]) else None

    # ATR (14)
    tr1 = high - low
    tr2 = abs(high - close.shift())
    tr3 = abs(low - close.shift())
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr_14 = float(tr.rolling(14).mean().iloc[-1]) if not np.isnan(tr.rolling(14).mean().iloc[-1]) else None

    # Trend direction (simple)
    if latest_ma20 and latest_ma60 and latest > latest_ma20 > latest_ma60:
        trend = "UPTREND"
    elif latest_ma20 and latest_ma60 and latest < latest_ma20 < latest_ma60:
        trend = "DOWNTREND"
    else:
        trend = "RANGING"

    # Support / resistance — last 60-day high and low
    key_resistance = float(high.tail(60).max())
    key_support = float(low.tail(60).min())

    if latest <= key_support * 1.005:
        at_sr = "AT_SUPPORT"
    elif latest >= key_resistance * 0.995:
        at_sr = "AT_RESISTANCE"
    else:
        at_sr = "MID_RANGE"

    price_vs_20ma = "ABOVE" if latest_ma20 and latest > latest_ma20 else "BELOW"
    price_vs_60ma = "ABOVE" if latest_ma60 and latest > latest_ma60 else "BELOW"
    price_vs_250ma = "ABOVE" if latest_ma250 and latest > latest_ma250 else "BELOW"

    # Volume
    vol_avg = float(volume.rolling(20).mean().iloc[-1]) if not np.isnan(volume.rolling(20).mean().iloc[-1]) else None
    vol_current = float(volume.iloc[-1])
    if vol_avg and vol_current > vol_avg * 1.5:
        volume_vs_avg = "HIGH"
    elif vol_avg and vol_current < vol_avg * 0.7:
        volume_vs_avg = "LOW"
    else:
        volume_vs_avg = "NORMAL"

    # Historical volatility (1m proxy)
    returns = close.pct_change().tail(20)
    hist_vol_1m = round(float(returns.std() * np.sqrt(252) * 100), 2) if not np.isnan(returns.std()) else None

    # IV ranges (use HV1m as proxy)
    iv_ranges = None
    if hist_vol_1m and latest:
        daily_1sd = round(latest * (hist_vol_1m / 100) / np.sqrt(252), 5)
        weekly_1sd = round(latest * (hist_vol_1m / 100) / np.sqrt(52), 5)
        monthly_1sd = round(latest * (hist_vol_1m / 100) / np.sqrt(12), 5)
        iv_ranges = {
            "daily_1sd": daily_1sd,
            "weekly_1sd": weekly_1sd,
            "monthly_1sd": monthly_1sd,
            "hard_stop_distance": round(daily_1sd * 1.5, 5),
            "soft_target_distance": round(daily_1sd * 3.0, 5),
        }

    return {
        "ticker": symbol,
        "current_price": round(latest, 5),
        "ma20": round(latest_ma20, 5) if latest_ma20 else None,
        "ma60": round(latest_ma60, 5) if latest_ma60 else None,
        "ma250": round(latest_ma250, 5) if latest_ma250 else None,
        "price_vs_20ma": price_vs_20ma,
        "price_vs_60ma": price_vs_60ma,
        "price_vs_250ma": price_vs_250ma,
        "ma_20_vs_60_cross": ma_20_vs_60_cross,
        "ma_60_vs_250_cross": ma_60_vs_250_cross,
        "rsi_14": round(rsi_14, 2) if rsi_14 else None,
        "atr_14": round(atr_14, 5) if atr_14 else None,
        "hist_vol_1m": hist_vol_1m,
        "trend_direction": trend,
        "price_pattern": "NONE",  # Pattern detection is hard to backfill
        "volume_vs_avg": volume_vs_avg,
        "key_support": round(key_support, 5),
        "key_resistance": round(key_resistance, 5),
        "at_support_resistance": at_sr,
        "iv_ranges": iv_ranges,
    }


# ─── FSM context for a historical date ────────────────────────────────────────

def build_historical_fsm_context(as_of: datetime) -> Dict[str, Any]:
    """
    Compute FSM composite as it would have been on a historical date,
    using only Fed documents and FRED yields known by then.
    """
    from app.services.fed_sentiment_service import (
        get_language_score, compute_composite, get_market_score,
    )
    from app.models.models import FedDocument
    from app.core.database import SessionLocal

    db = SessionLocal()
    try:
        # Pull recent Fed documents as of as_of
        cutoff_old = as_of - timedelta(days=90)
        docs_q = (
            db.query(FedDocument)
            .filter(FedDocument.document_date <= as_of)
            .filter(FedDocument.document_date >= cutoff_old)
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
            for d in docs_q
        ]

        language_score, key_phrases = get_language_score(recent_docs) if recent_docs else (None, [])

        # For market score, we need point-in-time yields
        # Use get_value_as_of for DGS2, T10Y2Y, FEDFUNDS
        y2 = get_value_as_of("DGS2", as_of)
        spread = get_value_as_of("T10Y2Y", as_of)
        ff = get_value_as_of("DFF", as_of)
        y2_30d = get_value_as_of("DGS2", as_of - timedelta(days=30))

        market_data = {
            "yield_2y": y2["value"] if y2 else None,
            "yield_spread_10y2y": spread["value"] if spread else None,
            "fed_target_rate": ff["value"] if ff else None,
            "yield_2y_30d_change": (y2["value"] - y2_30d["value"]) if (y2 and y2_30d) else None,
            "next_meeting_bps_priced": None,
            "is_stale": False,
            "market_score": None,  # will be computed below
        }

        # Compute market score using the same logic as get_market_score()
        # Simplified inline since the live function fetches FRED itself
        market_score = _compute_market_score_simple(market_data, ff)
        market_data["market_score"] = market_score

        composite = compute_composite(language_score, market_data, divergence_history=[])

        # Build pipeline context
        return {
            "available": True,
            "fed_regime": composite.get("fed_regime", "NEUTRAL"),
            "composite_score": round(composite.get("composite_score") or 0.0, 1),
            "language_score": round(composite.get("language_score") or 0.0, 1),
            "market_score": round(composite.get("market_score") or 0.0, 1),
            "is_pivot_in_progress": False,
            "volatility_multiplier": 1.0,
            "divergence_category": composite.get("divergence_category", "NEUTRAL"),
            "signal_direction": composite.get("signal_direction", "NEUTRAL"),
            "signal_conviction": composite.get("signal_conviction", "low"),
            "position_size_modifier": 1.0,
            "days_to_next_fomc": None,
            "next_fomc_date": None,
            "pre_fomc_window": False,
        }
    except Exception as e:
        logger.exception(f"[CTX] FSM context build failed for {as_of}: {e}")
        return {"available": False}
    finally:
        db.close()


def _compute_market_score_simple(market_data: Dict[str, Any], ff: Optional[Dict[str, Any]]) -> Optional[float]:
    """
    Simplified market score using yield deltas. Mirrors the simpler half of
    get_market_score() in fed_sentiment_service.py.
    """
    y2 = market_data.get("yield_2y")
    fed_rate = market_data.get("fed_target_rate")
    spread = market_data.get("yield_spread_10y2y")
    y2_30d_chg = market_data.get("yield_2y_30d_change")

    if y2 is None or fed_rate is None:
        return 0.0

    components = []

    # Near-term: 2Y yield vs Fed Funds (1Y horizon)
    near_term = (y2 - fed_rate) * 50  # 50bps = ~25 points
    components.append(("near_term", near_term, 0.35))

    # Yield momentum: 30d change in 2Y yield
    if y2_30d_chg is not None:
        momentum = y2_30d_chg * 200  # 0.5% chg = 100 points
        components.append(("yield_momentum", momentum, 0.20))

    # Curve shape: 10Y-2Y spread (negative = inverted = recession risk = dovish)
    if spread is not None:
        curve = spread * 30  # ±0.5% = ±15 points
        components.append(("curve_shape", curve, 0.15))

    if not components:
        return 0.0

    weighted = sum(score * weight for _, score, weight in components)
    total_weight = sum(weight for _, _, weight in components)
    score = weighted / total_weight if total_weight > 0 else 0.0
    return max(-100, min(100, round(score, 2)))


# ─── Master assembler ────────────────────────────────────────────────────────

def build_context(asset: str, as_of: datetime) -> Dict[str, Any]:
    """
    Build the full historical signal context dict for an (asset, date) pair.

    Returns: {
        "regime_data": {...},     # Stage 1 input
        "macro_data": {...},      # Stage 2 input
        "technicals": {...},      # Stage 3 input
        "fsm_context": {...},     # Injected into Stage 1+2 prompts
        "asset_class": str,
    }

    Returns empty dict if essential data is missing.
    """
    if as_of.tzinfo is None:
        as_of = pd.Timestamp(as_of, tz="UTC").to_pydatetime()

    regime_data = build_historical_regime(as_of)
    if not regime_data:
        return {}

    macro_data = build_historical_macro(as_of, asset=asset)
    technicals = build_historical_technicals(asset, as_of)
    fsm_context = build_historical_fsm_context(as_of)

    return {
        "regime_data": regime_data,
        "macro_data": macro_data,
        "technicals": technicals,
        "fsm_context": fsm_context,
        "asset_class": macro_data.get("asset_class", "FX"),
        "as_of": as_of.isoformat(),
        "asset": asset,
    }
