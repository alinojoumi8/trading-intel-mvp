"use client";

import { useEffect, useState } from "react";
import { getCOTLatest, COTLatestItem } from "@/lib/api";

interface COTPosition {
  symbol: string;
  netCommercial: number;  // net commercial positions (long - short)
  netNonCommercial: number;
  netRetail: number;
  commercialPct: number;
  nonCommercialPct: number;
  trend: "up" | "down" | "neutral";
}

function NetBar({ value, max }: { value: number; max: number }) {
  const pct = Math.min(100, Math.abs(value) / Math.max(max, 1)) * 100;
  const isLong = value >= 0;
  return (
    <div className="relative h-3 bg-zinc-800 rounded overflow-hidden">
      {/* Center line */}
      <div className="absolute left-1/2 top-0 bottom-0 w-px bg-zinc-600" />
      {/* Position bar */}
      <div
        className={`absolute top-0 bottom-0 rounded transition-all ${
          isLong ? "bg-green-500/70 left-1/2" : "bg-red-500/70 right-1/2"
        }`}
        style={isLong ? { width: `${pct}%` } : { width: `${pct}%` }}
      />
    </div>
  );
}

function TrendIcon({ trend }: { trend: "up" | "down" | "neutral" }) {
  if (trend === "up") {
    return (
      <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" className="text-green-400">
        <polyline points="23 6 13.5 15.5 8.5 10.5 1 18" />
        <polyline points="17 6 23 6 23 12" />
      </svg>
    );
  }
  if (trend === "down") {
    return (
      <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" className="text-red-400">
        <polyline points="23 18 13.5 8.5 8.5 13.5 1 6" />
        <polyline points="17 18 23 18 23 12" />
      </svg>
    );
  }
  return (
    <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" className="text-zinc-400">
      <line x1="5" y1="12" x2="19" y2="12" />
    </svg>
  );
}

function classifyCOT(item: COTLatestItem): COTPosition {
  const commLong = item.commercial_long ?? 0;
  const commShort = item.commercial_short ?? 0;
  const nonCommLong = item.noncommercial_long ?? 0;
  const nonCommShort = item.noncommercial_short ?? 0;

  const netComm = item.commercial_net ?? (commLong - commShort);
  const netNonComm = item.noncommercial_net ?? (nonCommLong - nonCommShort);

  const totalComm = commLong + commShort;
  const totalNonComm = nonCommLong + nonCommShort;
  const totalAll = totalComm + totalNonComm;

  const commercialPct = totalAll > 0 ? (totalComm / totalAll) * 100 : 50;
  const nonCommercialPct = totalAll > 0 ? (totalNonComm / totalAll) * 100 : 0;

  // Determine trend from net commercial value
  const trend: "up" | "down" | "neutral" =
    netComm > 10000 ? "up" : netComm < -10000 ? "down" : "neutral";

  return {
    symbol: item.instrument ?? "UNKNOWN",
    netCommercial: netComm,
    netNonCommercial: netNonComm,
    netRetail: 0,
    commercialPct,
    nonCommercialPct,
    trend,
  };
}

