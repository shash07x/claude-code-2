"use client";

import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { authApi, ApiError } from "@/lib/api";

function ResetPasswordForm() {
  const params = useSearchParams();
  const router = useRouter();
  const token = params.get("token") ?? "";

  const [password, setPassword] = useState("");
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await authApi.confirmPasswordReset(token, password);
      setDone(true);
      setTimeout(() => router.replace("/login"), 1500);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  }

  if (!token) {
    return (
      <div className="card">
        <div className="brand">
          Team<span>Sync</span>
        </div>
        <div className="alert error">This reset link is missing its token.</div>
        <div className="meta-row">
          <Link href="/forgot-password">Request a new link</Link>
        </div>
      </div>
    );
  }

  return (
    <form className="card" onSubmit={onSubmit}>
      <div className="brand">
        Team<span>Sync</span>
      </div>
      <div className="subtitle">Choose a new password.</div>

      {done && (
        <div className="alert success">
          Password updated. Redirecting to login…
        </div>
      )}
      {error && <div className="alert error">{error}</div>}

      <div className="field">
        <label htmlFor="password">New password</label>
        <input
          id="password"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
          autoComplete="new-password"
          disabled={done}
        />
        <span style={{ fontSize: 12, color: "var(--muted)" }}>
          At least 8 characters, with a letter and a number.
        </span>
      </div>

      <button className="primary" type="submit" disabled={loading || done}>
        {loading ? "Updating…" : "Update password"}
      </button>

      <div className="meta-row">
        <Link href="/login">Back to login</Link>
      </div>
    </form>
  );
}

export default function ResetPasswordPage() {
  return (
    <div className="auth-shell">
      <Suspense fallback={<div className="card">Loading…</div>}>
        <ResetPasswordForm />
      </Suspense>
    </div>
  );
}
