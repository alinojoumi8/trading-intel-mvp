import { NextResponse } from "next/server";

const API_BASE = "http://localhost:8000";

export async function GET(
  request: Request,
  { params }: { params: Promise<{ symbol: string }> }
) {
  const { symbol } = await params;

  try {
    const res = await fetch(`${API_BASE}/instruments/${symbol}`, {
      cache: "no-store",
    });
    if (!res.ok) {
      return NextResponse.json({ error: "Instrument not found" }, { status: res.status });
    }
    const data = await res.json();
    return NextResponse.json(data);
  } catch (error) {
    return NextResponse.json({ error: "Backend unavailable" }, { status: 503 });
  }
}
