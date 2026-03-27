"use client";

import { useEffect, useState, useCallback } from "react";
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
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
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

export default function COTHistoryPageContent() {
  const [snapshots, setSnapshots] = useState<COTSnapshot[]>([]);
  const [latest, setLatest] = useState<COTLatestItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [scraping, setScraping] = useState(false);
  const [scrapeResult, setScrapeResult] = useState<{ success: boolean; instruments_updated: string[]; errors: string[] } | null>(null);

  // Filters
  const [selectedInstruments, setSelectedInstruments] = useState<string[]>(["GOLD", "EUR", "GBP", "JPY"]);
  const [dateRange, setDateRange] = useState<DateRange>("3M");

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      // Calculate date_from based on dateRange
      let dateFrom: string | undefined;
      if (dateRange !== "ALL") {
        const now = new Date();
        const months = dateRange === "1M" ? 1 : dateRange === "3M" ? 3 : dateRange === "6M" ? 6 : 12;
        now.setMonth(now.getMonth() - months);
        dateFrom = now.toISOString().slice(0, 10);
      }

      const [historyData, latestData] = await Promise.all([
        getCOTHistory({ date_from: dateFrom, limit: 500 }),
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

  const toggleInstrument = (inst: string) => {
    setSelectedInstruments(prev =>
      prev.includes(inst) ? prev.filter(i => i !== inst) : [...prev, inst]
    );
  };

  // Transform data for the chart
  // Group by date, then pivot instruments
  const chartData = (() => {
    // Group by date and instrument
    const grouped: Record<string, Record<string, number>> = {};
    for (const snap of snapshots) {
      const dateKey = snap.report_date.slice(0, 10);
      if (!grouped[dateKey]) grouped[dateKey] = {};
      grouped[dateKey][snap.instrument] = snap.commercial_net;
    }

    return Object.entries(grouped)
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([date, instData]) => ({
        date,
        ...instData,
      }));
  })();

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="px-6 py-4 border-b border-zinc-800">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h1 className="text-white font-bold text-xl tracking-tight">COT HISTORY</h1>
            <p className="text-zinc-500 text-xs mt-0.5">Commitment of Traders — Commercial vs Non-Commercial Net Positions</p>
          </div>
          <button
            onClick={handleScrape}
            disabled={scraping}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-zinc-700 disabled:text-zinc-500 text-white text-xs font-medium rounded transition-colors"
          >
            {scraping ? (
              <>
                <svg className="animate-spin" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M21 12a9 9 0 1 1-6.219-8.56" />
                </svg>
                Scraping...
              </>
            ) : (
              <>
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <polyline points="23 4 23 10 17 10" />
                  <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" />
                </svg>
                Refresh COT Data
              </>
            )}
          </button>
        </div>

        {scrapeResult && (
          <div className={`mb-3 px-3 py-2 border rounded text-xs ${
            scrapeResult.success
              ? "bg-green-900/30 border-green-800 text-green-400"
              : "bg-red-900/30 border-red-800 text-red-400"
          }`}>
            {scrapeResult.success
              ? `Updated: ${scrapeResult.instruments_updated.join(", ") || "none"}`
              : `Errors: ${scrapeResult.errors.join("; ")}`}
          </div>
        )}

        {/* Latest snapshot cards */}
        {latest.length > 0 && (
          <div className="flex gap-3 flex-wrap mb-4">
            {latest.map(item => (
              <div key={item.instrument} className="bg-zinc-900/50 border border-zinc-800 rounded px-3 py-2 min-w-44">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-white text-xs font-bold" style={{ color: INSTRUMENT_COLORS[item.instrument] || "#fff" }}>
                    {item.instrument}
                  </span>
                  <span className="text-zinc-500 text-xs">{item.report_date || "No data"}</span>
                </div>
                <div className="flex gap-3 text-xs">
                  <div>
                    <span className="text-zinc-500">Comm: </span>
                    <span className={`font-mono font-medium ${
                      item.commercial_net >= 0 ? "text-green-400" : "text-red-400"
                    }`}>
                      {item.commercial_net >= 0 ? "+" : ""}{item.commercial_net.toLocaleString()}
                    </span>
                  </div>
                  <div>
                    <span className="text-zinc-500">NonComm: </span>
                    <span className={`font-mono font-medium ${
                      item.noncommercial_net >= 0 ? "text-green-400" : "text-red-400"
                    }`}>
                      {item.noncommercial_net >= 0 ? "+" : ""}{item.noncommercial_net.toLocaleString()}
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Filters */}
        <div className="flex items-center gap-4 flex-wrap">
          <div className="flex items-center gap-2">
            <span className="text-zinc-500 text-xs">Range:</span>
            <div className="flex gap-1">
              {(["1M", "3M", "6M", "1Y", "ALL"] as DateRange[]).map(range => (
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
              ))}
            </div>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-zinc-500 text-xs">Instruments:</span>
            <div className="flex gap-1">
              {INSTRUMENTS.map(inst => (
                <button
                  key={inst}
                  onClick={() => toggleInstrument(inst)}
                  className={`px-2 py-1 text-xs rounded transition-colors border ${
                    selectedInstruments.includes(inst)
                      ? "border-current text-white"
                      : "border-zinc-700 text-zinc-500 hover:text-zinc-300"
                  }`}
                  style={selectedInstruments.includes(inst) ? { color: INSTRUMENT_COLORS[inst], borderColor: INSTRUMENT_COLORS[inst] } : {}}
                >
                  {inst}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Chart */}
      <div className="flex-1 px-6 py-4 overflow-hidden">
        {loading ? (
          <div className="flex items-center justify-center h-full">
            <p className="text-zinc-500 text-sm">Loading COT data...</p>
          </div>
        ) : chartData.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full gap-3">
            <p className="text-zinc-400 text-sm">No COT data available</p>
            <p className="text-zinc-600 text-xs">Click "Refresh COT Data" to fetch from CFTC</p>
          </div>
        ) : (
          <div className="h-full">
            <p className="text-zinc-500 text-xs mb-2">Commercial Net Positioning Over Time</p>
            <ResponsiveContainer width="100%" height="85%">
              <LineChart data={chartData} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
                <XAxis
                  dataKey="date"
                  tick={{ fill: "#71717a", fontSize: 10 }}
                  tickFormatter={(val) => {
                    const d = new Date(val);
                    return `${d.getMonth() + 1}/${d.getFullYear().toString().slice(2)}`;
                  }}
                  interval="preserveStartEnd"
                  minTickGap={60}
                />
                <YAxis
                  tick={{ fill: "#71717a", fontSize: 10 }}
                  tickFormatter={(val) => `${(val / 1000).toFixed(0)}k`}
                  width={50}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "#18181b",
                    border: "1px solid #27272a",
                    borderRadius: "8px",
                    fontSize: "12px",
                    color: "#e4e4e7",
                  }}
                  labelFormatter={(label) => {
                    const d = new Date(label);
                    return d.toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric" });
                  }}
                  formatter={(value: number, name: string) => [
                    value.toLocaleString(),
                    name,
                  ]}
                />
                <Legend
                  wrapperStyle={{ fontSize: "12px", color: "#a1a1aa" }}
                />
                {selectedInstruments.map(inst => (
                  <Line
                    key={inst}
                    type="monotone"
                    dataKey={inst}
                    stroke={INSTRUMENT_COLORS[inst] || "#fff"}
                    strokeWidth={2}
                    dot={false}
                    activeDot={{ r: 4, strokeWidth: 0 }}
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>
    </div>
  );
}
