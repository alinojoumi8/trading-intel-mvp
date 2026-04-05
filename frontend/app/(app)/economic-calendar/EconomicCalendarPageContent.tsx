"use client";

import { useEffect, useState, useMemo } from "react";
import {
  getEconEvents,
  getUpcomingEconEvents,
  createEconEvent,
  deleteEconEvent,
  scrapeEconEvents,
  getImpactMap,
  EconEvent,
  ImpactMapResponse,
} from "@/lib/api";

// Country flag emojis
const COUNTRY_FLAGS: Record<string, string> = {
  US: "🇺🇸",
  EU: "🇪🇺",
  UK: "🇬🇧",
  JP: "🇯🇵",
  AU: "🇦🇺",
  CA: "🇨🇦",
  NZ: "🇳🇿",
  CH: "🇨🇭",
};

// Importance badge colors
const IMPORTANCE_STYLES = {
  high: {
    bg: "bg-red-900/30",
    text: "text-red-400",
    border: "border-red-700",
    dot: "bg-red-500",
  },
  medium: {
    bg: "bg-yellow-900/30",
    text: "text-yellow-400",
    border: "border-yellow-700",
    dot: "bg-yellow-500",
  },
  low: {
    bg: "bg-zinc-800/50",
    text: "text-zinc-400",
    border: "border-zinc-600",
    dot: "bg-zinc-500",
  },
};

// Calendar helpers
function getDaysInMonth(year: number, month: number): number {
  return new Date(year, month + 1, 0).getDate();
}

function getFirstDayOfMonth(year: number, month: number): number {
  return new Date(year, month, 1).getDay();
}

