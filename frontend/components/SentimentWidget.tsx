"use client";

import { useEffect, useState } from "react";
import { getRegimeByInstrument, RegimeItem } from "@/lib/api";

interface AssetSentiment {
  symbol: string;
  regime: string;
  trend: "up" | "down" | "neutral";
  color: string;
  riskOn: number; // 0-100, risk-on score
}

const ASSETS = ["BTC", "ETH", "GOLD", "EURUSD"];

function riskOnColor(score: number): string {
  if (score >= 65) return "text-green-400";
  if (score >= 45) return "text-yellow-400";
  return "text-red-400";
}

function riskOnBarColor(score: number): string {
  if (score >= 65) return "bg-green-400";
  if (score >= 45) return "bg-yellow-400";
  return "bg-red-400";
}

function computeRiskOn(trend: string, volatility: string): number {
  if (trend === "TRENDING_UP") return volatility === "HIGH" ? 85 : 75;
  if (trend === "TRENDING_DOWN") return volatility === "HIGH" ? 15 : 25;
  return 50; // RANGING
}

function RegimeIcon({ trend }: { trend: string }) {
  if (trend === "TRENDING_UP") {
    return (
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
        <polyline points="23 6 13.5 15.5 8.5 10.5 1 18" />
        <polyline points="17 6 23 6 23 12" />
      </svg>
    );
  }
  if (trend === "TRENDING_DOWN") {
    return (
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
        <polyline points="23 18 13.5 8.5 8.5 13.5 1 6" />
        <polyline points="17 18 23 18 23 12" />
      </svg>
    );
  }
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
      <line x1="5" y1="12" x2="19" y2="12" />
    </svg>
  );
}

export function SentimentWidget() {
  const [regimes, setRegimes] = useState<Record<string, RegimeItem | null>>({
    BTC: null,
    ETH: null,
    GOLD: null,
    EURUSD: null,
  });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchRegimes() {
      setLoading(true);
      try {
        const results = await Promise.allSettled(
          ASSETS.map(async (asset) => {
            const data = await getRegimeByInstrument(asset);
            return { asset, data };
          })
        );
        const newRegimes: Record<string, RegimeItem | null> = {};
        results.forEach((r) => {
          if (r.status === "fulfilled") {
            newRegimes[r.value.asset] = r.value.data;
          }
        });
        setRegimes((prev) => ({ ...prev, ...newRegimes }));
      } catch {
        // non-critical
      } finally {
        setLoading(false);
      }
    }
    fetchRegimes();
    const id = setInterval(fetchRegimes, 5 * 60 * 1000);
    return () => clearInterval(id);
  }, []);

  // Derive overall risk-on score (average of all assets)
  const scores = ASSETS.map((a) =>
    regimes[a] ? computeRiskOn(regimes[a]!.trend, regimes[a]!.volatility_regime) : 50
  );
  const overallRisk = Math.round(scores.reduce((a, b) => a + b, 0) / scores.length);

  const btcRisk = regimes.BTC ? computeRiskOn(regimes.BTC.trend, regimes.BTC.volatility_regime) : 50;
  const ethRisk = regimes.ETH ? computeRiskOn(regimes.ETH.trend, regimes.ETH.volatility_regime) : 50;
  const goldRisk = regimes.GOLD ? computeRiskOn(regimes.GOLD.trend, regimes.GOLD.volatility_regime) : 50;
  const eurusdRisk = regimes.EURUSD ? computeRiskOn(regimes.EURUSD.trend, regimes.EURUSD.volatility_regime) : 50;

  return (
    <div className="bg-zinc-900/60 border border-zinc-800 rounded-lg p-4">
      {/* Header */}
      <div className="flex items-center gap-2 mb-4">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-zinc-400">
          <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
        </svg>
        <h3 className="text-zinc-300 text-xs font-semibold uppercase tracking-wider">Market Sentiment</h3>
        <div className="ml-auto flex items-center gap-1">
          <div className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse" />
          <span className="text-zinc-600 text-xs">LIVE</span>
        </div>
      </div>

      {/* Overall Risk Gauge */}
      <div className="mb-4 bg-zinc-800/40 rounded-lg px-3 py-3">
        <div className="flex items-center justify-between mb-2">
          <span className="text-zinc-400 text-xs">Risk-On / Risk-Off</span>
          <span className={`text-sm font-bold ${riskOnColor(overallRisk)}`}>
            {overallRisk >= 65 ? "RISK-ON" : overallRisk >= 45 ? "NEUTRAL" : "RISK-OFF"}
          </span>
        </div>
        {/* Gauge bar */}
        <div className="relative h-2 rounded-full bg-zinc-700 overflow-hidden">
          <div
            className={`absolute left-0 top-0 h-full rounded-full transition-all duration-700 ${riskOnBarColor(overallRisk)}`}
            style={{ width: `${overallRisk}%` }}
          />
          {/* 50% marker */}
          <div className="absolute left-1/2 top-0 h-full w-px bg-zinc-500/50" />
        </div>
        <div className="flex justify-between mt-1">
          <span className="text-red-400 text-xs">Risk-Off</span>
          <span className="text-zinc-600 text-xs">50</span>
          <span className="text-green-400 text-xs">Risk-On</span>
        </div>
      </div>

      {/* Per-Asset Sentiment */}
      {loading ? (
        <div className="space-y-2">
          {[1, 2, 3, 4].map(i => (
            <div key={i} className="h-10 bg-zinc-800/50 rounded animate-pulse" />
          ))}
        </div>
      ) : (
        <div className="space-y-2">
          {ASSETS.map((asset) => {
            const data = regimes[asset];
            const trend = data?.trend ?? "RANGING";
            const volatility = data?.volatility_regime ?? "NORMAL";
            const risk = computeRiskOn(trend, volatility);
            const trendColor = risk >= 60 ? "text-green-400" : risk <= 40 ? "text-red-400" : "text-zinc-400";
            const barColor = riskOnBarColor(risk);

            return (
              <div key={asset} className="flex items-center gap-3">
                {/* Asset label */}
                <div className="w-14 shrink-0">
                  <span className="text-white text-xs font-bold">{asset}</span>
                </div>

                {/* Regime indicator */}
                <div className={`w-16 shrink-0 flex items-center gap-1 ${trendColor}`}>
                  <RegimeIcon trend={trend} />
                  <span className="text-xs font-medium capitalize">
                    {trend.replace(/_/g, " ").toLowerCase()}
                  </span>
                </div>

                {/* Risk bar */}
                <div className="flex-1 relative h-1.5 rounded-full bg-zinc-700 overflow-hidden">
                  <div
                    className={`absolute left-0 top-0 h-full rounded-full transition-all ${barColor}`}
                    style={{ width: `${risk}%` }}
                  />
                </div>

                {/* Score */}
                <div className={`w-10 shrink-0 text-right text-xs font-mono font-medium ${riskOnColor(risk)}`}>
                  {risk}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Footer */}
      <div className="mt-3 pt-3 border-t border-zinc-800">
        <span className="text-zinc-600 text-xs">Refreshes every 5 min</span>
      </div>
    </div>
  );
}
