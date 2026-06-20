"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";

/**
 * Client-side route guard.
 *
 * Because the API runs on a separate origin and the refresh token is an
 * httpOnly cookie scoped to that origin, Next.js middleware can't read it.
 * We instead gate protected pages on the client: while the session is being
 * restored we show a loader, and unauthenticated users are redirected to login.
 * (For middleware-level protection, front the API with a same-origin BFF — see
 * the README "Protected routes" note.)
 */
export function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { status } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (status === "unauthenticated") {
      router.replace("/login");
    }
  }, [status, router]);

  if (status !== "authenticated") {
    return <div className="center-screen">Loading…</div>;
  }
  return <>{children}</>;
}
