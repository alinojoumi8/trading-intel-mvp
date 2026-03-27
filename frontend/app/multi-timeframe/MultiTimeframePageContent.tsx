"use client";

import { useEffect, useState, useCallback } from "react";
import { getMultiTimeframe, generateSetup, MultiTimeframeResponse, TimeframeData, SetupItem } from "@/lib/api";

// ─── Color helpers ──────────────────────────────────────────────────────────

function trendColor(trend: string): string {
  switch (trend) {
    case "TRENDING_UP": return "text-green-400";
    case "TRENDING_DOWN": return "text-red-400";
    default: return "text-zinc-400";
  }
}

function trendBg(trend: string): string {
  switch (trend) {
    case "TRENDING_UP": return "bg-green-900/20 border-green-800";
    case "TRENDING_DOWN": return "bg-red-900/20 border-red-800";
    default: return "bg-zinc-900/20 border-zinc-800";
  }
}

function consensusColor(consensus: string): string {
  switch (consensus) {
    case "BULLISH": return "text-green-400 bg-green-900/30 border-green-700";
    case "BEARISH": return "text-red-400 bg-red-900/30 border-red-700";
    default: return "text-yellow-400 bg-yellow-900/30 border-yellow-700";
  }
}

function rsiZoneColor(rsi: number): string {
  if (rsi >= 70) return "bg-red-500";
  if (rsi <= 30) return "bg-green-500";
  if (rsi >= 60) return "bg-yellow-500";
  if (rsi <= 40) return "bg-blue-500";
  return "bg-zinc-600";
}

function directionColor(dir?: string): string {
  switch (dir) {
    case "long": return "text-green-400";
    case "short": return "text-red-400";
    default: return "text-zinc-400";
  }
}

// ─── RSI Bar ─────────────────────────────────────────────────────────────────

function RSIBar({ rsi }: { rsi: number }) {
  const pct = Math.min(100, Math.max(0, rsi));
  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-center justify-between text-xs">
        <span className="text-zinc-500">RSI(14)</span>
        <span className={`font-bold ${
          rsi >= 70 ? "text-red-400" : rsi <= 30 ? "text-green-400" : "text-zinc-300"
        }`}>
          {rsi.toFixed(1)}
        </span>
      </div>
      <div className="h-2 bg-zinc-800 rounded overflow-hidden relative">
        {/* Zone backgrounds */}
        <div className="absolute inset-y-0 left-0 w-[30%] bg-green-500/10" />
        <div className="absolute inset-y-0 right-0 w-[30%] bg-red-500/10" />
        {/* RSI fill */}
        <div
          className={`h-full ${rsiZoneColor(rsi)} transition-all duration-500`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <div className="flex justify-between text-[9px] text-zinc-600">
        <span>Oversold 30</span>
        <span>70 Overbought</span>
      </div>
    </div>
  );
}

// ─── MA Display ───────────────────────────────────────────────────────────────

function MADisplay({ tf }: { tf: TimeframeData }) {
  const price = tf.current_price;
  const ma20 = tf.ma_20;
  const ma60 = tf.ma_60;
  const support = tf.key_support;
  const resistance = tf.key_resistance;

  const ma20Pct = ma20 ? ((price - ma20) / ma20) * 100 : 0;
  const ma60Pct = ma60 ? ((price - ma60) / ma60) * 100 : 0;

  return (
    <div className="space-y-1.5">
      <div className="flex justify-between text-xs">
        <span className="text-zinc-500">Price</span>
        <span className="text-white font-mono font-medium">{price > 0 ? price.toFixed(5) : "—"}</span>
      </div>
      <div className="flex justify-between text-xs">
        <span className="text-zinc-500">MA(20)</span>
        <span className={`font-mono ${price >= ma20 ? "text-green-400" : "text-red-400"}`}>
          {ma20 > 0 ? ma20.toFixed(5) : "—"}
          {ma20 > 0 && (
            <span className="text-[10px] ml-1">
              {ma20Pct >= 0 ? "+" : ""}{ma20Pct.toFixed(2)}%
            </span>
          )}
        </span>
      </div>
      <div className="flex justify-between text-xs">
        <span className="text-zinc-500">MA(60)</span>
        <span className={`font-mono ${price >= ma60 ? "text-green-400" : "text-red-400"}`}>
          {ma60 > 0 ? ma60.toFixed(5) : "—"}
          {ma60 > 0 && (
            <span className="text-[10px] ml-1">
              {ma60Pct >= 0 ? "+" : ""}{ma60Pct.toFixed(2)}%
            </span>
          )}
        </span>
      </div>
      <div className="border-t border-zinc-800 pt-1.5 mt-1.5">
        <div className="flex justify-between text-xs">
          <span className="text-zinc-500">Support</span>
          <span className="text-blue-400 font-mono">{support > 0 ? support.toFixed(5) : "—"}</span>
        </div>
        <div className="flex justify-between text-xs">
          <span className="text-zinc-500">Resistance</span>
          <span className="text-red-400 font-mono">{resistance > 0 ? resistance.toFixed(5) : "—"}</span>
        </div>
      </div>
    </div>
  );
}

