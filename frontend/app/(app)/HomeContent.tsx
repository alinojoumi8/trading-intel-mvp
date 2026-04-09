"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { useSearchParams } from "next/navigation";
import { ContentItem, getContent, getFeaturedContent, runFullPipeline } from "@/lib/api";
import { ContentCard } from "@/components/ContentCard";
import { FilterBar } from "@/components/FilterBar";
import { SearchBar } from "@/components/SearchBar";
import { SentimentWidget } from "@/components/SentimentWidget";
import { EconCalWidget } from "@/components/EconCalWidget";

// Auto-regen if newest content is older than this many hours
const STALE_HOURS = 4;
// Poll for new content this often (ms) while page is open
const POLL_INTERVAL_MS = 2 * 60 * 1000; // 2 minutes

function formatRelative(iso: string): string {
  const ts = new Date(iso).getTime();
  if (isNaN(ts)) return "—";
  const diffMs = Date.now() - ts;
  const mins = Math.floor(diffMs / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
}

function newestTimestamp(items: ContentItem[]): string | null {
  if (items.length === 0) return null;
  let max = items[0].published_at;
  for (const it of items) {
    if (it.published_at > max) max = it.published_at;
  }
  return max;
}

function isStale(items: ContentItem[]): boolean {
  const ts = newestTimestamp(items);
  if (!ts) return true;
  const ageHours = (Date.now() - new Date(ts).getTime()) / 3600000;
  return ageHours >= STALE_HOURS;
}

export default function HomeContent() {
  const searchParams = useSearchParams();
  const [content, setContent] = useState<ContentItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);
  const [genStatus, setGenStatus] = useState<string | null>(null);
  const autoTriggeredRef = useRef(false);

  const search = searchParams.get("search") || "";
  const featured = searchParams.get("featured") === "true";

  const fetchContent = useCallback(async () => {
    setError(null);
    try {
      const filters = {
        type: searchParams.get("type") || undefined,
        direction: searchParams.get("direction") || undefined,
        timeframe: searchParams.get("timeframe") || undefined,
        confidence: searchParams.get("confidence") || undefined,
        featured: featured || undefined,
      };
      Object.keys(filters).forEach(k => {
        if (filters[k as keyof typeof filters] === undefined) {
          delete filters[k as keyof typeof filters];
        }
      });

      const data = featured ? await getFeaturedContent() : await getContent(filters);

      let filtered = data;
      if (search) {
        const q = search.toLowerCase();
        filtered = data.filter(
          (item) =>
            item.title.toLowerCase().includes(q) ||
            item.rationale.toLowerCase().includes(q) ||
            item.instrument?.toLowerCase().includes(q)
        );
      }

      setContent(filtered);
      return filtered;
    } catch (err) {
      setError(err instanceof Error ? err.message : "An error occurred");
      setContent([]);
      return [];
    }
  }, [searchParams, search, featured]);

  const triggerRegenerate = useCallback(async (auto: boolean) => {
    if (generating) return;
    setGenerating(true);
    setGenStatus(auto ? "Content is stale — generating fresh briefings & setups in the background..." : "Generating fresh content...");
    try {
      const res = await runFullPipeline();
      setGenStatus(`✓ ${res.message} (${res.total_count} new items)`);
      await fetchContent();
      setTimeout(() => setGenStatus(null), 8000);
    } catch (err) {
      setGenStatus(`✗ Generation failed: ${err instanceof Error ? err.message : "unknown error"}`);
      setTimeout(() => setGenStatus(null), 8000);
    } finally {
      setGenerating(false);
    }
  }, [generating, fetchContent]);

  // Initial load + auto-trigger if stale
  useEffect(() => {
    setLoading(true);
    autoTriggeredRef.current = false;
    fetchContent().then((items) => {
      setLoading(false);
      // Auto-trigger regen once per page visit if data is stale
      if (!autoTriggeredRef.current && items.length > 0 && isStale(items)) {
        autoTriggeredRef.current = true;
        triggerRegenerate(true);
      }
    });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams, featured]);

  // Background poll while the page is open — picks up content generated elsewhere
  useEffect(() => {
    const interval = setInterval(() => {
      if (!generating) fetchContent();
    }, POLL_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [fetchContent, generating]);

  const newest = newestTimestamp(content);
  const stale = isStale(content);

  return (
    <div className="flex gap-6 px-6 py-6">
      {/* Main content */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-white font-bold text-xl tracking-tight">TRADING INTELLIGENCE</h1>
            {newest && (
              <p className="text-zinc-500 text-xs mt-1 flex items-center gap-2">
                <span className={stale ? "text-yellow-400" : "text-green-400"}>●</span>
                Updated {formatRelative(newest)}
                {stale && <span className="text-yellow-500">(stale &gt;{STALE_HOURS}h)</span>}
                {generating && <span className="text-blue-400 animate-pulse">· Regenerating...</span>}
              </p>
            )}
          </div>
          <div className="flex items-center gap-1">
            <button
              onClick={() => triggerRegenerate(false)}
              disabled={generating}
              className="px-3 py-1.5 text-xs font-medium text-zinc-300 hover:text-white border border-zinc-700 hover:border-zinc-500 rounded mr-2 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1.5 transition-colors"
              title="Generate fresh briefings, trade setups, and roundup"
            >
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className={generating ? "animate-spin" : ""}>
                <path d="M21 12a9 9 0 1 1-6.219-8.56" />
              </svg>
              {generating ? "Generating..." : "Refresh"}
            </button>
            <button className="px-3 py-1.5 text-xs font-medium text-green-400 border-b-2 border-green-400">
              LIVE FEED
            </button>
            <button className="px-3 py-1.5 text-xs font-medium text-zinc-500 hover:text-zinc-300 transition-colors">
              WATCHLIST
            </button>
            <button className="px-3 py-1.5 text-xs font-medium text-zinc-500 hover:text-zinc-300 transition-colors">
              HISTORY
            </button>
            <div className="w-px h-4 bg-zinc-700 mx-2" />
            <button className="p-2 text-zinc-500 hover:text-zinc-300 transition-colors">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
                <path d="M13.73 21a2 2 0 0 1-3.46 0" />
              </svg>
            </button>
            <button className="p-2 text-zinc-500 hover:text-zinc-300 transition-colors">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="12" cy="12" r="3" />
                <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />
              </svg>
            </button>
            <div className="w-7 h-7 rounded-full bg-zinc-800 flex items-center justify-center ml-1">
              <span className="text-zinc-400 text-xs font-bold">A</span>
            </div>
          </div>
        </div>
        <div className="flex flex-col gap-6 mb-8">
          <SearchBar defaultValue={search} />
          <FilterBar showFeatured />
        </div>

        {genStatus && (
          <div className={`mb-6 px-4 py-2.5 border rounded text-xs ${
            genStatus.startsWith("✗")
              ? "bg-red-950/40 border-red-800 text-red-400"
              : genStatus.startsWith("✓")
                ? "bg-green-950/40 border-green-800 text-green-400"
                : "bg-blue-950/40 border-blue-800 text-blue-400"
          }`}>
            {genStatus}
          </div>
        )}

        {loading ? (
          <div className="flex items-center justify-center py-12">
            <p className="text-muted-foreground">Loading...</p>
          </div>
        ) : error ? (
          <div className="flex flex-col items-center justify-center py-12 gap-4">
            <p className="text-destructive">Error: {error}</p>
            <p className="text-sm text-muted-foreground">
              Make sure the FastAPI backend is running at localhost:8000
            </p>
          </div>
        ) : content.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 gap-2">
            <p className="text-lg font-medium">No content found</p>
            <p className="text-sm text-muted-foreground">
              Try adjusting your filters or search query
            </p>
          </div>
        ) : (
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {content.map((item) => (
              <ContentCard key={item.id} item={item} />
            ))}
          </div>
        )}
      </div>

      {/* Right sidebar widgets */}
      <aside className="w-72 shrink-0 space-y-4">
        <SentimentWidget />
        <EconCalWidget />
      </aside>
    </div>
  );
}
