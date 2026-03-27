"use client";

import { Suspense } from "react";
import { Sidebar } from "./Sidebar";

function SidebarFallback() {
  return (
    <aside className="w-56 min-h-screen bg-black border-r border-zinc-800 shrink-0">
      <div className="px-4 py-5 border-b border-zinc-800">
        <div className="flex items-center gap-2 mb-1">
          <div className="w-6 h-6 bg-green-500 rounded flex items-center justify-center">
            <div className="w-3 h-3 bg-white/30 rounded" />
          </div>
          <span className="text-white font-bold text-sm tracking-tight">PROTIER</span>
        </div>
        <span className="text-zinc-500 text-xs">COMMAND CENTER</span>
      </div>
    </aside>
  );
}

export function SidebarWrapper() {
  return (
    <Suspense fallback={<SidebarFallback />}>
      <Sidebar />
    </Suspense>
  );
}
