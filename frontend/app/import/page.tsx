"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { ProtectedRoute } from "@/components/protected-route";
import { NotificationPanel } from "@/components/notification-panel";
import { CsvImporter } from "@/components/csv-importer";
import { useAuth } from "@/lib/auth-context";

function ImportScreen() {
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
          <h1 className="board-page-title">Import from CSV</h1>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <NotificationPanel />
          <button className="ghost" onClick={onLogout}>
            Log out
          </button>
        </div>
      </div>

      <CsvImporter />
    </div>
  );
}

export default function ImportPage() {
  return (
    <ProtectedRoute>
      <ImportScreen />
    </ProtectedRoute>
  );
}
