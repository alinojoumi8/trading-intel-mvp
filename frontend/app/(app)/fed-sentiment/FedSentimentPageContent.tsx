"use client";

import { useEffect, useState, useCallback } from "react";
import {
  getFedComposite,
  getFedDocuments,
  getFedHistory,
  getFedPhraseTransitions,
  getFedBacktest,
  runFedBacktest,
  syncFedDocuments,
  scoreFedTier2,
  detectPhraseTransitions,
  FedComposite,
  FedDocument,
  FedHistoryItem,
  PhraseTransitionItem,
  BacktestResult,
} from "@/lib/api";
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  Cell,
} from "recharts";

// ─── Color helpers ─────────────────────────────────────────────────────────────

function scoreColor(score: number | null): string {
  if (score === null) return "text-zinc-400";
  if (score > 30) return "text-red-400";
  if (score > 10) return "text-orange-400";
  if (score < -30) return "text-blue-400";
  if (score < -10) return "text-sky-400";
  return "text-zinc-300";
}

function scoreBg(score: number | null): string {
  if (score === null) return "bg-zinc-800";
  if (score > 30) return "bg-red-950 border-red-800";
  if (score > 10) return "bg-orange-950 border-orange-800";
  if (score < -30) return "bg-blue-950 border-blue-800";
  if (score < -10) return "bg-sky-950 border-sky-800";
  return "bg-zinc-900 border-zinc-700";
}

function convictionBadge(conviction: string | null): string {
  switch (conviction) {
    case "high": return "bg-green-900/60 text-green-300 border border-green-700";
    case "medium": return "bg-yellow-900/60 text-yellow-300 border border-yellow-700";
    default: return "bg-zinc-800 text-zinc-400 border border-zinc-700";
  }
}

function directionColor(dir: string | null): string {
  if (dir === "USD_bullish") return "text-red-400";
  if (dir === "USD_bearish") return "text-blue-400";
  return "text-zinc-400";
}

function regimeLabel(regime: string | null): string {
  const map: Record<string, string> = {
    aggressive_tightening: "Aggressive Tightening",
    moderate_tightening: "Moderate Tightening",
    neutral_hold: "Neutral / Hold",
    moderate_easing: "Moderate Easing",
    aggressive_easing: "Aggressive Easing",
  };
  return regime ? (map[regime] || regime.replace(/_/g, " ")) : "—";
}

function docTypeLabel(t: string): string {
  const map: Record<string, string> = {
    statement: "FOMC Statement",
    minutes: "Minutes",
    speech: "Speech",
    speech_chair: "Chair Speech",
    speech_vice_chair: "Vice Chair Speech",
    speech_governor: "Governor Speech",
    beige_book: "Beige Book",
    testimony: "Testimony",
    press_conference: "Press Conf.",
    dot_plot: "Dot Plot",
  };
  return map[t] || t;
}

function formatDate(iso: string): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleDateString("en-US", {
      month: "short", day: "numeric", year: "numeric",
    });
  } catch {
    return iso.slice(0, 10);
  }
}

// ─── Composite Gauge ──────────────────────────────────────────────────────────

function CompositeGauge({ score }: { score: number | null }) {
  const s = score ?? 0;
  // Map -100..+100 to 0..180 degrees arc
  const pct = (s + 100) / 200; // 0..1
  const angle = pct * 180 - 90; // -90 (full dove) .. +90 (full hawk)
  const rad = (angle * Math.PI) / 180;

  // Needle tip position on a 100-radius semicircle centered at (110, 110)
  const needleLen = 72;
  const cx = 110;
  const cy = 110;
  const nx = cx + needleLen * Math.cos(rad - Math.PI / 2);
  const ny = cy + needleLen * Math.sin(rad - Math.PI / 2);

  const arcColor = s > 20 ? "#ef4444" : s < -20 ? "#3b82f6" : "#a1a1aa";

  return (
    <div className="flex flex-col items-center gap-2">
      <svg width="220" height="130" viewBox="0 0 220 130">
        {/* Background arc */}
        <path
          d="M 20 110 A 90 90 0 0 1 200 110"
          fill="none" stroke="#27272a" strokeWidth="18" strokeLinecap="round"
        />
        {/* Color arc based on score */}
        <path
          d="M 20 110 A 90 90 0 0 1 200 110"
          fill="none" stroke={arcColor} strokeWidth="18" strokeLinecap="round"
          strokeDasharray={`${pct * 283} 283`}
          opacity="0.7"
        />
        {/* Zone labels */}
        <text x="14" y="128" fill="#3b82f6" fontSize="9" fontWeight="bold">DOVE</text>
        <text x="178" y="128" fill="#ef4444" fontSize="9" fontWeight="bold">HAWK</text>
        <text x="98" y="24" fill="#71717a" fontSize="9">NEUTRAL</text>
        {/* Needle */}
        <line
          x1={cx} y1={cy}
          x2={nx} y2={ny}
          stroke="white" strokeWidth="2.5" strokeLinecap="round"
        />
        <circle cx={cx} cy={cy} r="5" fill="white" />
        {/* Score label */}
        <text x={cx} y={cy + 22} textAnchor="middle" fill="white" fontSize="20" fontWeight="bold">
          {s > 0 ? "+" : ""}{s.toFixed(0)}
        </text>
      </svg>
    </div>
  );
}

// ─── Score Bar ────────────────────────────────────────────────────────────────

