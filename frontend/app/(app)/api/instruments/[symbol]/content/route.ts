import { NextResponse } from "next/server";

import { getApiBaseUrl } from "@/lib/config";

const API_BASE = getApiBaseUrl();

export async function GET(
  request: Request,
  { params }: { params: Promise<{ symbol: string }> }
) {
  const { symbol } = await params;

  try {
    const res = await fetch(`${API_BASE}/instruments/symbol/${encodeURIComponent(symbol)}/content`, {
      cache: "no-store",
    });
    if (!res.ok) {
      return NextResponse.json({ error: "Failed to fetch content" }, { status: res.status });
    }
    const data = await res.json();
    return NextResponse.json(data);
  } catch (error) {
    return NextResponse.json({ error: "Backend unavailable" }, { status: 503 });
  }
}