function formatDate(dateStr: string): string {
  const date = new Date(dateStr);
  return date.toLocaleDateString("en-US", {
    weekday: "short",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatDateShort(dateStr: string): string {
  const date = new Date(dateStr);
  return date.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
  });
}

function formatTime(dateStr: string): string {
  const date = new Date(dateStr);
  return date.toLocaleTimeString("en-US", {
    hour: "2-digit",
    minute: "2-digit",
  });
}

interface CalendarDay {
  date: Date;
  isCurrentMonth: boolean;
  events: EconEvent[];
}

export default function EconomicCalendarPageContent() {
  const [view, setView] = useState<"calendar" | "list">("calendar");
  const [events, setEvents] = useState<EconEvent[]>([]);
  const [impactMap, setImpactMap] = useState<ImpactMapResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [scrapeLoading, setScrapeLoading] = useState(false);
  const [scrapeResult, setScrapeResult] = useState<string | null>(null);

  // Filters
  const [countryFilter, setCountryFilter] = useState<string>("");
  const [importanceFilter, setImportanceFilter] = useState<string>("");
  const [currencyFilter, setCurrencyFilter] = useState<string>("");

  // Calendar state
  const [currentDate, setCurrentDate] = useState(new Date());

  // Modal state
  const [showAddModal, setShowAddModal] = useState(false);
  const [newEvent, setNewEvent] = useState({
    event_name: "",
    country: "US",
    currency: "USD",
    event_date: "",
    importance: "medium",
    impact: "medium",
    previous: "",
    forecast: "",
    actual: "",
  });

  // Fetch data
  useEffect(() => {
    async function fetchData() {
      setLoading(true);
      setError(null);
      try {
        const [eventsData, impactData] = await Promise.all([
          getEconEvents({
            start_date: new Date(currentDate.getFullYear(), currentDate.getMonth(), 1).toISOString().split("T")[0],
            end_date: new Date(currentDate.getFullYear(), currentDate.getMonth() + 1, 0).toISOString().split("T")[0],
            country: countryFilter || undefined,
            importance: importanceFilter || undefined,
            currency: currencyFilter || undefined,
            limit: 500,
          }),
          getImpactMap(),
        ]);
        setEvents(eventsData.items);
        setImpactMap(impactData);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to fetch events");
      } finally {
        setLoading(false);
      }
    }

    fetchData();
  }, [currentDate, countryFilter, importanceFilter, currencyFilter]);

  // Upcoming events (next 7 days) for sidebar
  const [upcomingEvents, setUpcomingEvents] = useState<EconEvent[]>([]);
  useEffect(() => {
    async function fetchUpcoming() {
      try {
        const data = await getUpcomingEconEvents({ days: 7 });
        setUpcomingEvents(data.items);
      } catch {
        // Silently fail for upcoming
      }
    }
    fetchUpcoming();
  }, []);

  // Calendar grid
  const calendarDays = useMemo((): CalendarDay[] => {
    const year = currentDate.getFullYear();
    const month = currentDate.getMonth();
    const daysInMonth = getDaysInMonth(year, month);
    const firstDay = getFirstDayOfMonth(year, month);

    const days: CalendarDay[] = [];

    // Previous month days
    const prevMonth = month === 0 ? 11 : month - 1;
    const prevYear = month === 0 ? year - 1 : year;
    const daysInPrevMonth = getDaysInMonth(prevYear, prevMonth);
    for (let i = firstDay - 1; i >= 0; i--) {
      const date = new Date(prevYear, prevMonth, daysInPrevMonth - i);
      days.push({
        date,
        isCurrentMonth: false,
        events: events.filter((e) => {
          const ed = new Date(e.event_date);
          return ed.toDateString() === date.toDateString();
        }),
      });
    }

    // Current month days
    for (let d = 1; d <= daysInMonth; d++) {
      const date = new Date(year, month, d);
      days.push({
        date,
        isCurrentMonth: true,
        events: events.filter((e) => {
          const ed = new Date(e.event_date);
          return ed.toDateString() === date.toDateString();
        }),
      });
    }

    // Next month days
    const nextMonth = month === 11 ? 0 : month + 1;
    const nextYear = month === 11 ? year + 1 : year;
    const remainingDays = 42 - days.length;
    for (let d = 1; d <= remainingDays; d++) {
      const date = new Date(nextYear, nextMonth, d);
      days.push({
        date,
        isCurrentMonth: false,
        events: events.filter((e) => {
          const ed = new Date(e.event_date);
          return ed.toDateString() === date.toDateString();
        }),
      });
    }

    return days;
  }, [currentDate, events]);

  // Filtered events for list view
  const filteredEvents = useMemo(() => {
    let filtered = [...events];

    if (countryFilter) {
      filtered = filtered.filter((e) => e.country === countryFilter);
    }
    if (importanceFilter) {
      filtered = filtered.filter((e) => e.importance === importanceFilter);
    }
    if (currencyFilter) {
      filtered = filtered.filter((e) => e.currency === currencyFilter);
    }

    return filtered.sort(
      (a, b) => new Date(a.event_date).getTime() - new Date(b.event_date).getTime()
    );
  }, [events, countryFilter, importanceFilter, currencyFilter]);

  // Handlers
  async function handleScrape() {
    setScrapeLoading(true);
    setScrapeResult(null);
    try {
      const result = await scrapeEconEvents();
      setScrapeResult(
        `Created: ${result.events_created}, Updated: ${result.events_updated}${
          result.errors.length > 0 ? `, Errors: ${result.errors.join(", ")}` : ""
        }`
      );
      // Refresh events
      const eventsData = await getEconEvents({ limit: 500 });
      setEvents(eventsData.items);
      const upcoming = await getUpcomingEconEvents({ days: 7 });
      setUpcomingEvents(upcoming.items);
    } catch (err) {
      setScrapeResult(err instanceof Error ? err.message : "Scrape failed");
    } finally {
      setScrapeLoading(false);
    }
  }

  async function handleAddEvent() {
    try {
      await createEconEvent({
        ...newEvent,
        event_date: new Date(newEvent.event_date).toISOString(),
      });
      setShowAddModal(false);
      setNewEvent({
        event_name: "",
        country: "US",
        currency: "USD",
        event_date: "",
        importance: "medium",
        impact: "medium",
        previous: "",
        forecast: "",
        actual: "",
      });
      // Refresh
      const eventsData = await getEconEvents({ limit: 500 });
      setEvents(eventsData.items);
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to add event");
    }
  }

  async function handleDeleteEvent(id: number) {
    if (!confirm("Delete this event?")) return;
    try {
      await deleteEconEvent(id);
      setEvents((prev) => prev.filter((e) => e.id !== id));
      setUpcomingEvents((prev) => prev.filter((e) => e.id !== id));
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to delete");
    }
  }

  // Month navigation
  function prevMonth() {
    setCurrentDate(new Date(currentDate.getFullYear(), currentDate.getMonth() - 1, 1));
  }
  function nextMonth() {
    setCurrentDate(new Date(currentDate.getFullYear(), currentDate.getMonth() + 1, 1));
  }
  function goToToday() {
    setCurrentDate(new Date());
  }

  return (
    <div className="max-w-7xl mx-auto px-4 py-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-white font-bold text-xl tracking-tight">ECONOMIC CALENDAR</h1>
        <div className="flex items-center gap-2">
          <button
            onClick={handleScrape}
            disabled={scrapeLoading}
            className="px-3 py-1.5 text-xs font-medium text-yellow-400 border border-yellow-700 rounded hover:bg-yellow-900/20 transition-colors disabled:opacity-50"
          >
            {scrapeLoading ? "Scraping..." : "Refresh / Scrape"}
          </button>
          <button
            onClick={() => setShowAddModal(true)}
            className="px-3 py-1.5 text-xs font-medium text-green-400 border border-green-700 rounded hover:bg-green-900/20 transition-colors"
          >
            + Add Event
          </button>
        </div>
      </div>

      {/* Scrape result */}
      {scrapeResult && (
        <div className="mb-4 p-3 bg-yellow-900/20 border border-yellow-700 rounded text-yellow-400 text-sm">
          {scrapeResult}
        </div>
      )}

      {/* Filters */}
      <div className="flex flex-wrap gap-3 mb-6">
        <div className="flex items-center gap-2">
          <label className="text-xs text-zinc-400">Country:</label>
          <select
            value={countryFilter}
            onChange={(e) => setCountryFilter(e.target.value)}
            className="bg-zinc-900 border border-zinc-700 text-zinc-300 text-xs rounded px-2 py-1.5"
          >
            <option value="">All</option>
            <option value="US">🇺🇸 US</option>
            <option value="EU">🇪🇺 EU</option>
            <option value="UK">🇬🇧 UK</option>
            <option value="JP">🇯🇵 JP</option>
            <option value="AU">🇦🇺 AU</option>
            <option value="CA">🇨🇦 CA</option>
          </select>
        </div>

        <div className="flex items-center gap-2">
          <label className="text-xs text-zinc-400">Importance:</label>
          <select
            value={importanceFilter}
            onChange={(e) => setImportanceFilter(e.target.value)}
            className="bg-zinc-900 border border-zinc-700 text-zinc-300 text-xs rounded px-2 py-1.5"
          >
            <option value="">All</option>
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
          </select>
        </div>

        <div className="flex items-center gap-2">
          <label className="text-xs text-zinc-400">Currency:</label>
          <select
            value={currencyFilter}
            onChange={(e) => setCurrencyFilter(e.target.value)}
            className="bg-zinc-900 border border-zinc-700 text-zinc-300 text-xs rounded px-2 py-1.5"
          >
            <option value="">All</option>
            <option value="USD">USD</option>
            <option value="EUR">EUR</option>
            <option value="GBP">GBP</option>
            <option value="JPY">JPY</option>
            <option value="AUD">AUD</option>
            <option value="CAD">CAD</option>
          </select>
        </div>

        <div className="flex items-center gap-1 ml-auto">
          <button
            onClick={() => setView("calendar")}
            className={`px-3 py-1.5 text-xs font-medium rounded transition-colors ${
              view === "calendar"
                ? "bg-zinc-700 text-white"
                : "text-zinc-400 hover:text-zinc-200"
            }`}
          >
            Calendar
          </button>
          <button
            onClick={() => setView("list")}
            className={`px-3 py-1.5 text-xs font-medium rounded transition-colors ${
              view === "list"
                ? "bg-zinc-700 text-white"
                : "text-zinc-400 hover:text-zinc-200"
            }`}
          >
            List
          </button>
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-12">
          <p className="text-zinc-400">Loading events...</p>
        </div>
      ) : error ? (
        <div className="flex flex-col items-center justify-center py-12 gap-4">
          <p className="text-red-400">Error: {error}</p>
          <p className="text-sm text-zinc-400">Make sure the FastAPI backend is running at localhost:8000</p>
        </div>
      ) : (
        <div className="flex gap-6">
          {/* Main content */}
          <div className="flex-1">
            {view === "calendar" ? (
              <div className="bg-zinc-900/50 border border-zinc-800 rounded-lg overflow-hidden">
                {/* Calendar header */}
                <div className="flex items-center justify-between p-4 border-b border-zinc-800">
                  <button
                    onClick={prevMonth}
                    className="p-1.5 text-zinc-400 hover:text-white hover:bg-zinc-800 rounded transition-colors"
                  >
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M15 18l-6-6 6-6" />
                    </svg>
                  </button>
                  <div className="flex items-center gap-3">
                    <h2 className="text-white font-semibold">
                      {currentDate.toLocaleDateString("en-US", { month: "long", year: "numeric" })}
                    </h2>
                    <button
                      onClick={goToToday}
                      className="px-2 py-1 text-xs text-zinc-400 hover:text-white border border-zinc-700 rounded transition-colors"
                    >
                      Today
                    </button>
                  </div>
                  <button
                    onClick={nextMonth}
                    className="p-1.5 text-zinc-400 hover:text-white hover:bg-zinc-800 rounded transition-colors"
                  >
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M9 18l6-6-6-6" />
                    </svg>
                  </button>
                </div>

                {/* Calendar grid */}
                <div className="grid grid-cols-7">
                  {/* Day headers */}
                  {["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].map((day) => (
                    <div
                      key={day}
                      className="p-2 text-center text-xs font-medium text-zinc-500 border-b border-zinc-800"
                    >
                      {day}
                    </div>
                  ))}

                  {/* Days */}
                  {calendarDays.map((day, idx) => {
                    const isToday = day.date.toDateString() === new Date().toDateString();
                    const highImpactEvents = day.events.filter((e) => e.importance === "high");
                    const mediumImpactEvents = day.events.filter((e) => e.importance === "medium");

                    return (
                      <div
                        key={idx}
                        className={`min-h-24 p-2 border-b border-r border-zinc-800 ${
                          !day.isCurrentMonth ? "bg-zinc-900/30" : ""
                        } ${isToday ? "bg-zinc-800/50" : ""}`}
                      >
                        <div
                          className={`text-xs mb-1 ${
                            !day.isCurrentMonth
                              ? "text-zinc-600"
                              : isToday
                              ? "text-white font-bold"
                              : "text-zinc-400"
                          }`}
                        >
                          {day.date.getDate()}
                        </div>
                        <div className="space-y-0.5">
                          {day.events.slice(0, 3).map((event) => {
                            const style = IMPORTANCE_STYLES[event.importance];
                            return (
                              <div
                                key={event.id}
                                className={`text-xs px-1.5 py-0.5 rounded truncate ${style.bg} ${style.text} border ${style.border}`}
                                title={`${event.event_name} - ${event.currency}`}
                              >
                                {formatTime(event.event_date)} {event.event_name}
                              </div>
                            );
                          })}
                          {day.events.length > 3 && (
                            <div className="text-xs text-zinc-500 pl-1.5">
                              +{day.events.length - 3} more
                            </div>
                          )}
                          {/* Impact dots */}
                          {day.events.length > 0 && (
                            <div className="flex items-center gap-1 pl-1.5 mt-1">
                              {highImpactEvents.length > 0 && (
                                <span className="w-2 h-2 rounded-full bg-red-500" title="High impact events" />
                              )}
                              {mediumImpactEvents.length > 0 && (
                                <span className="w-2 h-2 rounded-full bg-yellow-500" title="Medium impact events" />
                              )}
                            </div>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            ) : (
              /* List View */
              <div className="space-y-3">
                {filteredEvents.length === 0 ? (
                  <div className="text-center py-12 text-zinc-400">
                    No events found for the selected filters
                  </div>
                ) : (
                  filteredEvents.map((event) => {
                    const style = IMPORTANCE_STYLES[event.importance];
                    return (
                      <div
                        key={event.id}
                        className={`bg-zinc-900/50 border ${style.border} rounded-lg p-4`}
                      >
                        <div className="flex items-start justify-between">
                          <div className="flex-1">
                            <div className="flex items-center gap-2 mb-1">
                              <span className="text-lg">
                                {COUNTRY_FLAGS[event.country] || "🌐"}
                              </span>
                              <h3 className="text-white font-medium">{event.event_name}</h3>
                              <span
                                className={`px-2 py-0.5 text-xs rounded border ${style.bg} ${style.text} ${style.border}`}
                              >
                                {event.importance.toUpperCase()}
                              </span>
                              <span className="text-xs text-zinc-500">{event.currency}</span>
                            </div>
                            <p className="text-sm text-zinc-400">
                              {formatDate(event.event_date)}
                            </p>
                          </div>
                          <button
                            onClick={() => handleDeleteEvent(event.id)}
                            className="p-1 text-zinc-500 hover:text-red-400 transition-colors"
                          >
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                              <path d="M3 6h18M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2" />
                            </svg>
                          </button>
                        </div>

                        {/* Previous/Forecast/Actual */}
                        {(event.previous || event.forecast || event.actual) && (
                          <div className="flex gap-6 mt-3 pt-3 border-t border-zinc-800">
                            {event.previous && (
                              <div>
                                <p className="text-xs text-zinc-500 mb-0.5">Previous</p>
                                <p className="text-sm text-zinc-300">{event.previous}</p>
                              </div>
                            )}
                            {event.forecast && (
                              <div>
                                <p className="text-xs text-zinc-500 mb-0.5">Forecast</p>
                                <p className="text-sm text-yellow-400">{event.forecast}</p>
                              </div>
                            )}
                            {event.actual && (
                              <div>
                                <p className="text-xs text-zinc-500 mb-0.5">Actual</p>
                                <p className="text-sm text-green-400">{event.actual}</p>
                              </div>
                            )}
                          </div>
                        )}

                        {/* Impacted instruments */}
                        {event.impacted_instruments && event.impacted_instruments.length > 0 && (
                          <div className="mt-3 pt-3 border-t border-zinc-800">
                            <p className="text-xs text-zinc-500 mb-1.5">Impact on instruments:</p>
                            <div className="flex flex-wrap gap-1.5">
                              {event.impacted_instruments.map((inst) => (
                                <span
                                  key={inst}
                                  className="px-2 py-0.5 text-xs bg-zinc-800 text-zinc-300 rounded"
                                >
                                  {inst}
                                </span>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    );
                  })
                )}
              </div>
            )}
          </div>

          {/* Sidebar - Upcoming high impact */}
          <div className="w-72 hidden lg:block">
            <div className="bg-zinc-900/50 border border-zinc-800 rounded-lg p-4 sticky top-4">
              <h3 className="text-white font-semibold mb-4">Upcoming (7 days)</h3>
              {upcomingEvents.length === 0 ? (
                <p className="text-zinc-500 text-sm">No upcoming events</p>
              ) : (
                <div className="space-y-3">
                  {upcomingEvents.map((event) => {
                    const style = IMPORTANCE_STYLES[event.importance];
                    return (
                      <div key={event.id} className="border-l-2 border-zinc-700 pl-3">
                        <div className="flex items-center gap-1.5 mb-0.5">
                          <span className="text-sm">{COUNTRY_FLAGS[event.country] || "🌐"}</span>
                          <span className={`text-xs ${style.text}`}>{event.event_name}</span>
                        </div>
                        <p className="text-xs text-zinc-500">
                          {formatDateShort(event.event_date)} • {formatTime(event.event_date)}
                        </p>
                        <div className="flex items-center gap-1 mt-1">
                          <span className={`w-1.5 h-1.5 rounded-full ${style.dot}`} />
                          <span className="text-xs text-zinc-500">{event.importance}</span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}

              {/* Impact map section */}
              {impactMap && (
                <div className="mt-6 pt-4 border-t border-zinc-800">
                  <h4 className="text-zinc-400 text-xs font-medium mb-3">Event Impact Guide</h4>
                  <div className="space-y-2">
                    {Object.entries(impactMap.mappings).slice(0, 8).map(([event, instruments]) => (
                      <div key={event} className="text-xs">
                        <p className="text-zinc-300 mb-0.5 truncate" title={event}>
                          {event.length > 25 ? event.slice(0, 25) + "..." : event}
                        </p>
                        <p className="text-zinc-500 truncate" title={instruments.join(", ")}>
                          → {instruments.join(", ")}
                        </p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Add Event Modal */}
      {showAddModal && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
          <div className="bg-zinc-900 border border-zinc-700 rounded-lg p-6 w-full max-w-md">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-white font-semibold">Add Economic Event</h2>
              <button
                onClick={() => setShowAddModal(false)}
                className="p-1 text-zinc-400 hover:text-white"
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M18 6L6 18M6 6l12 12" />
                </svg>
              </button>
            </div>

            <div className="space-y-4">
              <div>
                <label className="block text-xs text-zinc-400 mb-1">Event Name *</label>
                <input
                  type="text"
                  value={newEvent.event_name}
                  onChange={(e) => setNewEvent({ ...newEvent, event_name: e.target.value })}
                  className="w-full bg-zinc-800 border border-zinc-700 text-white text-sm rounded px-3 py-2"
                  placeholder="e.g., FOMC Rate Decision"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs text-zinc-400 mb-1">Country *</label>
                  <select
                    value={newEvent.country}
                    onChange={(e) => setNewEvent({ ...newEvent, country: e.target.value })}
                    className="w-full bg-zinc-800 border border-zinc-700 text-white text-sm rounded px-3 py-2"
                  >
                    <option value="US">🇺🇸 US</option>
                    <option value="EU">🇪🇺 EU</option>
                    <option value="UK">🇬🇧 UK</option>
                    <option value="JP">🇯🇵 JP</option>
                    <option value="AU">🇦🇺 AU</option>
                    <option value="CA">🇨🇦 CA</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs text-zinc-400 mb-1">Currency *</label>
                  <select
                    value={newEvent.currency}
                    onChange={(e) => setNewEvent({ ...newEvent, currency: e.target.value })}
                    className="w-full bg-zinc-800 border border-zinc-700 text-white text-sm rounded px-3 py-2"
                  >
                    <option value="USD">USD</option>
                    <option value="EUR">EUR</option>
                    <option value="GBP">GBP</option>
                    <option value="JPY">JPY</option>
                    <option value="AUD">AUD</option>
                    <option value="CAD">CAD</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-xs text-zinc-400 mb-1">Date & Time *</label>
                <input
                  type="datetime-local"
                  value={newEvent.event_date}
                  onChange={(e) => setNewEvent({ ...newEvent, event_date: e.target.value })}
                  className="w-full bg-zinc-800 border border-zinc-700 text-white text-sm rounded px-3 py-2"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs text-zinc-400 mb-1">Importance</label>
                  <select
                    value={newEvent.importance}
                    onChange={(e) => setNewEvent({ ...newEvent, importance: e.target.value })}
                    className="w-full bg-zinc-800 border border-zinc-700 text-white text-sm rounded px-3 py-2"
                  >
                    <option value="low">Low</option>
                    <option value="medium">Medium</option>
                    <option value="high">High</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs text-zinc-400 mb-1">Impact</label>
                  <select
                    value={newEvent.impact}
                    onChange={(e) => setNewEvent({ ...newEvent, impact: e.target.value })}
                    className="w-full bg-zinc-800 border border-zinc-700 text-white text-sm rounded px-3 py-2"
                  >
                    <option value="low">Low</option>
                    <option value="medium">Medium</option>
                    <option value="high">High</option>
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="block text-xs text-zinc-400 mb-1">Previous</label>
                  <input
                    type="text"
                    value={newEvent.previous}
                    onChange={(e) => setNewEvent({ ...newEvent, previous: e.target.value })}
                    className="w-full bg-zinc-800 border border-zinc-700 text-white text-sm rounded px-3 py-2"
                    placeholder="3.2%"
                  />
                </div>
                <div>
                  <label className="block text-xs text-zinc-400 mb-1">Forecast</label>
                  <input
                    type="text"
                    value={newEvent.forecast}
                    onChange={(e) => setNewEvent({ ...newEvent, forecast: e.target.value })}
                    className="w-full bg-zinc-800 border border-zinc-700 text-white text-sm rounded px-3 py-2"
                    placeholder="3.1%"
                  />
                </div>
                <div>
                  <label className="block text-xs text-zinc-400 mb-1">Actual</label>
                  <input
                    type="text"
                    value={newEvent.actual}
                    onChange={(e) => setNewEvent({ ...newEvent, actual: e.target.value })}
                    className="w-full bg-zinc-800 border border-zinc-700 text-white text-sm rounded px-3 py-2"
                    placeholder="3.0%"
                  />
                </div>
              </div>

              <div className="flex gap-3 pt-2">
                <button
                  onClick={() => setShowAddModal(false)}
                  className="flex-1 px-4 py-2 text-sm text-zinc-400 border border-zinc-700 rounded hover:bg-zinc-800 transition-colors"
                >
                  Cancel
                </button>
                <button
                  onClick={handleAddEvent}
                  disabled={!newEvent.event_name || !newEvent.event_date}
                  className="flex-1 px-4 py-2 text-sm text-white bg-green-600 rounded hover:bg-green-700 transition-colors disabled:opacity-50"
                >
                  Add Event
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
