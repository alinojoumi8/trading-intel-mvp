"use client";

import { useEffect, useState, useCallback } from "react";
import { getCorrelation, CorrelationResponse } from "@/lib/api";

const AVAILABLE_INSTRUMENTS = [
  "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "NZDUSD", "XAUUSD",
  "XAGUSD", "BTCUSD", "ETHUSD", "SPY", "QQQ", "DXY",
];

const DEFAULT_INSTRUMENTS = "EURUSD,GBPUSD,USDJPY,AUDUSD,USDCAD,NZDUSD,XAUUSD";

const TIMEFRAMES = [
  { value: "1M", label: "1 Month" },
  { value: "3M", label: "3 Months" },
  { value: "6M", label: "6 Months" },
];

// ─── Color helpers ──────────────────────────────────────────────────────────

function correlationToColor(value: number): string {
  // Red (-1) → White (0) → Green (+1)
  if (value >= 0) {
    const intensity = Math.round(value * 200);
    return `rgb(${255 - intensity}, ${255}, ${255 - intensity})`;
  } else {
    const intensity = Math.round(Math.abs(value) * 200);
    return `rgb(255, ${255 - intensity}, ${255 - intensity})`;
  }
}

function correlationTextColor(value: number): string {
  return Math.abs(value) > 0.5 ? "text-white" : "text-zinc-800";
}

// ─── Heatmap Cell ──────────────────────────────────────────────────────────

interface HeatmapCellProps {
  row: number;
  col: number;
  value: number;
  rowLabel: string;
  colLabel: string;
  isDiagonal: boolean;
}

function HeatmapCell({ row, col, value, rowLabel, colLabel, isDiagonal }: HeatmapCellProps) {
  const [showTooltip, setShowTooltip] = useState(false);

  if (isDiagonal) {
    return (
      <div
        className="w-14 h-14 flex items-center justify-center text-zinc-500 text-xs font-mono border border-zinc-800 bg-zinc-900"
        title={`${rowLabel} (self)`}
      >
        1.00
      </div>
    );
  }

  return (
    <div
      className="relative w-14 h-14 flex items-center justify-center text-xs font-mono border border-zinc-800 cursor-pointer transition-transform hover:scale-105 hover:z-10"
      style={{ backgroundColor: correlationToColor(value) }}
      onMouseEnter={() => setShowTooltip(true)}
      onMouseLeave={() => setShowTooltip(false)}
      title={`${rowLabel} vs ${colLabel}: ${value.toFixed(4)}`}
    >
      <span className={correlationTextColor(value)}>
        {value.toFixed(2)}
      </span>
      {showTooltip && (
        <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-3 py-2 bg-zinc-900 border border-zinc-700 rounded-lg text-white text-xs whitespace-nowrap z-50 shadow-lg">
          <p className="font-semibold">{rowLabel} / {colLabel}</p>
          <p className="text-zinc-400">Correlation: <span className="text-white font-mono">{value.toFixed(4)}</span></p>
          {value > 0.7 && <p className="text-green-400">Strong positive</p>}
          {value < -0.7 && <p className="text-red-400">Strong negative</p>}
          {value >= -0.7 && value <= 0.7 && <p className="text-yellow-400">Weak/Mixed</p>}
          <div className="absolute top-full left-1/2 -translate-x-1/2 border-4 border-transparent border-t-zinc-700" />
        </div>
      )}
    </div>
  );
}

// ─── Correlation Heatmap ────────────────────────────────────────────────────

interface CorrelationHeatmapProps {
  data: CorrelationResponse;
}

