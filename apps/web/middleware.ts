import { NextRequest, NextResponse } from "next/server";

// One place enforces the session:
//  - /api/auth/*  — Next route handlers that manage the login cookie (public)
//  - /api/v1/*    — proxied to the domain service; inject the Bearer header from
//                   the httpOnly cookie so browser fetches are authenticated
//  - everything else is a page: no cookie → redirect to /login
export function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl;
  const token = req.cookies.get("rv_token")?.value;

  if (pathname.startsWith("/api/auth")) {
    return NextResponse.next();
  }

  if (pathname.startsWith("/api/v1")) {
    const headers = new Headers(req.headers);
    if (token) headers.set("authorization", `Bearer ${token}`);
    return NextResponse.next({ request: { headers } });
  }

  if (!token && pathname !== "/login") {
    const url = req.nextUrl.clone();
    url.pathname = "/login";
    return NextResponse.redirect(url);
  }

  // Already signed in — keep them out of the login page.
  if (token && pathname === "/login") {
    const url = req.nextUrl.clone();
    url.pathname = "/";
    return NextResponse.redirect(url);
  }

  return NextResponse.next();
}

export const config = {
  // Run on everything except Next's static assets and the favicon.
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
