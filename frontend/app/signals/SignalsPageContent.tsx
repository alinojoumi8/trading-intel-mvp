"use client";

import { useEffect, useState, useCallback } from "react";
import {
  getSignals,
  getSignalStats,
  generateSignal,
  resolveSignal,
  TradingSignal,
  SignalStats,
} from "@/lib/api";

// ─── Color helpers ──────────────────────────────────────────────────────────

function signalColor(signal?: string): string {
  switch (signal) {
    case "BUY": return "text-green-400";
    case "SELL": return "text-red-400";
    case "WATCH_LIST": return "text-yellow-400";
    default: return "text-zinc-400";
  }
}

function signalBg(signal?: string): string {
  switch (signal) {
    case "BUY": return "bg-green-900/30 border-green-800";
    case "SELL": return "bg-red-900/30 border-red-800";
    case "WATCH_LIST": return "bg-yellow-900/30 border-yellow-800";
    default: return "bg-zinc-900/30 border-zinc-800";
  }
}

function gateColor(signal?: string): string {
  switch (signal) {
    case "GREEN": return "text-green-400";
    case "AMBER": return "text-yellow-400";
    case "RED": return "text-red-400";
    default: return "text-zinc-400";
  }
}

function gateBg(signal?: string): string {
  switch (signal) {
    case "GREEN": return "bg-green-900/30";
    case "AMBER": return "bg-yellow-900/30";
    case "RED": return "bg-red-900/30";
    default: return "bg-zinc-800/50";
  }
}

function regimeColor(regime?: string): string {
  switch (regime) {
    case "BULL": return "text-green-400";
    case "BEAR": return "text-red-400";
    case "TRANSITIONING_TO_BULL": return "text-blue-400";
    case "TRANSITIONING_TO_BEAR": return "text-orange-400";
    default: return "text-zinc-400";
  }
}

function confidenceColor(conf?: number): string {
  if (!conf) return "text-zinc-400";
  if (conf >= 80) return "text-green-400";
  if (conf >= 60) return "text-yellow-400";
  return "text-red-400";
}

function confidenceBar(conf?: number): string {
  if (!conf) return "bg-zinc-700";
  if (conf >= 80) return "bg-green-500";
  if (conf >= 60) return "bg-yellow-500";
  return "bg-red-500";
}

// ─── Stage Card ──────────────────────────────────────────────────────────────

