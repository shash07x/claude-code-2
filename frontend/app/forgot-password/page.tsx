"use client";

import { useState } from "react";
import Link from "next/link";
import { authApi, ApiError } from "@/lib/api";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setMessage(null);
    setLoading(true);
    try {
      const res = await authApi.requestPasswordReset(email);
      setMessage(res.detail);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="auth-shell">
      <form className="card" onSubmit={onSubmit}>
        <div className="brand">
          Team<span>Sync</span>
        </div>
        <div className="subtitle">
          Enter your email and we&apos;ll send a reset link.
        </div>

        {message && <div className="alert success">{message}</div>}
        {error && <div className="alert error">{error}</div>}

        <div className="field">
          <label htmlFor="email">Email</label>
          <input
            id="email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            autoComplete="email"
          />
        </div>

        <button className="primary" type="submit" disabled={loading}>
          {loading ? "Sending…" : "Send reset link"}
        </button>

        <div className="meta-row">
          <Link href="/login">Back to login</Link>
        </div>
      </form>
    </div>
  );
}
