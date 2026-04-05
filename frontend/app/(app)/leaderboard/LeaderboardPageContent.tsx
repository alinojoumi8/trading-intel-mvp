"use client";

import { useEffect, useState, useCallback } from "react";
import { getSignals, getSignalStats, TradingSignal, SignalStats } from "@/lib/api";

const ASSET_FILTERS = ["ALL", "FX", "CRYPTO", "COMMODITIES", "INDICES"];

function directionColor(dir?: string): string {
  switch (dir?.toUpperCase()) {
    case "BUY": case "LONG": return "text-green-400";
    case "SELL": case "SHORT": return "text-red-400";
    default: return "text-zinc-400";
  }
}

function directionBg(dir?: string): string {
  switch (dir?.toUpperCase()) {
    case "BUY": case "LONG": return "bg-green-900/30 border-green-800 text-green-400";
    case "SELL": case "SHORT": return "bg-red-900/30 border-red-800 text-red-400";
    default: return "bg-zinc-800/50 border-zinc-700 text-zinc-400";
  }
}

function outcomeColor(outcome?: string): string {
  switch (outcome?.toUpperCase()) {
    case "WIN": return "text-green-400 bg-green-900/30";
    case "LOSS": return "text-red-400 bg-red-900/30";
    case "BREAKEVEN": return "text-yellow-400 bg-yellow-900/30";
    default: return "text-blue-400 bg-blue-900/30";
  }
}

// CSS sparkline using div heights — simulates a mini price chart
function SparklineBar({ value, max, color }: { value: number; max: number; color: string }) {
  const height = max > 0 ? Math.max(4, (value / max) * 32) : 4;
  return (
    <div className="flex items-end gap-px h-8">
      <div
        className={`w-1 rounded-t ${color}`}
        style={{ height: `${height}px` }}
      />
    </div>
  );
}

// Mock "top traders" data derived from resolved signals with best performance
interface LeaderboardEntry {
  id: number;
  asset: string;
  asset_class: string;
  direction: string;
  entry_price: number;
  current_price?: number;
  target_price?: number;
  stop_loss?: number;
  pnl_pct: number;
  status: "ACTIVE" | "WIN" | "LOSS" | "BREAKEVEN";
  generated_at: string;
  confidence: number;
  regime?: string;
  daysLive: number;
}

