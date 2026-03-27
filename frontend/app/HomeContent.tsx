"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { ContentItem, getContent, getFeaturedContent } from "@/lib/api";
import { ContentCard } from "@/components/ContentCard";
import { FilterBar } from "@/components/FilterBar";
import { SearchBar } from "@/components/SearchBar";

export default function HomeContent() {
  const searchParams = useSearchParams();
  const [content, setContent] = useState<ContentItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const search = searchParams.get("search") || "";
  const featured = searchParams.get("featured") === "true";

  useEffect(() => {
    async function fetchContent() {
      setLoading(true);
      setError(null);
      try {
        const filters = {
          type: searchParams.get("type") || undefined,
          direction: searchParams.get("direction") || undefined,
          timeframe: searchParams.get("timeframe") || undefined,
          confidence: searchParams.get("confidence") || undefined,
          featured: featured || undefined,
        };
        // Remove undefined values
        Object.keys(filters).forEach(k => {
          if (filters[k as keyof typeof filters] === undefined) {
            delete filters[k as keyof typeof filters];
          }
        });

        const data = featured
          ? await getFeaturedContent()
          : await getContent(filters);

        // Client-side search filter (backend doesn't have full-text search)
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
      } catch (err) {
        setError(err instanceof Error ? err.message : "An error occurred");
        setContent([]);
      } finally {
        setLoading(false);
      }
    }

    fetchContent();
  }, [searchParams, featured]);

  return (
    <div className="max-w-7xl mx-auto px-4 py-6">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-white font-bold text-xl tracking-tight">TRADING INTELLIGENCE</h1>
        <div className="flex items-center gap-1">
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
  );
}
