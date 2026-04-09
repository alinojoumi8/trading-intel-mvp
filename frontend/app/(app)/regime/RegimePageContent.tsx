"use client";

import { useEffect, useState, useCallback } from "react";
import { getRegime, RegimeItem, RegimeResponse } from "@/lib/api";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  ReferenceArea,
} from "recharts";

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
    case "TRENDING_UP": return "bg-green-900/30 border-green-800";
    case "TRENDING_DOWN": return "bg-red-900/30 border-red-800";
    default: return "bg-zinc-900/30 border-zinc-800";
  }
}

function rsiColor(rsi: number): string {
  if (rsi >= 70) return "text-red-400";
  if (rsi <= 30) return "text-green-400";
  if (rsi >= 60) return "text-yellow-400";
  if (rsi <= 40) return "text-blue-400";
  return "text-zinc-300";
}

function confidenceBadge(conf: string): string {
  switch (conf) {
    case "HIGH": return "bg-green-900/50 text-green-400 border border-green-700";
    case "MEDIUM": return "bg-yellow-900/50 text-yellow-400 border border-yellow-700";
    default: return "bg-zinc-800/50 text-zinc-400 border border-zinc-700";
  }
}

function volatilityColor(vol: string): string {
  switch (vol) {
    case "HIGH": return "text-red-400";
    case "LOW": return "text-blue-400";
    default: return "text-zinc-300";
  }
}

// ─── Trend Arrow ───────────────────────────────────────────────────────────

function TrendArrow({ trend }: { trend: string }) {
  if (trend === "TRENDING_UP") return <span className="text-green-400 text-lg">▲</span>;
  if (trend === "TRENDING_DOWN") return <span className="text-red-400 text-lg">▼</span>;
  return <span className="text-zinc-500 text-lg">◆</span>;
}

// ─── RSI Gauge ─────────────────────────────────────────────────────────────

function RSIGauge({ rsi }: { rsi: number }) {
  const pct = Math.min(100, Math.max(0, rsi));
  const fillColor = rsi >= 70 ? "#ef4444" : rsi <= 30 ? "#22c55e" : "#eab308";
  return (
    <div className="flex flex-col items-center gap-1">
      <div className="w-16 h-16 relative">
        <svg viewBox="0 0 36 36" className="w-full h-full -rotate-90">
          <circle cx="18" cy="18" r="15.5" fill="none" stroke="#27272a" strokeWidth="3" />
          <circle
            cx="18" cy="18" r="15.5" fill="none"
            stroke={fillColor}
            strokeWidth="3"
            strokeDasharray={`${pct} 100`}
            strokeLinecap="round"
          />
        </svg>
        <div className="absolute inset-0 flex items-center justify-center">
          <span className={`text-xs font-bold ${rsiColor(rsi)}`}>{Math.round(rsi)}</span>
        </div>
      </div>
      <p className="text-zinc-500 text-[10px]">RSI(14)</p>
    </div>
  );
}

// ─── Regime Card ────────────────────────────────────────────────────────────

