import { NextRequest, NextResponse } from "next/server";

const API =
  process.env.API_BASE_URL ??
  process.env.NEXT_PUBLIC_API_BASE_URL ??
  "http://localhost:8000/api/v1";

// Proxies to the domain service's /auth/login and, on success, stores the token
// in an httpOnly cookie the browser JS can't read. The token never touches
// client-side storage.
export async function POST(req: NextRequest) {
  let body: { email?: string; password?: string };
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "Invalid request." }, { status: 400 });
  }

  const res = await fetch(`${API}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email: body.email, password: body.password }),
    cache: "no-store",
  }).catch(() => null);

  // Distinguish "can't reach the API" from "wrong credentials" — they are very
  // different problems and conflating them sends people down the wrong path.
  if (res === null) {
    return NextResponse.json(
      { error: "Could not reach the domain service on :8000. Is it running (make api / uvicorn)?" },
      { status: 502 },
    );
  }
  if (res.status === 401) {
    return NextResponse.json({ error: "Invalid email or password." }, { status: 401 });
  }
  if (!res.ok) {
    return NextResponse.json({ error: `Login failed (${res.status}).` }, { status: res.status });
  }

  const data = (await res.json()) as { token: string; user: unknown };
  const out = NextResponse.json({ user: data.user });
  out.cookies.set("rv_token", data.token, {
    httpOnly: true,
    sameSite: "lax",
    path: "/",
    maxAge: 60 * 60 * 12, // matches the token TTL
    secure: process.env.NODE_ENV === "production",
  });
  return out;
}
