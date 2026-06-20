"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { notificationsApi, type Notification } from "@/lib/api";

// --- Icon helpers (inline SVG, no icon library dependency) ------------------

function BellIcon({ hasUnread }: { hasUnread: boolean }) {
  return (
    <svg
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      style={{ display: "block" }}
    >
      <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
      <path d="M13.73 21a2 2 0 0 1-3.46 0" />
      {hasUnread && (
        <circle cx="19" cy="5" r="4" fill="var(--primary)" stroke="var(--bg)" strokeWidth="1.5" />
      )}
    </svg>
  );
}

function TrashIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="3 6 5 6 21 6" />
      <path d="M19 6l-1 14H6L5 6" />
      <path d="M10 11v6M14 11v6" />
      <path d="M9 6V4h6v2" />
    </svg>
  );
}

// --- Type badge -------------------------------------------------------------

const TYPE_LABELS: Record<Notification["type"], string> = {
  mention: "@",
  assignment: "→",
  comment: "💬",
  system: "ℹ",
};

// --- Relative time ----------------------------------------------------------

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60_000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

// --- Main component ---------------------------------------------------------

export function NotificationPanel() {
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<Notification[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [loading, setLoading] = useState(false);
  const panelRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);

  // Poll unread count every 30 seconds while mounted.
  const refreshCount = useCallback(async () => {
    try {
      const res = await notificationsApi.unreadCount();
      setUnreadCount(res.unread_count);
    } catch {
      // Silently ignore (user may not be authenticated yet).
    }
  }, []);

  useEffect(() => {
    refreshCount();
    const id = setInterval(refreshCount, 30_000);
    return () => clearInterval(id);
  }, [refreshCount]);

  // Load full list when the panel opens.
  useEffect(() => {
    if (!open) return;
    setLoading(true);
    notificationsApi
      .list({ limit: 30 })
      .then((res) => {
        setItems(res.items);
        setUnreadCount(res.unread_count);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [open]);

  // Close on outside click.
  useEffect(() => {
    if (!open) return;
    function onDown(e: MouseEvent) {
      if (
        panelRef.current &&
        !panelRef.current.contains(e.target as Node) &&
        buttonRef.current &&
        !buttonRef.current.contains(e.target as Node)
      ) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [open]);

  async function handleMarkRead(id: string) {
    try {
      const updated = await notificationsApi.markRead(id);
      setItems((prev) => prev.map((n) => (n.id === id ? updated : n)));
      setUnreadCount((c) => Math.max(0, c - 1));
    } catch {}
  }

  async function handleMarkAllRead() {
    try {
      await notificationsApi.markAllRead();
      setItems((prev) => prev.map((n) => ({ ...n, is_read: true })));
      setUnreadCount(0);
    } catch {}
  }

  async function handleDelete(id: string) {
    const item = items.find((n) => n.id === id);
    try {
      await notificationsApi.delete(id);
      setItems((prev) => prev.filter((n) => n.id !== id));
      if (item && !item.is_read) setUnreadCount((c) => Math.max(0, c - 1));
    } catch {}
  }

  return (
    <div className="notif-wrapper">
      <button
        ref={buttonRef}
        className="ghost notif-bell"
        onClick={() => setOpen((v) => !v)}
        aria-label={`Notifications${unreadCount > 0 ? ` (${unreadCount} unread)` : ""}`}
      >
        <BellIcon hasUnread={unreadCount > 0} />
        {unreadCount > 0 && (
          <span className="notif-badge">{unreadCount > 99 ? "99+" : unreadCount}</span>
        )}
      </button>

      {open && (
        <div ref={panelRef} className="notif-panel" role="dialog" aria-label="Notifications">
          <div className="notif-header">
            <span className="notif-title">Notifications</span>
            {unreadCount > 0 && (
              <button className="notif-mark-all" onClick={handleMarkAllRead}>
                Mark all read
              </button>
            )}
          </div>

          <div className="notif-list">
            {loading && (
              <div className="notif-empty">Loading…</div>
            )}
            {!loading && items.length === 0 && (
              <div className="notif-empty">You&apos;re all caught up!</div>
            )}
            {!loading &&
              items.map((n) => (
                <div
                  key={n.id}
                  className={`notif-item${n.is_read ? "" : " notif-item--unread"}`}
                  onClick={() => {
                    if (!n.is_read) handleMarkRead(n.id);
                  }}
                >
                  <span className="notif-type-badge">{TYPE_LABELS[n.type]}</span>
                  <div className="notif-content">
                    <div className="notif-item-title">{n.title}</div>
                    {n.body && <div className="notif-item-body">{n.body}</div>}
                    <div className="notif-item-time">{relativeTime(n.created_at)}</div>
                  </div>
                  <button
                    className="notif-delete"
                    onClick={(e) => {
                      e.stopPropagation();
                      handleDelete(n.id);
                    }}
                    aria-label="Delete notification"
                  >
                    <TrashIcon />
                  </button>
                </div>
              ))}
          </div>
        </div>
      )}
    </div>
  );
}