export function COTPositionsWidget() {
  const [positions, setPositions] = useState<COTPosition[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<string>("ALL");

  useEffect(() => {
    async function fetchCOT() {
      setLoading(true);
      try {
        const data = await getCOTLatest();
        const mapped = (data.instruments ?? []).map(classifyCOT);
        setPositions(mapped);
      } catch {
        // non-critical widget
      } finally {
        setLoading(false);
      }
    }
    fetchCOT();
    const id = setInterval(fetchCOT, 10 * 60 * 1000); // refresh every 10 min
    return () => clearInterval(id);
  }, []);

  const assets = ["ALL", "GOLD", "EUR", "GBP", "JPY", "OIL"];
  const filtered = selected === "ALL" ? positions : positions.filter(p => p.symbol.includes(selected));

  const maxAbs = Math.max(...positions.map(p => Math.abs(p.netCommercial)), 1);

  return (
    <div className="bg-zinc-900/60 border border-zinc-800 rounded-lg p-4">
      {/* Header */}
      <div className="flex items-center gap-2 mb-3">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-zinc-400">
          <rect x="3" y="3" width="18" height="18" rx="2" />
          <path d="M3 9h18" />
          <path d="M9 21V9" />
        </svg>
        <h3 className="text-zinc-300 text-xs font-semibold uppercase tracking-wider">COT Net Positions</h3>
        <div className="ml-auto flex items-center gap-1">
          <div className="w-1.5 h-1.5 rounded-full bg-yellow-400 animate-pulse" />
          <span className="text-zinc-600 text-xs">CFTC</span>
        </div>
      </div>

      {/* Asset filter pills */}
      <div className="flex gap-1 flex-wrap mb-3">
        {assets.map(asset => (
          <button
            key={asset}
            onClick={() => setSelected(asset)}
            className={`px-2 py-0.5 text-xs rounded transition-colors ${
              selected === asset
                ? "bg-zinc-700 text-white"
                : "bg-zinc-800/50 text-zinc-500 hover:text-zinc-300"
            }`}
          >
            {asset}
          </button>
        ))}
      </div>

      {/* Legend */}
      <div className="flex items-center gap-3 mb-2 text-xs">
        <div className="flex items-center gap-1">
          <div className="w-2 h-2 rounded-sm bg-green-500/70" />
          <span className="text-zinc-500">Comm Long</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-2 h-2 rounded-sm bg-red-500/70" />
          <span className="text-zinc-500">Comm Short</span>
        </div>
        <div className="ml-auto flex items-center gap-1">
          <div className="w-px h-3 bg-zinc-600" />
          <span className="text-zinc-600 text-xs">50%</span>
        </div>
      </div>

      {/* Positions list */}
      {loading ? (
        <div className="space-y-2">
          {[1, 2, 3, 4].map(i => (
            <div key={i} className="h-10 bg-zinc-800/50 rounded animate-pulse" />
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-4">
          <p className="text-zinc-500 text-xs">No COT data available</p>
        </div>
      ) : (
        <div className="space-y-2">
          {filtered.slice(0, 6).map((pos) => {
            const commLongPct = pos.netCommercial >= 0 ? 50 + (pos.netCommercial / maxAbs) * 50 : 50;
            return (
              <div key={pos.symbol} className="bg-zinc-800/30 rounded p-2.5">
                <div className="flex items-center justify-between mb-1.5">
                  <div className="flex items-center gap-1.5">
                    <TrendIcon trend={pos.trend} />
                    <span className="text-white text-xs font-bold">{pos.symbol}</span>
                  </div>
                  <span className={`text-xs font-mono font-medium ${
                    pos.netCommercial >= 0 ? "text-green-400" : "text-red-400"
                  }`}>
                    {pos.netCommercial >= 0 ? "+" : ""}{pos.netCommercial.toLocaleString()}
                  </span>
                </div>

                {/* Net position bar */}
                <NetBar value={pos.netCommercial} max={maxAbs} />

                {/* Sub-position breakdown */}
                <div className="flex gap-2 mt-1.5">
                  <div className="flex items-center gap-1">
                    <div className="w-1.5 h-1.5 rounded-full bg-purple-400/60" />
                    <span className="text-zinc-600 text-xs">NC</span>
                    <span className={`text-xs font-mono ${
                      pos.netNonCommercial >= 0 ? "text-purple-400" : "text-orange-400"
                    }`}>
                      {pos.netNonCommercial >= 0 ? "+" : ""}{pos.netNonCommercial.toLocaleString()}
                    </span>
                  </div>
                  <div className="ml-auto">
                    <span className="text-zinc-600 text-xs">Comm {pos.commercialPct.toFixed(0)}%</span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Footer */}
      <div className="mt-3 pt-3 border-t border-zinc-800 flex items-center justify-between">
        <span className="text-zinc-600 text-xs">CFTC COT · Updates daily</span>
        <a href="/cot" className="text-yellow-400 text-xs hover:text-yellow-300 transition-colors">
          Full COT →
        </a>
      </div>
    </div>
  );
}
