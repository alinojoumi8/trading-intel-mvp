"use client";

import { useEffect, useState, useCallback } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";
import {
  getV3BacktestRuns,
  getV3BacktestRunDetail,
  getV3BacktestSignals,
  getV3EquityCurve,
  V3BacktestRunSummary,
  V3BacktestRunDetail,
  V3BacktestSignal,
  V3EquityCurve,
} from "@/lib/api";

// ─── Color helpers ─────────────────────────────────────────────────────────────

function pctColor(v: number | null | undefined): string {
  if (v === null || v === undefined) return "text-zinc-500";
  if (v > 0) return "text-green-400";
  if (v < 0) return "text-red-400";
  return "text-zinc-400";
}

function winRateColor(rate: number | null): string {
  if (rate === null) return "text-zinc-500";
  if (rate >= 0.55) return "text-green-400";
  if (rate >= 0.45) return "text-yellow-400";
  return "text-red-400";
}

function outcomeBadge(outcome: string | null): string {
  switch (outcome) {
    case "WIN": return "bg-green-900/60 text-green-300 border-green-700";
    case "LOSS": return "bg-red-900/60 text-red-300 border-red-700";
    case "OPEN": return "bg-yellow-900/60 text-yellow-300 border-yellow-700";
    case "ENTRY_NOT_TRIGGERED": return "bg-zinc-800 text-zinc-500 border-zinc-700";
    default: return "bg-zinc-800 text-zinc-600 border-zinc-700";
  }
}

function signalColor(signal: string | null): string {
  switch (signal) {
    case "BUY": return "text-green-400";
    case "SELL": return "text-red-400";
    case "WATCH_LIST": return "text-yellow-400";
    default: return "text-zinc-500";
  }
}

function formatPct(v: number | null | undefined, digits = 2): string {
  if (v === null || v === undefined) return "—";
  return `${v > 0 ? "+" : ""}${v.toFixed(digits)}%`;
}

// ─── Per-Asset Card ────────────────────────────────────────────────────────────

function AssetCard({
  asset,
  data,
}: {
  asset: string;
  data: {
    total_signals: number;
    actionable: number;
    closed: number;
    wins: number;
    losses: number;
    win_rate: number | null;
    avg_r: number | null;
    total_pnl_pct: number;
  };
}) {
  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-4">
      <div className="flex items-baseline justify-between mb-3">
        <h3 className="text-white font-bold text-lg">{asset}</h3>
        <span className="text-zinc-600 text-xs">{data.total_signals} signals</span>
      </div>
      <div className="space-y-2">
        <div className="flex justify-between text-sm">
          <span className="text-zinc-500">Win Rate</span>
          <span className={`font-mono ${winRateColor(data.win_rate)}`}>
            {data.win_rate !== null ? `${(data.win_rate * 100).toFixed(0)}%` : "—"}
            <span className="text-zinc-600 text-xs ml-1">({data.wins}/{data.closed})</span>
          </span>
        </div>
        <div className="flex justify-between text-sm">
          <span className="text-zinc-500">Avg R</span>
          <span className={`font-mono ${pctColor(data.avg_r)}`}>
            {data.avg_r !== null ? data.avg_r.toFixed(2) : "—"}
          </span>
        </div>
        <div className="flex justify-between text-sm">
          <span className="text-zinc-500">Total P&amp;L</span>
          <span className={`font-mono font-bold ${pctColor(data.total_pnl_pct)}`}>
            {formatPct(data.total_pnl_pct)}
          </span>
        </div>
        <div className="border-t border-zinc-800 pt-2 mt-2 grid grid-cols-3 gap-2 text-xs">
          <div><span className="text-zinc-600">Actionable: </span><span className="text-zinc-300">{data.actionable}</span></div>
          <div><span className="text-zinc-600">Open: </span><span className="text-zinc-300">{data.actionable - data.closed}</span></div>
          <div><span className="text-zinc-600">Closed: </span><span className="text-zinc-300">{data.closed}</span></div>
        </div>
      </div>
    </div>
  );
}

// ─── Equity Curve Chart ────────────────────────────────────────────────────────

