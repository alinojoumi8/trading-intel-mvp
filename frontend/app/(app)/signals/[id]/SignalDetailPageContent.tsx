"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  getSignalById,
  TradingSignal,
  FSMContext,
} from "@/lib/api";

// ─── Helpers (same as SignalsPageContent) ────────────────────────────────────

function signalColor(signal?: string) {
  switch (signal) {
    case "BUY": return "text-green-400";
    case "SELL": return "text-red-400";
    case "WATCH_LIST": return "text-yellow-400";
    default: return "text-zinc-400";
  }
}

function gradeColor(grade?: string) {
  switch (grade) {
    case "A": return "text-emerald-400";
    case "B": return "text-green-400";
    case "C": return "text-yellow-400";
    case "WATCH": return "text-orange-400";
    default: return "text-zinc-500";
  }
}

function gradeBg(grade?: string) {
  switch (grade) {
    case "A": return "bg-emerald-900/60 border border-emerald-700 text-emerald-300";
    case "B": return "bg-green-900/60 border border-green-700 text-green-300";
    case "C": return "bg-yellow-900/60 border border-yellow-700 text-yellow-300";
    case "WATCH": return "bg-orange-900/60 border border-orange-700 text-orange-300";
    case "PASS": return "bg-zinc-800/60 border border-zinc-700 text-zinc-400";
    default: return "bg-zinc-800/60 border border-zinc-700 text-zinc-500";
  }
}

function gateColor(signal?: string) {
  switch (signal) {
    case "GREEN": return "text-green-400";
    case "AMBER": return "text-yellow-400";
    case "RED": return "text-red-400";
    default: return "text-zinc-400";
  }
}

function confidenceColor(conf?: number) {
  if (!conf) return "text-zinc-400";
  if (conf >= 80) return "text-green-400";
  if (conf >= 60) return "text-yellow-400";
  return "text-red-400";
}

function confidenceBar(conf?: number) {
  if (!conf) return "bg-zinc-700";
  if (conf >= 80) return "bg-green-500";
  if (conf >= 60) return "bg-yellow-500";
  return "bg-red-500";
}

// ─── Pre-Trade Checklist ──────────────────────────────────────────────────────