// ─── Timeframe Column ─────────────────────────────────────────────────────────

function TFColumn({ tf }: { tf: TimeframeData }) {
  return (
    <div className={`border rounded-lg p-4 ${trendBg(tf.trend)}`}>
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className={`text-2xl font-black tracking-wider ${
            tf.trend === "TRENDING_UP"
              ? "text-green-400"
              : tf.trend === "TRENDING_DOWN"
              ? "text-red-400"
              : "text-zinc-500"
          }`}>
            {tf.trend === "TRENDING_UP" ? "H" : tf.trend === "TRENDING_DOWN" ? "L" : "—"}
          </span>
          <div>
            <p className="text-white font-bold text-lg">{tf.timeframe}</p>
            <p className={`text-xs font-medium ${trendColor(tf.trend)}`}>
              {tf.trend.replace("_", " ")}
            </p>
          </div>
        </div>
        <div className="text-right">
          <p className="text-zinc-400 text-[10px]">ATR(14)</p>
          <p className="text-zinc-300 font-mono text-sm">
            {tf.atr_14 > 0 ? tf.atr_14.toFixed(5) : "—"}
          </p>
        </div>
      </div>

      <RSIBar rsi={tf.rsi_14} />

      <div className="mt-4">
        <MADisplay tf={tf} />
      </div>

      {tf.signals.length > 0 && (
        <div className="mt-4">
          <p className="text-zinc-500 text-[10px] uppercase font-semibold mb-1.5">Signals</p>
          <div className="flex flex-col gap-1">
            {tf.signals.map((signal) => {
              const isBullish = signal.toLowerCase().includes("bullish") ||
                signal.toLowerCase().includes("above") ||
                signal.toLowerCase().includes("oversold") ||
                signal.toLowerCase().includes("golden") ||
                signal.includes("Support");
              const isBearish = signal.toLowerCase().includes("bearish") ||
                signal.toLowerCase().includes("below") ||
                signal.toLowerCase().includes("overbought") ||
                signal.toLowerCase().includes("death") ||
                signal.includes("Resistance");
              const dotColor = isBullish ? "text-green-400" : isBearish ? "text-red-400" : "text-zinc-500";
              return (
                <div key={signal} className="flex items-center gap-1.5">
                  <span className={`text-[8px] ${dotColor}`}>·</span>
                  <span className="text-zinc-400 text-xs">{signal}</span>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Setup Row ───────────────────────────────────────────────────────────────

function SetupRow({ setup }: { setup: SetupItem }) {
  return (
    <div className="flex items-center justify-between py-2 border-b border-zinc-800/50 last:border-0">
      <div className="flex-1">
        <p className="text-zinc-200 text-xs font-medium">{setup.title}</p>
        <div className="flex items-center gap-2 mt-0.5">
          {setup.direction && (
            <span className={`text-[10px] font-medium ${directionColor(setup.direction)}`}>
              {setup.direction.toUpperCase()}
            </span>
          )}
          {setup.timeframe && (
            <span className="text-[10px] text-zinc-500">{setup.timeframe}</span>
          )}
          {setup.confidence && (
            <span className="text-[10px] text-zinc-500">
              {setup.confidence.toUpperCase()} conf
            </span>
          )}
          {setup.risk_reward_ratio && (
            <span className="text-[10px] text-zinc-500">R:R {setup.risk_reward_ratio}:1</span>
          )}
        </div>
      </div>
      <div className="text-right shrink-0 ml-4">
        {setup.entry_zone && (
          <p className="text-zinc-400 text-xs font-mono">{setup.entry_zone}</p>
        )}
        {setup.stop_loss && setup.take_profit && (
          <p className="text-zinc-600 text-[10px]">
            SL: {setup.stop_loss} · TP: {setup.take_profit}
          </p>
        )}
      </div>
    </div>
  );
}

// ─── Main Content ──────────────────────────────────────────────────────────

const INSTRUMENTS = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "NZDUSD", "XAUUSD", "BTCUSD"];

export default function MultiTimeframePageContent() {
  const [instrument, setInstrument] = useState("EURUSD");
  const [data, setData] = useState<MultiTimeframeResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [generateMsg, setGenerateMsg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadMTF = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await getMultiTimeframe(instrument);
      setData(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load multi-timeframe data");
    } finally {
      setLoading(false);
    }
  }, [instrument]);

  useEffect(() => {
    loadMTF();
  }, [loadMTF]);

  const handleGenerate = async () => {
    setGenerating(true);
    setGenerateMsg(null);
    try {
      const result = await generateSetup(instrument);
      setGenerateMsg(result.message);
      // Reload MTF data to get new setups
      await loadMTF();
    } catch (err) {
      setGenerateMsg(err instanceof Error ? err.message : "Setup generation failed");
    } finally {
      setGenerating(false);
    }
  };

  const tfByKey = Object.fromEntries((data?.timeframes ?? []).map((tf) => [tf.timeframe, tf]));

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="px-6 py-4 border-b border-zinc-800">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h1 className="text-white font-bold text-xl tracking-tight">MULTI-TIMEFRAME ANALYSIS</h1>
            <p className="text-zinc-500 text-xs mt-0.5">
              H4 · D1 · W1 — Trend, RSI, Moving Averages, Support & Resistance
            </p>
          </div>
          {data && (
            <div className={`px-4 py-2 rounded-lg border text-sm font-bold ${consensusColor(data.consensus)}`}>
              {data.consensus}
            </div>
          )}
        </div>

        {/* Instrument Selector */}
        <div className="flex items-center gap-3 flex-wrap">
          <div className="flex items-center bg-zinc-900 border border-zinc-700 rounded px-3">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentZinc-500" strokeWidth="2" className="mr-2 shrink-0">
              <circle cx="11" cy="11" r="8" />
              <path d="m21 21-4.35-4.35" />
            </svg>
            <select
              value={instrument}
              onChange={(e) => setInstrument(e.target.value)}
              className="bg-transparent text-white text-sm py-2 pr-4 focus:outline-none cursor-pointer"
            >
              {INSTRUMENTS.map((inst) => (
                <option key={inst} value={inst} className="bg-zinc-900">
                  {inst}
                </option>
              ))}
            </select>
          </div>

          <button
            onClick={handleGenerate}
            disabled={generating}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-zinc-700 disabled:text-zinc-500 text-white text-xs font-medium rounded transition-colors"
          >
            {generating ? (
              <>
                <svg className="animate-spin" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M21 12a9 9 0 1 1-6.219-8.56" />
                </svg>
                Generating...
              </>
            ) : (
              <>
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <polygon points="5 3 19 12 5 21 5 3" />
                </svg>
                Generate Setup
              </>
            )}
          </button>

          {generateMsg && (
            <span className="text-xs text-zinc-400">{generateMsg}</span>
          )}
        </div>

        {error && (
          <div className="mt-2 px-3 py-2 bg-red-900/30 border border-red-800 rounded text-red-400 text-xs">
            {error}
          </div>
        )}
      </div>

      {/* Loading */}
      {loading && (
        <div className="flex items-center justify-center h-48">
          <p className="text-zinc-500 text-sm">Loading {instrument} multi-timeframe data...</p>
        </div>
      )}

      {/* Content */}
      {!loading && !error && data && (
        <div className="flex-1 overflow-y-auto px-6 py-4">
          {/* Three-column timeframe layout */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {(["H4", "D1", "W1"] as const).map((tfKey) => {
              const tf = tfByKey[tfKey];
              if (!tf) {
                return (
                  <div key={tfKey} className="border border-zinc-800 rounded-lg p-4 bg-zinc-950 flex items-center justify-center h-64">
                    <p className="text-zinc-600 text-sm">No data for {tfKey}</p>
                  </div>
                );
              }
              return <TFColumn key={tfKey} tf={tf} />;
            })}
          </div>

          {/* Consensus Banner */}
          <div className={`mt-4 border rounded-lg p-4 ${consensusColor(data.consensus)}`}>
            <div className="flex items-center gap-3">
              <span className="text-2xl">
                {data.consensus === "BULLISH" ? "🟢" : data.consensus === "BEARISH" ? "🔴" : "🟡"}
              </span>
              <div>
                <p className="font-bold text-sm">
                  {data.consensus === "BULLISH"
                    ? "All Timeframes Aligned — Bullish Consensus"
                    : data.consensus === "BEARISH"
                    ? "All Timeframes Aligned — Bearish Consensus"
                    : "Timeframes Conflicting — Mixed Picture"}
                </p>
                <p className="text-xs opacity-70 mt-0.5">
                  {data.timeframes.map((tf) => `${tf.timeframe}: ${tf.trend.replace("_", " ")}`).join(" · ")}
                </p>
              </div>
            </div>
          </div>

          {/* Related Setups */}
          <div className="mt-6">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-white font-semibold text-sm">
                Related Setups
                {data.setups.length > 0 && (
                  <span className="text-zinc-500 font-normal text-xs ml-2">({data.setups.length})</span>
                )}
              </h2>
            </div>

            <div className="border border-zinc-800 rounded-lg bg-zinc-950 divide-y divide-zinc-800/50">
              {data.setups.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-8 text-center">
                  <p className="text-zinc-400 text-sm">No setups found for {data.instrument}</p>
                  <p className="text-zinc-600 text-xs mt-1">
                    Click &ldquo;Generate Setup&rdquo; to create one
                  </p>
                </div>
              ) : (
                data.setups.map((setup) => (
                  <SetupRow key={setup.id} setup={setup} />
                ))
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
