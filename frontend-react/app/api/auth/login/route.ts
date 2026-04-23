import { type NextRequest, NextResponse } from "next/server";

const BACKEND = process.env.BACKEND_URL ?? "http://localhost:8000";

export async function POST(request: NextRequest) {
  try {
    const { username, password } = await request.json();

    // FastAPI OAuth2 form expects application/x-www-form-urlencoded
    const form = new URLSearchParams();
    form.append("username", username);
    form.append("password", password);

    const backendRes = await fetch(`${BACKEND}/token`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: form.toString(),
    });

    if (!backendRes.ok) {
      const err = await backendRes.json().catch(() => ({}));
      return NextResponse.json(
        { detail: err?.detail ?? "Invalid credentials" },
        { status: backendRes.status }
      );
    }

    const data = await backendRes.json();
    const token: string = data.access_token;

    const response = NextResponse.json({ ok: true });
    response.cookies.set("token", token, {
      httpOnly: true,
      path: "/",
      sameSite: "strict",
      // secure: true   // enable in production (HTTPS)
      maxAge: 60 * 60 * 8, // 8 hours
    });
    return response;
  } catch {
    return NextResponse.json({ detail: "Login failed" }, { status: 500 });
  }
}
