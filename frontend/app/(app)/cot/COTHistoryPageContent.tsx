"use client";

import { useEffect, useState, useCallback, useMemo } from "react";
import {
  getCOTHistory,
  getCOTLatest,
  scrapeCOTData,
  COTSnapshot,
  COTLatestItem,
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
  Legend,
  ResponsiveContainer,
  ReferenceLine,
  ReferenceArea,
  Cell,
} from "recharts";

type DateRange = "1M" | "3M" | "6M" | "1Y" | "ALL";

const INSTRUMENTS = ["GOLD", "EUR", "GBP", "JPY", "OIL"];

const INSTRUMENT_COLORS: Record<string, string> = {
  GOLD: "#f59e0b",
  EUR: "#3b82f6",
  GBP: "#8b5cf6",
  JPY: "#ec4899",
  OIL: "#14b8a6",
};

const COT_INDEX_LOOKBACK = 52; // weeks

// ─── COT Index calculation ─────────────────────────────────────────────────

function computeCOTIndex(
  snapshots: COTSnapshot[],
  instrument: string,
  lookback: number = COT_INDEX_LOOKBACK
): { date: string; index: number }[] {
  // Filter and sort chronologically
  const sorted = snapshots
    .filter((s) => s.instrument === instrument)
    .sort((a, b) => a.report_date.localeCompare(b.report_date));

  if (sorted.length === 0) return [];

  return sorted.map((snap, i) => {
    // Look back N weeks from current position
    const windowStart = Math.max(0, i - lookback + 1);
    const window = sorted.slice(windowStart, i + 1);

    const nets = window.map((s) => s.commercial_net);
    const min = Math.min(...nets);
    const max = Math.max(...nets);
    const range = max - min;

    const index = range === 0 ? 50 : ((snap.commercial_net - min) / range) * 100;

    return {
      date: snap.report_date.slice(0, 10),
      index: Math.round(index * 10) / 10,
    };
  });
}

// ─── WoW Change calculation ─────────────────────────────────────────────────

function computeWoWChange(
  snapshots: COTSnapshot[],
  instrument: string
): { date: string; change: number }[] {
  const sorted = snapshots
    .filter((s) => s.instrument === instrument)
    .sort((a, b) => a.report_date.localeCompare(b.report_date));

  if (sorted.length < 2) return [];

  return sorted.slice(1).map((snap, i) => ({
    date: snap.report_date.slice(0, 10),
    change: snap.commercial_net - sorted[i].commercial_net,
  }));
}

// ─── Tooltip formatters ────────────────────────────────────────────────────

