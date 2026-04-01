"use client";

import { useEffect, useState, useRef } from "react";
import {
  analyzeNews,
  askAboutNews,
  NewsAnalysis,
  NewsItem,
} from "@/lib/api";

interface NewsDetailModalProps {
  item: NewsItem;
  onClose: () => void;
}

interface ChatMessage {
  role: "user" | "ai";
  text: string;
}

function timeAgo(dateStr?: string): string {
  if (!dateStr) return "";
  const diff = (Date.now() - new Date(dateStr).getTime()) / 1000;
  if (diff < 60) return "Just now";
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

function SentimentBadge({ label, score }: { label?: string; score?: number }) {
  if (!label && score == null) return null;
  const display = label || (score != null && score > 0.1 ? "Bullish" : score != null && score < -0.1 ? "Bearish" : "Neutral");
  const isPositive = display.toLowerCase().includes("bullish");
  const isNegative = display.toLowerCase().includes("bearish");

  return (
    <div
      className={`px-2.5 py-0.5 rounded-full flex items-center gap-1.5 border text-[10px] font-bold uppercase tracking-tight ${
        isPositive
          ? "bg-green-900/20 border-green-500/20 text-green-400"
          : isNegative
          ? "bg-red-900/20 border-red-500/20 text-red-400"
          : "bg-zinc-800/50 border-zinc-600/20 text-zinc-400"
      }`}
    >
      <span
        className={`w-1.5 h-1.5 rounded-full ${
          isPositive ? "bg-green-400" : isNegative ? "bg-red-400" : "bg-zinc-400"
        }`}
      />
      {display} {score != null ? score.toFixed(2) : ""}
    </div>
  );
}

function DirectionIcon({ direction }: { direction: string }) {
  if (direction === "Bullish") {
    return (
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" className="text-green-400">
        <path d="M12 19V5M5 12l7-7 7 7" />
      </svg>
    );
  }
  if (direction === "Bearish") {
    return (
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" className="text-red-400">
        <path d="M12 5v14M19 12l-7 7-7-7" />
      </svg>
    );
  }
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" className="text-amber-400">
      <path d="M5 12h14" />
    </svg>
  );
}

