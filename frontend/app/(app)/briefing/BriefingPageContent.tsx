"use client";

import { useEffect, useState, useCallback } from "react";
import {
  getRegimeByInstrument,
  getOutcomeStats,
  getUpcomingEconEvents,
  getSignals,
  RegimeItem,
  OutcomeStats,
  EconEvent,
  TradingSignal,
} from "@/lib/api";
import { COTPositionsWidget } from "@/components/COTPositionsWidget";

interface MarketSnapshot {
  symbol: string;
  trend: string;
  volatility: string;
  confidence: string;
  rsi: number;
  bias: "BULLISH" | "BEARISH" | "NEUTRAL";
  riskOn: number;
}

function TrendIcon({ trend }: { trend: string }) {
  if (trend === "TRENDING_UP") {
    return (
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" className="text-green-400">
        <polyline points="23 6 13.5 15.5 8.5 10.5 1 18" />
        <polyline points="17 6 23 6 23 12" />
      </svg>
    );
  }
  if (trend === "TRENDING_DOWN") {
    return (
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" className="text-red-400">
        <polyline points="23 18 13.5 8.5 8.5 13.5 1 6" />
        <polyline points="17 18 23 18 23 12" />
      </svg>
    );
  }
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" className="text-zinc-400">
      <line x1="5" y1="12" x2="19" y2="12" />
    </svg>
  );
}

function computeRiskOn(trend: string, volatility: string): number {
  if (trend === "TRENDING_UP") return volatility === "HIGH" ? 85 : 75;
  if (trend === "TRENDING_DOWN") return volatility === "HIGH" ? 15 : 25;
  return 50;
}

function impactBadge(impact: string) {
  const cls =
    impact === "HIGH"
      ? "bg-red-900/50 text-red-400 border-red-800"
      : impact === "MEDIUM"
      ? "bg-yellow-900/50 text-yellow-400 border-yellow-800"
      : "bg-green-900/50 text-green-400 border-green-800";
  return (
    <span className={`px-1.5 py-0.5 rounded text-xs font-medium border ${cls}`}>
      {impact}
    </span>
  );
}

function formatTime(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", hour12: false });
}

function timeUntil(iso: string): string {
  const diff = new Date(iso).getTime() - Date.now();
  if (diff <= 0) return "NOW";
  const h = Math.floor(diff / 3600000);
  const m = Math.floor((diff % 3600000) / 60000);
  if (h > 24) return `${Math.floor(h / 24)}D`;
  if (h > 0) return `${h}H ${m}M`;
  return `${m}M`;
}

const WATCHED = ["EURUSD", "XAUUSD", "BTCUSD", "USDJPY", "GBPUSD", "NAS100"];