function EquityCurveChart({ curve }: { curve: V3EquityCurve | null }) {
  if (!curve || curve.points.length === 0) {
    return (
      <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-5">
        <div className="text-zinc-400 text-xs font-semibold uppercase tracking-wider mb-3">
          Equity Curve
        </div>
        <div className="text-zinc-600 text-sm py-12 text-center">
          No closed trades yet — equity curve will appear as trades complete
        </div>
      </div>
    );
  }

  const chartData = curve.points.map((p, i) => ({
    idx: i,
    date: p.date.slice(0, 10),
    cumulative: p.cumulative_pct,
    asset: p.asset,
  }));

  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-5">
      <div className="flex items-center justify-between mb-3">
        <div>
          <div className="text-zinc-400 text-xs font-semibold uppercase tracking-wider">
            Equity Curve
          </div>
          <div className="text-zinc-600 text-xs mt-0.5">
            Cumulative P&amp;L across {curve.trades_count} closed trades · Max drawdown {curve.max_drawdown_pct.toFixed(1)}%
          </div>
        </div>
        <div className={`text-xl font-bold font-mono ${pctColor(curve.final_pnl_pct)}`}>
          {formatPct(curve.final_pnl_pct, 1)}
        </div>
      </div>
      <ResponsiveContainer width="100%" height={260}>
        <LineChart data={chartData} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
          <XAxis
            dataKey="date"
            tick={{ fill: "#71717a", fontSize: 10 }}
            tickFormatter={(v) => v.slice(5)}
            interval="preserveStartEnd"
          />
          <YAxis
            tick={{ fill: "#71717a", fontSize: 10 }}
            tickFormatter={(v) => `${v > 0 ? "+" : ""}${v.toFixed(1)}%`}
          />
          <Tooltip
            contentStyle={{ background: "#18181b", border: "1px solid #3f3f46", borderRadius: 6 }}
            labelStyle={{ color: "#a1a1aa", fontSize: 11 }}
            itemStyle={{ fontSize: 11 }}
            formatter={(value: number) => [`${value > 0 ? "+" : ""}${value.toFixed(2)}%`, "Cumulative"]}
          />
          <ReferenceLine y={0} stroke="#52525b" strokeDasharray="4 4" />
          <Line
            type="monotone"
            dataKey="cumulative"
            stroke="#22c55e"
            strokeWidth={2}
            dot={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

// ─── Signals Table ─────────────────────────────────────────────────────────────

function SignalsTable({ signals }: { signals: V3BacktestSignal[] }) {
  if (signals.length === 0) {
    return (
      <div className="text-zinc-600 text-sm py-8 text-center">
        No signals to display
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b border-zinc-800 text-zinc-500">
            <th className="text-left pb-2 pr-2">Date</th>
            <th className="text-left pb-2 pr-2">Asset</th>
            <th className="text-left pb-2 pr-2">Signal</th>
            <th className="text-right pb-2 pr-2">Conf</th>
            <th className="text-left pb-2 pr-2">Regime</th>
            <th className="text-left pb-2 pr-2">Bias</th>
            <th className="text-left pb-2 pr-2">FSM</th>
            <th className="text-right pb-2 pr-2">Entry</th>
            <th className="text-right pb-2 pr-2">Stop</th>
            <th className="text-right pb-2 pr-2">Target</th>
            <th className="text-left pb-2 pr-2">Outcome</th>
            <th className="text-right pb-2 pr-2">P&amp;L</th>
            <th className="text-right pb-2">R</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-zinc-800/40">
          {signals.map((s) => (
            <tr key={s.id} className="hover:bg-zinc-800/30">
              <td className="py-1.5 pr-2 text-zinc-500 whitespace-nowrap">
                {s.as_of_date.slice(0, 10)}
              </td>
              <td className="py-1.5 pr-2 text-zinc-300">{s.asset}</td>
              <td className={`py-1.5 pr-2 font-semibold ${signalColor(s.final_signal)}`}>
                {s.final_signal ?? "—"}
              </td>
              <td className="py-1.5 pr-2 text-right text-zinc-400 font-mono">
                {s.signal_confidence ?? "—"}
              </td>
              <td className="py-1.5 pr-2 text-zinc-400 text-[10px]">
                {s.market_regime?.replace(/_/g, " ").slice(0, 10) ?? "—"}
              </td>
              <td className="py-1.5 pr-2 text-zinc-400">{s.fundamental_bias?.slice(0, 4) ?? "—"}</td>
              <td className="py-1.5 pr-2 font-mono text-zinc-400">
                {s.fsm_composite_score !== null ? s.fsm_composite_score.toFixed(0) : "—"}
              </td>
              <td className="py-1.5 pr-2 text-right font-mono text-zinc-300">
                {s.entry_price?.toFixed(4) ?? "—"}
              </td>
              <td className="py-1.5 pr-2 text-right font-mono text-zinc-500">
                {s.stop_loss?.toFixed(4) ?? "—"}
              </td>
              <td className="py-1.5 pr-2 text-right font-mono text-zinc-500">
                {s.target_price?.toFixed(4) ?? "—"}
              </td>
              <td className="py-1.5 pr-2">
                {s.outcome ? (
                  <span className={`px-1.5 py-0.5 rounded text-[10px] border ${outcomeBadge(s.outcome)}`}>
                    {s.outcome === "ENTRY_NOT_TRIGGERED" ? "NO TRIG" : s.outcome}
                  </span>
                ) : "—"}
              </td>
              <td className={`py-1.5 pr-2 text-right font-mono ${pctColor(s.pnl_pct)}`}>
                {s.pnl_pct !== null ? formatPct(s.pnl_pct) : "—"}
              </td>
              <td className={`py-1.5 text-right font-mono ${pctColor(s.r_multiple)}`}>
                {s.r_multiple !== null ? s.r_multiple.toFixed(2) : "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ─── Main Page ─────────────────────────────────────────────────────────────────

export default function V3BacktestPageContent() {
  const [runs, setRuns] = useState<V3BacktestRunSummary[]>([]);
  const [selectedRun, setSelectedRun] = useState<string | null>(null);
  const [detail, setDetail] = useState<V3BacktestRunDetail | null>(null);
  const [signals, setSignals] = useState<V3BacktestSignal[]>([]);
  const [equity, setEquity] = useState<V3EquityCurve | null>(null);
  const [assetFilter, setAssetFilter] = useState<string | null>(null);
  const [outcomeFilter, setOutcomeFilter] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadRuns = useCallback(async () => {
    try {
      const list = await getV3BacktestRuns();
      setRuns(list);
      // Auto-select the most recent run
      if (list.length > 0 && !selectedRun) {
        setSelectedRun(list[0].run_id);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load runs");
    } finally {
      setLoading(false);
    }
  }, [selectedRun]);

  const loadRunDetail = useCallback(async () => {
    if (!selectedRun) return;
    try {
      const [d, sigs, eq] = await Promise.all([
        getV3BacktestRunDetail(selectedRun),
        getV3BacktestSignals(selectedRun, {
          asset: assetFilter ?? undefined,
          outcome: outcomeFilter ?? undefined,
          limit: 500,
        }),
        getV3EquityCurve(selectedRun, assetFilter ?? undefined),
      ]);
      setDetail(d);
      setSignals(sigs);
      setEquity(eq);
    } catch (e) {
      console.error(e);
    }
  }, [selectedRun, assetFilter, outcomeFilter]);

  useEffect(() => {
    loadRuns();
  }, [loadRuns]);

  useEffect(() => {
    loadRunDetail();
  }, [loadRunDetail]);

  // Auto-refresh every 30 seconds (since backtest is running)
  useEffect(() => {
    const interval = setInterval(() => {
      loadRuns();
      loadRunDetail();
    }, 30000);
    return () => clearInterval(interval);
  }, [loadRuns, loadRunDetail]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-zinc-500 text-sm">Loading V3 backtest data...</div>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6 max-w-7xl">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-white text-xl font-bold">V3 Pipeline Backtest</h1>
          <p className="text-zinc-500 text-sm mt-0.5">
            Historical replay of the 4-stage LLM signal pipeline against intraday DXY/EURUSD/XAUUSD/SPX data
          </p>
        </div>
        <div className="flex items-center gap-2">
          {runs.length > 0 && (
            <select
              value={selectedRun ?? ""}
              onChange={(e) => setSelectedRun(e.target.value)}
              className="px-3 py-1.5 bg-zinc-800 text-zinc-200 text-sm rounded border border-zinc-700"
            >
              {runs.map((r) => (
                <option key={r.run_id} value={r.run_id}>
                  {r.run_id} ({r.total_signals} signals)
                </option>
              ))}
            </select>
          )}
        </div>
      </div>

      {error && (
        <div className="text-xs text-red-400 bg-red-950 border border-red-800 rounded px-3 py-2">
          {error}
        </div>
      )}

      {/* Run summary header */}
      {detail && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <div className="rounded border border-zinc-800 bg-zinc-900 px-4 py-3">
            <div className="text-zinc-500 text-xs uppercase tracking-wider">Total Signals</div>
            <div className="text-2xl font-bold text-zinc-200 font-mono">{detail.total_signals}</div>
          </div>
          <div className="rounded border border-zinc-800 bg-zinc-900 px-4 py-3">
            <div className="text-zinc-500 text-xs uppercase tracking-wider">Closed Trades</div>
            <div className="text-2xl font-bold text-zinc-200 font-mono">
              {detail.total_closed}
              <span className="text-xs text-zinc-500 font-normal ml-2">({detail.total_wins} W)</span>
            </div>
          </div>
          <div className="rounded border border-zinc-800 bg-zinc-900 px-4 py-3">
            <div className="text-zinc-500 text-xs uppercase tracking-wider">Portfolio Win Rate</div>
            <div className={`text-2xl font-bold font-mono ${winRateColor(detail.portfolio_win_rate)}`}>
              {detail.portfolio_win_rate !== null ? `${(detail.portfolio_win_rate * 100).toFixed(0)}%` : "—"}
            </div>
          </div>
          <div className="rounded border border-zinc-800 bg-zinc-900 px-4 py-3">
            <div className="text-zinc-500 text-xs uppercase tracking-wider">Total P&amp;L</div>
            <div className={`text-2xl font-bold font-mono ${pctColor(detail.portfolio_pnl_pct)}`}>
              {formatPct(detail.portfolio_pnl_pct, 1)}
            </div>
          </div>
        </div>
      )}

      {/* Per-asset cards */}
      {detail && Object.keys(detail.per_asset).length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          {Object.entries(detail.per_asset).map(([asset, data]) => (
            <AssetCard key={asset} asset={asset} data={data} />
          ))}
        </div>
      )}

      {/* Equity curve */}
      <EquityCurveChart curve={equity} />

      {/* Filters */}
      <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-4">
        <div className="flex items-center justify-between mb-3">
          <div className="text-zinc-400 text-xs font-semibold uppercase tracking-wider">
            Signals ({signals.length})
          </div>
          <div className="flex items-center gap-2">
            <select
              value={assetFilter ?? ""}
              onChange={(e) => setAssetFilter(e.target.value || null)}
              className="px-2 py-1 bg-zinc-800 text-zinc-300 text-xs rounded border border-zinc-700"
            >
              <option value="">All assets</option>
              {detail && Object.keys(detail.per_asset).map((a) => (
                <option key={a} value={a}>{a}</option>
              ))}
            </select>
            <select
              value={outcomeFilter ?? ""}
              onChange={(e) => setOutcomeFilter(e.target.value || null)}
              className="px-2 py-1 bg-zinc-800 text-zinc-300 text-xs rounded border border-zinc-700"
            >
              <option value="">All outcomes</option>
              <option value="WIN">Wins</option>
              <option value="LOSS">Losses</option>
              <option value="OPEN">Open</option>
              <option value="ENTRY_NOT_TRIGGERED">Not triggered</option>
            </select>
          </div>
        </div>
        <SignalsTable signals={signals} />
      </div>

      <div className="text-zinc-600 text-xs text-center">
        Auto-refreshes every 30 seconds while backtest is running
      </div>
    </div>
  );
}