function formatDate(label: string) {
  const d = new Date(label);
  return d.toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

function formatTick(val: string) {
  const d = new Date(val);
  return `${d.getMonth() + 1}/${d.getFullYear().toString().slice(2)}`;
}

// ─── Main Component ────────────────────────────────────────────────────────

export default function COTHistoryPageContent() {
  const [snapshots, setSnapshots] = useState<COTSnapshot[]>([]);
  const [latest, setLatest] = useState<COTLatestItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [scraping, setScraping] = useState(false);
  const [scrapeResult, setScrapeResult] = useState<{
    success: boolean;
    instruments_updated: string[];
    errors: string[];
  } | null>(null);

  const [focusedInstrument, setFocusedInstrument] = useState("GOLD");
  const [dateRange, setDateRange] = useState<DateRange>("1Y");
  const [selectedIndexInstruments, setSelectedIndexInstruments] = useState<string[]>(["GOLD", "EUR", "GBP", "JPY"]);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      let dateFrom: string | undefined;
      if (dateRange !== "ALL") {
        const now = new Date();
        const months =
          dateRange === "1M" ? 1 : dateRange === "3M" ? 3 : dateRange === "6M" ? 6 : 12;
        // For COT Index we need extra lookback for the rolling window
        const extraMonths = dateRange === "1Y" ? 12 : dateRange === "6M" ? 12 : 6;
        now.setMonth(now.getMonth() - months - extraMonths);
        dateFrom = now.toISOString().slice(0, 10);
      }

      const limit = dateRange === "ALL" ? 5000 : 3000;
      const [historyData, latestData] = await Promise.all([
        getCOTHistory({ date_from: dateFrom, limit }),
        getCOTLatest(),
      ]);
      setSnapshots(historyData.items);
      setLatest(latestData.instruments);
    } catch (err) {
      console.error("Failed to load COT data:", err);
    } finally {
      setLoading(false);
    }
  }, [dateRange]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleScrape = async () => {
    setScraping(true);
    setScrapeResult(null);
    try {
      const result = await scrapeCOTData();
      setScrapeResult(result);
      if (result.success) {
        await loadData();
      }
    } catch (err) {
      console.error("Failed to scrape COT data:", err);
    } finally {
      setScraping(false);
    }
  };

  const toggleIndexInstrument = (inst: string) => {
    setSelectedIndexInstruments((prev) =>
      prev.includes(inst) ? prev.filter((i) => i !== inst) : [...prev, inst]
    );
  };

  // ─── Compute display date cutoff (exclude extra lookback data from charts)
  const displayDateFrom = useMemo(() => {
    if (dateRange === "ALL") return null;
    const now = new Date();
    const months =
      dateRange === "1M" ? 1 : dateRange === "3M" ? 3 : dateRange === "6M" ? 6 : 12;
    now.setMonth(now.getMonth() - months);
    return now.toISOString().slice(0, 10);
  }, [dateRange]);

  // ─── Chart 1: COT Index (multi-instrument) ───────────────────────────────

  const cotIndexData = useMemo(() => {
    const allSeries: Record<string, Record<string, number>> = {};

    for (const inst of selectedIndexInstruments) {
      const series = computeCOTIndex(snapshots, inst);
      for (const point of series) {
        if (displayDateFrom && point.date < displayDateFrom) continue;
        if (!allSeries[point.date]) allSeries[point.date] = {};
        allSeries[point.date][inst] = point.index;
      }
    }

    return Object.entries(allSeries)
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([date, data]) => ({ date, ...data }));
  }, [snapshots, selectedIndexInstruments, displayDateFrom]);

  // ─── Chart 2: Positioning overlay (single instrument) ─────────────────────

  const positioningData = useMemo(() => {
    const sorted = snapshots
      .filter((s) => s.instrument === focusedInstrument)
      .sort((a, b) => a.report_date.localeCompare(b.report_date))
      .filter((s) => !displayDateFrom || s.report_date.slice(0, 10) >= displayDateFrom);

    return sorted.map((s) => ({
      date: s.report_date.slice(0, 10),
      commercial_net: s.commercial_net,
      noncommercial_net: s.noncommercial_net,
      open_interest: s.open_interest,
    }));
  }, [snapshots, focusedInstrument, displayDateFrom]);

  // ─── Chart 3: WoW change (single instrument) ──────────────────────────────

  const wowData = useMemo(() => {
    const changes = computeWoWChange(snapshots, focusedInstrument);
    if (!displayDateFrom) return changes;
    return changes.filter((c) => c.date >= displayDateFrom);
  }, [snapshots, focusedInstrument, displayDateFrom]);

  // ─── Latest card for focused instrument ────────────────────────────────────

  const focusedLatest = latest.find((l) => l.instrument === focusedInstrument);

  const chartGridStyle = "#27272a";
  const tooltipStyle = {
    backgroundColor: "#18181b",
    border: "1px solid #27272a",
    borderRadius: "8px",
    fontSize: "12px",
    color: "#e4e4e7",
  };

  return (
    <div className="flex flex-col h-full overflow-y-auto">
      {/* ─── Header ─────────────────────────────────────────────────────── */}
      <div className="px-6 py-4 border-b border-zinc-800 shrink-0">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h1 className="text-white font-bold text-xl tracking-tight">
              COT ANALYSIS
            </h1>
            <p className="text-zinc-500 text-xs mt-0.5">
              Commitment of Traders — Index · Positioning · Weekly Changes
            </p>
          </div>
          <button
            onClick={handleScrape}
            disabled={scraping}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-zinc-700 disabled:text-zinc-500 text-white text-xs font-medium rounded transition-colors"
          >
            {scraping ? (
              <>
                <svg
                  className="animate-spin"
                  width="12"
                  height="12"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                >
                  <path d="M21 12a9 9 0 1 1-6.219-8.56" />
                </svg>
                Syncing...
              </>
            ) : (
              <>
                <svg
                  width="12"
                  height="12"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                >
                  <polyline points="23 4 23 10 17 10" />
                  <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" />
                </svg>
                Sync COT Data
              </>
            )}
          </button>
        </div>

        {scrapeResult && (
          <div
            className={`mb-3 px-3 py-2 border rounded text-xs ${
              scrapeResult.success
                ? "bg-green-900/30 border-green-800 text-green-400"
                : "bg-red-900/30 border-red-800 text-red-400"
            }`}
          >
            {scrapeResult.success
              ? `Updated: ${scrapeResult.instruments_updated.join(", ") || "none"}`
              : `Errors: ${scrapeResult.errors.join("; ")}`}
          </div>
        )}

        {/* Focused instrument summary card */}
        {focusedLatest && focusedLatest.report_date && (
          <div className="bg-zinc-900/50 border border-zinc-800 rounded px-4 py-3 mb-4">
            <div className="flex items-center justify-between mb-2">
              <span
                className="text-sm font-bold"
                style={{ color: INSTRUMENT_COLORS[focusedInstrument] }}
              >
                {focusedInstrument}
              </span>
              <span className="text-zinc-500 text-xs">
                Report: {focusedLatest.report_date}
              </span>
            </div>
            <div className="grid grid-cols-5 gap-4 text-xs">
              {[
                ["Comm Long", focusedLatest.commercial_long],
                ["Comm Short", focusedLatest.commercial_short],
                ["Comm Net", focusedLatest.commercial_net],
                ["Spec Net", focusedLatest.noncommercial_net],
                ["Open Interest", focusedLatest.open_interest],
              ].map(([label, val]) => (
                <div key={label as string}>
                  <p className="text-zinc-500">{label}</p>
                  <p
                    className={`font-mono font-medium ${
                      typeof val === "number" && val < 0
                        ? "text-red-400"
                        : "text-green-400"
                    }`}
                  >
                    {typeof val === "number"
                      ? (val >= 0 ? "+" : "") + val.toLocaleString()
                      : val}
                  </p>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ─── Filters ────────────────────────────────────────────────── */}
        <div className="flex items-center gap-6 flex-wrap">
          {/* Date range */}
          <div className="flex items-center gap-2">
            <span className="text-zinc-500 text-xs">Range:</span>
            <div className="flex gap-1">
              {(["1M", "3M", "6M", "1Y", "ALL"] as DateRange[]).map(
                (range) => (
                  <button
                    key={range}
                    onClick={() => setDateRange(range)}
                    className={`px-2 py-1 text-xs rounded transition-colors ${
                      dateRange === range
                        ? "bg-zinc-700 text-white"
                        : "bg-zinc-800 text-zinc-400 hover:text-zinc-200"
                    }`}
                  >
                    {range}
                  </button>
                )
              )}
            </div>
          </div>

          {/* Focus instrument (for charts 2 & 3) */}
          <div className="flex items-center gap-2">
            <span className="text-zinc-500 text-xs">Focus:</span>
            <div className="flex gap-1">
              {INSTRUMENTS.map((inst) => (
                <button
                  key={inst}
                  onClick={() => setFocusedInstrument(inst)}
                  className={`px-2 py-1 text-xs rounded transition-colors border ${
                    focusedInstrument === inst
                      ? "text-white border-current"
                      : "border-zinc-700 text-zinc-500 hover:text-zinc-300"
                  }`}
                  style={
                    focusedInstrument === inst
                      ? {
                          color: INSTRUMENT_COLORS[inst],
                          borderColor: INSTRUMENT_COLORS[inst],
                        }
                      : {}
                  }
                >
                  {inst}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* ─── Charts ─────────────────────────────────────────────────────── */}
      {loading ? (
        <div className="flex items-center justify-center flex-1">
          <p className="text-zinc-500 text-sm">Loading COT data...</p>
        </div>
      ) : cotIndexData.length === 0 ? (
        <div className="flex flex-col items-center justify-center flex-1 gap-3">
          <p className="text-zinc-400 text-sm">No COT data available</p>
          <p className="text-zinc-600 text-xs">
            Click &quot;Sync COT Data&quot; to fetch from CFTC
          </p>
        </div>
      ) : (
        <div className="flex flex-col px-6 py-4 gap-6 min-h-0">
          {/* ─── Chart 1: COT Index (primary, tall) ───────────────────── */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <div>
                <p className="text-white text-sm font-semibold">COT INDEX</p>
                <p className="text-zinc-500 text-xs">
                  Commercial net position normalized 0-100 over {COT_INDEX_LOOKBACK}-week
                  lookback — extremes signal reversals
                </p>
              </div>
              {/* Index instrument toggles */}
              <div className="flex gap-1">
                {INSTRUMENTS.map((inst) => (
                  <button
                    key={inst}
                    onClick={() => toggleIndexInstrument(inst)}
                    className={`px-2 py-0.5 text-[10px] rounded transition-colors ${
                      selectedIndexInstruments.includes(inst)
                        ? "text-white"
                        : "text-zinc-600"
                    }`}
                    style={
                      selectedIndexInstruments.includes(inst)
                        ? { color: INSTRUMENT_COLORS[inst] }
                        : {}
                    }
                  >
                    {inst}
                  </button>
                ))}
              </div>
            </div>
            <ResponsiveContainer width="100%" height={320}>
              <LineChart
                data={cotIndexData}
                margin={{ top: 5, right: 20, bottom: 5, left: 0 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke={chartGridStyle} />
                {/* Extreme zones */}
                <ReferenceArea
                  y1={90}
                  y2={100}
                  fill="#22c55e"
                  fillOpacity={0.08}
                />
                <ReferenceArea
                  y1={0}
                  y2={10}
                  fill="#ef4444"
                  fillOpacity={0.08}
                />
                <ReferenceLine
                  y={80}
                  stroke="#22c55e"
                  strokeDasharray="3 3"
                  strokeOpacity={0.4}
                />
                <ReferenceLine
                  y={20}
                  stroke="#ef4444"
                  strokeDasharray="3 3"
                  strokeOpacity={0.4}
                />
                <ReferenceLine
                  y={50}
                  stroke="#52525b"
                  strokeDasharray="2 4"
                  strokeOpacity={0.5}
                />
                <XAxis
                  dataKey="date"
                  tick={{ fill: "#71717a", fontSize: 10 }}
                  tickFormatter={formatTick}
                  interval="preserveStartEnd"
                  minTickGap={60}
                />
                <YAxis
                  domain={[0, 100]}
                  tick={{ fill: "#71717a", fontSize: 10 }}
                  ticks={[0, 20, 50, 80, 100]}
                  width={35}
                />
                <Tooltip
                  contentStyle={tooltipStyle}
                  labelFormatter={formatDate}
                  formatter={(value: number, name: string) => [
                    `${value.toFixed(1)}`,
                    `${name} Index`,
                  ]}
                />
                <Legend wrapperStyle={{ fontSize: "11px", color: "#a1a1aa" }} />
                {selectedIndexInstruments.map((inst) => (
                  <Line
                    key={inst}
                    type="monotone"
                    dataKey={inst}
                    stroke={INSTRUMENT_COLORS[inst] || "#fff"}
                    strokeWidth={2}
                    dot={false}
                    activeDot={{ r: 4, strokeWidth: 0 }}
                    connectNulls
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </div>

          {/* ─── Chart 2: Positioning Overlay (secondary) ─────────────── */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <div>
                <p className="text-white text-sm font-semibold">
                  POSITIONING —{" "}
                  <span style={{ color: INSTRUMENT_COLORS[focusedInstrument] }}>
                    {focusedInstrument}
                  </span>
                </p>
                <p className="text-zinc-500 text-xs">
                  Commercial (solid) vs Speculator (dashed) net contracts —
                  divergence = signal
                </p>
              </div>
            </div>
            <ResponsiveContainer width="100%" height={200}>
              <LineChart
                data={positioningData}
                margin={{ top: 5, right: 20, bottom: 5, left: 0 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke={chartGridStyle} />
                <ReferenceLine y={0} stroke="#52525b" />
                <XAxis
                  dataKey="date"
                  tick={{ fill: "#71717a", fontSize: 10 }}
                  tickFormatter={formatTick}
                  interval="preserveStartEnd"
                  minTickGap={60}
                />
                <YAxis
                  tick={{ fill: "#71717a", fontSize: 10 }}
                  tickFormatter={(val) => `${(val / 1000).toFixed(0)}k`}
                  width={50}
                />
                <Tooltip
                  contentStyle={tooltipStyle}
                  labelFormatter={formatDate}
                  formatter={(value: number, name: string) => [
                    value.toLocaleString(),
                    name === "commercial_net"
                      ? "Commercial"
                      : name === "noncommercial_net"
                      ? "Speculator"
                      : "Open Interest",
                  ]}
                />
                <Legend
                  wrapperStyle={{ fontSize: "11px", color: "#a1a1aa" }}
                  formatter={(value) =>
                    value === "commercial_net"
                      ? "Commercial"
                      : value === "noncommercial_net"
                      ? "Speculator"
                      : "Open Interest"
                  }
                />
                <Line
                  type="monotone"
                  dataKey="commercial_net"
                  stroke={INSTRUMENT_COLORS[focusedInstrument]}
                  strokeWidth={2}
                  dot={false}
                  activeDot={{ r: 3, strokeWidth: 0 }}
                />
                <Line
                  type="monotone"
                  dataKey="noncommercial_net"
                  stroke={INSTRUMENT_COLORS[focusedInstrument]}
                  strokeWidth={1.5}
                  strokeDasharray="6 3"
                  dot={false}
                  activeDot={{ r: 3, strokeWidth: 0 }}
                  opacity={0.6}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>

          {/* ─── Chart 3: Week-over-Week Change (secondary) ───────────── */}
          <div className="pb-4">
            <div className="flex items-center justify-between mb-2">
              <div>
                <p className="text-white text-sm font-semibold">
                  WEEKLY CHANGE —{" "}
                  <span style={{ color: INSTRUMENT_COLORS[focusedInstrument] }}>
                    {focusedInstrument}
                  </span>
                </p>
                <p className="text-zinc-500 text-xs">
                  Week-over-week change in commercial net positioning — spikes
                  confirm turns
                </p>
              </div>
            </div>
            <ResponsiveContainer width="100%" height={180}>
              <BarChart
                data={wowData}
                margin={{ top: 5, right: 20, bottom: 5, left: 0 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke={chartGridStyle} />
                <ReferenceLine y={0} stroke="#52525b" />
                <XAxis
                  dataKey="date"
                  tick={{ fill: "#71717a", fontSize: 10 }}
                  tickFormatter={formatTick}
                  interval="preserveStartEnd"
                  minTickGap={60}
                />
                <YAxis
                  tick={{ fill: "#71717a", fontSize: 10 }}
                  tickFormatter={(val) => `${(val / 1000).toFixed(0)}k`}
                  width={50}
                />
                <Tooltip
                  contentStyle={tooltipStyle}
                  labelFormatter={formatDate}
                  formatter={(value: number) => [
                    (value >= 0 ? "+" : "") + value.toLocaleString(),
                    "WoW Change",
                  ]}
                />
                <Bar dataKey="change" radius={[2, 2, 0, 0]}>
                  {wowData.map((entry, i) => (
                    <Cell
                      key={i}
                      fill={entry.change >= 0 ? "#22c55e" : "#ef4444"}
                      fillOpacity={0.7}
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}
    </div>
  );
}
