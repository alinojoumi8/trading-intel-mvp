interface InstrumentBadgeProps {
  symbol: string;
  assetClass?: "FX" | "Commodities" | "Crypto" | "Indices" | "fx" | "commodities" | "crypto" | "indices";
}

const assetClassColors: Record<string, string> = {
  FX: "bg-blue-900 text-blue-300",
  Commodities: "bg-amber-900 text-amber-300",
  Crypto: "bg-purple-900 text-purple-300",
  Indices: "bg-green-900 text-green-300",
  fx: "bg-blue-900 text-blue-300",
  commodities: "bg-amber-900 text-amber-300",
  crypto: "bg-purple-900 text-purple-300",
  indices: "bg-green-900 text-green-300",
};

export function InstrumentBadge({ symbol, assetClass }: InstrumentBadgeProps) {
  const colorClass = assetClass
    ? assetClassColors[assetClass] || "bg-zinc-800 text-zinc-300"
    : "bg-zinc-800 text-zinc-300";

  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${colorClass}`}
    >
      {symbol}
    </span>
  );
}
