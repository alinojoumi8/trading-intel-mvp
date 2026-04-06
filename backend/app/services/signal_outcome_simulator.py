"""
Trade outcome simulator for backtesting.

Given a trading signal — entry price, stop loss, target, direction, generated_at —
replays subsequent 1-minute bars from intraday Parquet data and determines:
  1. Did the entry trigger? (price reached entry zone within the entry window)
  2. Did the trade hit stop or target first? (first-touch wins)
  3. What was the final P&L?

Pure data processing — no LLM, no live API calls. Deterministic and fast.
"""
import logging
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Literal, Optional

import pandas as pd

from app.services.intraday_loader import get_window

logger = logging.getLogger(__name__)


# ─── Types ───────────────────────────────────────────────────────────────────

Direction = Literal["LONG", "SHORT"]
Outcome = Literal["WIN", "LOSS", "BREAKEVEN", "ENTRY_NOT_TRIGGERED", "OPEN", "NO_DATA"]


@dataclass
class SignalToSimulate:
    """Minimal info needed to simulate a trade outcome."""
    asset: str
    direction: Direction
    entry_price: float
    stop_loss: float
    target_price: float             # T1 at 2R (50% exit)
    generated_at: datetime          # UTC
    entry_window_hours: int = 24    # How long to wait for entry trigger
    max_hold_days: int = 7          # Max time to hold the trade
    entry_tolerance_pct: float = 0.05  # Treat "near entry" as triggered (0.05 = 5 bps)
    target_2: Optional[float] = None   # T2 at 3R (30% exit)
    target_3: Optional[float] = None   # T3 at 4.5R (20% exit)


@dataclass
class SimulationResult:
    asset: str
    direction: Direction
    outcome: Outcome
    entry_price: float
    stop_loss: float
    target_price: float
    generated_at: str
    # Filled when entry triggers
    entry_triggered: bool = False
    entry_time: Optional[str] = None
    entry_actual_price: Optional[float] = None
    # Filled when trade closes
    exit_time: Optional[str] = None
    exit_price: Optional[float] = None
    bars_in_trade: int = 0
    pnl_pct: Optional[float] = None
    # R-multiple: profit/loss in units of risk
    r_multiple: Optional[float] = None
    risk_distance: Optional[float] = None
    reward_distance: Optional[float] = None
    risk_reward_ratio: Optional[float] = None
    # Multi-target tracking
    t1_hit: bool = False
    t2_hit: bool = False
    t3_hit: bool = False
    # Diagnostics
    max_favorable_excursion_pct: Optional[float] = None  # Best price reached during trade
    max_adverse_excursion_pct: Optional[float] = None    # Worst price reached during trade
    notes: Optional[str] = None


# ─── Outcome Simulator ───────────────────────────────────────────────────────