function PreTradeChecklist({ signal }: { signal: TradingSignal }) {
  const checks: { label: string; pass: boolean | null; note?: string }[] = [
    {
      label: "Gate Signal GREEN or AMBER",
      pass: signal.gate_signal === "GREEN" ? true : signal.gate_signal === "AMBER" ? null : false,
      note: signal.gate_signal ?? "—",
    },
    {
      label: "Fundamental bias confirmed",
      pass: signal.fundamental_bias === "BULLISH" || signal.fundamental_bias === "BEARISH",
      note: signal.fundamental_bias ?? "—",
    },
    {
      label: "Signal confidence ≥ 70%",
      pass: signal.signal_confidence != null ? signal.signal_confidence >= 70 : null,
      note: signal.signal_confidence != null ? `${signal.signal_confidence}%` : "—",
    },
    {
      label: "Risk:Reward ≥ 2:1",
      pass: signal.risk_reward_ratio != null ? signal.risk_reward_ratio >= 2 : null,
      note: signal.risk_reward_ratio != null ? `${signal.risk_reward_ratio}:1` : "—",
    },
    {
      label: "Entry price set",
      pass: signal.entry_price != null,
      note: signal.entry_price?.toFixed(5) ?? "—",
    },
    {
      label: "Stop loss set",
      pass: signal.stop_loss != null,
      note: signal.stop_loss?.toFixed(5) ?? "—",
    },
    {
      label: "Regime not SIDELINES",
      pass: signal.trading_mode !== "SIDELINES",
      note: signal.trading_mode ?? "—",
    },
    {
      label: "Signal grade B or better",
      pass: signal.signal_grade === "A" ? true : signal.signal_grade === "B" ? true : signal.signal_grade === "C" ? null : signal.signal_grade ? false : null,
      note: signal.signal_grade ?? "—",
    },
  ];

  const passed = checks.filter(c => c.pass === true).length;
  const total = checks.length;

  return (
    <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-white">Pre-Trade Checklist</h3>
        <span className={`text-xs font-bold px-2.5 py-1 rounded-full ${
          passed >= 6 ? "bg-green-900/50 text-green-400" :
          passed >= 4 ? "bg-yellow-900/50 text-yellow-400" :
          "bg-red-900/50 text-red-400"
        }`}>
          {passed}/{total} passed
        </span>
      </div>
      <div className="space-y-2">
        {checks.map((c, i) => (
          <div key={i} className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className={`w-5 h-5 rounded-full flex items-center justify-center text-[11px] font-bold shrink-0 ${
                c.pass === true ? "bg-green-900/60 text-green-400 border border-green-700" :
                c.pass === false ? "bg-red-900/60 text-red-400 border border-red-700" :
                "bg-yellow-900/60 text-yellow-400 border border-yellow-700"
              }`}>
                {c.pass === true ? "✓" : c.pass === false ? "✗" : "~"}
              </div>
              <span className={`text-sm ${c.pass === true ? "text-zinc-200" : c.pass === false ? "text-zinc-500 line-through" : "text-zinc-400"}`}>
                {c.label}
              </span>
            </div>
            {c.note && <span className="text-zinc-500 text-xs font-mono">{c.note}</span>}
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── FSM Badge ────────────────────────────────────────────────────────────────

function FsmBadge({ fsm }: { fsm?: FSMContext | null }) {
  if (!fsm || fsm.available === false) {
    return <p className="text-zinc-600 text-xs">Fed sentiment unavailable</p>;
  }
  const composite = fsm.composite_score;
  const compositeLabel = composite != null ? `${composite > 0 ? "+" : ""}${composite.toFixed(0)}` : "—";
  const compositeColor = composite != null && composite > 10 ? "text-red-400" : composite != null && composite < -10 ? "text-blue-400" : "text-zinc-400";

  return (
    <div className="flex flex-wrap gap-2 text-xs">
      <span className="px-1.5 py-0.5 rounded bg-zinc-800 border border-zinc-700 text-zinc-300 font-semibold">FSM</span>
      <span className="text-zinc-300">{fsm.fed_regime?.replace(/_/g, " ") ?? "—"}</span>
      <span className="text-zinc-700">·</span>
      <span className="text-zinc-400">{fsm.divergence_category?.replace(/_/g, " ") ?? "—"}</span>
      <span className="text-zinc-700">·</span>
      <span className={compositeColor}>Composite: {compositeLabel}</span>
      {fsm.pre_fomc_window && (
        <span className="px-1.5 py-0.5 rounded bg-orange-950/60 text-orange-300 border border-orange-800 font-semibold">PRE-FOMC</span>
      )}
    </div>
  );
}

// ─── Stage Card ───────────────────────────────────────────────────────────────

function StageCard({ stage, title, color }: { stage?: object; title: string; color: string }) {
  if (!stage) return null;
  const entries = Object.entries(stage as Record<string, unknown>).filter(
    ([, val]) => val !== null && val !== undefined && val !== "" && typeof val !== "object"
  );
  return (
    <div className={`border ${color} rounded-lg p-4`}>
      <p className="text-xs font-semibold uppercase tracking-wider text-zinc-400 mb-3">{title}</p>
      <div className="space-y-1.5">
        {entries.map(([key, val]) => (
          <div key={key} className="flex justify-between text-xs gap-4">
            <span className="text-zinc-500 capitalize shrink-0">{key.replace(/_/g, " ")}</span>
            <span className="text-zinc-300 font-mono text-right">{String(val)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── Main Component ───────────────────────────────────────────────────────────

export default function SignalDetailPageContent() {
  const params = useParams();
  const router = useRouter();
  const signalId = params?.id ? Number(params.id) : null;

  const [signal, setSignal] = useState<TradingSignal | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!signalId) return;
    setLoading(true);
    getSignalById(signalId)
      .then(setSignal)
      .catch(e => setError(e instanceof Error ? e.message : "Failed to load signal"))
      .finally(() => setLoading(false));
  }, [signalId]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full min-h-96">
        <p className="text-zinc-500">Loading signal...</p>
      </div>
    );
  }

  if (error || !signal) {
    return (
      <div className="flex flex-col items-center justify-center h-full min-h-96 gap-3">
        <p className="text-red-400">{error ?? "Signal not found"}</p>
        <button onClick={() => router.push("/signals")} className="text-xs text-zinc-500 hover:text-zinc-300 underline">
          ← Back to signals
        </button>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto px-6 py-8 space-y-6">
      {/* Back nav */}
      <button onClick={() => router.push("/signals")} className="flex items-center gap-2 text-zinc-500 hover:text-zinc-300 text-sm transition-colors">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <polyline points="15 18 9 12 15 6" />
        </svg>
        Back to signals
      </button>

      {/* Signal Header */}
      <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-3 flex-wrap mb-2">
              <span className="text-3xl font-bold text-white">{signal.asset}</span>
              <span className={`text-2xl font-bold ${signalColor(signal.final_signal)}`}>{signal.final_signal}</span>
              {signal.signal_grade && (
                <span className={`text-base font-bold px-3 py-1 rounded ${gradeBg(signal.signal_grade)}`}>
                  Grade {signal.signal_grade}
                </span>
              )}
              {signal.outcome && signal.outcome !== "ACTIVE" && (
                <span className={`px-3 py-1 rounded text-sm font-bold ${
                  signal.outcome === "WIN" ? "bg-green-900/50 text-green-400" :
                  signal.outcome === "LOSS" ? "bg-red-900/50 text-red-400" :
                  "bg-yellow-900/50 text-yellow-400"
                }`}>{signal.outcome}</span>
              )}
            </div>
            <p className="text-zinc-500 text-sm">
              {signal.asset_class} · {signal.generated_at ? new Date(signal.generated_at).toLocaleString() : "N/A"}
              {signal.id ? ` · ID #${signal.id}` : ""}
            </p>
          </div>
          <div className="flex gap-6 text-center">
            {signal.signal_confidence != null && (
              <div>
                <p className={`text-2xl font-bold ${confidenceColor(signal.signal_confidence)}`}>{signal.signal_confidence}%</p>
                <p className="text-zinc-600 text-xs">Confidence</p>
              </div>
            )}
            {signal.risk_reward_ratio != null && (
              <div>
                <p className="text-2xl font-bold text-zinc-200 font-mono">{signal.risk_reward_ratio}:1</p>
                <p className="text-zinc-600 text-xs">R:R (T1)</p>
              </div>
            )}
          </div>
        </div>

        {signal.signal_confidence != null && (
          <div className="mt-4 flex items-center gap-3">
            <div className="flex-1 h-2 bg-zinc-800 rounded-full overflow-hidden">
              <div className={`h-full ${confidenceBar(signal.signal_confidence)} transition-all`} style={{ width: `${signal.signal_confidence}%` }} />
            </div>
            <span className={`text-xs font-medium ${confidenceColor(signal.signal_confidence)}`}>{signal.signal_confidence}% confidence</span>
          </div>
        )}

        {signal.signal_summary && (
          <p className="text-zinc-300 text-sm leading-relaxed mt-4 border-t border-zinc-800 pt-4">{signal.signal_summary}</p>
        )}
      </div>

      {/* Two-column: Checklist + Trade Params */}
      <div className="grid md:grid-cols-2 gap-4">
        <PreTradeChecklist signal={signal} />

        {/* Trade Parameters */}
        <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-5">
          <h3 className="text-sm font-semibold text-white mb-4">Trade Parameters</h3>
          <div className="space-y-3">
            {[
              ["Direction", signal.direction],
              ["Entry Price", signal.entry_price?.toFixed(5)],
              ["Stop Loss", signal.stop_loss?.toFixed(5)],
              ["Target T1 (2R)", signal.target_price?.toFixed(5)],
              ["Position Size", signal.recommended_position_size_pct != null ? `${signal.recommended_position_size_pct}%` : "N/A"],
              ["Hold Time", signal.trade_horizon ? signal.trade_horizon.replace(/_/g, " ") : "N/A"],
              ["Gate Signal", signal.gate_signal],
            ].map(([label, val]) => (
              <div key={label as string} className="flex justify-between text-sm border-b border-zinc-800/50 pb-2">
                <span className="text-zinc-500">{label}</span>
                <span className="text-white font-mono">{val ?? "N/A"}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Stage summary bar */}
      <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-5">
        <h3 className="text-sm font-semibold text-white mb-4">4-Stage Pipeline Summary</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-center text-xs">
          <div className="border border-blue-800/50 rounded-lg p-3">
            <p className="text-zinc-500 mb-1">Stage 1 — Regime</p>
            <p className={`font-bold ${signal.market_regime === "BULL" ? "text-green-400" : signal.market_regime === "BEAR" ? "text-red-400" : "text-yellow-400"}`}>
              {signal.market_regime ?? "—"}
            </p>
            <p className="text-zinc-600 mt-1">{signal.volatility_regime ?? ""}</p>
          </div>
          <div className="border border-purple-800/50 rounded-lg p-3">
            <p className="text-zinc-500 mb-1">Stage 2 — Macro</p>
            <p className={`font-bold ${signal.fundamental_bias === "BULLISH" ? "text-green-400" : signal.fundamental_bias === "BEARISH" ? "text-red-400" : "text-zinc-400"}`}>
              {signal.fundamental_bias ?? "—"}
            </p>
            <p className="text-zinc-600 mt-1">{signal.bias_strength ?? ""}</p>
          </div>
          <div className="border border-orange-800/50 rounded-lg p-3">
            <p className="text-zinc-500 mb-1">Stage 3 — Gate</p>
            <p className={`font-bold ${gateColor(signal.gate_signal)}`}>{signal.gate_signal ?? "—"}</p>
            <p className="text-zinc-600 mt-1">{signal.technical_alignment ?? ""}</p>
          </div>
          <div className="border border-green-800/50 rounded-lg p-3">
            <p className="text-zinc-500 mb-1">Stage 4 — Signal</p>
            <p className={`font-bold ${signalColor(signal.final_signal)}`}>{signal.final_signal ?? "—"}</p>
            <p className={`mt-1 ${signal.signal_grade ? gradeColor(signal.signal_grade) : "text-zinc-600"}`}>
              {signal.signal_grade ? `Grade ${signal.signal_grade}` : ""}
            </p>
          </div>
        </div>
      </div>

      {/* FSM Context */}
      {signal.fsm_context && (
        <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-5">
          <h3 className="text-sm font-semibold text-white mb-3">Fed Sentiment Module (FSM)</h3>
          <FsmBadge fsm={signal.fsm_context} />
        </div>
      )}

      {/* Stage Outputs */}
      {(signal.stage1 || signal.stage2 || signal.stage3 || signal.stage4) && (
        <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-5">
          <h3 className="text-sm font-semibold text-white mb-4">Full Stage Outputs</h3>
          <div className="grid md:grid-cols-2 gap-4">
            <StageCard stage={signal.stage1 as object} title="Stage 1 — Market Regime" color="border-blue-800" />
            <StageCard stage={signal.stage2 as object} title="Stage 2 — Fundamentals" color="border-purple-800" />
            <StageCard stage={signal.stage3 as object} title="Stage 3 — Gatekeeping" color="border-orange-800" />
            <StageCard stage={signal.stage4 as object} title="Stage 4 — Final Signal" color="border-green-800" />
          </div>
        </div>
      )}

      {/* Risks + Invalidation */}
      <div className="grid md:grid-cols-2 gap-4">
        {signal.key_risks && signal.key_risks.length > 0 && (
          <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-5">
            <h3 className="text-sm font-semibold text-white mb-3">Key Risks</h3>
            <ul className="space-y-2">
              {signal.key_risks.map((risk, i) => (
                <li key={i} className="text-zinc-400 text-sm flex gap-2">
                  <span className="text-red-500 shrink-0">·</span>
                  <span>{risk}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
        {signal.invalidation_conditions && signal.invalidation_conditions.length > 0 && (
          <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-5">
            <h3 className="text-sm font-semibold text-white mb-3">Invalidation Conditions</h3>
            <ul className="space-y-2">
              {signal.invalidation_conditions.map((cond, i) => (
                <li key={i} className="text-zinc-400 text-sm flex gap-2">
                  <span className="text-yellow-500 shrink-0">×</span>
                  <span>{cond}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {/* Top Drivers */}
      {signal.top_drivers && signal.top_drivers.length > 0 && (
        <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-5">
          <h3 className="text-sm font-semibold text-white mb-3">Top Macro Drivers</h3>
          <div className="flex flex-wrap gap-2">
            {signal.top_drivers.map(d => (
              <span key={d} className="px-3 py-1 bg-purple-900/30 text-purple-400 text-sm rounded-full border border-purple-800/50">{d}</span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
