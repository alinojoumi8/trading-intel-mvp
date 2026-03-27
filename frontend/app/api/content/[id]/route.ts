import { NextResponse } from "next/server";

const API_BASE = "http://localhost:8000";

export async function GET(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;

  try {
    const res = await fetch(`${API_BASE}/content/${id}`, {
      cache: "no-store",
    });
    if (!res.ok) {
      return NextResponse.json({ error: "Content not found" }, { status: res.status });
    }
    const data = await res.json();
    return NextResponse.json(data);
  } catch (error) {
    return NextResponse.json({ error: "Backend unavailable" }, { status: 503 });
  }
}