export default function BriefingPageContent() {
  const [regimes, setRegimes] = useState<Record<string, RegimeItem | null>>({});
  const [stats, setStats] = useState<OutcomeStats | null>(null);
  const [events, setEvents] = useState<EconEvent[]>([]);
  const [signals, setSignals] = useState<TradingSignal[]>([]);
  const [loading, setLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState<string>("");

  const loadAll = useCallback(async () => {
    setLoading(true);
    try {
      const [regimeResults, statsData, eventsData, signalsData] = await Promise.allSettled([
        Promise.allSettled(
          WATCHED.map(async (sym) => {
            const data = await getRegimeByInstrument(sym);
            return { sym, data };
          })
        ),
        getOutcomeStats(),
        getUpcomingEconEvents({ days: 7 }),
        getSignals({ limit: 20 }),
      ]);

      // Extract regimes
      if (regimeResults.status === "fulfilled") {
        const map: Record<string, RegimeItem | null> = {};
        regimeResults.value.forEach((r) => {
          if (r.status === "fulfilled") map[r.value.sym] = r.value.data;
        });
        setRegimes(map);
      }

      if (statsData.status === "fulfilled") setStats(statsData.value);
      if (eventsData.status === "fulfilled") setEvents((eventsData.value as any).items ?? []);
      if (signalsData.status === "fulfilled") setSignals(signalsData.value.items ?? []);

      setLastUpdated(new Date().toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", hour12: false }));
    } catch (err) {
      console.error("Briefing load error:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  // ─── Derived data ────────────────────────────────────────────────────────

  const overallRisk = (() => {
    const scores = WATCHED.map((s) =>
      regimes[s] ? computeRiskOn(regimes[s]!.trend, regimes[s]!.volatility_regime) : 50
    );
    return Math.round(scores.reduce((a, b) => a + b, 0) / scores.length);
  })();

  const riskLabel =
    overallRisk >= 65 ? "RISK-ON" : overallRisk >= 45 ? "NEUTRAL" : "RISK-OFF";
  const riskColor =
    overallRisk >= 65 ? "text-green-400" : overallRisk >= 45 ? "text-yellow-400" : "text-red-400";

  const winRate = stats?.win_rate ?? 0;
  const winColor = winRate >= 55 ? "text-green-400" : winRate >= 45 ? "text-yellow-400" : "text-red-400";

  const nextEvents = events.filter((e) => new Date(e.event_date).getTime() > Date.now()).slice(0, 5);
  const highImpactEvents = events.filter(
    (e) => (e.impact ?? "MEDIUM").toUpperCase() === "HIGH" && new Date(e.event_date).getTime() > Date.now()
  );

  const topSignals = [...signals]
    .filter((s) => s.outcome === undefined)
    .slice(0, 5);

  const marketSnapshots: MarketSnapshot[] = WATCHED.map((sym) => {
    const reg = regimes[sym];
    const trend = reg?.trend ?? "RANGING";
    const vol = reg?.volatility_regime ?? "NORMAL";
    const risk = computeRiskOn(trend, vol);
    const bias: MarketSnapshot["bias"] =
      risk >= 60 ? "BULLISH" : risk <= 40 ? "BEARISH" : "NEUTRAL";
    return {
      symbol: sym,
      trend,
      volatility: vol,
      confidence: reg?.confidence ?? "MEDIUM",
      rsi: reg?.rsi ?? 50,
      bias,
      riskOn: risk,
    };
  });

  return (
    <div className="flex flex-col h-full bg-black min-h-screen">
      {/* ─── Header ─────────────────────────────────────────────────── */}
      <div className="px-6 py-5 border-b border-zinc-800 bg-zinc-950/80 backdrop-blur-sm sticky top-0 z-10">
        <div className="flex items-center justify-between mb-1">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-green-500/10 border border-green-500/30 flex items-center justify-center">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#00FF41" strokeWidth="2">
                <path d="M12 2L2 7l10 5 10-5-10-5z" />
                <path d="M2 17l10 5 10-5" />
                <path d="M2 12l10 5 10-5" />
              </svg>
            </div>
            <div>
              <h1 className="text-white font-bold text-xl tracking-tight">MORNING BRIEFING</h1>
              <p className="text-zinc-500 text-xs">
                {new Date().toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric", year: "numeric" })}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
              <span className="text-green-400 text-xs font-medium">LIVE</span>
            </div>
            {lastUpdated && (
              <span className="text-zinc-600 text-xs">Updated {lastUpdated}</span>
            )}
            <button
              onClick={loadAll}
              disabled={loading}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-zinc-800 hover:bg-zinc-700 border border-zinc-700 rounded-lg text-zinc-400 hover:text-white text-xs transition-colors disabled:opacity-50"
            >
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
                className={loading ? "animate-spin" : ""}>
                <polyline points="23 4 23 10 17 10" />
                <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" />
              </svg>
              Refresh
            </button>
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-6 py-6 space-y-6">
        {/* ─── ① Macro Radar ──────────────────────────────────────── */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* Risk Mood */}
          <div className="bg-zinc-900/60 border border-zinc-800 rounded-xl p-5">
            <div className="flex items-center gap-2 mb-4">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-zinc-500">
                <circle cx="12" cy="12" r="10" />
                <path d="M12 8v4l3 3" />
              </svg>
              <span className="text-zinc-400 text-xs font-semibold uppercase tracking-wider">Risk Mood</span>
            </div>
            <div className="flex items-end gap-3">
              <div className="flex-1">
                <div className="relative h-3 rounded-full bg-zinc-800 overflow-hidden mb-2">
                  <div
                    className={`absolute left-0 top-0 h-full rounded-full transition-all duration-700 ${
                      overallRisk >= 65 ? "bg-green-400" : overallRisk >= 45 ? "bg-yellow-400" : "bg-red-400"
                    }`}
                    style={{ width: `${overallRisk}%` }}
                  />
                </div>
                <div className="flex justify-between">
                  <span className="text-red-400 text-xs">Risk-Off</span>
                  <span className="text-zinc-600 text-xs">50</span>
                  <span className="text-green-400 text-xs">Risk-On</span>
                </div>
              </div>
              <div className="text-right">
                <p className={`text-3xl font-bold ${riskColor}`}>{overallRisk}</p>
                <p className={`text-sm font-bold ${riskColor}`}>{riskLabel}</p>
              </div>
            </div>
          </div>

          {/* Win Rate Card */}
          <div className="bg-zinc-900/60 border border-zinc-800 rounded-xl p-5">
            <div className="flex items-center gap-2 mb-4">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-zinc-500">
                <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
              </svg>
              <span className="text-zinc-400 text-xs font-semibold uppercase tracking-wider">Signal Performance</span>
            </div>
            <div className="flex items-end gap-3">
              <div className="flex-1">
                <div className="relative h-3 rounded-full bg-zinc-800 overflow-hidden mb-2">
                  <div
                    className="absolute left-0 top-0 h-full rounded-full bg-green-500 transition-all duration-700"
                    style={{ width: `${winRate}%` }}
                  />
                  <div className="absolute left-1/2 top-0 h-full w-px bg-zinc-600" />
                </div>
                <div className="flex justify-between">
                  <span className="text-red-400 text-xs">0%</span>
                  <span className="text-zinc-600 text-xs">50%</span>
                  <span className="text-green-400 text-xs">100%</span>
                </div>
              </div>
              <div className="text-right">
                <p className={`text-3xl font-bold ${winColor}`}>{winRate}%</p>
                <p className="text-zinc-500 text-sm">Win Rate</p>
              </div>
            </div>
            {stats && (
              <div className="flex gap-4 mt-3 pt-3 border-t border-zinc-800">
                <div>
                  <p className="text-green-400 text-xs font-bold">{stats.won_count}W</p>
                </div>
                <div>
                  <p className="text-red-400 text-xs font-bold">{stats.lost_count}L</p>
                </div>
                <div>
                  <p className="text-zinc-500 text-xs font-bold">
                    {(stats.avg_pnl_pips ?? 0) > 0 ? "+" : ""}{(stats.avg_pnl_pips ?? 0).toFixed(1)} avg pips
                  </p>
                </div>
              </div>
            )}
          </div>

          {/* Economic Calendar Snapshot */}
          <div className="bg-zinc-900/60 border border-zinc-800 rounded-xl p-5">
            <div className="flex items-center gap-2 mb-3">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-zinc-500">
                <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
                <line x1="16" y1="2" x2="16" y2="6" />
                <line x1="8" y1="2" x2="8" y2="6" />
                <line x1="3" y1="10" x2="21" y2="10" />
              </svg>
              <span className="text-zinc-400 text-xs font-semibold uppercase tracking-wider">Today&apos;s High Impact</span>
              {highImpactEvents.length > 0 && (
                <span className="ml-auto px-2 py-0.5 rounded-full bg-red-900/50 text-red-400 text-xs font-bold border border-red-800">
                  {highImpactEvents.length}
                </span>
              )}
            </div>
            {highImpactEvents.length === 0 ? (
              <div className="flex items-center justify-center h-16">
                <p className="text-zinc-600 text-xs">No high-impact events today</p>
              </div>
            ) : (
              <div className="space-y-2">
                {highImpactEvents.slice(0, 3).map((ev) => (
                  <div key={ev.id} className="flex items-center gap-2">
                    <div className="w-6 h-6 rounded bg-zinc-800 flex items-center justify-center shrink-0">
                      <span className="text-zinc-400 text-xs font-bold">{ev.currency}</span>
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-zinc-300 text-xs truncate">{ev.event_name}</p>
                    </div>
                    <span className="text-zinc-500 text-xs font-mono shrink-0">
                      {formatTime(ev.event_date)}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* ─── ①.5 COT Net Positions Widget ─────────────────────── */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <COTPositionsWidget />
        </div>

        {/* ─── ② Market Radar Grid ────────────────────────────────── */}
        <div>
          <div className="flex items-center gap-2 mb-3">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-zinc-500">
              <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
            </svg>
            <h2 className="text-zinc-400 text-xs font-semibold uppercase tracking-wider">Market Radar</h2>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
            {marketSnapshots.map((snap) => {
              const bgColor =
                snap.bias === "BULLISH"
                  ? "border-green-800/50 bg-green-900/10"
                  : snap.bias === "BEARISH"
                  ? "border-red-800/50 bg-red-900/10"
                  : "border-zinc-800 bg-zinc-900/30";
              const biasTextColor =
                snap.bias === "BULLISH"
                  ? "text-green-400"
                  : snap.bias === "BEARISH"
                  ? "text-red-400"
                  : "text-zinc-400";
              const riskBarColor =
                snap.riskOn >= 65 ? "bg-green-400" : snap.riskOn >= 45 ? "bg-yellow-400" : "bg-red-400";

              return (
                <div key={snap.symbol} className={`border rounded-xl p-4 ${bgColor}`}>
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-white text-sm font-bold">{snap.symbol}</span>
                    <TrendIcon trend={snap.trend} />
                  </div>
                  <div className="flex items-center gap-1 mb-3">
                    <span className={`text-xs font-bold ${biasTextColor}`}>{snap.bias}</span>
                    <span className="text-zinc-600 text-xs">·</span>
                    <span className="text-zinc-500 text-xs">{snap.volatility}</span>
                  </div>
                  {/* Mini risk bar */}
                  <div className="relative h-1.5 rounded-full bg-zinc-800 overflow-hidden mb-1">
                    <div className={`absolute left-0 top-0 h-full rounded-full ${riskBarColor}`} style={{ width: `${snap.riskOn}%` }} />
                  </div>
                  <div className="flex justify-between">
                    <span className="text-zinc-600 text-xs">Risk</span>
                    <span className={`text-xs font-mono font-medium ${snap.riskOn >= 65 ? "text-green-400" : snap.riskOn >= 45 ? "text-yellow-400" : "text-red-400"}`}>
                      {snap.riskOn}
                    </span>
                  </div>
                  <div className="mt-2 pt-2 border-t border-zinc-800/50">
                    <div className="flex justify-between">
                      <span className="text-zinc-600 text-xs">Conf</span>
                      <span className="text-zinc-400 text-xs font-mono">{snap.confidence}</span>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* ─── ③ Active Signals ──────────────────────────────────── */}
        <div>
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-zinc-500">
                <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
              </svg>
              <h2 className="text-zinc-400 text-xs font-semibold uppercase tracking-wider">Active Setups</h2>
            </div>
            <span className="text-zinc-600 text-xs">{topSignals.length} open</span>
          </div>
          {loading ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
              {[1, 2, 3].map((i) => (
                <div key={i} className="h-28 bg-zinc-900/40 border border-zinc-800/50 rounded-xl animate-pulse" />
              ))}
            </div>
          ) : topSignals.length === 0 ? (
            <div className="border border-zinc-800 rounded-xl p-8 text-center">
              <p className="text-zinc-600 text-sm">No active setups</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
              {topSignals.map((sig) => {
                const dir = sig.final_signal?.toUpperCase() || sig.direction?.toUpperCase() || "";
                const isBuy = dir === "BUY" || dir === "LONG";
                const dirColor = isBuy ? "text-green-400" : "text-red-400";
                const dirBg = isBuy ? "bg-green-900/30 border-green-800" : "bg-red-900/30 border-red-800";

                return (
                  <div key={sig.id} className="border border-zinc-800 bg-zinc-900/40 rounded-xl p-4 hover:bg-zinc-900/70 transition-colors">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-white text-sm font-bold">{sig.asset}</span>
                      <span className={`px-2 py-0.5 rounded text-xs font-bold border ${dirBg} ${dirColor}`}>
                        {dir || "—"}
                      </span>
                    </div>
                    <div className="grid grid-cols-3 gap-2 text-xs">
                      <div>
                        <p className="text-zinc-600">Entry</p>
                        <p className="text-zinc-300 font-mono">
                          {sig.entry_price ? sig.entry_price.toFixed(sig.entry_price < 10 ? 4 : 2) : "—"}
                        </p>
                      </div>
                      <div>
                        <p className="text-zinc-600">Target</p>
                        <p className="text-green-400 font-mono">
                          {sig.target_price ? `↑${sig.target_price.toFixed(sig.target_price < 10 ? 4 : 2)}` : "—"}
                        </p>
                      </div>
                      <div>
                        <p className="text-zinc-600">Stop</p>
                        <p className="text-red-400 font-mono">
                          {sig.stop_loss ? sig.stop_loss.toFixed(sig.stop_loss < 10 ? 4 : 2) : "—"}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center justify-between mt-3 pt-2 border-t border-zinc-800/50">
                      <span className="text-zinc-600 text-xs">{sig.signal_confidence ?? 0}% confidence</span>
                      <span className="text-zinc-600 text-xs">{sig.market_regime ?? "—"}</span>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* ─── ④ Upcoming Economic Events ──────────────────────────── */}
        {nextEvents.length > 0 && (
          <div>
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-zinc-500">
                  <circle cx="12" cy="12" r="10" />
                  <polyline points="12 6 12 12 16 14" />
                </svg>
                <h2 className="text-zinc-400 text-xs font-semibold uppercase tracking-wider">Upcoming Catalysts</h2>
              </div>
              <a href="/economic-calendar" className="text-green-400 text-xs hover:text-green-300 transition-colors">
                Full calendar →
              </a>
            </div>
            <div className="border border-zinc-800 rounded-xl overflow-hidden">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-zinc-800">
                    <th className="text-left px-4 py-2 text-zinc-600 text-xs font-semibold uppercase tracking-wider">Time</th>
                    <th className="text-left px-4 py-2 text-zinc-600 text-xs font-semibold uppercase tracking-wider">Event</th>
                    <th className="text-left px-4 py-2 text-zinc-600 text-xs font-semibold uppercase tracking-wider">Currency</th>
                    <th className="text-left px-4 py-2 text-zinc-600 text-xs font-semibold uppercase tracking-wider">Impact</th>
                    <th className="text-left px-4 py-2 text-zinc-600 text-xs font-semibold uppercase tracking-wider">Countdown</th>
                  </tr>
                </thead>
                <tbody>
                  {nextEvents.map((ev, idx) => (
                    <tr key={ev.id ?? idx} className="border-b border-zinc-800/50 last:border-0 hover:bg-zinc-900/30 transition-colors">
                      <td className="px-4 py-3">
                        <span className="text-zinc-300 text-xs font-mono">{formatTime(ev.event_date)}</span>
                      </td>
                      <td className="px-4 py-3">
                        <span className="text-zinc-200 text-xs">{ev.event_name}</span>
                      </td>
                      <td className="px-4 py-3">
                        <div className="w-6 h-6 rounded bg-zinc-800 flex items-center justify-center">
                          <span className="text-zinc-400 text-xs font-bold">{ev.currency}</span>
                        </div>
                      </td>
                      <td className="px-4 py-3">{impactBadge((ev.impact ?? "MEDIUM").toUpperCase())}</td>
                      <td className="px-4 py-3">
                        <span className="text-green-400 text-xs font-mono font-medium">{timeUntil(ev.event_date)}</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* ─── ⑤ Regime Summary ──────────────────────────────────── */}
        {Object.keys(regimes).length > 0 && (
          <div>
            <div className="flex items-center gap-2 mb-3">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-zinc-500">
                <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
              </svg>
              <h2 className="text-zinc-400 text-xs font-semibold uppercase tracking-wider">Regime Analysis</h2>
            </div>
            <div className="border border-zinc-800 rounded-xl overflow-hidden">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-zinc-800">
                    <th className="text-left px-4 py-2 text-zinc-600 text-xs font-semibold uppercase tracking-wider">Instrument</th>
                    <th className="text-left px-4 py-2 text-zinc-600 text-xs font-semibold uppercase tracking-wider">Trend</th>
                    <th className="text-left px-4 py-2 text-zinc-600 text-xs font-semibold uppercase tracking-wider">Volatility</th>
                    <th className="text-left px-4 py-2 text-zinc-600 text-xs font-semibold uppercase tracking-wider">RSI</th>
                    <th className="text-left px-4 py-2 text-zinc-600 text-xs font-semibold uppercase tracking-wider">Confidence</th>
                    <th className="text-left px-4 py-2 text-zinc-600 text-xs font-semibold uppercase tracking-wider">Bias</th>
                  </tr>
                </thead>
                <tbody>
                  {WATCHED.map((sym) => {
                    const reg = regimes[sym];
                    if (!reg) return null;
                    const risk = computeRiskOn(reg.trend, reg.volatility_regime);
                    const bias =
                      risk >= 60 ? "BULLISH" : risk <= 40 ? "BEARISH" : "NEUTRAL";
                    const biasColor =
                      bias === "BULLISH"
                        ? "text-green-400"
                        : bias === "BEARISH"
                        ? "text-red-400"
                        : "text-zinc-400";
                    return (
                      <tr key={sym} className="border-b border-zinc-800/50 last:border-0 hover:bg-zinc-900/30 transition-colors">
                        <td className="px-4 py-3">
                          <span className="text-white text-xs font-bold">{sym}</span>
                        </td>
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-1.5">
                            <TrendIcon trend={reg.trend} />
                            <span className="text-zinc-300 text-xs capitalize">
                              {reg.trend.replace(/_/g, " ").toLowerCase()}
                            </span>
                          </div>
                        </td>
                        <td className="px-4 py-3">
                          <span className={`text-xs font-medium ${
                            reg.volatility_regime === "HIGH"
                              ? "text-red-400"
                              : reg.volatility_regime === "LOW"
                              ? "text-green-400"
                              : "text-zinc-400"
                          }`}>
                            {reg.volatility_regime}
                          </span>
                        </td>
                        <td className="px-4 py-3">
                          <span className="text-zinc-300 text-xs font-mono">{reg.rsi.toFixed(1)}</span>
                        </td>
                        <td className="px-4 py-3">
                          <span className="text-zinc-300 text-xs font-mono">{reg.confidence}</span>
                        </td>
                        <td className="px-4 py-3">
                          <span className={`text-xs font-bold ${biasColor}`}>{bias}</span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* ─── ⑥ Quick Stats Footer ──────────────────────────────── */}
        {stats && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="bg-zinc-900/40 border border-zinc-800 rounded-xl px-4 py-3 flex items-center gap-3">
              <div className="w-8 h-8 rounded-lg bg-zinc-800 flex items-center justify-center">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-zinc-400">
                  <path d="M18 20V10" /><path d="M12 20V4" /><path d="M6 20v-6" />
                </svg>
              </div>
              <div>
                <p className="text-white text-sm font-bold">{stats.total_setups}</p>
                <p className="text-zinc-600 text-xs">Total Setups</p>
              </div>
            </div>
            <div className="bg-zinc-900/40 border border-zinc-800 rounded-xl px-4 py-3 flex items-center gap-3">
              <div className="w-8 h-8 rounded-lg bg-zinc-800 flex items-center justify-center">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-green-400">
                  <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
                </svg>
              </div>
              <div>
                <p className="text-green-400 text-sm font-bold">
                  {stats.avg_pnl_pips != null
                    ? `${stats.avg_pnl_pips > 0 ? "+" : ""}${stats.avg_pnl_pips.toFixed(1)}`
                    : "—"} pips
                </p>
                <p className="text-zinc-600 text-xs">Avg P&L</p>
              </div>
            </div>
            <div className="bg-zinc-900/40 border border-zinc-800 rounded-xl px-4 py-3 flex items-center gap-3">
              <div className="w-8 h-8 rounded-lg bg-zinc-800 flex items-center justify-center">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-zinc-400">
                  <circle cx="12" cy="12" r="10" /><polyline points="12 6 12 12 16 14" />
                </svg>
              </div>
              <div>
                <p className="text-white text-sm font-bold">{stats.open_count}</p>
                <p className="text-zinc-600 text-xs">Open Setups</p>
              </div>
            </div>
            <div className="bg-zinc-900/40 border border-zinc-800 rounded-xl px-4 py-3 flex items-center gap-3">
              <div className="w-8 h-8 rounded-lg bg-zinc-800 flex items-center justify-center">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-zinc-400">
                  <polyline points="23 6 13.5 15.5 8.5 10.5 1 18" /><polyline points="17 6 23 6 23 12" />
                </svg>
              </div>
              <div>
                <p className="text-white text-sm font-bold">
                  {stats.avg_risk_reward != null ? `${stats.avg_risk_reward}:1` : "—"}
                </p>
                <p className="text-zinc-600 text-xs">Avg R:R</p>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