function ScoreBar({
  label,
  score,
  showTier,
}: {
  label: string;
  score: number | null;
  showTier?: string;
}) {
  const s = score ?? 0;
  const pct = Math.abs(s); // 0..100
  const isPositive = s >= 0;

  return (
    <div className="flex items-center gap-3">
      <span className="text-zinc-500 text-xs w-28 shrink-0">{label}</span>
      <div className="flex-1 flex items-center gap-1 h-5">
        {/* Left (dovish) */}
        <div className="flex-1 flex justify-end">
          {!isPositive && (
            <div
              className="h-4 bg-blue-500 rounded-l"
              style={{ width: `${pct}%`, maxWidth: "100%", opacity: 0.75 }}
            />
          )}
        </div>
        {/* Center */}
        <div className="w-px h-4 bg-zinc-600 shrink-0" />
        {/* Right (hawkish) */}
        <div className="flex-1">
          {isPositive && (
            <div
              className="h-4 bg-red-500 rounded-r"
              style={{ width: `${pct}%`, maxWidth: "100%", opacity: 0.75 }}
            />
          )}
        </div>
      </div>
      <span className={`text-sm font-mono w-12 text-right shrink-0 ${scoreColor(score)}`}>
        {score !== null ? `${s > 0 ? "+" : ""}${s.toFixed(1)}` : "—"}
      </span>
      {showTier && (
        <span className="text-zinc-600 text-xs w-8">{showTier}</span>
      )}
    </div>
  );
}

// ─── Phrase Transition Card ───────────────────────────────────────────────────

function signalBadgeStyle(signal: string | null): string {
  switch (signal) {
    case "hawkish_pivot": return "bg-red-900/60 text-red-300 border border-red-700";
    case "extremely_hawkish": return "bg-red-900/80 text-red-200 border border-red-600 font-bold";
    case "hawkish_lean":
    case "hawkish_shift": return "bg-orange-900/60 text-orange-300 border border-orange-700";
    case "dovish_pivot": return "bg-blue-900/60 text-blue-300 border border-blue-700";
    case "dovish_shift": return "bg-sky-900/60 text-sky-300 border border-sky-700";
    default: return "bg-zinc-800 text-zinc-400 border border-zinc-700";
  }
}

function signalLabel(signal: string | null): string {
  const map: Record<string, string> = {
    hawkish_pivot: "Hawkish Pivot",
    extremely_hawkish: "Extreme Hawkish",
    hawkish_lean: "Hawkish Lean",
    hawkish_shift: "Hawkish Shift",
    dovish_pivot: "Dovish Pivot",
    dovish_shift: "Dovish Shift",
  };
  return signal ? (map[signal] || signal.replace(/_/g, " ")) : "Signal";
}

function PhraseTransitionCard({ transition: t }: { transition: PhraseTransitionItem }) {
  const fromDate = t.doc_from_date ? new Date(t.doc_from_date).toLocaleDateString("en-US", { month: "short", year: "numeric" }) : "—";
  const toDate = t.doc_to_date ? new Date(t.doc_to_date).toLocaleDateString("en-US", { month: "short", year: "numeric" }) : "—";

  return (
    <div className="flex items-start gap-3 rounded-lg border border-zinc-800/60 bg-zinc-800/20 px-4 py-3">
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap mb-1">
          <span className={`px-1.5 py-0.5 rounded text-xs ${signalBadgeStyle(t.signal_type)}`}>
            {signalLabel(t.signal_type)}
          </span>
          <span className="text-zinc-600 text-xs">{fromDate} → {toDate}</span>
        </div>
        <div className="flex items-center gap-2 text-sm">
          <span className="text-zinc-400 font-mono text-xs bg-zinc-800 px-1.5 py-0.5 rounded">
            &ldquo;{t.phrase_from}&rdquo;
          </span>
          <span className="text-zinc-600 text-xs shrink-0">→</span>
          <span className={`font-mono text-xs px-1.5 py-0.5 rounded ${
            t.signal_type?.includes("hawk") ? "bg-red-950/60 text-red-300" : "bg-blue-950/60 text-blue-300"
          }`}>
            &ldquo;{t.phrase_to}&rdquo;
          </span>
        </div>
        {t.description && (
          <div className="text-zinc-500 text-xs mt-1.5 leading-relaxed">{t.description}</div>
        )}
      </div>
    </div>
  );
}


// ─── Backtest Section ─────────────────────────────────────────────────────────