function CorrelationHeatmap({ data }: CorrelationHeatmapProps) {
  const { instruments, matrix } = data;
  const n = instruments.length;

  return (
    <div className="inline-block">
      {/* Column headers */}
      <div className="flex ml-14 mb-1">
        {instruments.map(inst => (
          <div key={inst} className="w-14 text-center text-[10px] text-zinc-500 font-medium mx-px">
            {inst}
          </div>
        ))}
      </div>

      {/* Rows */}
      <div className="space-y-px">
        {instruments.map((rowInst, i) => (
          <div key={rowInst} className="flex items-center">
            {/* Row label */}
            <div className="w-14 text-right pr-2 text-[10px] text-zinc-500 font-medium">
              {rowInst}
            </div>
            {/* Cells */}
            <div className="flex space-x-px">
              {instruments.map((colInst, j) => (
                <HeatmapCell
                  key={`${i}-${j}`}
                  row={i}
                  col={j}
                  value={matrix[i][j]}
                  rowLabel={rowInst}
                  colLabel={colInst}
                  isDiagonal={i === j}
                />
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── Color Legend ───────────────────────────────────────────────────────────

function ColorLegend() {
  const steps = [-1, -0.75, -0.5, -0.25, 0, 0.25, 0.5, 0.75, 1];
  return (
    <div className="flex items-center gap-2">
      <span className="text-zinc-500 text-[10px]">-1</span>
      <div className="flex h-3 w-40 rounded overflow-hidden">
        {steps.map((val, i) => (
          <div
            key={i}
            className="flex-1"
            style={{ backgroundColor: correlationToColor(val) }}
          />
        ))}
      </div>
      <span className="text-zinc-500 text-[10px]">+1</span>
      <div className="flex items-center gap-3 ml-4 text-[10px] text-zinc-500">
        <span className="flex items-center gap-1">
          <span className="w-3 h-3 rounded" style={{ backgroundColor: correlationToColor(-0.8) }} />
          Negative
        </span>
        <span className="flex items-center gap-1">
          <span className="w-3 h-3 rounded" style={{ backgroundColor: correlationToColor(0) }} />
          Neutral
        </span>
        <span className="flex items-center gap-1">
          <span className="w-3 h-3 rounded" style={{ backgroundColor: correlationToColor(0.8) }} />
          Positive
        </span>
      </div>
    </div>
  );
}

// ─── Main Content ──────────────────────────────────────────────────────────

export default function CorrelationPageContent() {
  const [data, setData] = useState<CorrelationResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedInstruments, setSelectedInstruments] = useState(DEFAULT_INSTRUMENTS);
  const [timeframe, setTimeframe] = useState("3M");
  const [showCustom, setShowCustom] = useState(false);

  const loadCorrelation = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await getCorrelation({
        instruments: selectedInstruments,
        timeframe,
      });
      setData(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load correlation data");
    } finally {
      setLoading(false);
    }
  }, [selectedInstruments, timeframe]);

  useEffect(() => {
    loadCorrelation();
  }, [loadCorrelation]);

  const handleInstrumentToggle = (inst: string) => {
    const current = selectedInstruments.split(",").map(s => s.trim()).filter(Boolean);
    if (current.includes(inst)) {
      if (current.length <= 2) return; // Keep at least 2
      setSelectedInstruments(current.filter(i => i !== inst).join(","));
    } else {
      setSelectedInstruments([...current, inst].join(","));
    }
  };

  const presets = [
    { label: "Major FX", value: "EURUSD,GBPUSD,USDJPY,AUDUSD,USDCAD,NZDUSD" },
    { label: "FX + Gold", value: "EURUSD,GBPUSD,USDJPY,AUDUSD,USDCAD,NZDUSD,XAUUSD" },
    { label: "All FX", value: "EURUSD,GBPUSD,USDJPY,AUDUSD,USDCAD,NZDUSD,XAUUSD,XAGUSD" },
    { label: "Crypto", value: "BTCUSD,ETHUSD" },
  ];

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="px-6 py-4 border-b border-zinc-800">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h1 className="text-white font-bold text-xl tracking-tight">FX CORRELATION MATRIX</h1>
            <p className="text-zinc-500 text-xs mt-0.5">
              Pearson correlation of daily returns · {data?.timeframe || "3M"}
            </p>
          </div>
          {data && (
            <p className="text-zinc-600 text-[10px]">
              Updated: {new Date(data.computed_at).toLocaleString()}
            </p>
          )}
        </div>

        {/* Timeframe selector */}
        <div className="flex items-center gap-4 mb-3">
          <div className="flex items-center gap-2">
            <span className="text-zinc-500 text-xs">Timeframe:</span>
            <div className="flex gap-1">
              {TIMEFRAMES.map(tf => (
                <button
                  key={tf.value}
                  onClick={() => setTimeframe(tf.value)}
                  className={`px-3 py-1 text-xs rounded transition-colors ${
                    timeframe === tf.value
                      ? "bg-blue-900/50 text-blue-400 border border-blue-700"
                      : "bg-zinc-800 text-zinc-400 hover:bg-zinc-700 border border-transparent"
                  }`}
                >
                  {tf.label}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Instrument presets */}
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-zinc-500 text-xs">Presets:</span>
          {presets.map(preset => (
            <button
              key={preset.label}
              onClick={() => setSelectedInstruments(preset.value)}
              className={`px-2 py-1 text-[10px] rounded transition-colors ${
                selectedInstruments === preset.value
                  ? "bg-zinc-700 text-white"
                  : "bg-zinc-800 text-zinc-500 hover:bg-zinc-700"
              }`}
            >
              {preset.label}
            </button>
          ))}
          <button
            onClick={() => setShowCustom(!showCustom)}
            className={`px-2 py-1 text-[10px] rounded transition-colors ${
              showCustom ? "bg-zinc-700 text-white" : "bg-zinc-800 text-zinc-500 hover:bg-zinc-700"
            }`}
          >
            Custom
          </button>
        </div>

        {/* Custom instrument selector */}
        {showCustom && (
          <div className="mt-3 p-3 border border-zinc-700 rounded bg-zinc-950">
            <p className="text-zinc-500 text-[10px] mb-2">Select instruments (min 2, max 10):</p>
            <div className="flex flex-wrap gap-1">
              {AVAILABLE_INSTRUMENTS.map(inst => {
                const isSelected = selectedInstruments.split(",").map(s => s.trim()).includes(inst);
                return (
                  <button
                    key={inst}
                    onClick={() => handleInstrumentToggle(inst)}
                    disabled={
                      !isSelected && selectedInstruments.split(",").length >= 10
                    }
                    className={`px-2 py-0.5 text-[10px] rounded transition-colors ${
                      isSelected
                        ? "bg-blue-900/50 text-blue-400 border border-blue-700"
                        : "bg-zinc-800 text-zinc-500 hover:bg-zinc-700 border border-transparent disabled:opacity-40"
                    }`}
                  >
                    {inst}
                  </button>
                );
              })}
            </div>
          </div>
        )}
      </div>

      {/* Error */}
      {error && (
        <div className="mx-6 mt-4 px-4 py-3 bg-red-900/30 border border-red-800 rounded text-red-400 text-xs">
          {error}
        </div>
      )}

      {/* Content */}
      <div className="flex-1 overflow-y-auto px-6 py-4">
        {loading ? (
          <div className="flex items-center justify-center h-64">
            <div className="flex flex-col items-center gap-3">
              <div className="w-8 h-8 border-2 border-zinc-600 border-t-transparent rounded-full animate-spin" />
              <p className="text-zinc-500 text-sm">Fetching market data...</p>
            </div>
          </div>
        ) : data ? (
          <div>
            {/* Summary */}
            <div className="grid grid-cols-2 gap-4 mb-6">
              {data.strongest_positive[2] > 0.5 && (
                <div className="border border-green-900/50 bg-green-950/20 rounded-lg p-3">
                  <p className="text-green-400 text-[10px] uppercase tracking-wider mb-1">Strongest Positive</p>
                  <p className="text-white text-sm font-medium">
                    {data.strongest_positive[0]} / {data.strongest_positive[1]}
                  </p>
                  <p className="text-green-400 text-lg font-bold font-mono">
                    +{data.strongest_positive[2].toFixed(4)}
                  </p>
                </div>
              )}
              {data.strongest_negative[2] < -0.5 && (
                <div className="border border-red-900/50 bg-red-950/20 rounded-lg p-3">
                  <p className="text-red-400 text-[10px] uppercase tracking-wider mb-1">Strongest Negative</p>
                  <p className="text-white text-sm font-medium">
                    {data.strongest_negative[0]} / {data.strongest_negative[1]}
                  </p>
                  <p className="text-red-400 text-lg font-bold font-mono">
                    {data.strongest_negative[2].toFixed(4)}
                  </p>
                </div>
              )}
            </div>

            {/* Heatmap */}
            <div className="overflow-x-auto pb-4">
              <CorrelationHeatmap data={data} />
            </div>

            {/* Legend */}
            <div className="mt-6">
              <ColorLegend />
            </div>

            {/* Interpretation guide */}
            <div className="mt-6 grid grid-cols-3 gap-4 text-xs">
              <div className="border border-zinc-800 rounded p-3">
                <p className="text-green-400 font-semibold mb-1">{">"} 0.7</p>
                <p className="text-zinc-500">Strong positive correlation — pairs move together</p>
              </div>
              <div className="border border-zinc-800 rounded p-3">
                <p className="text-yellow-400 font-semibold mb-1">-0.7 to 0.7</p>
                <p className="text-zinc-500">Weak/no correlation — pairs move independently</p>
              </div>
              <div className="border border-zinc-800 rounded p-3">
                <p className="text-red-400 font-semibold mb-1">{"<"} -0.7</p>
                <p className="text-zinc-500">Strong negative correlation — pairs move opposite</p>
              </div>
            </div>

            {/* Trading note */}
            <p className="text-zinc-600 text-[10px] mt-4 italic">
              Note: High positive correlation ({">"} 0.7) suggests pairs move together — avoid redundant positions.
              High negative correlation ({"<"} -0.7) suggests pairs move opposite — can be used for hedging.
            </p>
          </div>
        ) : null}
      </div>
    </div>
  );
}