def simulate_signal(signal: SignalToSimulate) -> SimulationResult:
    """
    Replay intraday bars to determine the outcome of a single signal.

    Logic:
        1. Pull bars from `generated_at` forward.
        2. Wait up to `entry_window_hours` for the entry to trigger.
           - LONG triggers when low ≤ entry_price (limit fill at entry_price)
             OR when close ≥ entry_price (market enters above level).
           - SHORT triggers when high ≥ entry_price OR close ≤ entry_price.
        3. After entry, scan up to `max_hold_days` for stop/target hit.
           - LONG stop: low ≤ stop_loss → LOSS
           - LONG target: high ≥ target_price → WIN
           - SHORT inverse.
        4. First-touch wins. If both hit in the same bar, conservatively
           assume the stop hit first (LOSS) — protects against optimistic backtests.
        5. If neither hits before max_hold_days, mark OPEN with current P&L.
    """
    # Validation
    if signal.direction == "LONG":
        if signal.stop_loss >= signal.entry_price:
            return _no_data_result(signal, "Invalid LONG: stop_loss must be below entry")
        if signal.target_price <= signal.entry_price:
            return _no_data_result(signal, "Invalid LONG: target must be above entry")
    elif signal.direction == "SHORT":
        if signal.stop_loss <= signal.entry_price:
            return _no_data_result(signal, "Invalid SHORT: stop_loss must be above entry")
        if signal.target_price >= signal.entry_price:
            return _no_data_result(signal, "Invalid SHORT: target must be below entry")
    else:
        return _no_data_result(signal, f"Unknown direction: {signal.direction}")

    # Compute risk and reward distances for R-multiple math
    if signal.direction == "LONG":
        risk_distance = signal.entry_price - signal.stop_loss
        reward_distance = signal.target_price - signal.entry_price
    else:
        risk_distance = signal.stop_loss - signal.entry_price
        reward_distance = signal.entry_price - signal.target_price

    rr_ratio = reward_distance / risk_distance if risk_distance > 0 else None

    # Pull bars: from signal time → (entry_window + max_hold) days later
    end_time = signal.generated_at + timedelta(
        hours=signal.entry_window_hours,
    ) + timedelta(days=signal.max_hold_days)

    # Ensure UTC timezone
    start_utc = signal.generated_at
    if start_utc.tzinfo is None:
        start_utc = pd.Timestamp(start_utc, tz="UTC").to_pydatetime()
    end_utc = end_time
    if end_utc.tzinfo is None:
        end_utc = pd.Timestamp(end_utc, tz="UTC").to_pydatetime()

    bars = get_window(signal.asset, start_utc, end_utc)
    if bars.empty:
        return _no_data_result(signal, f"No intraday data for {signal.asset} after {start_utc}")

    # ─── Phase A: Wait for entry trigger ──────────────────────────
    # Entry semantics:
    #   - LONG limit (entry < current price): wait for low to touch entry
    #   - LONG breakout (entry > current price): wait for high to reach entry
    #   - LONG market (entry ≈ current price): trigger immediately
    #   - SHORT limit (entry > current price): wait for high to reach entry
    #   - SHORT breakdown (entry < current price): wait for low to touch entry
    #   - SHORT market (entry ≈ current price): trigger immediately
    entry_deadline = start_utc + timedelta(hours=signal.entry_window_hours)
    entry_window_bars = bars[bars.index < entry_deadline]
    if entry_window_bars.empty:
        return _no_data_result(signal, "No bars available within entry window")

    # Use the first bar's close as the "current price" reference at signal time
    current_price = float(entry_window_bars.iloc[0]["close"])
    tol_pct = max(signal.entry_tolerance_pct, 0.05) / 100  # min 5 bps
    tol_abs = current_price * tol_pct

    # Sanity check: reject signals with absurd entry distance (>10% from current)
    entry_distance_pct = abs(signal.entry_price - current_price) / current_price * 100
    if entry_distance_pct > 10:
        return SimulationResult(
            asset=signal.asset,
            direction=signal.direction,
            outcome="ENTRY_NOT_TRIGGERED",
            entry_price=signal.entry_price,
            stop_loss=signal.stop_loss,
            target_price=signal.target_price,
            generated_at=start_utc.isoformat(),
            risk_distance=risk_distance,
            reward_distance=reward_distance,
            risk_reward_ratio=rr_ratio,
            notes=f"Entry {signal.entry_price} is {entry_distance_pct:.1f}% from current price {current_price:.4f} — rejected as unrealistic",
        )

    entry_idx = None
    entry_price_actual = None

    for idx, bar in entry_window_bars.iterrows():
        bar_high = float(bar["high"])
        bar_low = float(bar["low"])

        if signal.direction == "LONG":
            if signal.entry_price < current_price - tol_abs:
                # LIMIT BUY: waiting for price to dip down to entry
                if bar_low <= signal.entry_price:
                    entry_idx = idx
                    entry_price_actual = signal.entry_price
                    break
            elif signal.entry_price > current_price + tol_abs:
                # BREAKOUT BUY: waiting for price to rally up to entry
                if bar_high >= signal.entry_price:
                    entry_idx = idx
                    entry_price_actual = signal.entry_price
                    break
            else:
                # MARKET BUY: enter immediately at the first bar's close
                entry_idx = idx
                entry_price_actual = float(bar["close"])
                break
        else:  # SHORT
            if signal.entry_price > current_price + tol_abs:
                # LIMIT SELL: waiting for price to rally up to entry
                if bar_high >= signal.entry_price:
                    entry_idx = idx
                    entry_price_actual = signal.entry_price
                    break
            elif signal.entry_price < current_price - tol_abs:
                # BREAKDOWN SELL: waiting for price to fall to entry
                if bar_low <= signal.entry_price:
                    entry_idx = idx
                    entry_price_actual = signal.entry_price
                    break
            else:
                # MARKET SELL: enter immediately
                entry_idx = idx
                entry_price_actual = float(bar["close"])
                break

    if entry_idx is None:
        return SimulationResult(
            asset=signal.asset,
            direction=signal.direction,
            outcome="ENTRY_NOT_TRIGGERED",
            entry_price=signal.entry_price,
            stop_loss=signal.stop_loss,
            target_price=signal.target_price,
            generated_at=start_utc.isoformat(),
            entry_triggered=False,
            risk_distance=risk_distance,
            reward_distance=reward_distance,
            risk_reward_ratio=rr_ratio,
            notes=f"Entry never triggered within {signal.entry_window_hours}h window",
        )

    # ─── Phase B: Track trade until stop/target/expiry ────────────
    trade_bars = bars[bars.index > entry_idx]
    expiry = entry_idx + timedelta(days=signal.max_hold_days)
    trade_bars = trade_bars[trade_bars.index <= expiry]

    if trade_bars.empty:
        return SimulationResult(
            asset=signal.asset,
            direction=signal.direction,
            outcome="OPEN",
            entry_price=signal.entry_price,
            stop_loss=signal.stop_loss,
            target_price=signal.target_price,
            generated_at=start_utc.isoformat(),
            entry_triggered=True,
            entry_time=entry_idx.isoformat(),
            entry_actual_price=entry_price_actual,
            risk_distance=risk_distance,
            reward_distance=reward_distance,
            risk_reward_ratio=rr_ratio,
            notes="Entry triggered but no subsequent bars available",
        )

    # ─── Phase B: Multi-target partial exit simulation ────────────────
    # Partial exit plan (spec Section 5.2): 50% at T1, 30% at T2, 20% at T3.
    # After T1 hit, the effective stop moves to entry (breakeven protection).
    # If stop hits before T1 → full LOSS. After T1 → worst case BREAKEVEN.
    # Weighted P&L: 0.5 × T1_pct + 0.3 × T2_pct + 0.2 × T3_pct

    outcome: Outcome = "OPEN"
    exit_idx = None
    exit_price = None
    mfe = 0.0
    mae = 0.0

    t1_hit = False
    t2_hit = False
    t3_hit = False
    t1_exit_price: Optional[float] = None
    t2_exit_price: Optional[float] = None
    t3_exit_price: Optional[float] = None
    stop_after_t1 = entry_price_actual  # Breakeven stop once T1 hit

    # Effective stop: pre-T1 = signal.stop_loss, post-T1 = entry (breakeven)
    active_stop = signal.stop_loss

    for idx, bar in trade_bars.iterrows():
        high = float(bar["high"])
        low = float(bar["low"])

        # Update MFE/MAE
        if signal.direction == "LONG":
            fav = (high - entry_price_actual) / entry_price_actual * 100
            adv = (low - entry_price_actual) / entry_price_actual * 100
        else:
            fav = (entry_price_actual - low) / entry_price_actual * 100
            adv = (entry_price_actual - high) / entry_price_actual * 100
        if fav > mfe:
            mfe = fav
        if adv < mae:
            mae = adv

        if signal.direction == "LONG":
            stop_hit = low <= active_stop
            t1_trigger = (not t1_hit) and high >= signal.target_price
            t2_trigger = t1_hit and (not t2_hit) and signal.target_2 and high >= signal.target_2
            t3_trigger = t2_hit and (not t3_hit) and signal.target_3 and high >= signal.target_3
        else:  # SHORT
            stop_hit = high >= active_stop
            t1_trigger = (not t1_hit) and low <= signal.target_price
            t2_trigger = t1_hit and (not t2_hit) and signal.target_2 and low <= signal.target_2
            t3_trigger = t2_hit and (not t3_hit) and signal.target_3 and low <= signal.target_3

        # Check stop first (conservative)
        if stop_hit and not t1_hit:
            # Stopped out before T1 — full loss
            outcome = "LOSS"
            exit_price = active_stop
            exit_idx = idx
            break
        elif stop_hit and t1_hit:
            # Stopped at breakeven after T1 — partial WIN (T1 locked in)
            outcome = "BREAKEVEN"
            exit_price = active_stop
            exit_idx = idx
            break

        # Check targets in order
        if t3_trigger:
            t3_hit = True
            t3_exit_price = signal.target_3
            outcome = "WIN"
            exit_price = signal.target_3
            exit_idx = idx
            break
        elif t2_trigger:
            t2_hit = True
            t2_exit_price = signal.target_2
        elif t1_trigger:
            t1_hit = True
            t1_exit_price = signal.target_price
            # Move stop to breakeven after T1
            active_stop = stop_after_t1

    # Trade still open at expiry?
    if exit_idx is None:
        exit_idx = trade_bars.index[-1]
        exit_price = float(trade_bars.iloc[-1]["close"])
        if t1_hit:
            outcome = "WIN"  # At minimum T1 was hit
        else:
            outcome = "OPEN"

    # ─── Weighted P&L (partial exit model) ───────────────────────────
    # Compute per-tranche P&L, then weight 50/30/20
    def _pnl(ep: float, xp: float) -> float:
        if signal.direction == "LONG":
            return (xp - ep) / ep * 100
        return (ep - xp) / ep * 100

    if t1_hit:
        w1 = _pnl(entry_price_actual, t1_exit_price or signal.target_price)
        w2 = _pnl(entry_price_actual, t2_exit_price or signal.target_2 or exit_price) if signal.target_2 else _pnl(entry_price_actual, exit_price)
        w3 = _pnl(entry_price_actual, t3_exit_price or signal.target_3 or exit_price) if signal.target_3 else _pnl(entry_price_actual, exit_price)
        # Weights: T1=50%, T2=30%, T3=20%
        pnl_pct = 0.50 * w1 + 0.30 * w2 + 0.20 * w3
    else:
        # No partial exits — standard single exit P&L
        pnl_pct = _pnl(entry_price_actual, exit_price)

    r_multiple = pnl_pct / (risk_distance / entry_price_actual * 100) if risk_distance > 0 else None

    return SimulationResult(
        asset=signal.asset,
        direction=signal.direction,
        outcome=outcome,
        entry_price=signal.entry_price,
        stop_loss=signal.stop_loss,
        target_price=signal.target_price,
        generated_at=start_utc.isoformat(),
        entry_triggered=True,
        entry_time=entry_idx.isoformat(),
        entry_actual_price=round(entry_price_actual, 5),
        exit_time=exit_idx.isoformat(),
        exit_price=round(exit_price, 5),
        bars_in_trade=len(trade_bars[trade_bars.index <= exit_idx]),
        pnl_pct=round(pnl_pct, 4),
        r_multiple=round(r_multiple, 3) if r_multiple is not None else None,
        risk_distance=round(risk_distance, 5),
        reward_distance=round(reward_distance, 5),
        risk_reward_ratio=round(rr_ratio, 2) if rr_ratio is not None else None,
        t1_hit=t1_hit,
        t2_hit=t2_hit,
        t3_hit=t3_hit,
        max_favorable_excursion_pct=round(mfe, 3),
        max_adverse_excursion_pct=round(mae, 3),
    )