function BacktestSection({
  backtest,
  running,
  currentMode,
  onRun,
}: {
  backtest: BacktestResult | null;
  running: boolean;
  currentMode: boolean;
  onRun: (useTier2: boolean) => void;
}) {
  const m = backtest?.metrics ?? {};
  const events = backtest?.events ?? [];

  const formatPct = (v: number | null | undefined) =>
    v === null || v === undefined ? "—" : `${(v * 100).toFixed(0)}%`;

  const accuracyColor = (v: number | null | undefined) => {
    if (v === null || v === undefined) return "text-zinc-500";
    if (v >= 0.7) return "text-green-400";
    if (v >= 0.55) return "text-yellow-400";
    return "text-red-400";
  };

  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-5">
      <div className="flex items-center justify-between mb-4">
        <div>
          <div className="text-zinc-400 text-xs font-semibold uppercase tracking-wider">
            Backtest & Score Calibration
          </div>
          <div className="text-zinc-600 text-xs mt-0.5">
            10 historical FOMC events (2018–2024) — validates dictionary + LLM scorers vs actual DXY reactions
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => onRun(false)}
            disabled={running}
            className="px-3 py-1.5 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 text-sm rounded border border-zinc-700 disabled:opacity-50 transition-colors"
          >
            {running && !currentMode ? "Running..." : "Run T1 Backtest"}
          </button>
          <button
            onClick={() => onRun(true)}
            disabled={running}
            className="px-3 py-1.5 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 text-sm rounded border border-zinc-700 disabled:opacity-50 transition-colors"
          >
            {running && currentMode ? "Running..." : "Run T1+T2 Backtest"}
          </button>
        </div>
      </div>

      {!backtest || events.length === 0 ? (
        <div className="text-zinc-600 text-xs py-8 text-center">
          No backtest run yet. Click &ldquo;Run T1 Backtest&rdquo; (fast) or &ldquo;Run T1+T2&rdquo; (slow, ~2 min) to validate scoring.
        </div>
      ) : (
        <>
          {/* Aggregate metrics */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
            <div className="rounded border border-zinc-800 bg-zinc-800/40 px-3 py-2">
              <div className="text-zinc-500 text-xs uppercase tracking-wider">Direction (all)</div>
              <div className={`text-2xl font-bold font-mono ${accuracyColor(m.direction_accuracy)}`}>
                {formatPct(m.direction_accuracy)}
              </div>
              <div className="text-zinc-600 text-xs">
                {m.direction_correct}/{m.direction_evaluated} events
              </div>
            </div>
            <div className="rounded border border-blue-900/40 bg-blue-950/20 px-3 py-2">
              <div className="text-blue-300 text-xs uppercase tracking-wider">Direction (filtered)</div>
              <div className={`text-2xl font-bold font-mono ${accuracyColor(m.direction_accuracy_filtered)}`}>
                {formatPct(m.direction_accuracy_filtered)}
              </div>
              <div className="text-zinc-600 text-xs">
                {m.direction_correct_filtered}/{m.direction_evaluated_filtered} non priced-in
              </div>
            </div>
            <div className="rounded border border-zinc-800 bg-zinc-800/40 px-3 py-2">
              <div className="text-zinc-500 text-xs uppercase tracking-wider">Surprise Detection</div>
              <div className={`text-2xl font-bold font-mono ${accuracyColor(m.surprise_detection_rate)}`}>
                {formatPct(m.surprise_detection_rate)}
              </div>
              <div className="text-zinc-600 text-xs">
                {m.surprise_detected}/{m.surprise_total} surprises
              </div>
            </div>
            <div className="rounded border border-zinc-800 bg-zinc-800/40 px-3 py-2">
              <div className="text-zinc-500 text-xs uppercase tracking-wider">Priced-In Detector</div>
              <div className="text-2xl font-bold font-mono text-zinc-300">
                {m.detector_flagged_priced_in ?? 0}
              </div>
              <div className="text-zinc-600 text-xs">
                of {m.direction_evaluated} flagged
              </div>
            </div>
          </div>

          {/* Events table */}
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-zinc-800 text-zinc-500">
                  <th className="text-left pb-2 pr-2">Date</th>
                  <th className="text-left pb-2 pr-2">Event</th>
                  <th className="text-right pb-2 pr-2">T1</th>
                  <th className="text-right pb-2 pr-2">T2</th>
                  <th className="text-right pb-2 pr-2">Final</th>
                  <th className="text-left pb-2 pr-2" title="2Y yield priced-in detector: priced_in / partial / surprise">PI</th>
                  <th className="text-left pb-2 pr-2">Pred</th>
                  <th className="text-right pb-2 pr-1" title="DXY move at +30 minutes (statement only)">+30m</th>
                  <th className="text-right pb-2 pr-2" title="DXY move at +90 minutes (statement + press conference)">+90m</th>
                  <th className="text-left pb-2 pr-2">Actual</th>
                  <th className="text-center pb-2">✓</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-800/40">
                {events.map((ev) => {
                  const correct = ev.direction_correct === true;
                  const wrong = ev.direction_correct === false;
                  const pct30 = ev.dxy_reaction?.pct_30m;
                  const pct90 = ev.dxy_reaction?.pct_90m ?? ev.dxy_reaction?.composite_24h_pct;
                  const fmtPct = (v?: number | null) => {
                    if (v === undefined || v === null) return "—";
                    const sign = v > 0 ? "+" : "";
                    const cls = v > 0.10 ? "text-red-400" : v < -0.10 ? "text-blue-400" : "text-zinc-500";
                    return <span className={cls}>{sign}{v.toFixed(2)}%</span>;
                  };
                  return (
                    <tr key={ev.date} className="hover:bg-zinc-800/30">
                      <td className="py-1.5 pr-2 text-zinc-500 whitespace-nowrap">{ev.date}</td>
                      <td className="py-1.5 pr-2 text-zinc-300 max-w-xs truncate" title={ev.event}>
                        {ev.event}
                      </td>
                      <td className={`py-1.5 pr-2 text-right font-mono ${ev.tier1_score && ev.tier1_score > 0 ? "text-red-400" : ev.tier1_score && ev.tier1_score < 0 ? "text-blue-400" : "text-zinc-500"}`}>
                        {ev.tier1_score !== undefined && ev.tier1_score !== null ? ev.tier1_score.toFixed(0) : "—"}
                      </td>
                      <td className={`py-1.5 pr-2 text-right font-mono ${ev.tier2_score && ev.tier2_score > 0 ? "text-red-400" : ev.tier2_score && ev.tier2_score < 0 ? "text-blue-400" : "text-zinc-500"}`}>
                        {ev.tier2_score !== undefined && ev.tier2_score !== null ? ev.tier2_score.toFixed(0) : "—"}
                      </td>
                      <td className={`py-1.5 pr-2 text-right font-mono font-bold ${ev.final_score && ev.final_score > 0 ? "text-red-300" : ev.final_score && ev.final_score < 0 ? "text-blue-300" : "text-zinc-400"}`}>
                        {ev.final_score !== undefined && ev.final_score !== null ? ev.final_score.toFixed(0) : "—"}
                      </td>
                      <td className="py-1.5 pr-2">
                        {(() => {
                          const pi = ev.priced_in_detector;
                          if (!pi || !pi.available) return <span className="text-zinc-700">—</span>;
                          const cat = pi.category;
                          const cls =
                            cat === "priced_in" ? "bg-orange-950/60 text-orange-300 border-orange-800" :
                            cat === "surprise" ? "bg-green-950/60 text-green-300 border-green-800" :
                            cat === "partial" ? "bg-zinc-800/60 text-zinc-400 border-zinc-700" :
                            "bg-zinc-900 text-zinc-600 border-zinc-800";
                          const label =
                            cat === "priced_in" ? "PI" :
                            cat === "surprise" ? "SURP" :
                            cat === "partial" ? "PART" : "—";
                          return (
                            <span className={`px-1 py-0.5 rounded border text-[9px] font-bold ${cls}`} title={`ratio=${pi.ratio} pre=${pi.pre_move_bps}bp post=${pi.post_move_bps}bp`}>
                              {label}
                            </span>
                          );
                        })()}
                      </td>
                      <td className="py-1.5 pr-2 text-zinc-400">
                        {ev.predicted_direction === "USD_bullish" ? "↑ B" :
                         ev.predicted_direction === "USD_bearish" ? "↓ B" : "→ N"}
                        {ev.raw_predicted_direction && ev.raw_predicted_direction !== ev.predicted_direction && (
                          <span className="text-orange-500 text-[9px] ml-1" title="Detector overrode the language prediction">*</span>
                        )}
                      </td>
                      <td className="py-1.5 pr-1 text-right font-mono">{fmtPct(pct30)}</td>
                      <td className="py-1.5 pr-2 text-right font-mono">{fmtPct(pct90)}</td>
                      <td className="py-1.5 pr-2 text-zinc-400">
                        {ev.actual_direction === "USD_bullish" ? "↑ B" :
                         ev.actual_direction === "USD_bearish" ? "↓ B" :
                         ev.actual_direction === "neutral" ? "→ N" : "—"}
                      </td>
                      <td className="py-1.5 text-center">
                        {correct && <span className="text-green-400">✓</span>}
                        {wrong && <span className="text-red-400">✗</span>}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Calibration insights */}
          <div className="mt-4 text-xs text-zinc-500 space-y-1.5 leading-relaxed">
            <div className="font-semibold text-zinc-400">Calibration Insights:</div>
            <div>• <span className="text-zinc-400">Ground truth:</span> 90-minute DXY move from FOMC release time (Dukascopy 1-min data, 2017-2026).</div>
            <div>• <span className="text-blue-300">PI column (priced-in detector):</span> compares 2Y yield move 30 days BEFORE the meeting vs 5 days AFTER. <span className="text-orange-300">PI</span> = priced in (ratio &gt; 0.70, language signal overridden to neutral). <span className="text-green-300">SURP</span> = real surprise (ratio &lt; 0.40). <span className="text-zinc-400">PART</span> = mixed.</div>
            <div>• <span className="text-zinc-400">Direction (filtered):</span> the realistic ceiling — accuracy on events the priced-in detector did NOT flag. Use this to judge whether language scoring is improving on its actual usable subset.</div>
            <div>• <span className="text-orange-400">Asterisk (*)</span> next to a prediction means the priced-in detector overrode the raw language prediction.</div>
            {events.length > 0 && (
              <div className="pt-1 mt-1 border-t border-zinc-800/60 text-zinc-500">
                <span className="text-zinc-400">Honest conclusion from this 10-event set:</span> language scoring (T1, T2, or both) hits a structural ceiling near 20-30% direction accuracy because most FOMC outcomes are priced in before the meeting, and the remaining surprises live in Powell&rsquo;s press conference Q&amp;A rather than the prepared statement. The detector&rsquo;s job is not to boost accuracy directly — it&rsquo;s to <em>filter out</em> the events where language scoring shouldn&rsquo;t even be applied, leaving a more honest read of the system.
              </div>
            )}
          </div>

          {backtest.ran_at && (
            <div className="text-zinc-700 text-xs text-right mt-3">
              Ran {new Date(backtest.ran_at).toLocaleString()} ({backtest.use_tier2 ? "T1+T2 LLM" : "T1 only"})
            </div>
          )}
        </>
      )}
    </div>
  );
}


// ─── FOMC Countdown Banner ────────────────────────────────────────────────────

function FomcCountdownBanner({ days, date }: { days: number; date: string | null }) {
  const isImminent = days <= 1;   // ≤24h
  const isPreWindow = days <= 2;  // ≤48h
  const isUpcoming = days <= 14;  // ≤2 weeks

  const fmtDate = date ? new Date(date).toLocaleDateString("en-US", {
    weekday: "short", month: "short", day: "numeric", year: "numeric",
  }) : null;

  // Tier styling: imminent (orange/pulse) > pre-window (yellow) > upcoming (zinc/info)
  const tier = isImminent ? "imminent" : isPreWindow ? "pre" : isUpcoming ? "upcoming" : "info";
  const styles = {
    imminent: { bg: "bg-orange-950/60 border-orange-700/60", text: "text-orange-300", num: "text-orange-400", pulse: true },
    pre:      { bg: "bg-yellow-950/40 border-yellow-700/40", text: "text-yellow-300", num: "text-yellow-400", pulse: false },
    upcoming: { bg: "bg-zinc-900 border-zinc-700",           text: "text-zinc-300",   num: "text-zinc-200",   pulse: false },
    info:     { bg: "bg-zinc-900 border-zinc-800",           text: "text-zinc-400",   num: "text-zinc-300",   pulse: false },
  }[tier];

  // Headline + sub
  const headline =
    isImminent ? "FOMC Meeting Imminent" :
    isPreWindow ? "FOMC Pre-Meeting Window" :
    "Next FOMC Meeting";
  const sub =
    isImminent ? `In ~${Math.round(days * 24)}h — position sizes auto-reduced, signals downgraded` :
    isPreWindow ? `In ~${Math.round(days * 24)}h — elevated event risk, reduced confidence on new signals` :
    isUpcoming ? `In ${Math.round(days)} days — monitoring for pre-meeting positioning` :
    `In ${Math.round(days)} days`;

  // Big readout
  const readout =
    days < 1 ? `${Math.round(days * 24)}h` :
    days < 2 ? `${Math.round(days * 24)}h` :
    `${Math.round(days)}d`;

  return (
    <div className={`flex items-center gap-3 rounded-lg border px-4 py-3 ${styles.bg}`}>
      <div className={`text-lg shrink-0 ${styles.pulse ? "animate-pulse" : ""}`}>
        🏛
      </div>
      <div className="flex-1 min-w-0">
        <div className={`text-sm font-semibold ${styles.text}`}>
          {headline}
        </div>
        <div className="text-xs text-zinc-400 mt-0.5">
          {sub}
          {fmtDate && <span className="ml-2 text-zinc-500">({fmtDate})</span>}
        </div>
      </div>
      <div className={`text-2xl font-bold font-mono shrink-0 ${styles.num}`}>
        {readout}
      </div>
    </div>
  );
}


// ─── Main Component ───────────────────────────────────────────────────────────

export default function FedSentimentPageContent() {
  const [composite, setComposite] = useState<FedComposite | null>(null);
  const [documents, setDocuments] = useState<FedDocument[]>([]);
  const [history, setHistory] = useState<FedHistoryItem[]>([]);
  const [transitions, setTransitions] = useState<PhraseTransitionItem[]>([]);
  const [backtest, setBacktest] = useState<BacktestResult | null>(null);
  const [backtestUseTier2, setBacktestUseTier2] = useState(false);
  const [backtestRunning, setBacktestRunning] = useState(false);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [scoring, setScoring] = useState(false);
  const [detecting, setDetecting] = useState(false);
  const [statusMsg, setStatusMsg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [comp, docs, hist, trans, bt] = await Promise.all([
        getFedComposite(),
        getFedDocuments(90),
        getFedHistory(90),
        getFedPhraseTransitions(20),
        getFedBacktest(false).catch(() => null),
      ]);
      setComposite(comp);
      setDocuments(docs);
      setHistory(hist);
      setTransitions(trans);
      if (bt && bt.events && bt.events.length > 0) setBacktest(bt);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load Fed sentiment data");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const handleSync = async () => {
    setSyncing(true);
    setStatusMsg(null);
    try {
      const res = await syncFedDocuments();
      setStatusMsg(res.message);
      await load();
    } catch (e) {
      setStatusMsg(e instanceof Error ? e.message : "Sync failed");
    } finally {
      setSyncing(false);
    }
  };

  const handleScoreTier2 = async () => {
    setScoring(true);
    setStatusMsg(null);
    try {
      const res = await scoreFedTier2(5);
      setStatusMsg(res.message);
      await load();
    } catch (e) {
      setStatusMsg(e instanceof Error ? e.message : "Tier 2 scoring failed");
    } finally {
      setScoring(false);
    }
  };

  const handleDetectTransitions = async () => {
    setDetecting(true);
    setStatusMsg(null);
    try {
      const res = await detectPhraseTransitions();
      setStatusMsg(res.message);
      await load();
    } catch (e) {
      setStatusMsg(e instanceof Error ? e.message : "Transition detection failed");
    } finally {
      setDetecting(false);
    }
  };

  const handleRunBacktest = async (useTier2: boolean) => {
    setBacktestRunning(true);
    setBacktestUseTier2(useTier2);
    setStatusMsg(null);
    try {
      const res = await runFedBacktest(useTier2);
      setBacktest(res);
      const m = res.metrics;
      setStatusMsg(
        `Backtest complete: ${m.direction_correct}/${m.direction_evaluated} direction accuracy, ` +
        `${m.surprise_detected}/${m.surprise_total} surprises detected.`
      );
    } catch (e) {
      setStatusMsg(e instanceof Error ? e.message : "Backtest failed");
    } finally {
      setBacktestRunning(false);
    }
  };

  // Prepare chart data
  const chartData = history.map((h) => ({
    date: h.timestamp ? h.timestamp.slice(0, 10) : "",
    composite: h.composite_score !== null ? +h.composite_score.toFixed(1) : null,
    language: h.language_score !== null ? +h.language_score.toFixed(1) : null,
    market: h.market_score !== null ? +h.market_score.toFixed(1) : null,
    divergence: h.divergence_score !== null ? +h.divergence_score.toFixed(1) : null,
  }));

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-zinc-500 text-sm">Loading Fed Sentiment...</div>
      </div>
    );
  }

  const comp = composite;
  const noData = !comp || comp.composite_score === null;

  return (
    <div className="p-6 space-y-6 max-w-7xl">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-white text-xl font-bold">Fed Sentiment</h1>
          <p className="text-zinc-500 text-sm mt-0.5">
            Language NLP + market-implied expectations · divergence signal
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleSync}
            disabled={syncing}
            className="px-3 py-1.5 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 text-sm rounded border border-zinc-700 disabled:opacity-50 transition-colors"
          >
            {syncing ? "Syncing..." : "Sync Documents"}
          </button>
          <button
            onClick={handleScoreTier2}
            disabled={scoring}
            className="px-3 py-1.5 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 text-sm rounded border border-zinc-700 disabled:opacity-50 transition-colors"
          >
            {scoring ? "Scoring..." : "Score Tier 2 (LLM)"}
          </button>
          <button
            onClick={handleDetectTransitions}
            disabled={detecting}
            className="px-3 py-1.5 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 text-sm rounded border border-zinc-700 disabled:opacity-50 transition-colors"
          >
            {detecting ? "Detecting..." : "Detect Transitions"}
          </button>
        </div>
      </div>

      {/* FOMC Countdown Banner */}
      {comp?.days_to_next_fomc !== null && comp?.days_to_next_fomc !== undefined && (
        <FomcCountdownBanner
          days={comp.days_to_next_fomc}
          date={comp.next_fomc_date}
        />
      )}

      {/* FSM Methodology Note — backtest showed language scoring has structural ceiling */}
      <div className="rounded-lg border border-blue-900/40 bg-blue-950/20 px-4 py-3 text-xs">
        <div className="font-semibold text-blue-300 mb-1">How to read this page</div>
        <div className="text-zinc-400 leading-relaxed">
          FSM is a <span className="text-blue-300">context signal</span>, not a directional predictor.
          Backtests show language scoring alone can&apos;t reliably predict USD direction (~20-30% on 10 events)
          because most FOMC outcomes are priced in before the meeting. The most actionable fields below are{" "}
          <span className="text-zinc-200 font-medium">Divergence Category</span> (Fed vs market expectations) and{" "}
          <span className="text-zinc-200 font-medium">Pre-FOMC Window</span> — the V3 pipeline already uses these
          to gate signal generation.
        </div>
      </div>

      {statusMsg && (
        <div className="text-xs text-zinc-400 bg-zinc-900 border border-zinc-700 rounded px-3 py-2">
          {statusMsg}
        </div>
      )}
      {error && (
        <div className="text-xs text-red-400 bg-red-950 border border-red-800 rounded px-3 py-2">
          {error}
        </div>
      )}

      {/* Top row: Gauge + Signal Card + Market Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">

        {/* Divergence Category Card — the lead actionable signal */}
        <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-5 flex flex-col gap-3">
          <div className="text-zinc-400 text-xs font-semibold uppercase tracking-wider">
            Divergence Category
            <span className="ml-2 text-[10px] text-blue-400 font-normal normal-case">★ primary signal</span>
          </div>
          {noData ? (
            <div className="text-zinc-600 text-sm">No signal — insufficient data</div>
          ) : (
            <>
              <div className={`text-base font-bold ${
                comp?.divergence_category?.includes("hawkish") ? "text-red-300" :
                comp?.divergence_category?.includes("dovish") ? "text-blue-300" : "text-zinc-300"
              }`}>
                {comp?.divergence_category?.replace(/_/g, " ").toUpperCase() ?? "ALIGNED"}
              </div>
              <div className="text-xs text-zinc-400 leading-relaxed">
                {comp?.divergence_category === "hawkish_surprise" && "Fed language is more hawkish than market expectations — potential USD upside catalyst."}
                {comp?.divergence_category === "dovish_surprise" && "Fed language is more dovish than market expectations — potential USD downside catalyst."}
                {comp?.divergence_category === "hawkish_priced_in" && "Fed is hawkish but markets already price it. Limited fresh upside."}
                {comp?.divergence_category === "dovish_priced_in" && "Fed is dovish but markets already price it. Limited fresh downside."}
                {(!comp?.divergence_category || comp?.divergence_category === "aligned") && "Fed language and market expectations are aligned. No fresh catalyst."}
              </div>
              <div className="text-xs text-zinc-500 mt-1">
                Score: <span className={scoreColor(comp?.divergence_score ?? null)}>
                  {comp?.divergence_score !== null ? `${(comp?.divergence_score ?? 0) > 0 ? "+" : ""}${comp?.divergence_score?.toFixed(1)}` : "—"}
                </span>
                <span className="ml-3">Z-score: <span className="text-zinc-300 font-mono">{comp?.divergence_zscore?.toFixed(1) ?? "—"}</span></span>
              </div>
              <div className="mt-2 pt-2 border-t border-zinc-800 text-xs text-zinc-500">
                Regime: <span className="text-zinc-300 font-medium">{regimeLabel(comp?.fed_regime ?? null)}</span>
              </div>
            </>
          )}
        </div>

        {/* Composite Gauge — context only, demoted */}
        <div className={`rounded-lg border p-5 flex flex-col items-center gap-2 ${scoreBg(comp?.composite_score ?? null)}`}>
          <div className="text-zinc-400 text-xs font-semibold uppercase tracking-wider">
            Composite Score
            <span className="ml-2 text-[10px] text-zinc-500 font-normal normal-case">context only</span>
          </div>
          <CompositeGauge score={comp?.composite_score ?? null} />
          <div className="text-zinc-500 text-[11px] text-center leading-snug">
            Language NLP + market expectations.<br/>
            <span className="text-zinc-600">Not used as a directional predictor — see divergence category.</span>
          </div>
          {comp?.is_stale && (
            <span className="text-yellow-500 text-xs">⚠ Stale data</span>
          )}
        </div>

        {/* Market Data */}
        <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-5 flex flex-col gap-3">
          <div className="text-zinc-400 text-xs font-semibold uppercase tracking-wider">Market Expectations</div>
          <div className="space-y-2.5">
            <div className="flex justify-between items-center">
              <span className="text-zinc-500 text-xs">Fed Target Rate</span>
              <span className="text-zinc-200 text-sm font-mono">
                {comp?.fed_target_rate !== null && comp?.fed_target_rate !== undefined
                  ? `${comp.fed_target_rate.toFixed(2)}%` : "—"}
              </span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-zinc-500 text-xs">2Y Treasury Yield</span>
              <span className={`text-sm font-mono ${scoreColor(comp?.yield_2y !== null ? ((comp?.yield_2y ?? 0) - (comp?.fed_target_rate ?? 0)) * 50 : null)}`}>
                {comp?.yield_2y !== null && comp?.yield_2y !== undefined
                  ? `${comp.yield_2y.toFixed(2)}%` : "—"}
              </span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-zinc-500 text-xs">10Y−2Y Spread</span>
              <span className={`text-sm font-mono ${(comp?.yield_spread_10y2y ?? 0) >= 0 ? "text-green-400" : "text-red-400"}`}>
                {comp?.yield_spread_10y2y !== null && comp?.yield_spread_10y2y !== undefined
                  ? `${(comp.yield_spread_10y2y > 0 ? "+" : "")}${comp.yield_spread_10y2y.toFixed(2)}%` : "—"}
              </span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-zinc-500 text-xs">2Y Yield (30d Chg)</span>
              <span className={`text-sm font-mono ${(comp?.yield_2y_30d_change ?? 0) > 0 ? "text-red-400" : "text-blue-400"}`}>
                {comp?.yield_2y_30d_change !== null && comp?.yield_2y_30d_change !== undefined
                  ? `${comp.yield_2y_30d_change > 0 ? "+" : ""}${comp.yield_2y_30d_change.toFixed(3)}%` : "—"}
              </span>
            </div>
          </div>
          {comp?.days_to_next_fomc !== null && comp?.days_to_next_fomc !== undefined && (
            <div className="flex justify-between items-center">
              <span className="text-zinc-500 text-xs">Next FOMC</span>
              <span className={`text-sm font-mono ${
                comp.days_to_next_fomc <= 1 ? "text-orange-400" :
                comp.days_to_next_fomc <= 7 ? "text-yellow-400" : "text-zinc-400"
              }`}>
                {comp.days_to_next_fomc < 1
                  ? `${Math.round(comp.days_to_next_fomc * 24)}h`
                  : `${Math.round(comp.days_to_next_fomc)}d`}
              </span>
            </div>
          )}
          <div className="mt-auto pt-2 border-t border-zinc-800">
            <div className="text-zinc-500 text-xs mb-1">Market Score</div>
            <ScoreBar label="" score={comp?.market_score ?? null} />
          </div>
        </div>
      </div>

      {/* Score Breakdown */}
      <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-5">
        <div className="text-zinc-400 text-xs font-semibold uppercase tracking-wider mb-4">Score Breakdown</div>
        <div className="space-y-3">
          <ScoreBar label="Language (NLP)" score={comp?.language_score ?? null} showTier="T1+T2" />
          <ScoreBar label="Market-Implied" score={comp?.market_score ?? null} showTier="FRED" />
          <div className="border-t border-zinc-800 pt-3">
            <ScoreBar label="Composite" score={comp?.composite_score ?? null} />
          </div>
          <div className="border-t border-zinc-800 pt-3">
            <ScoreBar label="Divergence" score={comp?.divergence_score ?? null} />
          </div>
        </div>
        <div className="mt-3 text-xs text-zinc-600 flex gap-3">
          <span className="text-blue-500">◀ Dovish</span>
          <span className="flex-1 text-center">0</span>
          <span className="text-red-500">Hawkish ▶</span>
        </div>
      </div>

      {/* Key Phrases */}
      {(comp?.key_phrases?.length ?? 0) > 0 && (
        <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-5">
          <div className="text-zinc-400 text-xs font-semibold uppercase tracking-wider mb-3">
            Key Phrases Detected
          </div>
          <div className="space-y-1.5">
            {(comp?.key_phrases ?? []).slice(0, 8).map((phrase, i) => (
              <div key={i} className="text-zinc-400 text-xs bg-zinc-800/60 rounded px-3 py-1.5 leading-relaxed">
                &ldquo;{phrase.length > 120 ? phrase.slice(0, 120) + "…" : phrase}&rdquo;
              </div>
            ))}
          </div>
        </div>
      )}

      {/* History Chart */}
      {chartData.length > 1 && (
        <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-5">
          <div className="text-zinc-400 text-xs font-semibold uppercase tracking-wider mb-4">
            Score History (90 days)
          </div>
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={chartData} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
              <XAxis
                dataKey="date"
                tick={{ fill: "#71717a", fontSize: 10 }}
                tickFormatter={(v) => v.slice(5)}
              />
              <YAxis
                domain={[-100, 100]}
                tick={{ fill: "#71717a", fontSize: 10 }}
                tickCount={5}
              />
              <Tooltip
                contentStyle={{ background: "#18181b", border: "1px solid #3f3f46", borderRadius: 6 }}
                labelStyle={{ color: "#a1a1aa", fontSize: 11 }}
                itemStyle={{ fontSize: 11 }}
              />
              <ReferenceLine y={0} stroke="#52525b" strokeDasharray="4 4" />
              <ReferenceLine y={25} stroke="#ef4444" strokeDasharray="2 4" opacity={0.3} />
              <ReferenceLine y={-25} stroke="#3b82f6" strokeDasharray="2 4" opacity={0.3} />
              <Line
                type="monotone" dataKey="composite"
                stroke="#22c55e" strokeWidth={2} dot={false} name="Composite"
              />
              <Line
                type="monotone" dataKey="language"
                stroke="#a855f7" strokeWidth={1.5} dot={false}
                strokeDasharray="4 2" name="Language"
              />
              <Line
                type="monotone" dataKey="market"
                stroke="#f59e0b" strokeWidth={1.5} dot={false}
                strokeDasharray="4 2" name="Market"
              />
            </LineChart>
          </ResponsiveContainer>
          <div className="flex items-center gap-4 mt-2 justify-center">
            {[
              { color: "#22c55e", label: "Composite" },
              { color: "#a855f7", label: "Language" },
              { color: "#f59e0b", label: "Market" },
            ].map((l) => (
              <div key={l.label} className="flex items-center gap-1.5">
                <div className="w-3 h-0.5" style={{ background: l.color }} />
                <span className="text-zinc-500 text-xs">{l.label}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Phrase Transition Tracker */}
      <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-5">
        <div className="flex items-center justify-between mb-4">
          <div>
            <div className="text-zinc-400 text-xs font-semibold uppercase tracking-wider">
              Phrase Transition Tracker
            </div>
            <div className="text-zinc-600 text-xs mt-0.5">
              Key language shifts between consecutive FOMC statements — historically precede policy pivots
            </div>
          </div>
          {transitions.length > 0 && (
            <span className="text-xs bg-zinc-800 text-zinc-400 px-2 py-0.5 rounded">
              {transitions.length} detected
            </span>
          )}
        </div>

        {transitions.length === 0 ? (
          <div className="text-zinc-600 text-xs py-4 text-center">
            No transitions detected yet — click &ldquo;Detect Transitions&rdquo; after syncing FOMC statements with full text
          </div>
        ) : (
          <div className="space-y-2.5">
            {transitions.map((t) => (
              <PhraseTransitionCard key={t.id} transition={t} />
            ))}
          </div>
        )}
      </div>

      {/* Backtest Calibration */}
      <BacktestSection
        backtest={backtest}
        running={backtestRunning}
        currentMode={backtestUseTier2}
        onRun={handleRunBacktest}
      />

      {/* Documents Table */}
      <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-5">
        <div className="flex items-center justify-between mb-4">
          <div className="text-zinc-400 text-xs font-semibold uppercase tracking-wider">
            Fed Documents ({documents.length})
          </div>
          <div className="flex gap-3 text-xs text-zinc-600">
            <span>T1 = Dictionary scorer</span>
            <span>·</span>
            <span>Blended = T1 (30%) + T2 LLM (70%)</span>
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-zinc-800">
                <th className="text-left text-xs text-zinc-500 pb-2 pr-4">Date</th>
                <th className="text-left text-xs text-zinc-500 pb-2 pr-4">Type</th>
                <th className="text-left text-xs text-zinc-500 pb-2 pr-6">Title</th>
                <th className="text-right text-xs text-zinc-500 pb-2 pr-3">T1</th>
                <th className="text-right text-xs text-zinc-500 pb-2">Blended</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-800/50">
              {documents.length === 0 ? (
                <tr>
                  <td colSpan={5} className="text-zinc-600 text-xs py-6 text-center">
                    No documents — click &ldquo;Sync Documents&rdquo; to fetch from federalreserve.gov
                  </td>
                </tr>
              ) : (
                documents.slice(0, 25).map((doc) => (
                  <tr key={doc.id} className="hover:bg-zinc-800/30">
                    <td className="py-2 pr-4 text-zinc-500 text-xs whitespace-nowrap">
                      {formatDate(doc.document_date)}
                    </td>
                    <td className="py-2 pr-4 whitespace-nowrap">
                      <span className="text-xs bg-zinc-800 text-zinc-400 px-1.5 py-0.5 rounded">
                        {docTypeLabel(doc.document_type)}
                      </span>
                    </td>
                    <td className="py-2 pr-6">
                      {doc.source_url ? (
                        <a
                          href={doc.source_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-zinc-300 hover:text-white text-xs transition-colors"
                        >
                          {doc.title.length > 70 ? doc.title.slice(0, 70) + "…" : doc.title}
                        </a>
                      ) : (
                        <span className="text-zinc-400 text-xs">
                          {doc.title.length > 70 ? doc.title.slice(0, 70) + "…" : doc.title}
                        </span>
                      )}
                      {doc.speaker && (
                        <span className="ml-2 text-zinc-600 text-xs">{doc.speaker}</span>
                      )}
                    </td>
                    <td className={`py-2 pr-3 text-right font-mono text-xs ${scoreColor(doc.tier1_score)}`}>
                      {doc.tier1_score !== null && doc.tier1_score !== undefined
                        ? `${doc.tier1_score > 0 ? "+" : ""}${doc.tier1_score.toFixed(1)}`
                        : "—"}
                    </td>
                    <td className={`py-2 text-right font-mono text-xs font-semibold ${scoreColor(doc.blended_score ?? null)}`}>
                      {doc.blended_score !== null && doc.blended_score !== undefined
                        ? `${doc.blended_score > 0 ? "+" : ""}${doc.blended_score.toFixed(1)}`
                        : <span className="text-zinc-700">T1 only</span>}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {comp?.generated_at && (
        <div className="text-zinc-700 text-xs text-right">
          Updated {new Date(comp.generated_at).toLocaleString()}
        </div>
      )}
    </div>
  );
}
