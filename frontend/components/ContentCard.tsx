"use client";

import Link from "next/link";
import { ContentItem } from "@/lib/api";
import { InstrumentBadge } from "./InstrumentBadge";
import { ConfidenceBadge } from "./ConfidenceBadge";

interface ContentCardProps {
  item: ContentItem;
}

// ─── Helpers ───────────────────────────────────────────────────────────────

function formatTimestamp(dateString: string): string {
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffHrs = Math.floor(diffMs / (1000 * 60 * 60));
  const diffDays = Math.floor(diffHrs / 24);

  if (diffHrs < 1) return "Just now";
  if (diffHrs < 24) return `${diffHrs}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;
  return date.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

// ─── Border color by type / direction ────────────────────────────────────

function borderColor(item: ContentItem): string {
  if (item.type === "setup") {
    return item.direction === "long"
      ? "border-l-green-500"
      : item.direction === "short"
      ? "border-l-red-500"
      : "border-l-zinc-600";
  }
  if (item.type === "contrarian_alert") return "border-l-red-500";
  if (item.type === "macro_roundup") return "border-l-orange-500";
  if (item.type === "briefing") return "border-l-blue-500";
  return "border-l-zinc-600";
}

// ─── Type badge ───────────────────────────────────────────────────────────

const TYPE_META: Record<string, { label: string; color: string }> = {
  briefing:       { label: "Morning Briefing", color: "bg-blue-900 text-blue-300 border border-blue-700" },
  setup:          { label: "Trade Setup",      color: "bg-zinc-800 text-zinc-300 border border-zinc-700" },
  macro_roundup:  { label: "Macro Roundup",   color: "bg-orange-900/50 text-orange-400 border border-orange-800" },
  contrarian_alert: { label: "Contrarian Alert", color: "bg-red-900/50 text-red-400 border border-red-800" },
};

// ─── Direction badge ──────────────────────────────────────────────────────

function DirectionBadge({ direction }: { direction: string }) {
  if (direction === "long") {
    return <span className="text-xs font-bold text-green-400 tracking-wide">LONG</span>;
  }
  if (direction === "short") {
    return <span className="text-xs font-bold text-red-400 tracking-wide">SHORT</span>;
  }
  return null;
}

// ─── Main component ──────────────────────────────────────────────────────

export function ContentCard({ item }: ContentCardProps) {
  const typeMeta = TYPE_META[item.type] ?? { label: item.type, color: "bg-zinc-800 text-zinc-300" };
  const border = borderColor(item);

  return (
    <article
      className={`
        bg-zinc-950 border border-zinc-800 border-l-2 ${border}
        rounded-md p-4 flex flex-col gap-3
        hover:border-zinc-700 transition-colors cursor-pointer
        group
      `}
    >
      {/* ── Top row: type badge + featured badge + timestamp ── */}
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2 flex-wrap">
          <span className={`text-xs px-2 py-0.5 rounded-sm font-medium ${typeMeta.color}`}>
            {typeMeta.label}
          </span>
          {item.featured && (
            <span className="text-xs px-2 py-0.5 rounded-sm font-bold bg-amber-500 text-black">
              FEATURED
            </span>
          )}
        </div>
        <span className="text-xs text-zinc-500 shrink-0">
          {formatTimestamp(item.published_at)}
        </span>
      </div>

      {/* ── Title ── */}
      <h3 className="text-white font-semibold text-sm leading-snug line-clamp-2 group-hover:text-zinc-100 transition-colors">
        {item.title}
      </h3>

      {/* ── Instrument + direction row ── */}
      <div className="flex items-center gap-2 flex-wrap">
        {item.instrument && (
          <Link href={`/instrument/${item.instrument}`} onClick={(e) => e.stopPropagation()}>
            <InstrumentBadge symbol={item.instrument} />
          </Link>
        )}
        <DirectionBadge direction={item.direction ?? ""} />
        <ConfidenceBadge level={item.confidence} />
      </div>

      {/* ── Setup metrics table (Trade Setups only) ── */}
      {(item.entry_zone || item.stop_loss || item.take_profit) && (
        <div className="grid grid-cols-3 gap-1 bg-zinc-900 rounded p-2">
          {item.entry_zone && (
            <div className="flex flex-col gap-0.5">
              <span className="text-zinc-500 text-xs">ENTRY</span>
              <span className="text-white font-mono text-xs">{item.entry_zone}</span>
            </div>
          )}
          {item.stop_loss && (
            <div className="flex flex-col gap-0.5 border-l border-zinc-800 pl-2">
              <span className="text-zinc-500 text-xs">STOPLOSS</span>
              <span className="text-red-400 font-mono text-xs">{item.stop_loss}</span>
            </div>
          )}
          {item.take_profit && (
            <div className="flex flex-col gap-0.5 border-l border-zinc-800 pl-2">
              <span className="text-zinc-500 text-xs">TARGET</span>
              <span className="text-green-400 font-mono text-xs">{item.take_profit}</span>
            </div>
          )}
        </div>
      )}

      {/* ── Rationale ── */}
      <p className="text-zinc-400 text-xs leading-relaxed line-clamp-3">
        {item.rationale}
      </p>

      {/* ── Footer: tags + hashtag-like categorization ── */}
      <div className="flex flex-wrap gap-1.5 mt-auto pt-1 border-t border-zinc-800/50">
        {item.tags.map((tag) => (
          <span
            key={tag}
            className="text-xs text-zinc-500 hover:text-zinc-300 transition-colors"
          >
            #{tag}
          </span>
        ))}
      </div>
    </article>
  );
}
