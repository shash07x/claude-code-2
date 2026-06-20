"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  issuesApi,
  type BoardColumn,
  type Issue,
  type IssuePriority,
  type IssueStatus,
} from "@/lib/api";

const PRIORITY_LABEL: Record<IssuePriority, string> = {
  low: "Low",
  medium: "Medium",
  high: "High",
  urgent: "Urgent",
};

// --- Pure helper: produce the board state after moving `id` into a column ----

function applyLocalMove(
  columns: BoardColumn[],
  id: string,
  targetStatus: IssueStatus,
  index: number
): BoardColumn[] {
  let moved: Issue | undefined;
  const without = columns.map((col) => ({
    ...col,
    items: col.items.filter((it) => {
      if (it.id === id) {
        moved = it;
        return false;
      }
      return true;
    }),
  }));
  if (!moved) return columns;
  const movedIssue = moved;

  return without.map((col) => {
    if (col.status !== targetStatus) return col;
    const items = [...col.items];
    const clamped = Math.max(0, Math.min(index, items.length));
    items.splice(clamped, 0, { ...movedIssue, status: targetStatus });
    return { ...col, items };
  });
}

// --- Component ---------------------------------------------------------------

export function SprintBoard() {
  const [columns, setColumns] = useState<BoardColumn[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [draggingId, setDraggingId] = useState<string | null>(null);
  const [dragOverStatus, setDragOverStatus] = useState<IssueStatus | null>(null);
  const [drafts, setDrafts] = useState<Record<string, string>>({});

  const listRefs = useRef<Record<string, HTMLDivElement | null>>({});

  const loadBoard = useCallback(async () => {
    try {
      const res = await issuesApi.board();
      setColumns(res.columns);
      setError(null);
    } catch {
      setError("Failed to load the board.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadBoard();
  }, [loadBoard]);

  // Compute the insertion index within a column from the pointer Y position,
  // ignoring the card currently being dragged.
  function computeDropIndex(
    statusKey: IssueStatus,
    clientY: number,
    dragId: string
  ): number {
    const listEl = listRefs.current[statusKey];
    if (!listEl) return 0;
    const cards = Array.from(
      listEl.querySelectorAll<HTMLElement>("[data-card-id]")
    ).filter((c) => c.dataset.cardId !== dragId);
    for (let i = 0; i < cards.length; i++) {
      const rect = cards[i].getBoundingClientRect();
      if (clientY < rect.top + rect.height / 2) return i;
    }
    return cards.length;
  }

  function onDragStart(e: React.DragEvent, issue: Issue) {
    setDraggingId(issue.id);
    e.dataTransfer.effectAllowed = "move";
    e.dataTransfer.setData("text/plain", issue.id); // required by Firefox
  }

  function onDragEnd() {
    setDraggingId(null);
    setDragOverStatus(null);
  }

  function onColumnDragOver(e: React.DragEvent, statusKey: IssueStatus) {
    if (!draggingId) return;
    e.preventDefault(); // allow drop
    e.dataTransfer.dropEffect = "move";
    if (dragOverStatus !== statusKey) setDragOverStatus(statusKey);
  }

  async function onColumnDrop(e: React.DragEvent, statusKey: IssueStatus) {
    e.preventDefault();
    const id = draggingId;
    setDraggingId(null);
    setDragOverStatus(null);
    if (!id) return;

    const index = computeDropIndex(statusKey, e.clientY, id);
    const previous = columns;
    const optimistic = applyLocalMove(columns, id, statusKey, index);
    setColumns(optimistic);

    try {
      // Persist the drop. `index` is the position within the target column
      // excluding the dragged card — exactly what the API expects.
      await issuesApi.move(id, statusKey, index);
    } catch {
      setColumns(previous); // roll back, then resync from the server
      setError("Couldn't save that move. Reloading…");
      loadBoard();
    }
  }

  async function onAddCard(statusKey: IssueStatus) {
    const title = (drafts[statusKey] ?? "").trim();
    if (!title) return;
    setDrafts((d) => ({ ...d, [statusKey]: "" }));
    try {
      const created = await issuesApi.create({ title, status: statusKey });
      setColumns((cols) =>
        cols.map((c) =>
          c.status === statusKey ? { ...c, items: [...c.items, created] } : c
        )
      );
    } catch {
      setError("Couldn't add that card.");
    }
  }

  async function onDeleteCard(id: string) {
    const previous = columns;
    setColumns((cols) =>
      cols.map((c) => ({ ...c, items: c.items.filter((it) => it.id !== id) }))
    );
    try {
      await issuesApi.delete(id);
    } catch {
      setColumns(previous);
      setError("Couldn't delete that card.");
    }
  }

  if (loading) {
    return <div className="board-status">Loading board…</div>;
  }

  return (
    <div>
      {error && <div className="alert error board-alert">{error}</div>}
      <div className="board-columns">
        {columns.map((col) => (
          <div
            key={col.status}
            className={`board-column${
              dragOverStatus === col.status ? " board-column--over" : ""
            }`}
            onDragOver={(e) => onColumnDragOver(e, col.status)}
            onDrop={(e) => onColumnDrop(e, col.status)}
            onDragLeave={() => {
              if (dragOverStatus === col.status) setDragOverStatus(null);
            }}
          >
            <div className="board-column-header">
              <span className="board-column-title">{col.title}</span>
              <span className="board-column-count">{col.items.length}</span>
            </div>

            <div
              className="board-list"
              ref={(el) => {
                listRefs.current[col.status] = el;
              }}
            >
              {col.items.map((issue) => (
                <div
                  key={issue.id}
                  data-card-id={issue.id}
                  className={`issue-card${
                    draggingId === issue.id ? " issue-card--dragging" : ""
                  }`}
                  draggable
                  onDragStart={(e) => onDragStart(e, issue)}
                  onDragEnd={onDragEnd}
                >
                  <div className="issue-card-top">
                    <span className="issue-card-title">{issue.title}</span>
                    <button
                      className="issue-card-delete"
                      onClick={() => onDeleteCard(issue.id)}
                      aria-label="Delete card"
                      title="Delete"
                    >
                      ×
                    </button>
                  </div>
                  {issue.description && (
                    <div className="issue-card-desc">{issue.description}</div>
                  )}
                  <div className="issue-card-footer">
                    <span
                      className={`prio prio--${issue.priority}`}
                      title={`Priority: ${PRIORITY_LABEL[issue.priority]}`}
                    >
                      {PRIORITY_LABEL[issue.priority]}
                    </span>
                  </div>
                </div>
              ))}

              {col.items.length === 0 && (
                <div className="board-empty">Drop cards here</div>
              )}
            </div>

            <form
              className="board-add"
              onSubmit={(e) => {
                e.preventDefault();
                onAddCard(col.status);
              }}
            >
              <input
                placeholder="+ Add a card"
                value={drafts[col.status] ?? ""}
                onChange={(e) =>
                  setDrafts((d) => ({ ...d, [col.status]: e.target.value }))
                }
              />
            </form>
          </div>
        ))}
      </div>
    </div>
  );
}
