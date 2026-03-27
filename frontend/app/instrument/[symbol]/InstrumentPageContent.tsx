"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { ContentItem, Instrument } from "@/lib/api";
import { ContentCard } from "@/components/ContentCard";
import { InstrumentBadge } from "@/components/InstrumentBadge";

export default function InstrumentPageContent() {
  const params = useParams();
  const symbol = params.symbol as string;
  const [instrument, setInstrument] = useState<Instrument | null>(null);
  const [content, setContent] = useState<ContentItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchData() {
      setLoading(true);
      setError(null);
      try {
        const [instrumentRes, contentRes] = await Promise.all([
          fetch(`/api/instruments/${symbol}`),
          fetch(`/api/instruments/${symbol}/content`),
        ]);

        if (!instrumentRes.ok) throw new Error("Instrument not found");
        if (!contentRes.ok) throw new Error("Failed to fetch content");

        const instrumentData = await instrumentRes.json();
        const contentData = await contentRes.json();

        setInstrument(instrumentData);
        setContent(contentData);
      } catch (err) {
        setError(err instanceof Error ? err.message : "An error occurred");
      } finally {
        setLoading(false);
      }
    }

    fetchData();
  }, [symbol]);

  if (loading) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-12">
        <p className="text-muted-foreground">Loading...</p>
      </div>
    );
  }

  if (error || !instrument) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-12">
        <p className="text-destructive">Error: {error || "Instrument not found"}</p>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 py-6">
      <div className="mb-8">
        <div className="flex items-center gap-4 mb-2">
          <InstrumentBadge symbol={instrument.symbol} assetClass={instrument.asset_class} />
          <h1 className="text-2xl font-bold">{instrument.name}</h1>
        </div>
        <p className="text-muted-foreground">
          {instrument.asset_class} · {content.length} {content.length === 1 ? "item" : "items"}
        </p>
      </div>

      {content.length === 0 ? (
        <p className="text-muted-foreground">No content available for this instrument.</p>
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
