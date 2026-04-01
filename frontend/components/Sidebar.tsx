"use client";

import React from "react";
import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";

const navItems = [
  {
    section: "INTELLIGENCE",
    items: [
      { label: "Intelligence", href: "/", icon: "chart" },
      { label: "Trade Setups", href: "/?type=setup", icon: "trending" },
      { label: "Signals", href: "/signals", icon: "signals" },
      { label: "News", href: "/news", icon: "newspaper" },
      { label: "Macro Roundup", href: "/?type=macro_roundup", icon: "globe" },
    ],
  },
  {
    section: "MARKET ANALYSIS",
    items: [
      { label: "Regime", href: "/regime", icon: "activity" },
      { label: "Multi-Timeframe", href: "/multi-timeframe", icon: "layers" },
      { label: "Correlation", href: "/correlation", icon: "grid" },
      { label: "Economic Calendar", href: "/economic-calendar", icon: "calendar" },
    ],
  },
  {
    section: "ANALYTICS",
    items: [
      { label: "Performance", href: "/performance", icon: "performance" },
      { label: "Leaderboard", href: "/leaderboard", icon: "leaderboard" },
      { label: "COT History", href: "/cot", icon: "cot" },
    ],
  },
  {
    section: "WORKSPACE",
    items: [
      { label: "Morning Briefing", href: "/briefing", icon: "briefcase" },
      { label: "Alerts", href: "/alerts", icon: "bell" },
    ],
  },
];

const icons: Record<string, React.ReactNode> = {
  chart: (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
    </svg>
  ),
  trending: (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <polyline points="23 6 13.5 15.5 8.5 10.5 1 18" />
      <polyline points="17 6 23 6 23 12" />
    </svg>
  ),
  globe: (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <circle cx="12" cy="12" r="10" />
      <line x1="2" y1="12" x2="22" y2="12" />
      <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
    </svg>
  ),
  briefcase: (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <rect x="2" y="7" width="20" height="14" rx="2" ry="2" />
      <path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16" />
    </svg>
  ),
  bell: (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
      <path d="M13.73 21a2 2 0 0 1-3.46 0" />
    </svg>
  ),
  help: (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <circle cx="12" cy="12" r="10" />
      <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3" />
      <line x1="12" y1="17" x2="12.01" y2="17" />
    </svg>
  ),
  file: (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <polyline points="14 2 14 8 20 8" />
      <line x1="16" y1="13" x2="8" y2="13" />
      <line x1="16" y1="17" x2="8" y2="17" />
      <polyline points="10 9 9 9 8 9" />
    </svg>
  ),
  newspaper: (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M4 22h16a2 2 0 0 0 2-2V4a2 2 0 0 0-2-2H8a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2zm0 0V4a2 2 0 0 0-2-2H4" />
      <path d="M18 14h-8" />
      <path d="M15 18h-5" />
      <path d="M10 6h8v4h-8V6z" />
    </svg>
  ),
  signals: (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
    </svg>
  ),
  performance: (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M18 20V10" />
      <path d="M12 20V4" />
      <path d="M6 20v-6" />
    </svg>
  ),
  cot: (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <rect x="3" y="3" width="18" height="18" rx="2" />
      <path d="M3 9h18" />
      <path d="M9 21V9" />
    </svg>
  ),
  leaderboard: (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <line x1="18" y1="20" x2="18" y2="10" />
      <line x1="12" y1="20" x2="12" y2="4" />
      <line x1="6" y1="20" x2="6" y2="14" />
      <line x1="2" y1="20" x2="22" y2="20" />
    </svg>
  ),
  activity: (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
    </svg>
  ),
  layers: (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <polygon points="12 2 2 7 12 12 22 7 12 2" />
      <polyline points="2 17 12 22 22 17" />
      <polyline points="2 12 12 17 22 12" />
    </svg>
  ),
  grid: (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <rect x="3" y="3" width="7" height="7" />
      <rect x="14" y="3" width="7" height="7" />
      <rect x="14" y="14" width="7" height="7" />
      <rect x="3" y="14" width="7" height="7" />
    </svg>
  ),
  calendar: (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
      <line x1="16" y1="2" x2="16" y2="6" />
      <line x1="8" y1="2" x2="8" y2="6" />
      <line x1="3" y1="10" x2="21" y2="10" />
    </svg>
  ),
};

export function Sidebar() {
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const isActive = (item: { href: string; label: string }) => {
    if (item.href === "/") {
      return pathname === "/" && !searchParams.has("type");
    }
    if (item.href.startsWith("/?")) {
      const typeValue = item.href.split("=")[1];
      return searchParams.get("type") === typeValue;
    }
    return pathname === item.href;
  };

  return (
    <aside className="w-56 min-h-screen bg-black border-r border-zinc-800 flex flex-col shrink-0">
      <div className="px-4 py-5 border-b border-zinc-800">
        <div className="flex items-center gap-2 mb-1">
          <div className="w-6 h-6 bg-green-500 rounded flex items-center justify-center">
            <svg width="10" height="10" viewBox="0 0 24 24" fill="white">
              <polygon points="5 3 19 12 5 21 5 3" />
            </svg>
          </div>
          <span className="text-white font-bold text-sm tracking-tight">PROTIER</span>
        </div>
        <span className="text-zinc-500 text-xs">COMMAND CENTER</span>
      </div>

      <nav className="flex-1 px-3 py-4 space-y-6">
        {navItems.map((section) => (
          <div key={section.section}>
            <span className="text-zinc-600 text-xs font-semibold uppercase tracking-wider px-2 mb-2 block">
              {section.section}
            </span>
            <div className="space-y-0.5">
              {section.items.map((item) => {
                const active = isActive(item);
                return (
                  <Link
                    key={item.label}
                    href={item.href}
                    className={`flex items-center gap-3 px-3 py-2 rounded text-sm transition-colors ${
                      active
                        ? "text-green-400 bg-zinc-900 border-l-2 border-green-400"
                        : "text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900"
                    }`}
                  >
                    <span className={active ? "text-green-400" : "text-zinc-500"}>
                      {icons[item.icon]}
                    </span>
                    {item.label}
                  </Link>
                );
              })}
            </div>
          </div>
        ))}
      </nav>

      <div className="px-3 py-4 border-t border-zinc-800">
        <div className="flex items-center gap-3 px-3 py-2">
          <div className="w-7 h-7 rounded-full bg-zinc-800 flex items-center justify-center">
            <span className="text-zinc-400 text-xs font-bold">A</span>
          </div>
          <div>
            <p className="text-white text-xs font-medium">Admin</p>
            <p className="text-zinc-600 text-xs">Trading Intel</p>
          </div>
        </div>
      </div>
    </aside>
  );
}