function StageCard({ stage, title, color }: { stage?: object; title: string; color: string }) {
  if (!stage) return null;
  const entries = Object.entries(stage as Record<string, unknown>).filter(
    ([, val]) => val !== null && val !== undefined && val !== "" && typeof val !== "object"
  );
  return (
    <div className={`border ${color} rounded-lg p-4`}>
      <p className="text-xs font-semibold uppercase tracking-wider text-zinc-400 mb-2">{title}</p>
      <div className="space-y-1">
        {entries.map(([key, val]) => (
          <div key={key} className="flex justify-between text-xs">
            <span className="text-zinc-500 capitalize">{key.replace(/_/g, " ")}</span>
            <span className="text-zinc-300 font-mono">{String(val)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── Signal Detail Modal ───────────────────────────────────────────────────

function SignalModal({
  signal,
  onClose,
  onResolve,
}: {
  signal: TradingSignal;
  onClose: () => void;
  onResolve: (id: number, outcome: "WIN" | "LOSS" | "BREAKEVEN") => void;
}) {
  return (
    <div className="fixed inset-0 bg-black/70 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div
        className="bg-zinc-950 border border-zinc-800 rounded-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto"
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-start justify-between p-6 border-b border-zinc-800">
          <div>
            <div className="flex items-center gap-3">
              <span className="text-2xl font-bold text-white">{signal.asset}</span>
              <span className={`text-lg font-bold ${signalColor(signal.final_signal)}`}>
                {signal.final_signal}
              </span>
              {signal.signal_confidence != null && (
                <span className={`text-lg font-bold ${confidenceColor(signal.signal_confidence)}`}>
                  {signal.signal_confidence}%
                </span>
              )}
            </div>
            <p className="text-zinc-500 text-xs mt-1">
              {signal.asset_class} · Generated {signal.generated_at ? new Date(signal.generated_at).toLocaleString() : "N/A"}
              {signal.id ? ` · ID: ${signal.id}` : ""}
            </p>
          </div>
          <button onClick={onClose} className="text-zinc-500 hover:text-white text-xl">×</button>
        </div>

        {/* Signal Summary */}
        {signal.signal_summary && (
          <div className="px-6 py-4 border-b border-zinc-800">
            <p className="text-zinc-300 text-sm leading-relaxed">{signal.signal_summary}</p>
          </div>
        )}

        {/* Trade Parameters */}
        <div className="px-6 py-4 border-b border-zinc-800">
          <p className="text-xs font-semibold uppercase tracking-wider text-zinc-500 mb-3">Trade Parameters</p>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {[
              ["Direction", signal.direction],
              ["Entry", signal.entry_price?.toFixed(5)],
              ["Stop Loss", signal.stop_loss?.toFixed(5)],
              ["Target", signal.target_price?.toFixed(5)],
              ["R:R", signal.risk_reward_ratio ? `${signal.risk_reward_ratio}:1` : "N/A"],
              ["Position", signal.recommended_position_size_pct != null ? `${signal.recommended_position_size_pct}%` : "N/A"],
              ["Horizon", signal.trade_horizon],
              ["Gate", signal.gate_signal],
            ].map(([label, val]) => (
              <div key={label as string}>
                <p className="text-zinc-600 text-xs mb-1">{label}</p>
                <p className="text-white text-sm font-mono">{val ?? "N/A"}</p>
              </div>
            ))}
          </div>
        </div>

        {/* Stage Outputs */}
        {(signal.stage1 || signal.stage2 || signal.stage3 || signal.stage4) && (
          <div className="px-6 py-4 border-b border-zinc-800">
            <p className="text-xs font-semibold uppercase tracking-wider text-zinc-500 mb-3">Stage Details</p>
            <div className="grid grid-cols-2 gap-3">
              <StageCard stage={signal.stage1} title="Stage 1 — Regime" color="border-blue-800" />
              <StageCard stage={signal.stage2} title="Stage 2 — Fundamentals" color="border-purple-800" />
              <StageCard stage={signal.stage3} title="Stage 3 — Gatekeeping" color="border-orange-800" />
              <StageCard stage={signal.stage4} title="Stage 4 — Signal" color="border-green-800" />
            </div>
          </div>
        )}

        {/* Key Risks */}
        {signal.key_risks && signal.key_risks.length > 0 && (
          <div className="px-6 py-4 border-b border-zinc-800">
            <p className="text-xs font-semibold uppercase tracking-wider text-zinc-500 mb-2">Key Risks</p>
            <ul className="space-y-1">
              {signal.key_risks.map((risk, i) => (
                <li key={i} className="text-zinc-400 text-xs flex gap-2">
                  <span className="text-red-500">·</span>
                  <span>{risk}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Invalidation */}
        {signal.invalidation_conditions && signal.invalidation_conditions.length > 0 && (
          <div className="px-6 py-4 border-b border-zinc-800">
            <p className="text-xs font-semibold uppercase tracking-wider text-zinc-500 mb-2">Invalidation Conditions</p>
            <ul className="space-y-1">
              {signal.invalidation_conditions.map((cond, i) => (
                <li key={i} className="text-zinc-400 text-xs flex gap-2">
                  <span className="text-yellow-500">×</span>
                  <span>{cond}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Top Drivers */}
        {signal.top_drivers && signal.top_drivers.length > 0 && (
          <div className="px-6 py-4 border-b border-zinc-800">
            <p className="text-xs font-semibold uppercase tracking-wider text-zinc-500 mb-2">Top Macro Drivers</p>
            <div className="flex flex-wrap gap-2">
              {signal.top_drivers.map((d) => (
                <span key={d} className="px-2 py-0.5 bg-purple-900/30 text-purple-400 text-xs rounded">{d}</span>
              ))}
            </div>
          </div>
        )}

        {/* Resolve actions */}
        {signal.id && signal.outcome === "ACTIVE" && (
          <div className="px-6 py-4 flex items-center gap-3">
            <p className="text-zinc-500 text-xs">Mark outcome:</p>
            {(["WIN", "LOSS", "BREAKEVEN"] as const).map(outcome => (
              <button
                key={outcome}
                onClick={() => { onResolve(signal.id!, outcome); onClose(); }}
                className={`px-3 py-1.5 text-xs font-medium rounded transition-colors ${
                  outcome === "WIN" ? "bg-green-900/50 text-green-400 hover:bg-green-900" :
                  outcome === "LOSS" ? "bg-red-900/50 text-red-400 hover:bg-red-900" :
                  "bg-yellow-900/50 text-yellow-400 hover:bg-yellow-900"
                }`}
              >
                {outcome}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Main Content ──────────────────────────────────────────────────────────

export default function SignalsPageContent() {
  const [asset, setAsset] = useState("");
  const [generating, setGenerating] = useState(false);
  const [latestSignal, setLatestSignal] = useState<TradingSignal | null>(null);
  const [signals, setSignals] = useState<TradingSignal[]>([]);
  const [stats, setStats] = useState<SignalStats | null>(null);
  const [total, setTotal] = useState(0);
  const [loadingSignals, setLoadingSignals] = useState(true);
  const [selectedSignal, setSelectedSignal] = useState<TradingSignal | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadSignals = useCallback(async () => {
    setLoadingSignals(true);
    try {
      const data = await getSignals({ limit: 20 });
      setSignals(data.items);
      setTotal(data.total);
    } catch (err) {
      console.error("Failed to load signals:", err);
    } finally {
      setLoadingSignals(false);
    }
  }, []);

  const loadStats = useCallback(async () => {
    try {
      const s = await getSignalStats();
      setStats(s);
    } catch (err) {
      console.error("Failed to load stats:", err);
    }
  }, []);

  useEffect(() => {
    loadSignals();
    loadStats();
  }, [loadSignals, loadStats]);

  const handleGenerate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!asset.trim()) return;
    setGenerating(true);
    setError(null);
    try {
      const result = await generateSignal(asset.trim().toUpperCase());
      setLatestSignal(result as TradingSignal);
      await loadSignals();
      await loadStats();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Generation failed");
    } finally {
      setGenerating(false);
    }
  };

  const handleResolve = async (id: number, outcome: "WIN" | "LOSS" | "BREAKEVEN") => {
    try {
      await resolveSignal(id, outcome);
      await loadSignals();
      await loadStats();
    } catch (err) {
      console.error("Resolve failed:", err);
    }
  };

  const assetExamples = ["EURUSD", "GBPUSD", "XAUUSD", "BTCUSD", "SPY", "AAPL"];

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="px-6 py-4 border-b border-zinc-800">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h1 className="text-white font-bold text-xl tracking-tight">TRADING SIGNALS</h1>
            <p className="text-zinc-500 text-xs mt-0.5">ITPM WISH Framework · 4-Stage Pipeline</p>
          </div>
          {stats && (
            <div className="flex gap-6 text-xs">
              <div className="text-center">
                <p className="text-zinc-400 text-lg font-bold">{stats.total_signals}</p>
                <p className="text-zinc-600">Total</p>
              </div>
              {stats.win_rate != null && (
                <div className="text-center">
                  <p className={`text-lg font-bold ${stats.win_rate >= 50 ? "text-green-400" : "text-red-400"}`}>
                    {stats.win_rate}%
                  </p>
                  <p className="text-zinc-600">Win Rate</p>
                </div>
              )}
              <div className="text-center">
                <p className="text-yellow-400 text-lg font-bold">{stats.active}</p>
                <p className="text-zinc-600">Active</p>
              </div>
              {stats.avg_confidence != null && (
                <div className="text-center">
                  <p className="text-blue-400 text-lg font-bold">{stats.avg_confidence}%</p>
                  <p className="text-zinc-600">Avg Conf</p>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Generate form */}
        <form onSubmit={handleGenerate} className="flex items-center gap-3">
          <div className="flex items-center bg-zinc-900 border border-zinc-700 rounded px-3">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="current-zinc-500" strokeWidth="2" className="mr-2 shrink-0">
              <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
            </svg>
            <input
              type="text"
              value={asset}
              onChange={e => setAsset(e.target.value.toUpperCase())}
              placeholder="Enter asset ticker..."
              className="bg-transparent text-white text-sm py-2 w-48 focus:outline-none placeholder-zinc-600"
              autoComplete="off"
            />
          </div>
          <button
            type="submit"
            disabled={generating || !asset.trim()}
            className="flex items-center gap-2 px-4 py-2 bg-green-600 hover:bg-green-500 disabled:bg-zinc-700 disabled:text-zinc-500 text-white text-xs font-medium rounded transition-colors"
          >
            {generating ? (
              <>
                <svg className="animate-spin" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M21 12a9 9 0 1 1-6.219-8.56" />
                </svg>
                Running 4 stages...
              </>
            ) : (
              <>
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <polygon points="5 3 19 12 5 21 5 3" />
                </svg>
                Generate Signal
              </>
            )}
          </button>
          <div className="flex gap-1">
            {assetExamples.map(ex => (
              <button
                key={ex}
                type="button"
                onClick={() => setAsset(ex)}
                className="px-2 py-1 bg-zinc-800 hover:bg-zinc-700 text-zinc-400 hover:text-zinc-200 text-xs rounded transition-colors"
              >
                {ex}
              </button>
            ))}
          </div>
        </form>

        {error && (
          <div className="mt-2 px-3 py-2 bg-red-900/30 border border-red-800 rounded text-red-400 text-xs">
            {error}
          </div>
        )}
      </div>

      {/* Latest signal preview */}
      {latestSignal && latestSignal.final_signal && (
        <div className={`mx-6 mt-4 border rounded-lg p-4 ${signalBg(latestSignal.final_signal)}`}>
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-3">
              <span className="text-white font-bold text-lg">{latestSignal.asset}</span>
              <span className={`text-lg font-bold ${signalColor(latestSignal.final_signal)}`}>
                {latestSignal.final_signal}
              </span>
              <span className="text-zinc-500 text-xs">{latestSignal.direction}</span>
              {latestSignal.signal_confidence != null && (
                <span className={`text-sm font-bold ${confidenceColor(latestSignal.signal_confidence)}`}>
                  {latestSignal.signal_confidence}%
                </span>
              )}
            </div>
            <button
              onClick={() => setSelectedSignal(latestSignal)}
              className="text-zinc-500 hover:text-white text-xs border border-zinc-700 hover:border-zinc-500 px-3 py-1 rounded transition-colors"
            >
              Full details →
            </button>
          </div>

          {/* Mini stage summary */}
          <div className="grid grid-cols-4 gap-3 mb-3">
            {[
              ["Regime", <span key="r" className={regimeColor(latestSignal.market_regime)}>{latestSignal.market_regime ?? "—"}</span>],
              ["Bias", <span key="b" className={latestSignal.fundamental_bias === "BULLISH" ? "text-green-400" : latestSignal.fundamental_bias === "BEARISH" ? "text-red-400" : "text-zinc-400"}>{latestSignal.fundamental_bias ?? "—"}</span>],
              ["Gate", <span key="g" className={gateColor(latestSignal.gate_signal)}>{latestSignal.gate_signal ?? "—"}</span>],
              ["R:R", <span key="rr" className="text-zinc-300 font-mono">{latestSignal.risk_reward_ratio ? `${latestSignal.risk_reward_ratio}:1` : "—"}</span>],
            ].map(([label, val]) => (
              <div key={label as string} className="text-center">
                <p className="text-zinc-600 text-[10px] uppercase">{label}</p>
                <div className="text-sm font-medium mt-0.5">{val}</div>
              </div>
            ))}
          </div>

          {/* Confidence bar */}
          {latestSignal.signal_confidence != null && (
            <div className="flex items-center gap-3">
              <div className="flex-1 h-1.5 bg-zinc-800 rounded overflow-hidden">
                <div
                  className={`h-full ${confidenceBar(latestSignal.signal_confidence)} transition-all`}
                  style={{ width: `${latestSignal.signal_confidence}%` }}
                />
              </div>
              <span className={`text-xs font-medium ${confidenceColor(latestSignal.signal_confidence)}`}>
                {latestSignal.signal_confidence}% confidence
              </span>
            </div>
          )}

          {/* Trade params */}
          <div className="flex gap-6 mt-3 text-xs">
            {[
              ["Entry", latestSignal.entry_price],
              ["Stop Loss", latestSignal.stop_loss],
              ["Target", latestSignal.target_price],
              ["Position Size", latestSignal.recommended_position_size_pct != null ? `${latestSignal.recommended_position_size_pct}%` : "N/A"],
            ].map(([label, val]) => (
              <div key={label as string}>
                <span className="text-zinc-600">{label}: </span>
                <span className="text-zinc-300 font-mono">{val != null ? String(val) : "—"}</span>
              </div>
            ))}
          </div>

          {latestSignal.signal_summary && (
            <p className="text-zinc-400 text-xs mt-2 leading-relaxed">
              {latestSignal.signal_summary}
            </p>
          )}
        </div>
      )}

      {/* Signals list */}
      <div className="flex-1 overflow-y-auto px-6 py-4">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-white font-semibold text-sm">
            Signal History
            <span className="text-zinc-500 font-normal text-xs ml-2">({total} total)</span>
          </h2>
        </div>

        {loadingSignals ? (
          <div className="flex items-center justify-center h-32">
            <p className="text-zinc-500 text-sm">Loading...</p>
          </div>
        ) : signals.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-32 gap-2">
            <p className="text-zinc-400 text-sm">No signals yet</p>
            <p className="text-zinc-600 text-xs">Enter an asset ticker above to generate your first signal</p>
          </div>
        ) : (
          <div className="space-y-2">
            {signals.map(sig => (
              <button
                key={sig.id}
                onClick={() => setSelectedSignal(sig)}
                className={`w-full text-left border rounded-lg p-4 hover:bg-zinc-900/50 transition-colors ${signalBg(sig.final_signal)}`}
              >
                <div className="flex items-center justify-between mb-1">
                  <div className="flex items-center gap-3">
                    <span className="text-white font-bold">{sig.asset}</span>
                    <span className={`text-sm font-bold ${signalColor(sig.final_signal)}`}>{sig.final_signal}</span>
                    <span className="text-zinc-500 text-xs">{sig.direction}</span>
                    {sig.signal_confidence != null && (
                      <span className={`text-xs font-medium ${confidenceColor(sig.signal_confidence)}`}>
                        {sig.signal_confidence}%
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-4 text-xs text-zinc-500">
                    {sig.outcome && (
                      <span className={`px-2 py-0.5 rounded text-[10px] font-medium ${
                        sig.outcome === "WIN" ? "bg-green-900/50 text-green-400" :
                        sig.outcome === "LOSS" ? "bg-red-900/50 text-red-400" :
                        sig.outcome === "BREAKEVEN" ? "bg-yellow-900/50 text-yellow-400" :
                        sig.outcome === "ACTIVE" ? "bg-blue-900/50 text-blue-400" :
                        "bg-zinc-800 text-zinc-400"
                      }`}>
                        {sig.outcome}
                      </span>
                    )}
                    <span>{sig.generated_at ? new Date(sig.generated_at).toLocaleDateString() : ""}</span>
                    <span className={`${gateColor(sig.gate_signal)}`}>● {sig.gate_signal}</span>
                  </div>
                </div>

                <div className="flex gap-4 text-xs text-zinc-500">
                  <span>Regime: <span className={regimeColor(sig.market_regime)}>{sig.market_regime}</span></span>
                  <span>Bias: <span className={sig.fundamental_bias === "BULLISH" ? "text-green-400" : sig.fundamental_bias === "BEARISH" ? "text-red-400" : "text-zinc-400"}>{sig.fundamental_bias}</span></span>
                  <span>R:R: <span className="text-zinc-300 font-mono">{sig.risk_reward_ratio ? `${sig.risk_reward_ratio}:1` : "—"}</span></span>
                  {sig.entry_price && <span>Entry: <span className="text-zinc-300 font-mono">{sig.entry_price.toFixed(5)}</span></span>}
                </div>
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Modal */}
      {selectedSignal && (
        <SignalModal
          signal={selectedSignal}
          onClose={() => setSelectedSignal(null)}
          onResolve={handleResolve}
        />
      )}
    </div>
  );
}