function RegimeCard({ item, selected, onClick }: { item: RegimeItem; selected: boolean; onClick: () => void }) {
  return (
    <div
      onClick={onClick}
      className={`cursor-pointer border rounded-lg p-4 transition-all ${trendBg(item.trend)} ${
        selected ? "ring-2 ring-zinc-500" : "hover:border-zinc-600"
      }`}
    >
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="text-white font-bold text-sm">{item.instrument}</span>
          <TrendArrow trend={item.trend} />
        </div>
        <span className={`text-[10px] font-bold px-2 py-0.5 rounded ${confidenceBadge(item.confidence)}`}>
          {item.confidence}
        </span>
      </div>

      <div className="flex items-center gap-3">
        <RSIGauge rsi={item.rsi} />
        <div className="flex-1 space-y-1">
          <div className="flex justify-between text-xs">
            <span className="text-zinc-500">ATR%</span>
            <span className={`font-mono font-medium ${volatilityColor(item.volatility_regime)}`}>
              {item.atr_percent.toFixed(4)}%
            </span>
          </div>
          <div className="flex justify-between text-xs">
            <span className="text-zinc-500">Vol</span>
            <span className={`font-medium ${volatilityColor(item.volatility_regime)}`}>
              {item.volatility_regime}
            </span>
          </div>
          <div className="flex justify-between text-xs">
            <span className="text-zinc-500">Trend</span>
            <span className={`font-medium ${trendColor(item.trend)}`}>
              {item.trend.replace("_", " ")}
            </span>
          </div>
        </div>
      </div>

      {item.signals.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1">
          {item.signals.slice(0, 3).map((s) => (
            <span key={s} className="text-[9px] px-1.5 py-0.5 bg-zinc-800/60 text-zinc-400 rounded">
              {s}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

// ─── Regime History Chart ──────────────────────────────────────────────────

interface HistoryDataPoint {
  date: string;
  rsi: number;
  regime: string;
  atr_percent: number;
}

function buildChartData(history: RegimeItem["regime_history"]): HistoryDataPoint[] {
  return history.map((h) => ({
    date: h.recorded_at ? new Date(h.recorded_at).toLocaleDateString("en-US", { month: "short", day: "numeric" }) : "",
    rsi: h.rsi_14,
    regime: h.regime,
    atr_percent: h.atr_percent,
  }));
}

function RegimeHistoryChart({ history }: { history: RegimeItem["regime_history"] }) {
  const data = buildChartData(history);

  if (data.length < 2) {
    return (
      <div className="flex items-center justify-center h-40 text-zinc-500 text-sm">
        Not enough history data yet. Check back tomorrow.
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={220}>
      <LineChart data={data} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
        <XAxis
          dataKey="date"
          tick={{ fill: "#71717a", fontSize: 10 }}
          tickLine={{ stroke: "#27272a" }}
        />
        <YAxis
          domain={[0, 100]}
          tick={{ fill: "#71717a", fontSize: 10 }}
          tickLine={{ stroke: "#27272a" }}
        />
        <Tooltip
          contentStyle={{ backgroundColor: "#18181b", border: "1px solid #27272a", fontSize: 12 }}
          labelStyle={{ color: "#a1a1aa" }}
        />
        {/* Overbought zone */}
        <ReferenceArea y1={70} y2={100} fill="#ef4444" fillOpacity={0.08} />
        {/* Oversold zone */}
        <ReferenceArea y1={0} y2={30} fill="#22c55e" fillOpacity={0.08} />
        <ReferenceLine y={70} stroke="#ef4444" strokeDasharray="3 3" strokeOpacity={0.5} />
        <ReferenceLine y={50} stroke="#52525b" strokeDasharray="3 3" strokeOpacity={0.3} />
        <ReferenceLine y={30} stroke="#22c55e" strokeDasharray="3 3" strokeOpacity={0.5} />
        <Line
          type="monotone"
          dataKey="rsi"
          stroke="#60a5fa"
          strokeWidth={2}
          dot={false}
          activeDot={{ r: 4, fill: "#60a5fa" }}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}

// ─── Main Content ──────────────────────────────────────────────────────────

const ALL_INSTRUMENTS = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "NZDUSD", "XAUUSD", "BTCUSD", "ETHUSD", "SPY"];

export default function RegimePageContent() {
  const [data, setData] = useState<RegimeResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedInstrument, setSelectedInstrument] = useState<string | null>(null);
  const [filter, setFilter] = useState<string>("ALL");
  const [error, setError] = useState<string | null>(null);

  const loadRegime = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await getRegime();
      setData(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load regime data");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadRegime();
  }, [loadRegime]);

  const filteredItems = data?.items.filter((item) => {
    if (filter === "ALL") return true;
    return item.instrument === filter;
  }) ?? [];

  const selectedItem = selectedInstrument
    ? filteredItems.find((i) => i.instrument === selectedInstrument)
    : null;

  const instrumentStats = {
    trendingUp: data?.items.filter((i) => i.trend === "TRENDING_UP").length ?? 0,
    trendingDown: data?.items.filter((i) => i.trend === "TRENDING_DOWN").length ?? 0,
    ranging: data?.items.filter((i) => i.trend === "RANGING").length ?? 0,
    highVol: data?.items.filter((i) => i.volatility_regime === "HIGH").length ?? 0,
  };

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="px-6 py-4 border-b border-zinc-800">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h1 className="text-white font-bold text-xl tracking-tight">MARKET REGIME</h1>
            <p className="text-zinc-500 text-xs mt-0.5">
              Trend direction · Volatility regime · RSI levels
            </p>
          </div>
          {data && (
            <div className="flex gap-4 text-xs">
              <div className="text-center">
                <p className="text-green-400 text-lg font-bold">{instrumentStats.trendingUp}</p>
                <p className="text-zinc-600">Trending Up</p>
              </div>
              <div className="text-center">
                <p className="text-red-400 text-lg font-bold">{instrumentStats.trendingDown}</p>
                <p className="text-zinc-600">Trending Down</p>
              </div>
              <div className="text-center">
                <p className="text-zinc-400 text-lg font-bold">{instrumentStats.ranging}</p>
                <p className="text-zinc-600">Ranging</p>
              </div>
              <div className="text-center">
                <p className="text-orange-400 text-lg font-bold">{instrumentStats.highVol}</p>
                <p className="text-zinc-600">High Vol</p>
              </div>
            </div>
          )}
        </div>

        {/* Filter */}
        <div className="flex items-center gap-2 flex-wrap">
          <button
            onClick={() => { setFilter("ALL"); setSelectedInstrument(null); }}
            className={`px-3 py-1 text-xs rounded transition-colors ${
              filter === "ALL" ? "bg-zinc-700 text-white" : "bg-zinc-800 text-zinc-400 hover:bg-zinc-700"
            }`}
          >
            ALL
          </button>
          {ALL_INSTRUMENTS.map((inst) => (
            <button
              key={inst}
              onClick={() => { setFilter(inst); setSelectedInstrument(null); }}
              className={`px-3 py-1 text-xs rounded transition-colors ${
                filter === inst ? "bg-zinc-700 text-white" : "bg-zinc-800 text-zinc-400 hover:bg-zinc-700"
              }`}
            >
              {inst}
            </button>
          ))}
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="mx-6 mt-4 px-4 py-3 bg-red-900/30 border border-red-800 rounded text-red-400 text-sm">
          {error}
        </div>
      )}

      {/* Loading */}
      {loading && (
        <div className="flex items-center justify-center h-40">
          <p className="text-zinc-500 text-sm">Loading regime data...</p>
        </div>
      )}

      {/* Regime Grid */}
      {!loading && !error && (
        <div className="flex-1 overflow-y-auto px-6 py-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {filteredItems.map((item) => (
              <RegimeCard
                key={item.instrument}
                item={item}
                selected={selectedInstrument === item.instrument}
                onClick={() =>
                  setSelectedInstrument(selectedInstrument === item.instrument ? null : item.instrument)
                }
              />
            ))}
          </div>

          {/* Legend */}
          <div className="mt-6 flex items-center gap-6 text-xs text-zinc-500">
            <div className="flex items-center gap-1.5">
              <span className="text-green-400">▲</span> TRENDING_UP
            </div>
            <div className="flex items-center gap-1.5">
              <span className="text-red-400">▼</span> TRENDING_DOWN
            </div>
            <div className="flex items-center gap-1.5">
              <span className="text-zinc-500">◆</span> RANGING
            </div>
            <div className="flex items-center gap-1.5 ml-4 border-l border-zinc-800 pl-4">
              <span className="text-red-400">▮</span> Overbought (RSI &gt;70)
            </div>
            <div className="flex items-center gap-1.5">
              <span className="text-green-400">▮</span> Oversold (RSI &lt;30)
            </div>
          </div>

          {/* Regime History Section */}
          {(selectedItem || filter !== "ALL") && (
            <div className="mt-8">
              <div className="flex items-center justify-between mb-3">
                <h2 className="text-white font-semibold text-sm">
                  {selectedItem ? `Regime History — ${selectedItem.instrument}` : "Regime History (All Instruments)"}
                </h2>
                <button
                  onClick={() => setSelectedInstrument(null)}
                  className="text-zinc-500 hover:text-white text-xs transition-colors"
                >
                  Clear selection
                </button>
              </div>

              {selectedItem ? (
                <div className="border border-zinc-800 rounded-lg p-4 bg-zinc-950">
                  <div className="mb-4 flex items-center gap-4 text-xs">
                    <div>
                      <span className="text-zinc-500">Current RSI: </span>
                      <span className={`font-bold ${rsiColor(selectedItem.rsi)}`}>{selectedItem.rsi}</span>
                    </div>
                    <div>
                      <span className="text-zinc-500">ATR%: </span>
                      <span className={`font-bold ${volatilityColor(selectedItem.volatility_regime)}`}>
                        {selectedItem.atr_percent.toFixed(4)}%
                      </span>
                    </div>
                    <div>
                      <span className="text-zinc-500">Volatility: </span>
                      <span className={`font-bold ${volatilityColor(selectedItem.volatility_regime)}`}>
                        {selectedItem.volatility_regime}
                      </span>
                    </div>
                  </div>
                  <RegimeHistoryChart history={selectedItem.regime_history} />
                  <p className="text-zinc-600 text-[10px] mt-2 text-center">
                    RSI(14) over last {selectedItem.regime_history.length} sessions · Red = Overbought, Green = Oversold
                  </p>
                </div>
              ) : (
                <div className="border border-zinc-800 rounded-lg p-4 bg-zinc-950">
                  <p className="text-zinc-500 text-xs mb-4 text-center">
                    Select a single instrument to view its regime history chart
                  </p>
                  <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
                    {filteredItems.map((item) => (
                      <div key={item.instrument} className="text-center">
                        <p className="text-zinc-400 text-xs font-medium mb-1">{item.instrument}</p>
                        <p className={`text-lg font-bold ${trendColor(item.trend)}`}>
                          {item.trend === "TRENDING_UP" ? "▲" : item.trend === "TRENDING_DOWN" ? "▼" : "◆"}
                        </p>
                        <p className={`text-xs font-mono ${rsiColor(item.rsi)}`}>RSI {item.rsi}</p>
                        <p className={`text-[10px] ${volatilityColor(item.volatility_regime)}`}>
                          {item.volatility_regime} vol
                        </p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
