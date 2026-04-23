/**
 * Generic passthrough proxy to the FastAPI backend.
 *
 * Every request to /api/proxy/<path...> is forwarded to
 * http://localhost:8000/<path...> with the httpOnly cookie token
 * attached as Authorization: Bearer <token>.
 *
 * This means the JWT never touches client-side JavaScript.
 */
import { type NextRequest, NextResponse } from "next/server";

const BACKEND = process.env.BACKEND_URL ?? "http://localhost:8000";

async function handler(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const { path } = await params;
  const targetPath = path.join("/");
  const targetUrl = `${BACKEND}/${targetPath}${request.nextUrl.search}`;

  const token = request.cookies.get("token")?.value;
  if (!token) {
    return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });
  }

  // Forward the request body for non-GET methods
  const body =
    request.method !== "GET" && request.method !== "HEAD"
      ? await request.text()
      : undefined;

  const headers: Record<string, string> = {
    Authorization: `Bearer ${token}`,
    "Content-Type": request.headers.get("content-type") ?? "application/json",
  };

  const backendRes = await fetch(targetUrl, {
    method: request.method,
    headers,
    body,
  });

  const responseBody = await backendRes.text();

  return new NextResponse(responseBody, {
    status: backendRes.status,
    headers: {
      "Content-Type":
        backendRes.headers.get("content-type") ?? "application/json",
    },
  });
}

export { handler as DELETE, handler as GET, handler as PATCH, handler as POST, handler as PUT };

