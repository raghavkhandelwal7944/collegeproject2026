import { type NextRequest, NextResponse } from "next/server";

const BACKEND = process.env.BACKEND_URL ?? "http://localhost:8000";

export async function POST(request: NextRequest) {
  try {
    const { username, password, first_name, last_name, email } = await request.json();

    const backendRes = await fetch(`${BACKEND}/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password, first_name, last_name, email }),
    });

    if (!backendRes.ok) {
      const err = await backendRes.json().catch(() => ({}));
      return NextResponse.json(
        { detail: err?.detail ?? "Signup failed" },
        { status: backendRes.status }
      );
    }

    return NextResponse.json({ ok: true }, { status: 201 });
  } catch {
    return NextResponse.json({ detail: "Signup failed" }, { status: 500 });
  }
}

    