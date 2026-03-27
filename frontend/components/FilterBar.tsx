"use client";

import { useRouter, useSearchParams } from "next/navigation";

const contentTypes = [
  { value: "", label: "All Types" },
  { value: "briefing", label: "Briefing" },
  { value: "setup", label: "Trade Setup" },
  { value: "macro_roundup", label: "Macro Roundup" },
  { value: "contrarian_alert", label: "Contrarian Alert" },
];

const assetClasses = [
  { value: "", label: "All Assets" },
  { value: "FX", label: "FX" },
  { value: "Commodities", label: "Commodities" },
  { value: "Crypto", label: "Crypto" },
  { value: "Indices", label: "Indices" },
];

const directions = [
  { value: "", label: "All Directions" },
  { value: "long", label: "Long" },
  { value: "short", label: "Short" },
];

const timeframes = [
  { value: "", label: "All Timeframes" },
  { value: "scalp", label: "Scalp" },
  { value: "H4", label: "H4" },
  { value: "D1", label: "D1" },
];

const confidences = [
  { value: "", label: "All Confidence" },
  { value: "high", label: "High" },
  { value: "medium", label: "Medium" },
  { value: "low", label: "Low" },
];

interface FilterBarProps {
  showFeatured?: boolean;
}

export function FilterBar({ showFeatured = false }: FilterBarProps) {
  const router = useRouter();
  const searchParams = useSearchParams();

  const createQueryString = (name: string, value: string) => {
    const params = new URLSearchParams(searchParams.toString());
    if (value) {
      params.set(name, value);
    } else {
      params.delete(name);
    }
    return params.toString();
  };

  const handleChange = (name: string, value: string) => {
    router.push(`/?${createQueryString(name, value)}`);
  };

  return (
    <div className="flex flex-wrap gap-3">
      {showFeatured && (
        <button
          onClick={() => handleChange("featured", searchParams.get("featured") ? "" : "true")}
          className={`px-3 py-1.5 text-xs font-medium rounded transition-colors ${
            searchParams.get("featured") === "true"
              ? "bg-blue-600 text-white"
              : "bg-zinc-800 text-zinc-300 hover:bg-zinc-700"
          }`}
        >
          Top Picks
        </button>
      )}

      <select
        value={searchParams.get("type") || ""}
        onChange={(e) => handleChange("type", e.target.value)}
        className="px-3 py-1.5 text-xs bg-zinc-800 border border-zinc-700 rounded text-zinc-300 focus:outline-none focus:ring-2 focus:ring-blue-500"
      >
        {contentTypes.map((t) => (
          <option key={t.value} value={t.value}>{t.label}</option>
        ))}
      </select>

      <select
        value={searchParams.get("asset_class") || ""}
        onChange={(e) => handleChange("asset_class", e.target.value)}
        className="px-3 py-1.5 text-xs bg-zinc-800 border border-zinc-700 rounded text-zinc-300 focus:outline-none focus:ring-2 focus:ring-blue-500"
      >
        {assetClasses.map((a) => (
          <option key={a.value} value={a.value}>{a.label}</option>
        ))}
      </select>

      <select
        value={searchParams.get("direction") || ""}
        onChange={(e) => handleChange("direction", e.target.value)}
        className="px-3 py-1.5 text-xs bg-zinc-800 border border-zinc-700 rounded text-zinc-300 focus:outline-none focus:ring-2 focus:ring-blue-500"
      >
        {directions.map((d) => (
          <option key={d.value} value={d.value}>{d.label}</option>
        ))}
      </select>

      <select
        value={searchParams.get("timeframe") || ""}
        onChange={(e) => handleChange("timeframe", e.target.value)}
        className="px-3 py-1.5 text-xs bg-zinc-800 border border-zinc-700 rounded text-zinc-300 focus:outline-none focus:ring-2 focus:ring-blue-500"
      >
        {timeframes.map((t) => (
          <option key={t.value} value={t.value}>{t.label}</option>
        ))}
      </select>

      <select
        value={searchParams.get("confidence") || ""}
        onChange={(e) => handleChange("confidence", e.target.value)}
        className="px-3 py-1.5 text-xs bg-zinc-800 border border-zinc-700 rounded text-zinc-300 focus:outline-none focus:ring-2 focus:ring-blue-500"
      >
        {confidences.map((c) => (
          <option key={c.value} value={c.value}>{c.label}</option>
        ))}
      </select>
    </div>
  );
}
