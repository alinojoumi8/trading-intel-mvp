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

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="px-6 py-4 border-b border-zinc-800">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h1 className="text-white font-bold text-xl tracking-tight">PERFORMANCE</h1>
            <p className="text-zinc-500 text-xs mt-0.5">Trade setup outcomes &amp; win rates</p>
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

      {/* Summary Cards */}
      {stats && (
        <div className="px-6 py-4 border-b border-zinc-800">
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            <div className="bg-zinc-900/50 border border-zinc-800 rounded-lg p-4">
              <p className="text-zinc-500 text-xs uppercase mb-1">Total Setups</p>
              <p className="text-white text-2xl font-bold">{stats.total_setups}</p>
              <p className="text-zinc-600 text-xs mt-1">
                {stats.open_count} open · {stats.resolved_count} resolved
              </p>
            </div>

            <div className="bg-zinc-900/50 border border-zinc-800 rounded-lg p-4">
              <p className="text-zinc-500 text-xs uppercase mb-1">Win Rate</p>
              <p className={`text-2xl font-bold ${(stats.win_rate ?? 0) >= 50 ? "text-green-400" : "text-red-400"}`}>
                {stats.win_rate != null ? `${stats.win_rate}%` : "—"}
              </p>
              <p className="text-zinc-600 text-xs mt-1">
                {stats.won_count}W / {stats.lost_count}L
              </p>
            </div>

            <div className="bg-zinc-900/50 border border-zinc-800 rounded-lg p-4">
              <p className="text-zinc-500 text-xs uppercase mb-1">Avg R:R</p>
              <p className="text-white text-2xl font-bold">
                {stats.avg_risk_reward != null ? `${stats.avg_risk_reward}:1` : "—"}
              </p>
              <p className="text-zinc-600 text-xs mt-1">Risk reward ratio</p>
            </div>

            <div className="bg-zinc-900/50 border border-zinc-800 rounded-lg p-4">
              <p className="text-zinc-500 text-xs uppercase mb-1">Best Instrument</p>
              {bestInstrument ? (
                <>
                  <p className="text-green-400 text-xl font-bold">{bestInstrument[0]}</p>
                  <p className="text-zinc-600 text-xs mt-1">{bestInstrument[1].win_rate}% WR ({bestInstrument[1].total} setups)</p>
                </>
              ) : (
                <p className="text-zinc-500 text-xl font-bold">—</p>
              )}
            </div>

            <div className="bg-zinc-900/50 border border-zinc-800 rounded-lg p-4">
              <p className="text-zinc-500 text-xs uppercase mb-1">Worst Instrument</p>
              {worstInstrument ? (
                <>
                  <p className="text-red-400 text-xl font-bold">{worstInstrument[0]}</p>
                  <p className="text-zinc-600 text-xs mt-1">{worstInstrument[1].win_rate}% WR ({worstInstrument[1].total} setups)</p>
                </>
              ) : (
                <p className="text-zinc-500 text-xl font-bold">—</p>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Stats Breakdown */}
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

      {/* Outcomes Table */}
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
