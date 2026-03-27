interface ConfidenceBadgeProps {
  level: "high" | "medium" | "low";
}

const confidenceConfig: Record<string, { bg: string; text: string; label: string }> = {
  high: { bg: "bg-green-900/50", text: "text-green-400", label: "High" },
  medium: { bg: "bg-yellow-900/50", text: "text-yellow-400", label: "Medium" },
  low: { bg: "bg-red-900/50", text: "text-red-400", label: "Low" },
};

export function ConfidenceBadge({ level }: ConfidenceBadgeProps) {
  const config = confidenceConfig[level ?? ""];

  if (!config) {
    return null;
  }

  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${config.bg} ${config.text}`}>
      {config.label} Confidence
    </span>
  );
}
