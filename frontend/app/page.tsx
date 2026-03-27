import { Suspense } from "react";
import HomeContent from "./HomeContent";

function SearchBarFallback() {
  return (
    <div className="h-10 w-full max-w-md bg-zinc-900 rounded-lg animate-pulse" />
  );
}

function FilterBarFallback() {
  return (
    <div className="flex gap-3">
      <div className="h-8 w-20 bg-zinc-900 rounded animate-pulse" />
      <div className="h-8 w-24 bg-zinc-900 rounded animate-pulse" />
      <div className="h-8 w-20 bg-zinc-900 rounded animate-pulse" />
    </div>
  );
}

export default function HomePage() {
  return (
    <Suspense fallback={<div className="max-w-7xl mx-auto px-4 py-6"><div className="flex flex-col gap-6 mb-8"><SearchBarFallback /><FilterBarFallback /></div><div className="flex items-center justify-center py-12"><p className="text-muted-foreground">Loading...</p></div></div>}>
      <HomeContent />
    </Suspense>
  );
}
