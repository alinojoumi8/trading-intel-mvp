"use client";

import { useEffect, useState, useCallback } from "react";
import {
  getOutcomeStats,
  getTradeOutcomes,
  createOrUpdateOutcome,
  OutcomeStats,
  TradeOutcome,
} from "@/lib/api";

type DateRange = "1M" | "3M" | "6M" | "1Y" | "ALL";

export default function PerformancePageContent() {
  const [stats, setStats] = useState<OutcomeStats | null>(null);
  const [outcomes, setOutcomes] = useState<TradeOutcome[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);

  // Filters
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [instrumentFilter, setInstrumentFilter] = useState<string>("");
  const [dateRange, setDateRange] = useState<DateRange>("ALL");

  // Outcome edit state
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editStatus, setEditStatus] = useState<string>("open");
  const [editPnlPips, setEditPnlPips] = useState<string>("");
  const [editNote, setEditNote] = useState<string>("");

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [statsData, outcomesData] = await Promise.all([
        getOutcomeStats(),
        getTradeOutcomes({
          status: statusFilter || undefined,
          instrument: instrumentFilter || undefined,
          limit: 100,
        }),
      ]);
      setStats(statsData);
      setOutcomes(outcomesData.items);
      setTotal(outcomesData.total);
    } catch (err) {
      console.error("Failed to load performance data:", err);
    } finally {
      setLoading(false);
    }
  }, [statusFilter, instrumentFilter, dateRange]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleResolve = async (outcome: TradeOutcome, status: string) => {
    try {
      await createOrUpdateOutcome({
        content_item_id: outcome.content_item_id,
        status,
        result_note: outcome.result_note,
        pnl_pips: outcome.pnl_pips,
      });
      await loadData();
    } catch (err) {
      console.error("Failed to update outcome:", err);
    }
  };

  const handleSaveEdit = async (outcome: TradeOutcome) => {
    try {
      await createOrUpdateOutcome({
        content_item_id: outcome.content_item_id,
        status: editStatus,
        result_note: editNote || undefined,
        pnl_pips: editPnlPips ? parseFloat(editPnlPips) : undefined,
      });
      setEditingId(null);
      await loadData();
    } catch (err) {
      console.error("Failed to save outcome:", err);
    }
  };

  const startEdit = (outcome: TradeOutcome) => {
    setEditingId(outcome.id);
    setEditStatus(outcome.status);
    setEditPnlPips(outcome.pnl_pips?.toString() ?? "");
    setEditNote(outcome.result_note ?? "");
  };

  // Compute best/worst instrument
  const bestInstrument = stats
    ? Object.entries(stats.by_instrument)
        .filter(([, d]) => d.win_rate !== null && d.total >= 3)
        .sort((a, b) => (b[1].win_rate ?? 0) - (a[1].win_rate ?? 0))[0]
    : null;

  const worstInstrument = stats
    ? Object.entries(stats.by_instrument)
        .filter(([, d]) => d.win_rate !== null && d.total >= 3)
        .sort((a, b) => (a[1].win_rate ?? 0) - (b[1].win_rate ?? 0))[0]
    : null;

  const statusColor = (status: string) => {
    switch (status) {
      case "won": return "text-green-400 bg-green-900/30";
      case "lost": return "text-red-400 bg-red-900/30";
      case "breakeven": return "text-yellow-400 bg-yellow-900/30";
      case "cancelled": return "text-zinc-400 bg-zinc-800/50";
      default: return "text-blue-400 bg-blue-900/30";
    }
  };

  // ─── Dashboard Metrics ───────────────────────────────────────────────────
  const totalResolved = stats ? stats.won_count + stats.lost_count + stats.breakeven_count : 0;
  const winPct = stats && stats.resolved_count > 0 ? (stats.won_count / stats.resolved_count) * 100 : 0;
  const lossPct = stats && stats.resolved_count > 0 ? (stats.lost_count / stats.resolved_count) * 100 : 0;
  const bePct = stats && stats.resolved_count > 0 ? (stats.breakeven_count / stats.resolved_count) * 100 : 0;

  // Compute max bar height for instrument chart
  const allInstrumentWR = stats
    ? Object.entries(stats.by_instrument).map(([, d]) => d.win_rate ?? 0)
    : [];
  const maxWR = Math.max(...allInstrumentWR, 1);

  // Sort instruments by win rate
  const sortedInstruments = stats
    ? Object.entries(stats.by_instrument)
        .filter(([, d]) => d.total > 0)
        .sort((a, b) => (b[1].win_rate ?? 0) - (a[1].win_rate ?? 0))
    : [];

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="px-6 py-4 border-b border-zinc-800">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h1 className="text-white font-bold text-xl tracking-tight">PERFORMANCE</h1>
            <p className="text-zinc-500 text-xs mt-0.5">Trade setup outcomes & win rates</p>
          </div>
          <div className="flex items-center gap-2">
            <div className="flex items-center gap-1.5">
              <div className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
              <span className="text-green-400 text-xs font-medium">LIVE</span>
            </div>
          </div>
        </div>

        {/* Filters */}
        <div className="flex items-center gap-3 flex-wrap">
          <select
            value={statusFilter}
            onChange={e => setStatusFilter(e.target.value)}
            className="bg-zinc-900 border border-zinc-700 text-zinc-300 text-xs rounded px-3 py-1.5 focus:outline-none"
          >
            <option value="">All statuses</option>
            <option value="open">Open</option>
            <option value="won">Won</option>
            <option value="lost">Lost</option>
            <option value="breakeven">Breakeven</option>
            <option value="cancelled">Cancelled</option>
          </select>

          <input
            type="text"
            value={instrumentFilter}
            onChange={e => setInstrumentFilter(e.target.value.toUpperCase())}
            placeholder="Instrument (e.g. EURUSD)"
            className="bg-zinc-900 border border-zinc-700 text-zinc-300 text-xs rounded px-3 py-1.5 focus:outline-none w-40"
          />

          <div className="flex gap-1">
            {(["1M", "3M", "6M", "1Y", "ALL"] as DateRange[]).map(range => (
              <button
                key={range}
                onClick={() => setDateRange(range)}
                className={`px-2 py-1 text-xs rounded transition-colors ${
                  dateRange === range
                    ? "bg-zinc-700 text-white"
                    : "bg-zinc-800 text-zinc-400 hover:text-zinc-200"
                }`}
              >
                {range}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* ─── KPI Cards ─────────────────────────────────────────────────── */}
      {stats && (
        <div className="px-6 py-5 border-b border-zinc-800">
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            {/* Total Setups */}
            <div className="bg-zinc-900/50 border border-zinc-800 rounded-lg p-4">
              <p className="text-zinc-500 text-xs uppercase mb-1 tracking-wider">Total Setups</p>
              <p className="text-white text-2xl font-bold">{stats.total_setups}</p>
              <div className="flex gap-2 mt-1">
                <span className="text-zinc-600 text-xs">{stats.open_count} open</span>
                <span className="text-zinc-700">·</span>
                <span className="text-zinc-600 text-xs">{stats.resolved_count} resolved</span>
              </div>
            </div>

            {/* Win Rate */}
            <div className="bg-zinc-900/50 border border-zinc-800 rounded-lg p-4">
              <p className="text-zinc-500 text-xs uppercase mb-1 tracking-wider">Win Rate</p>
              <p className={`text-2xl font-bold ${winPct >= 50 ? "text-green-400" : "text-red-400"}`}>
                {stats.win_rate != null ? `${stats.win_rate}%` : "—"}
              </p>
              <p className="text-zinc-600 text-xs mt-1">
                {stats.won_count}W / {stats.lost_count}L
              </p>
            </div>

            {/* Avg Pips */}
            <div className="bg-zinc-900/50 border border-zinc-800 rounded-lg p-4">
              <p className="text-zinc-500 text-xs uppercase mb-1 tracking-wider">Avg Pips</p>
              <p className={`text-2xl font-bold ${
                (stats.avg_pnl_pips ?? 0) > 0 ? "text-green-400" :
                (stats.avg_pnl_pips ?? 0) < 0 ? "text-red-400" : "text-zinc-300"
              }`}>
                {stats.avg_pnl_pips != null
                  ? `${stats.avg_pnl_pips > 0 ? "+" : ""}${stats.avg_pnl_pips.toFixed(1)}`
                  : "—"}
              </p>
              <p className="text-zinc-600 text-xs mt-1">per setup</p>
            </div>

            {/* Avg R:R */}
            <div className="bg-zinc-900/50 border border-zinc-800 rounded-lg p-4">
              <p className="text-zinc-500 text-xs uppercase mb-1 tracking-wider">Avg R:R</p>
              <p className="text-white text-2xl font-bold">
                {stats.avg_risk_reward != null ? `${stats.avg_risk_reward}:1` : "—"}
              </p>
              <p className="text-zinc-600 text-xs mt-1">risk reward ratio</p>
            </div>

            {/* Best Instrument */}
            <div className="bg-zinc-900/50 border border-zinc-800 rounded-lg p-4">
              <p className="text-zinc-500 text-xs uppercase mb-1 tracking-wider">Best Instrument</p>
              {bestInstrument ? (
                <>
                  <p className="text-green-400 text-xl font-bold">{bestInstrument[0]}</p>
                  <p className="text-zinc-600 text-xs mt-1">
                    {bestInstrument[1].win_rate}% WR · {bestInstrument[1].total} setups
                  </p>
                </>
              ) : (
                <p className="text-zinc-500 text-xl font-bold">—</p>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ─── Visual Bar Chart: Wins vs Losses ──────────────────────────── */}
      {stats && stats.resolved_count > 0 && (
        <div className="px-6 py-5 border-b border-zinc-800">
          <h3 className="text-zinc-400 text-xs font-semibold uppercase tracking-wider mb-4">
            Win / Loss Breakdown
          </h3>
          <div className="flex items-end gap-3 mb-2">
            {/* Stacked bar */}
            <div className="flex-1 h-36 flex rounded overflow-hidden gap-px bg-zinc-800">
              {/* Win segment */}
              <div
                className="bg-green-500/80 relative group"
                style={{ width: `${winPct}%`, minWidth: winPct > 0 ? "4px" : "0" }}
              >
                <div className="absolute -top-8 left-1/2 -translate-x-1/2 text-green-400 text-xs font-bold opacity-0 group-hover:opacity-100 transition-opacity">
                  {winPct.toFixed(1)}%
                </div>
                <div
                  className="absolute bottom-0 left-0 right-0 bg-green-500/20 flex items-end justify-center pb-1 opacity-0 group-hover:opacity-100 transition-opacity"
                  style={{ height: `${(winPct / 100) * 100}%` }}
                >
                  <span className="text-green-300 text-xs font-bold">{stats.won_count}W</span>
                </div>
              </div>
              {/* Loss segment */}
              <div
                className="bg-red-500/80 relative group"
                style={{ width: `${lossPct}%`, minWidth: lossPct > 0 ? "4px" : "0" }}
              >
                <div className="absolute -top-8 left-1/2 -translate-x-1/2 text-red-400 text-xs font-bold opacity-0 group-hover:opacity-100 transition-opacity">
                  {lossPct.toFixed(1)}%
                </div>
                <div
                  className="absolute bottom-0 left-0 right-0 bg-red-500/20 flex items-end justify-center pb-1 opacity-0 group-hover:opacity-100 transition-opacity"
                  style={{ height: `${(lossPct / 100) * 100}%` }}
                >
                  <span className="text-red-300 text-xs font-bold">{stats.lost_count}L</span>
                </div>
              </div>
              {/* Breakeven segment */}
              {bePct > 0 && (
                <div
                  className="bg-yellow-500/60 relative group"
                  style={{ width: `${bePct}%`, minWidth: "4px" }}
                >
                  <div className="absolute -top-8 left-1/2 -translate-x-1/2 text-yellow-400 text-xs font-bold opacity-0 group-hover:opacity-100 transition-opacity">
                    {bePct.toFixed(1)}%
                  </div>
                </div>
              )}
            </div>

            {/* Legend + stats */}
            <div className="flex flex-col gap-3 w-32">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 rounded-sm bg-green-500/80" />
                  <span className="text-zinc-400 text-xs">Win</span>
                </div>
                <span className="text-green-400 text-sm font-bold">{winPct.toFixed(0)}%</span>
              </div>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 rounded-sm bg-red-500/80" />
                  <span className="text-zinc-400 text-xs">Loss</span>
                </div>
                <span className="text-red-400 text-sm font-bold">{lossPct.toFixed(0)}%</span>
              </div>
              {bePct > 0 && (
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <div className="w-3 h-3 rounded-sm bg-yellow-500/60" />
                    <span className="text-zinc-400 text-xs">BE</span>
                  </div>
                  <span className="text-yellow-400 text-sm font-bold">{bePct.toFixed(0)}%</span>
                </div>
              )}
              <div className="border-t border-zinc-800 pt-2 mt-1">
                <div className="flex justify-between">
                  <span className="text-zinc-500 text-xs">Total</span>
                  <span className="text-zinc-300 text-xs font-medium">{totalResolved}</span>
                </div>
                {worstInstrument && (
                  <div className="flex justify-between mt-1">
                    <span className="text-zinc-500 text-xs">Worst</span>
                    <span className="text-red-400 text-xs">{worstInstrument[0]}</span>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ─── Per-Instrument Bar Chart ───────────────────────────────────── */}
      {sortedInstruments.length > 0 && (
        <div className="px-6 py-5 border-b border-zinc-800">
          <h3 className="text-zinc-400 text-xs font-semibold uppercase tracking-wider mb-4">
            Performance by Instrument
          </h3>
          <div className="flex items-end gap-2 h-44">
            {sortedInstruments.map(([inst, data]) => {
              const barHeight = maxWR > 0 ? ((data.win_rate ?? 0) / maxWR) * 100 : 0;
              const wr = data.win_rate ?? 0;
              const color = wr >= 60 ? "text-green-400" : wr >= 50 ? "text-green-300" : wr >= 40 ? "text-yellow-400" : "text-red-400";
              const barColor = wr >= 60 ? "bg-green-500" : wr >= 50 ? "bg-green-400" : wr >= 40 ? "bg-yellow-500" : "bg-red-500";
              return (
                <div key={inst} className="flex-1 flex flex-col items-center gap-1 group">
                  <div className="relative w-full flex items-end justify-center" style={{ height: "160px" }}>
                    {/* 50% reference line */}
                    <div
                      className="absolute w-full border-t border-dashed border-zinc-700"
                      style={{ bottom: "50%" }}
                    />
                    {/* Bar */}
                    <div
                      className={`w-8 rounded-t transition-all ${barColor} opacity-80 group-hover:opacity-100`}
                      style={{ height: `${barHeight}%`, minHeight: barHeight > 0 ? "4px" : "0" }}
                    />
                    {/* Tooltip */}
                    <div className="absolute -top-16 left-1/2 -translate-x-1/2 bg-zinc-800 border border-zinc-600 rounded px-2 py-1 opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none whitespace-nowrap z-10">
                      <p className={`text-xs font-bold ${color}`}>{wr}% WR</p>
                      <p className="text-zinc-400 text-xs">{data.total} setups</p>
                    </div>
                  </div>
                  {/* Label */}
                  <span className="text-zinc-500 text-xs text-center truncate w-full">{inst}</span>
                  <span className={`text-xs font-bold ${color}`}>{wr}%</span>
                </div>
              );
            })}
          </div>
          {/* X-axis labels handled above */}
        </div>
      )}

      {/* ─── Stats Breakdown Grid ────────────────────────────────────────── */}
      {stats && (Object.keys(stats.by_instrument).length > 0 || Object.keys(stats.by_direction).length > 0) && (
        <div className="px-6 py-4 border-b border-zinc-800">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {/* By Instrument */}
            {Object.keys(stats.by_instrument).length > 0 && (
              <div>
                <h3 className="text-zinc-400 text-xs font-semibold uppercase tracking-wider mb-3">By Instrument</h3>
                <div className="space-y-2">
                  {Object.entries(stats.by_instrument).map(([inst, data]) => (
                    <div key={inst} className="flex items-center justify-between">
                      <span className="text-zinc-300 text-xs">{inst}</span>
                      <div className="flex items-center gap-2">
                        <div className="w-24 h-1.5 bg-zinc-800 rounded overflow-hidden">
                          <div
                            className="h-full bg-green-500 rounded transition-all"
                            style={{ width: `${data.win_rate ?? 0}%` }}
                          />
                        </div>
                        <span className={`text-xs font-mono w-12 text-right ${
                          (data.win_rate ?? 0) >= 50 ? "text-green-400" : "text-red-400"
                        }`}>
                          {data.win_rate != null ? `${data.win_rate}%` : "—"}
                        </span>
                        <span className="text-zinc-600 text-xs w-8 text-right">{data.total}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* By Direction */}
            {Object.keys(stats.by_direction).length > 0 && (
              <div>
                <h3 className="text-zinc-400 text-xs font-semibold uppercase tracking-wider mb-3">By Direction</h3>
                <div className="space-y-2">
                  {Object.entries(stats.by_direction).map(([dir, data]) => (
                    <div key={dir} className="flex items-center justify-between">
                      <span className={`text-xs font-medium ${
                        dir === "long" ? "text-green-400" : dir === "short" ? "text-red-400" : "text-zinc-300"
                      }`}>
                        {dir.toUpperCase()}
                      </span>
                      <div className="flex items-center gap-2">
                        <div className="w-24 h-1.5 bg-zinc-800 rounded overflow-hidden">
                          <div
                            className="h-full bg-green-500 rounded transition-all"
                            style={{ width: `${data.win_rate ?? 0}%` }}
                          />
                        </div>
                        <span className={`text-xs font-mono w-12 text-right ${
                          (data.win_rate ?? 0) >= 50 ? "text-green-400" : "text-red-400"
                        }`}>
                          {data.win_rate != null ? `${data.win_rate}%` : "—"}
                        </span>
                        <span className="text-zinc-600 text-xs w-8 text-right">{data.total}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* By Timeframe */}
            {Object.keys(stats.by_timeframe).length > 0 && (
              <div>
                <h3 className="text-zinc-400 text-xs font-semibold uppercase tracking-wider mb-3">By Timeframe</h3>
                <div className="space-y-2">
                  {Object.entries(stats.by_timeframe).map(([tf, data]) => (
                    <div key={tf} className="flex items-center justify-between">
                      <span className="text-zinc-300 text-xs">{tf.toUpperCase()}</span>
                      <div className="flex items-center gap-2">
                        <div className="w-24 h-1.5 bg-zinc-800 rounded overflow-hidden">
                          <div
                            className="h-full bg-green-500 rounded transition-all"
                            style={{ width: `${data.win_rate ?? 0}%` }}
                          />
                        </div>
                        <span className={`text-xs font-mono w-12 text-right ${
                          (data.win_rate ?? 0) >= 50 ? "text-green-400" : "text-red-400"
                        }`}>
                          {data.win_rate != null ? `${data.win_rate}%` : "—"}
                        </span>
                        <span className="text-zinc-600 text-xs w-8 text-right">{data.total}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ─── Outcomes Table ───────────────────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto px-6 py-4">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-white font-semibold text-sm">
            Setups
            <span className="text-zinc-500 font-normal text-xs ml-2">({total} total)</span>
          </h2>
        </div>

        {loading ? (
          <div className="flex items-center justify-center h-32">
            <p className="text-zinc-500 text-sm">Loading...</p>
          </div>
        ) : outcomes.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-32 gap-2">
            <p className="text-zinc-400 text-sm">No trade outcomes yet</p>
            <p className="text-zinc-600 text-xs">Track your setup outcomes to see performance stats</p>
          </div>
        ) : (
          <div className="space-y-2">
            {outcomes.map(outcome => (
              <div
                key={outcome.id}
                className="bg-zinc-900/50 border border-zinc-800 rounded-lg px-4 py-3 flex items-center justify-between gap-4"
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-white text-xs font-medium truncate">
                      {outcome.content_title || `Setup #${outcome.content_item_id}`}
                    </span>
                    {outcome.instrument_symbol && (
                      <span className="px-1.5 py-0.5 bg-zinc-800 text-zinc-400 text-xs rounded">
                        {outcome.instrument_symbol}
                      </span>
                    )}
                    {editingId === outcome.id ? (
                      <select
                        value={editStatus}
                        onChange={e => setEditStatus(e.target.value)}
                        className="bg-zinc-800 border border-zinc-600 text-zinc-300 text-xs rounded px-2 py-0.5"
                      >
                        <option value="open">Open</option>
                        <option value="won">Won</option>
                        <option value="lost">Lost</option>
                        <option value="breakeven">Breakeven</option>
                        <option value="cancelled">Cancelled</option>
                      </select>
                    ) : (
                      <span className={`px-2 py-0.5 rounded text-xs font-medium ${statusColor(outcome.status)}`}>
                        {outcome.status.toUpperCase()}
                      </span>
                    )}
                  </div>

                  {outcome.result_note && (
                    <p className="text-zinc-500 text-xs truncate">{outcome.result_note}</p>
                  )}

                  <div className="flex items-center gap-3 mt-1 text-xs text-zinc-500">
                    {outcome.actual_entry && <span>Entry: {outcome.actual_entry}</span>}
                    {outcome.actual_sl && <span>SL: {outcome.actual_sl}</span>}
                    {outcome.actual_tp && <span>TP: {outcome.actual_tp}</span>}
                    {outcome.outcome_date && (
                      <span>{new Date(outcome.outcome_date).toLocaleDateString()}</span>
                    )}
                  </div>
                </div>

                <div className="flex items-center gap-3 shrink-0">
                  {outcome.pnl_pips != null && (
                    <span className={`text-sm font-mono font-bold ${
                      outcome.pnl_pips > 0 ? "text-green-400" : outcome.pnl_pips < 0 ? "text-red-400" : "text-zinc-400"
                    }`}>
                      {outcome.pnl_pips > 0 ? "+" : ""}{outcome.pnl_pips} pips
                    </span>
                  )}

                  {editingId === outcome.id ? (
                    <div className="flex items-center gap-2">
                      <input
                        type="number"
                        value={editPnlPips}
                        onChange={e => setEditPnlPips(e.target.value)}
                        placeholder="Pnl pips"
                        className="bg-zinc-800 border border-zinc-600 text-zinc-300 text-xs rounded px-2 py-1 w-20"
                      />
                      <input
                        type="text"
                        value={editNote}
                        onChange={e => setEditNote(e.target.value)}
                        placeholder="Note"
                        className="bg-zinc-800 border border-zinc-600 text-zinc-300 text-xs rounded px-2 py-1 w-28"
                      />
                      <button
                        onClick={() => handleSaveEdit(outcome)}
                        className="px-2 py-1 bg-green-600 hover:bg-green-500 text-white text-xs rounded"
                      >
                        Save
                      </button>
                      <button
                        onClick={() => setEditingId(null)}
                        className="px-2 py-1 bg-zinc-700 hover:bg-zinc-600 text-zinc-300 text-xs rounded"
                      >
                        Cancel
                      </button>
                    </div>
                  ) : (
                    <button
                      onClick={() => startEdit(outcome)}
                      className="px-2 py-1 bg-zinc-800 hover:bg-zinc-700 text-zinc-400 hover:text-zinc-200 text-xs rounded transition-colors"
                    >
                      Edit
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