function InstrumentBadge({ instrument, direction }: { instrument: string; direction: string }) {
  const colors =
    direction === "Bullish"
      ? "bg-green-900/10 border-green-500/20 text-green-400"
      : direction === "Bearish"
      ? "bg-red-900/10 border-red-500/20 text-red-400"
      : "bg-zinc-800 border-zinc-600/20 text-amber-400";

  return (
    <div className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md border ${colors}`}>
      <span className="text-[10px] font-bold text-zinc-200">{instrument}</span>
      <DirectionIcon direction={direction} />
      <span className="text-[10px] font-bold uppercase">{direction}</span>
    </div>
  );
}

function SkeletonLoader() {
  return (
    <div className="bg-zinc-900/50 rounded-lg p-5 border border-zinc-800/30 animate-pulse">
      <div className="h-2.5 bg-zinc-800 rounded-full w-3/4 mb-3" />
      <div className="h-2 bg-zinc-800 rounded-full w-1/2 mb-5" />
      <div className="flex gap-2">
        <div className="h-6 w-20 bg-zinc-800 rounded-md" />
        <div className="h-6 w-20 bg-zinc-800 rounded-md" />
      </div>
    </div>
  );
}

export default function NewsDetailModal({ item, onClose }: NewsDetailModalProps) {
  const [analysis, setAnalysis] = useState<NewsAnalysis | null>(null);
  const [analysisLoading, setAnalysisLoading] = useState(true);
  const [analysisError, setAnalysisError] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [question, setQuestion] = useState("");
  const [asking, setAsking] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Auto-trigger analysis on mount
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const result = await analyzeNews({
          title: item.title,
          description: item.description || "",
          source: item.source_name || "",
        });
        if (!cancelled) setAnalysis(result);
      } catch (e) {
        if (!cancelled) setAnalysisError("Failed to generate analysis.");
      } finally {
        if (!cancelled) setAnalysisLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [item]);

  // Scroll chat to bottom
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Close on Escape
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [onClose]);

  const handleAsk = async () => {
    const q = question.trim();
    if (!q || asking) return;

    setQuestion("");
    setMessages((prev) => [...prev, { role: "user", text: q }]);
    setAsking(true);

    try {
      const result = await askAboutNews({
        title: item.title,
        description: item.description || "",
        question: q,
        analysis_summary: analysis?.summary || "",
        conversation: messages,
      });
      setMessages((prev) => [...prev, { role: "ai", text: result.answer }]);
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: "ai", text: "Sorry, I couldn't process that question. Please try again." },
      ]);
    } finally {
      setAsking(false);
      inputRef.current?.focus();
    }
  };

  return (
    <div
      className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4"
      onClick={onClose}
    >
      <main
        className="w-full max-w-2xl bg-zinc-950 border border-zinc-800/50 rounded-xl overflow-hidden shadow-2xl flex flex-col"
        style={{ maxHeight: "min(90vh, 800px)" }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* ── Header ── */}
        <header className="flex justify-between items-center px-4 h-14 bg-zinc-900 border-b border-zinc-800/50 shrink-0">
          <div className="flex items-center gap-3">
            <span className="text-xs font-medium text-zinc-500 uppercase tracking-wider">
              {timeAgo(item.published_at || undefined)}
            </span>
            <h1 className="text-sm font-bold text-blue-400">Market Intel</h1>
          </div>
          <div className="flex items-center gap-3">
            <SentimentBadge label={undefined} score={undefined} />
            <button
              onClick={onClose}
              className="hover:bg-zinc-800 transition-colors p-1.5 rounded-lg text-zinc-400"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M18 6L6 18M6 6l12 12" />
              </svg>
            </button>
          </div>
        </header>

        {/* ── Scrollable Content ── */}
        <div className="flex-1 overflow-y-auto">
          {/* Article */}
          <article className="p-6 space-y-4">
            <h2 className="text-lg leading-tight font-semibold text-white">
              {item.title}
            </h2>
            {item.description && (
              <p className="text-zinc-400 text-sm leading-relaxed">
                {item.description}
              </p>
            )}
            {item.url && (
              <a
                href={item.url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 text-blue-400 text-xs font-medium hover:underline"
                onClick={(e) => e.stopPropagation()}
              >
                Read original article
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
                  <polyline points="15 3 21 3 21 9" />
                  <line x1="10" y1="14" x2="21" y2="3" />
                </svg>
              </a>
            )}
          </article>

          {/* AI Analysis */}
          <section className="mx-6 border-t border-zinc-800/50 py-6">
            <div className="flex items-center gap-2 mb-4">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-blue-400">
                <path d="M12 2a8 8 0 0 0-8 8c0 3 1.5 5.5 4 7v3h8v-3c2.5-1.5 4-4 4-7a8 8 0 0 0-8-8z" />
                <path d="M9 22h6" />
              </svg>
              <h3 className="text-sm font-bold text-white tracking-wide">
                AI Trading Analysis
              </h3>
            </div>

            {analysisLoading ? (
              <SkeletonLoader />
            ) : analysisError ? (
              <div className="bg-zinc-900/50 rounded-lg p-4 border border-zinc-800/30">
                <p className="text-sm text-zinc-500">{analysisError}</p>
              </div>
            ) : analysis ? (
              <div className="bg-zinc-900 rounded-lg p-5 border border-zinc-800/30">
                <p className="text-sm text-zinc-200 mb-4 leading-relaxed">
                  {analysis.summary}
                </p>

                {analysis.instruments.length > 0 && (
                  <div className="flex flex-wrap gap-2 mb-4">
                    {analysis.instruments.map((inst) => (
                      <InstrumentBadge
                        key={inst.instrument}
                        instrument={inst.instrument}
                        direction={inst.direction}
                      />
                    ))}
                  </div>
                )}

                <div className="flex items-center gap-2 pt-3 border-t border-zinc-800/30">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-zinc-500">
                    <ellipse cx="12" cy="5" rx="9" ry="3" />
                    <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3" />
                    <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5" />
                  </svg>
                  <span className="text-[11px] font-medium text-zinc-500 uppercase tracking-widest">
                    {analysis.regime_note}
                  </span>
                </div>
              </div>
            ) : null}
          </section>

          {/* Chat Q&A */}
          {messages.length > 0 && (
            <section className="px-6 pb-6 space-y-3">
              {messages.map((msg, i) =>
                msg.role === "user" ? (
                  <div key={i} className="flex justify-end">
                    <div className="bg-blue-900/60 text-white px-4 py-2.5 rounded-xl rounded-tr-none max-w-[85%] text-sm">
                      {msg.text}
                    </div>
                  </div>
                ) : (
                  <div key={i} className="flex justify-start items-start gap-2">
                    <div className="w-6 h-6 rounded-full bg-blue-400/20 flex items-center justify-center shrink-0 mt-0.5">
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-blue-400">
                        <path d="M12 2a8 8 0 0 0-8 8c0 3 1.5 5.5 4 7v3h8v-3c2.5-1.5 4-4 4-7a8 8 0 0 0-8-8z" />
                      </svg>
                    </div>
                    <div className="bg-zinc-800 text-zinc-200 px-4 py-2.5 rounded-xl rounded-tl-none max-w-[85%] text-sm leading-relaxed">
                      {msg.text}
                    </div>
                  </div>
                )
              )}
              {asking && (
                <div className="flex justify-start items-start gap-2">
                  <div className="w-6 h-6 rounded-full bg-blue-400/20 flex items-center justify-center shrink-0">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-blue-400">
                      <path d="M12 2a8 8 0 0 0-8 8c0 3 1.5 5.5 4 7v3h8v-3c2.5-1.5 4-4 4-7a8 8 0 0 0-8-8z" />
                    </svg>
                  </div>
                  <div className="bg-zinc-800 text-zinc-500 px-4 py-2.5 rounded-xl rounded-tl-none text-sm animate-pulse">
                    Analyzing...
                  </div>
                </div>
              )}
              <div ref={chatEndRef} />
            </section>
          )}
        </div>

        {/* ── Input Bar ── */}
        <footer className="p-4 bg-zinc-900/80 border-t border-zinc-800/50 shrink-0">
          <div className="relative">
            <input
              ref={inputRef}
              type="text"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  handleAsk();
                }
              }}
              placeholder="Ask about this news..."
              className="w-full bg-zinc-800 border border-zinc-700/50 rounded-lg py-3 px-4 pr-12 text-sm text-white placeholder:text-zinc-500 focus:outline-none focus:ring-1 focus:ring-blue-500/40 transition-all"
              disabled={asking}
            />
            <button
              onClick={handleAsk}
              disabled={asking || !question.trim()}
              className="absolute right-2 top-1/2 -translate-y-1/2 p-1.5 text-blue-400 hover:bg-blue-400/10 rounded-md transition-all disabled:opacity-30"
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <line x1="22" y1="2" x2="11" y2="13" />
                <polygon points="22 2 15 22 11 13 2 9 22 2" />
              </svg>
            </button>
          </div>
        </footer>
      </main>
    </div>
  );
}
