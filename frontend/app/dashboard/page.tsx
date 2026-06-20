"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { ProtectedRoute } from "@/components/protected-route";
import { NotificationPanel } from "@/components/notification-panel";
import { useAuth } from "@/lib/auth-context";

function DashboardContent() {
  const { user, logout } = useAuth();
  const router = useRouter();

  async function onLogout() {
    await logout();
    router.replace("/login");
  }

  return (
    <div className="dashboard">
      <div className="dashboard-header">
        <div className="brand">
          Team<span>Sync</span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <NotificationPanel />
          <button className="ghost" onClick={onLogout}>
            Log out
          </button>
        </div>
      </div>

      <div className="card" style={{ maxWidth: "100%" }}>
        <h2 style={{ marginTop: 0 }}>
          Welcome{user?.full_name ? `, ${user.full_name}` : ""} 👋
        </h2>
        <p style={{ color: "var(--muted)" }}>
          You&apos;re signed in to a protected page. This route is only reachable
          with a valid session.
        </p>
        <p style={{ display: "flex", gap: "20px" }}>
          <Link href="/board" className="board-cta">
            Open Sprint Board →
          </Link>
          <Link href="/import" className="board-cta">
            Import from CSV →
          </Link>
        </p>
        <ul style={{ color: "var(--muted)", fontSize: 14, lineHeight: 1.9 }}>
          <li>
            <strong style={{ color: "var(--text)" }}>Email:</strong> {user?.email}
          </li>
          <li>
            <strong style={{ color: "var(--text)" }}>User ID:</strong> {user?.id}
          </li>
          <li>
            <strong style={{ color: "var(--text)" }}>Verified:</strong>{" "}
            {user?.is_verified ? "yes" : "no"}
          </li>
        </ul>
      </div>
    </div>
  );
}

export default function DashboardPage() {
  return (
    <ProtectedRoute>
      <DashboardContent />
    </ProtectedRoute>
  );
}
