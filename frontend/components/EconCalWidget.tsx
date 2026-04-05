"use client";

import { useEffect, useState, useRef } from "react";
import { getUpcomingEconEvents, EconEvent } from "@/lib/api";

const impactColors: Record<string, string> = {
  HIGH: "text-red-400 bg-red-900/30 border border-red-800/50",
  MEDIUM: "text-yellow-400 bg-yellow-900/30 border border-yellow-800/50",
  LOW: "text-green-400 bg-green-900/30 border border-green-800/50",
};

const impactDot: Record<string, string> = {
  HIGH: "bg-red-400",
  MEDIUM: "bg-yellow-400",
  LOW: "bg-green-400",
};

function formatTime(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", hour12: false });
}

function timeUntil(iso: string): string {
  const diff = new Date(iso).getTime() - Date.now();
  if (diff <= 0) return "NOW";
  const h = Math.floor(diff / 3600000);
  const m = Math.floor((diff % 3600000) / 60000);
  if (h > 24) return `${Math.floor(h / 24)}D`;
  if (h > 0) return `${h}H ${m}M`;
  return `${m}M`;
}

export function EconCalWidget() {
  const [events, setEvents] = useState<EconEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [showHighOnly, setShowHighOnly] = useState(false);
  const [countdown, setCountdown] = useState<string>("");
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchEvents = async () => {
    try {
      const data = await getUpcomingEconEvents({ days: 14 });
      setEvents(data.items);
    } catch {
      // silently fail — widget is non-critical
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchEvents();
    const id = setInterval(fetchEvents, 5 * 60 * 1000); // refresh every 5 min
    intervalRef.current = id;
    return () => clearInterval(id);
  }, []);

  // Countdown to next event
  useEffect(() => {
    if (events.length === 0) return;
    const update = () => {
      const next = events.find(e => new Date(e.event_date).getTime() > Date.now());
      if (next) setCountdown(timeUntil(next.event_date));
      else setCountdown("—");
    };
    update();
    const id = setInterval(update, 30000);
    return () => clearInterval(id);
  }, [events]);

  const filtered = showHighOnly
    ? events.filter(e => (e.impact ?? "MEDIUM").toUpperCase() === "HIGH")
    : events.slice(0, 5);

  const nextEvent = events.find(e => new Date(e.event_date).getTime() > Date.now());

  return (
    <div className="bg-zinc-900/60 border border-zinc-800 rounded-lg p-4">
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-zinc-400">
            <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
            <line x1="16" y1="2" x2="16" y2="6" />
            <line x1="8" y1="2" x2="8" y2="6" />
            <line x1="3" y1="10" x2="21" y2="10" />
          </svg>
          <h3 className="text-zinc-300 text-xs font-semibold uppercase tracking-wider">Economic Calendar</h3>
        </div>
        <button
          onClick={() => setShowHighOnly(v => !v)}
          className={`px-2 py-0.5 rounded text-xs transition-colors ${
            showHighOnly
              ? "bg-red-900/40 text-red-400 border border-red-800/50"
              : "bg-zinc-800 text-zinc-500 hover:text-zinc-300"
          }`}
        >
          HIGH
        </button>
      </div>

      {/* Countdown */}
      {nextEvent && (
        <div className="flex items-center gap-2 mb-3 bg-zinc-800/50 rounded px-3 py-2">
          <div className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse" />
          <span className="text-zinc-500 text-xs">Next</span>
          <span className="text-white text-xs font-medium">{nextEvent.event_name}</span>
          <div className="ml-auto flex items-center gap-1">
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-zinc-500">
              <circle cx="12" cy="12" r="10" />
              <polyline points="12 6 12 12 16 14" />
            </svg>
            <span className="text-green-400 text-xs font-mono font-medium">{countdown}</span>
          </div>
        </div>
      )}

      {/* Events list */}
      {loading ? (
        <div className="space-y-2">
          {[1, 2, 3].map(i => (
            <div key={i} className="h-10 bg-zinc-800/50 rounded animate-pulse" />
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-6">
          <p className="text-zinc-500 text-xs">No upcoming events</p>
        </div>
      ) : (
        <div className="space-y-1.5">
          {filtered.map((event, idx) => {
            const impact = (event.impact ?? "MEDIUM").toUpperCase();
            const isNext = nextEvent?.id === event.id;
            return (
              <div
                key={event.id ?? idx}
                className={`flex items-center gap-2.5 px-2.5 py-2 rounded transition-colors ${
                  isNext ? "bg-zinc-800/70" : "hover:bg-zinc-800/30"
                }`}
              >
                {/* Time */}
                <div className="w-10 shrink-0">
                  <span className="text-zinc-400 text-xs font-mono">
                    {formatTime(event.event_date)}
                  </span>
                </div>

                {/* Currency flag placeholder */}
                <div className="w-6 h-6 rounded flex items-center justify-center bg-zinc-800 text-zinc-400 text-xs font-bold shrink-0">
                  {event.currency ?? "?"}
                </div>

                {/* Name + impact */}
                <div className="flex-1 min-w-0">
                  <p className="text-zinc-300 text-xs leading-tight truncate">{event.event_name}</p>
                    <span className={`inline-block mt-0.5 px-1.5 py-0.5 rounded text-xs font-medium ${impactColors[impact]}`}>
                      {impact} IMPACT
                    </span>
                </div>

                {/* Previous / Forecast (if available) */}
                {(event.previous !== undefined || event.forecast !== undefined) && (
                  <div className="flex flex-col items-end shrink-0">
                    {event.previous !== undefined && (
                      <span className="text-zinc-600 text-xs">Prev: {event.previous}</span>
                    )}
                    {event.forecast !== undefined && (
                      <span className="text-zinc-500 text-xs">Fcst: {event.forecast}</span>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Footer */}
      <div className="mt-3 pt-3 border-t border-zinc-800 flex items-center justify-between">
        <span className="text-zinc-600 text-xs">Auto-refreshes every 5 min</span>
        <a href="/economic-calendar" className="text-green-400 text-xs hover:text-green-300 transition-colors">
          Full calendar →
        </a>
      </div>
    </div>
  );
}
