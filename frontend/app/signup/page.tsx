"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/lib/auth-context";
import { ApiError } from "@/lib/api";

export default function SignupPage() {
  const { signup } = useAuth();
  const router = useRouter();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await signup(email, password, fullName);
      router.replace("/dashboard");
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
        <div className="subtitle">Create your account — it takes a minute.</div>

        {error && <div className="alert error">{error}</div>}

        <div className="field">
          <label htmlFor="fullName">Full name</label>
          <input
            id="fullName"
            type="text"
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            autoComplete="name"
          />
        </div>
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
        <div className="field">
          <label htmlFor="password">Password</label>
          <input
            id="password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            autoComplete="new-password"
          />
          <span style={{ fontSize: 12, color: "var(--muted)" }}>
            At least 8 characters, with a letter and a number.
          </span>
        </div>

        <button className="primary" type="submit" disabled={loading}>
          {loading ? "Creating account…" : "Sign up"}
        </button>

        <div className="meta-row">
          <span>Already have an account?</span>
          <Link href="/login">Log in</Link>
        </div>
      </form>
    </div>
  );
}