def _no_data_result(signal: SignalToSimulate, reason: str) -> SimulationResult:
    return SimulationResult(
        asset=signal.asset,
        direction=signal.direction,
        outcome="NO_DATA",
        entry_price=signal.entry_price,
        stop_loss=signal.stop_loss,
        target_price=signal.target_price,
        generated_at=signal.generated_at.isoformat() if hasattr(signal.generated_at, "isoformat") else str(signal.generated_at),
        notes=reason,
    )


# ─── Batch simulation ────────────────────────────────────────────────────────

def simulate_signals(signals: List[SignalToSimulate]) -> List[SimulationResult]:
    """Simulate a list of signals and return results."""
    return [simulate_signal(s) for s in signals]


# ─── Aggregate metrics ───────────────────────────────────────────────────────

def aggregate_metrics(results: List[SimulationResult]) -> Dict[str, Any]:
    """Compute portfolio-level metrics from a list of simulation results."""
    if not results:
        return {"total": 0}

    closed = [r for r in results if r.outcome in ("WIN", "LOSS")]
    triggered = [r for r in results if r.entry_triggered]
    not_triggered = [r for r in results if r.outcome == "ENTRY_NOT_TRIGGERED"]

    wins = [r for r in closed if r.outcome == "WIN"]
    losses = [r for r in closed if r.outcome == "LOSS"]

    win_rate = len(wins) / len(closed) if closed else None
    avg_win_pct = sum(r.pnl_pct for r in wins) / len(wins) if wins else None
    avg_loss_pct = sum(r.pnl_pct for r in losses) / len(losses) if losses else None
    avg_r = sum(r.r_multiple for r in closed if r.r_multiple is not None) / len(closed) if closed else None

    # Total return: sum of all P&L (assumes equal sizing)
    total_return_pct = sum(r.pnl_pct for r in closed if r.pnl_pct is not None)

    # Profit factor: gross profit / gross loss
    gross_profit = sum(r.pnl_pct for r in wins)
    gross_loss = abs(sum(r.pnl_pct for r in losses))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else None

    # Expectancy per trade (R-multiple based)
    expectancy_r = avg_r if avg_r is not None else None

    # Risk-adjusted metrics (requires ≥ 2 closed trades)
    sharpe_ratio = None
    sortino_ratio = None
    max_drawdown_pct = None
    recovery_factor = None

    if len(closed) >= 2:
        returns = [r.pnl_pct for r in closed if r.pnl_pct is not None]
        n = len(returns)
        mean_r = sum(returns) / n
        variance = sum((x - mean_r) ** 2 for x in returns) / n
        std_r = variance ** 0.5

        # Sharpe — annualised assuming ~252 trading days, risk-free = 0
        if std_r > 0:
            sharpe_ratio = round(mean_r / std_r * (252 ** 0.5), 3)

        # Sortino — downside deviation only
        downside = [x for x in returns if x < 0]
        if downside:
            down_variance = sum(x ** 2 for x in downside) / n
            down_std = down_variance ** 0.5
            if down_std > 0:
                sortino_ratio = round(mean_r / down_std * (252 ** 0.5), 3)

        # Max drawdown — peak-to-trough on cumulative P&L
        cumulative = 0.0
        peak = 0.0
        max_dd = 0.0
        for r in returns:
            cumulative += r
            if cumulative > peak:
                peak = cumulative
            drawdown = peak - cumulative
            if drawdown > max_dd:
                max_dd = drawdown
        max_drawdown_pct = round(max_dd, 3)

        # Recovery factor — total return / max drawdown
        if max_dd > 0:
            recovery_factor = round(total_return_pct / max_dd, 3)

    return {
        "total_signals": len(results),
        "triggered": len(triggered),
        "not_triggered": len(not_triggered),
        "trigger_rate": len(triggered) / len(results) if results else None,
        "closed": len(closed),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": round(win_rate, 3) if win_rate is not None else None,
        "avg_win_pct": round(avg_win_pct, 3) if avg_win_pct is not None else None,
        "avg_loss_pct": round(avg_loss_pct, 3) if avg_loss_pct is not None else None,
        "avg_r_multiple": round(avg_r, 3) if avg_r is not None else None,
        "expectancy_r": round(expectancy_r, 3) if expectancy_r is not None else None,
        "total_return_pct": round(total_return_pct, 2),
        "gross_profit_pct": round(gross_profit, 2),
        "gross_loss_pct": round(gross_loss, 2),
        "profit_factor": round(profit_factor, 2) if profit_factor is not None else None,
        "sharpe_ratio": sharpe_ratio,
        "sortino_ratio": sortino_ratio,
        "max_drawdown_pct": max_drawdown_pct,
        "recovery_factor": recovery_factor,
    }