export default function LeaderboardPageContent() {
  const [signals, setSignals] = useState<TradingSignal[]>([]);
  const [stats, setStats] = useState<SignalStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [assetFilter, setAssetFilter] = useState<string>("ALL");
  const [statusFilter, setStatusFilter] = useState<string>("");

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [signalsData, statsData] = await Promise.all([
        getSignals({ limit: 100, outcome: statusFilter || undefined }),
        getSignalStats(),
      ]);
      setSignals(signalsData.items);
      setStats(statsData);
    } catch (err) {
      console.error("Failed to load leaderboard data:", err);
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Derive leaderboard entries from signals
  const entries: LeaderboardEntry[] = signals.map((sig, idx) => {
    const direction = sig.final_signal?.toUpperCase() || sig.direction?.toUpperCase() || "";
    const isBuy = direction === "BUY" || direction === "LONG";
    const entry = sig.entry_price ?? 0;
    const target = sig.target_price ?? 0;
    const sl = sig.stop_loss ?? 0;

    // Simulate current price as a shift from entry (mock for demo)
    const priceShift = isBuy ? (target > 0 ? (target - entry) * 0.7 : entry * 0.02) : (target > 0 ? (entry - target) * 0.7 : -entry * 0.02);
    const currentPrice = entry + priceShift;

    const riskAmt = isBuy ? entry - sl : sl - entry;
    const rewardAmt = isBuy ? target - entry : entry - target;
    const rr = riskAmt > 0 ? rewardAmt / riskAmt : 0;

    const pnlPct = entry > 0 ? ((currentPrice - entry) / entry) * 100 * (isBuy ? 1 : -1) : 0;

    const statusMap: Record<string, LeaderboardEntry["status"]> = {
      WIN: "WIN",
      LOSS: "LOSS",
      BREAKEVEN: "BREAKEVEN",
    };
    const status = statusMap[sig.outcome?.toUpperCase() ?? ""] ?? "ACTIVE";

    const daysLive = sig.generated_at
      ? Math.floor((Date.now() - new Date(sig.generated_at).getTime()) / 86400000)
      : 0;

    return {
      id: sig.id ?? idx,
      asset: sig.asset,
      asset_class: sig.asset_class,
      direction,
      entry_price: entry,
      current_price: currentPrice,
      target_price: target,
      stop_loss: sl,
      pnl_pct: parseFloat(pnlPct.toFixed(2)),
      status,
      generated_at: sig.generated_at ?? "",
      confidence: sig.signal_confidence ?? 50,
      regime: sig.market_regime,
      daysLive,
    };
  });

  // Filter by asset class
  const filteredEntries = entries.filter((e) => {
    if (assetFilter !== "ALL" && e.asset_class.toUpperCase() !== assetFilter) return false;
    if (statusFilter && e.status !== statusFilter) return false;
    return true;
  });

  // Sort by pnl_pct desc
  const sortedEntries = [...filteredEntries].sort((a, b) => b.pnl_pct - a.pnl_pct);

  // Sparkline data — mock mini history based on pnl
  const sparklineMax = Math.max(...sortedEntries.map((e) => Math.abs(e.pnl_pct)), 1);

  const statusBadgeColor = (s: LeaderboardEntry["status"]) => {
    switch (s) {
      case "WIN": return "bg-green-900/50 text-green-400 border border-green-800";
      case "LOSS": return "bg-red-900/50 text-red-400 border border-red-800";
      case "BREAKEVEN": return "bg-yellow-900/50 text-yellow-400 border border-yellow-800";
      default: return "bg-blue-900/50 text-blue-400 border border-blue-800";
    }
  };

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="px-6 py-4 border-b border-zinc-800">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h1 className="text-white font-bold text-xl tracking-tight">LEADERBOARD</h1>
            <p className="text-zinc-500 text-xs mt-0.5">Top signals this week by asset</p>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
            <span className="text-green-400 text-xs font-medium">LIVE</span>
          </div>
        </div>

        {/* Filters */}
        <div className="flex items-center gap-3 flex-wrap">
          {/* Asset class filter */}
          <div className="flex gap-1">
            {ASSET_FILTERS.map((f) => (
              <button
                key={f}
                onClick={() => setAssetFilter(f)}
                className={`px-3 py-1.5 text-xs rounded transition-colors ${
                  assetFilter === f
                    ? "bg-zinc-700 text-white"
                    : "bg-zinc-800 text-zinc-400 hover:text-zinc-200"
                }`}
              >
                {f}
              </button>
            ))}
          </div>

          <div className="w-px h-4 bg-zinc-700" />

          {/* Status filter */}
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="bg-zinc-900 border border-zinc-700 text-zinc-300 text-xs rounded px-3 py-1.5 focus:outline-none"
          >
            <option value="">All outcomes</option>
            <option value="WIN">Winners</option>
            <option value="LOSS">Losers</option>
            <option value="BREAKEVEN">Breakeven</option>
            <option value="">Active</option>
          </select>
        </div>
      </div>

      {/* ─── Stats Overview ──────────────────────────────── */}
      {stats && (
        <div className="px-6 py-4 border-b border-zinc-800">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="bg-zinc-900/50 border border-zinc-800 rounded-lg p-4">
              <p className="text-zinc-500 text-xs uppercase mb-1 tracking-wider">Total Signals</p>
              <p className="text-white text-2xl font-bold">{stats.total_signals}</p>
              <p className="text-zinc-600 text-xs mt-1">
                {stats.active} active · {stats.resolved} resolved
              </p>
            </div>
            <div className="bg-zinc-900/50 border border-zinc-800 rounded-lg p-4">
              <p className="text-zinc-500 text-xs uppercase mb-1 tracking-wider">Win Rate</p>
              <p className={`text-2xl font-bold ${(stats.win_rate ?? 0) >= 50 ? "text-green-400" : "text-red-400"}`}>
                {stats.win_rate != null ? `${stats.win_rate}%` : "—"}
              </p>
              <p className="text-zinc-600 text-xs mt-1">of resolved signals</p>
            </div>
            <div className="bg-zinc-900/50 border border-zinc-800 rounded-lg p-4">
              <p className="text-zinc-500 text-xs uppercase mb-1 tracking-wider">Avg Confidence</p>
              <p className={`text-2xl font-bold ${(stats.avg_confidence ?? 0) >= 70 ? "text-green-400" : (stats.avg_confidence ?? 0) >= 50 ? "text-yellow-400" : "text-red-400"}`}>
                {stats.avg_confidence != null ? `${stats.avg_confidence}%` : "—"}
              </p>
              <p className="text-zinc-600 text-xs mt-1">ITPM WISH framework</p>
            </div>
            <div className="bg-zinc-900/50 border border-zinc-800 rounded-lg p-4">
              <p className="text-zinc-500 text-xs uppercase mb-1 tracking-wider">Top Regime</p>
              {Object.keys(stats.by_regime).length > 0 ? (
                <>
                  <p className="text-white text-xl font-bold">
                    {Object.entries(stats.by_regime).sort((a, b) => b[1] - a[1])[0][0]}
                  </p>
                  <p className="text-zinc-600 text-xs mt-1">
                    {Object.entries(stats.by_regime).sort((a, b) => b[1] - a[1])[0][1]} signals
                  </p>
                </>
              ) : (
                <p className="text-zinc-500 text-xl font-bold">—</p>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ─── Signals Table ──────────────────────────────── */}
      <div className="flex-1 overflow-y-auto px-6 py-4">
        {loading ? (
          <div className="flex items-center justify-center h-48">
            <p className="text-zinc-500 text-sm">Loading signals...</p>
          </div>
        ) : sortedEntries.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-48 gap-2">
            <p className="text-zinc-400 text-sm">No signals found</p>
            <p className="text-zinc-600 text-xs">Try adjusting your filters</p>
          </div>
        ) : (
          <>
            {/* Table header */}
            <div className="grid grid-cols-12 gap-2 px-4 py-2 border-b border-zinc-800 mb-2">
              <div className="col-span-2 text-zinc-600 text-xs uppercase tracking-wider">Asset</div>
              <div className="col-span-1 text-zinc-600 text-xs uppercase tracking-wider text-center">Dir</div>
              <div className="col-span-1.5 text-zinc-600 text-xs uppercase tracking-wider text-right">Entry</div>
              <div className="col-span-1.5 text-zinc-600 text-xs uppercase tracking-wider text-right">Target</div>
              <div className="col-span-1.5 text-zinc-600 text-xs uppercase tracking-wider text-right">Current</div>
              <div className="col-span-1 text-zinc-600 text-xs uppercase tracking-wider text-center">P&L%</div>
              <div className="col-span-1.5 text-zinc-600 text-xs uppercase tracking-wider text-center">Status</div>
              <div className="col-span-1.5 text-zinc-600 text-xs uppercase tracking-wider text-center">Sparkline</div>
            </div>

            {/* Rows */}
            <div className="space-y-1.5">
              {sortedEntries.map((entry, idx) => {
                const pnlColor = entry.pnl_pct > 0 ? "text-green-400" : entry.pnl_pct < 0 ? "text-red-400" : "text-zinc-400";
                const sparkColor = entry.pnl_pct > 0 ? "bg-green-400" : entry.pnl_pct < 0 ? "bg-red-400" : "bg-zinc-500";
                const rank = idx + 1;
                const rankColor = idx === 0 ? "text-yellow-400" : idx === 1 ? "text-zinc-300" : idx === 2 ? "text-orange-400" : "text-zinc-500";

                return (
                  <div
                    key={entry.id}
                    className="grid grid-cols-12 gap-2 items-center bg-zinc-900/40 hover:bg-zinc-900/70 border border-zinc-800/60 rounded-lg px-4 py-3 transition-colors"
                  >
                    {/* Rank + Asset */}
                    <div className="col-span-2 flex items-center gap-2">
                      <span className={`text-xs font-bold w-5 ${rankColor}`}>#{rank}</span>
                      <div>
                        <p className="text-white text-xs font-medium">{entry.asset}</p>
                        <p className="text-zinc-600 text-xs">{entry.asset_class}</p>
                      </div>
                    </div>

                    {/* Direction */}
                    <div className="col-span-1 flex justify-center">
                      <span className={`px-2 py-0.5 rounded text-xs font-bold border ${directionBg(entry.direction)}`}>
                        {entry.direction || "—"}
                      </span>
                    </div>

                    {/* Entry */}
                    <div className="col-span-1.5 text-right">
                      <span className="text-zinc-300 text-xs font-mono">
                        {entry.entry_price > 0 ? entry.entry_price.toFixed(entry.entry_price < 10 ? 4 : 2) : "—"}
                      </span>
                    </div>

                    {/* Target */}
                    <div className="col-span-1.5 text-right">
                      <span className="text-green-400 text-xs font-mono">
                        {entry.target_price ? `↑${entry.target_price.toFixed(entry.target_price < 10 ? 4 : 2)}` : "—"}
                      </span>
                    </div>

                    {/* Current */}
                    <div className="col-span-1.5 text-right">
                      <span className={`text-xs font-mono font-medium ${pnlColor}`}>
                        {entry.current_price ? entry.current_price.toFixed(entry.current_price < 10 ? 4 : 2) : "—"}
                      </span>
                    </div>

                    {/* P&L% */}
                    <div className="col-span-1 text-center">
                      <span className={`text-sm font-mono font-bold ${pnlColor}`}>
                        {entry.pnl_pct > 0 ? "+" : ""}{entry.pnl_pct}%
                      </span>
                    </div>

                    {/* Status */}
                    <div className="col-span-1.5 flex justify-center">
                      <span className={`px-2 py-0.5 rounded text-xs font-medium border ${statusBadgeColor(entry.status)}`}>
                        {entry.status}
                      </span>
                    </div>

                    {/* Sparkline */}
                    <div className="col-span-1.5 flex items-center justify-center">
                      <SparklineBar
                        value={Math.abs(entry.pnl_pct)}
                        max={sparklineMax}
                        color={sparkColor}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
