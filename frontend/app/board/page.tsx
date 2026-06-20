"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { ProtectedRoute } from "@/components/protected-route";
import { NotificationPanel } from "@/components/notification-panel";
import { SprintBoard } from "@/components/sprint-board";
import { useAuth } from "@/lib/auth-context";

function BoardScreen() {
  const { logout } = useAuth();
  const router = useRouter();

  async function onLogout() {
    await logout();
    router.replace("/login");
  }

  return (
    <div className="board-page">
      <div className="board-page-header">
        <div className="board-page-heading">
          <Link href="/dashboard" className="brand brand-link">
            Team<span>Sync</span>
          </Link>
          <h1 className="board-page-title">Sprint Board</h1>
          <Link href="/import" className="board-subnav-link">
            Import CSV
          </Link>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <NotificationPanel />
          <button className="ghost" onClick={onLogout}>
            Log out
          </button>
        </div>
      </div>

      <SprintBoard />
    </div>
  );
}

export default function BoardPage() {
  return (
    <ProtectedRoute>
      <BoardScreen />
    </ProtectedRoute>
  );
}
