import { NextResponse } from "next/server";

import { getApiBaseUrl } from "@/lib/config";

const API_BASE = getApiBaseUrl();

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const query = searchParams.toString();

  try {
    const res = await fetch(`${API_BASE}/content${query ? `?${query}` : ""}`, {
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
