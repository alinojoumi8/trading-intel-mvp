"use client";

import React, { useEffect, useState, useCallback } from "react";
import {
  getNews,
  getNewsCategories,
  fetchNews,
  markNewsRead,
  markNewsStarred,
  NewsItem,
} from "@/lib/api";
import NewsDetailModal from "@/components/NewsDetailModal";

function timeAgo(dateStr?: string): string {
  if (!dateStr) return "Unknown";
  const diff = (Date.now() - new Date(dateStr).getTime()) / 1000;
  if (diff < 60) return "Just now";
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

function categoryColor(cat: string): string {
  const map: Record<string, string> = {
    Forex: "text-blue-400 bg-blue-900/30",
    Cryptocurrency: "text-orange-400 bg-orange-900/30",
    Commodities: "text-amber-400 bg-amber-900/30",
    General: "text-zinc-400 bg-zinc-800/50",
    Economic: "text-purple-400 bg-purple-900/30",
    Futures: "text-green-400 bg-green-900/30",
    Options: "text-cyan-400 bg-cyan-900/30",
    Stocks: "text-emerald-400 bg-emerald-900/30",
    Technical: "text-yellow-400 bg-yellow-900/30",
    Alternative: "text-pink-400 bg-pink-900/30",
  };
  return map[cat] ?? "text-zinc-400 bg-zinc-800/50";
}

export default function NewsPageContent() {
  const [items, setItems] = useState<NewsItem[]>([]);
  const [categories, setCategories] = useState<string[]>([]);
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [filter, setFilter] = useState<"all" | "unread" | "starred">("all");
  const [loading, setLoading] = useState(true);
  const [fetching, setFetching] = useState(false);
  const [fetchResult, setFetchResult] = useState<{ sources_updated: number; new_items: number; errors: number } | null>(null);
  const [total, setTotal] = useState(0);
  const [expandedIds, setExpandedIds] = useState<Set<number>>(new Set());
  const [selectedItem, setSelectedItem] = useState<NewsItem | null>(null);
  const LIMIT = 30;
  const offsetRef = React.useRef(0);
  const hasAutoFetched = React.useRef(false);

  const loadCategories = useCallback(async () => {
    try {
      const cats = await getNewsCategories();
      setCategories(cats);
    } catch {
      // non-critical
    }
  }, []);

  const loadNews = useCallback(async (resetOffset = false) => {
    setLoading(true);
    try {
      const newOffset = resetOffset ? 0 : offsetRef.current;
      const filters: Parameters<typeof getNews>[0] = {
        limit: LIMIT,
        offset: newOffset,
      };
      if (selectedCategory) filters.category = selectedCategory;
      if (filter === "unread") filters.is_read = false;
      if (filter === "starred") filters.is_starred = true;

      const data = await getNews(filters);
      if (resetOffset) {
        setItems(data.items);
      } else {
        setItems(prev => [...prev, ...data.items]);
      }
      setTotal(data.total);
      offsetRef.current = newOffset + data.items.length;
    } catch (err) {
      console.error("Failed to load news:", err);
    } finally {
      setLoading(false);
    }
  }, [selectedCategory, filter]);

  const autoFetchNews = useCallback(async () => {
    if (hasAutoFetched.current) return;
    hasAutoFetched.current = true;
    setFetching(true);
    try {
      const result = await fetchNews(selectedCategory ?? undefined);
      setFetchResult(result);
      // Immediately load fresh results from DB
      offsetRef.current = 0;
      const filters: Parameters<typeof getNews>[0] = { limit: LIMIT, offset: 0 };
      if (selectedCategory) filters.category = selectedCategory;
      if (filter === "unread") filters.is_read = false;
      if (filter === "starred") filters.is_starred = true;
      const data = await getNews(filters);
      setItems(data.items);
      setTotal(data.total);
      offsetRef.current = data.items.length;
    } catch (err) {
      console.error("Auto-fetch failed:", err);
      // Fallback: load from cache
      loadNews(true);
    } finally {
      setFetching(false);
    }
  }, [selectedCategory, filter, loadNews]);

  useEffect(() => {
    loadCategories();
    autoFetchNews();
  }, [loadCategories, autoFetchNews]);

  useEffect(() => {
    // Only re-load from DB when category/filter changes after initial auto-fetch
    if (hasAutoFetched.current) {
      offsetRef.current = 0;
      loadNews(true);
    }
  }, [loadNews]);

  const handleRefresh = async () => {
    setFetching(true);
    setFetchResult(null);
    try {
      const result = await fetchNews(selectedCategory ?? undefined);
      setFetchResult(result);
      await loadNews(true);
    } catch (err) {
      console.error("Fetch failed:", err);
    } finally {
      setFetching(false);
    }
  };

  const handleMarkRead = async (item: NewsItem) => {
    await markNewsRead(item.id, !item.is_read);
    setItems(prev =>
      prev.map(it => (it.id === item.id ? { ...it, is_read: !it.is_read } : it))
    );
  };

  const handleMarkStarred = async (item: NewsItem) => {
    await markNewsStarred(item.id, !item.is_starred);
    setItems(prev =>
      prev.map(it => (it.id === item.id ? { ...it, is_starred: !it.is_starred } : it))
    );
  };

  const hasMore = items.length < total;

  return (
    <div className="flex flex-col h-full">
      {/* ── Header ── */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-zinc-800">
        <div>
          <h1 className="text-white font-bold text-xl tracking-tight">NEWS FEED</h1>
          <p className="text-zinc-500 text-xs mt-0.5">
            {total > 0 ? `${total} articles` : "Loading..."}
          </p>
        </div>
        <div className="flex items-center gap-3">
          {/* Filter chips */}
          <div className="flex gap-1 bg-zinc-900 rounded p-1">
            {([["all", "All"], ["unread", "Unread"], ["starred", "Starred"]] as const).map(([val, label]) => (
              <button
                key={val}
                onClick={() => setFilter(val)}
                className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
                  filter === val
                    ? "bg-zinc-800 text-white"
                    : "text-zinc-500 hover:text-zinc-300"
                }`}
              >
                {label}
              </button>
            ))}
          </div>

          <button
            onClick={handleRefresh}
            disabled={fetching}
            className="flex items-center gap-2 px-4 py-2 bg-green-900/50 hover:bg-green-900/70 text-green-400 text-xs font-medium rounded transition-colors disabled:opacity-50"
          >
            <svg
              width="12"
              height="12"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              className={fetching ? "animate-spin" : ""}
            >
              <polyline points="23 4 23 10 17 10" />
              <polyline points="1 20 1 14 7 14" />
              <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
            </svg>
            {fetching ? "Refreshing..." : "Refresh"}
          </button>
        </div>
      </div>

      {/* Fetch result toast */}
      {fetchResult && (
        <div className="mx-6 mt-3 px-4 py-2 bg-zinc-900 border border-zinc-800 rounded text-xs text-zinc-400">
          <span className="text-green-400 font-medium">{fetchResult.new_items} new items</span>
          {" from "}
          <span>{fetchResult.sources_updated} sources</span>
          {fetchResult.errors > 0 && (
            <span className="text-red-400"> · {fetchResult.errors} errors</span>
          )}
          <button
            onClick={() => setFetchResult(null)}
            className="float-right text-zinc-600 hover:text-zinc-400"
          >
            ×
          </button>
        </div>
      )}

      <div className="flex flex-1 overflow-hidden">
        {/* ── Category sidebar ── */}
        <aside className="w-48 shrink-0 border-r border-zinc-800 overflow-y-auto py-4 px-3">
          <p className="text-zinc-600 text-xs font-semibold uppercase tracking-wider px-2 mb-2">
            Categories
          </p>
          <button
            onClick={() => setSelectedCategory(null)}
            className={`w-full text-left px-3 py-1.5 rounded text-xs mb-0.5 transition-colors ${
              selectedCategory === null
                ? "bg-zinc-800 text-white font-medium"
                : "text-zinc-500 hover:text-zinc-300 hover:bg-zinc-900"
            }`}
          >
            All Sources
          </button>
          {categories.map(cat => (
            <button
              key={cat}
              onClick={() => setSelectedCategory(cat)}
              className={`w-full text-left px-3 py-1.5 rounded text-xs mb-0.5 transition-colors flex items-center gap-2 ${
                selectedCategory === cat
                  ? "bg-zinc-800 text-white font-medium"
                  : "text-zinc-500 hover:text-zinc-300 hover:bg-zinc-900"
              }`}
            >
              <span className={`inline-block w-1.5 h-1.5 rounded-full ${selectedCategory === cat ? "bg-green-400" : "bg-zinc-700"}`} />
              {cat}
            </button>
          ))}
        </aside>

        {/* ── News feed ── */}
        <main className="flex-1 overflow-y-auto">
          {loading && items.length === 0 ? (
            <div className="flex items-center justify-center h-48">
              <p className="text-zinc-500 text-sm">Loading news...</p>
            </div>
          ) : items.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-48 gap-2">
              <p className="text-zinc-400 text-sm">No news articles found</p>
              <p className="text-zinc-600 text-xs">Click Refresh to fetch the latest news</p>
            </div>
          ) : (
            <div className="divide-y divide-zinc-900">
              {items.map(item => (
                <article
                  key={item.id}
                  className={`px-6 py-4 hover:bg-zinc-950/50 transition-colors ${
                    item.is_read ? "opacity-60" : ""
                  }`}
                >
                  {/* Meta row */}
                  <div className="flex items-center gap-2 mb-2 flex-wrap">
                    <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium ${categoryColor(item.source_category)}`}>
                      {item.source_category}
                    </span>
                    <span className="text-zinc-600 text-[10px]">{item.source_name}</span>
                    <span className="text-zinc-700 text-[10px]">·</span>
                    <span className="text-zinc-600 text-[10px]">{timeAgo(item.published_at)}</span>
                    {item.tags && (
                      <>
                        <span className="text-zinc-700 text-[10px]">·</span>
                        <span className="text-zinc-600 text-[10px]">#{item.tags}</span>
                      </>
                    )}
                  </div>

                  {/* Title — click to open detail modal */}
                  <button
                    onClick={() => {
                      setSelectedItem(item);
                      if (!item.is_read) handleMarkRead(item);
                    }}
                    className="block mb-2 text-sm font-medium text-zinc-200 hover:text-white leading-snug text-left cursor-pointer"
                  >
                    {item.is_read ? "" : (
                      <span className="inline-block w-1.5 h-1.5 rounded-full bg-green-500 mr-2 mb-0.5" />
                    )}
                    {item.title}
                  </button>

                  {/* Description */}
                  {item.description && (
                    <div
                      className="mb-3 cursor-pointer"
                      onClick={(e) => {
                        e.stopPropagation();
                        setExpandedIds((prev) => {
                          const next = new Set(prev);
                          if (next.has(item.id)) next.delete(item.id);
                          else next.add(item.id);
                          return next;
                        });
                      }}
                    >
                      <p className={`text-zinc-500 text-xs leading-relaxed ${expandedIds.has(item.id) ? "" : "line-clamp-2"}`}>
                        {item.description}
                      </p>
                      {item.description.length > 100 && (
                        <span className="text-xs text-blue-400 hover:text-blue-300 transition-colors">
                          {expandedIds.has(item.id) ? "Show less" : "Read more..."}
                        </span>
                      )}
                    </div>
                  )}

                  {/* Actions */}
                  <div className="flex items-center gap-3">
                    <a
                      href={item.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-xs text-zinc-500 hover:text-zinc-300 flex items-center gap-1 transition-colors"
                    >
                      Read full article
                      <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
                        <polyline points="15 3 21 3 21 9" />
                        <line x1="10" y1="14" x2="21" y2="3" />
                      </svg>
                    </a>

                    <button
                      onClick={() => handleMarkRead(item)}
                      className={`text-xs flex items-center gap-1 transition-colors ${
                        item.is_read ? "text-zinc-500 hover:text-zinc-400" : "text-zinc-500 hover:text-zinc-300"
                      }`}
                    >
                      <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        {item.is_read ? (
                          <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z M1 12s3 5 11 5 11-5 11-5-3-5-11-5-11 5-11 5z" />
                        ) : (
                          <>
                            <circle cx="12" cy="12" r="10" />
                            <path d="M12 8v4M12 16h.01" />
                          </>
                        )}
                      </svg>
                      {item.is_read ? "Read" : "Mark read"}
                    </button>

                    <button
                      onClick={() => handleMarkStarred(item)}
                      className={`text-xs flex items-center gap-1 transition-colors ${
                        item.is_starred ? "text-yellow-400" : "text-zinc-500 hover:text-zinc-300"
                      }`}
                    >
                      <svg width="10" height="10" viewBox="0 0 24 24" fill={item.is_starred ? "currentColor" : "none"} stroke="currentColor" strokeWidth="2">
                        <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
                      </svg>
                      {item.is_starred ? "Starred" : "Star"}
                    </button>
                  </div>
                </article>
              ))}

              {/* Load more */}
              {hasMore && (
                <div className="px-6 py-6 flex justify-center">
                  <button
                    onClick={() => loadNews(false)}
                    disabled={loading}
                    className="px-6 py-2 bg-zinc-900 hover:bg-zinc-800 text-zinc-400 text-xs rounded transition-colors disabled:opacity-50"
                  >
                    {loading ? "Loading..." : `Load more (${total - items.length} remaining)`}
                  </button>
                </div>
              )}
            </div>
          )}
        </main>
      </div>

      {/* News Detail Modal */}
      {selectedItem && (
        <NewsDetailModal
          item={selectedItem}
          onClose={() => setSelectedItem(null)}
        />
      )}
    </div>
  );
}
