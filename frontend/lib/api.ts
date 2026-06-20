// Thin API client for the TeamSync auth backend.
//
// Access token lives in memory only (not localStorage) to reduce XSS exposure.
// The refresh token is an httpOnly cookie the browser sends automatically with
// `credentials: "include"`. On a 401 we transparently try one refresh + retry.

const API_BASE =
  (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000") + "/api/v1";

export interface Notification {
  id: string;
  user_id: string;
  type: "mention" | "assignment" | "comment" | "system";
  title: string;
  body: string | null;
  resource_type: string | null;
  resource_id: string | null;
  is_read: boolean;
  read_at: string | null;
  created_at: string;
}

export interface NotificationListResponse {
  items: Notification[];
  total: number;
  unread_count: number;
}

export interface UnreadCountResponse {
  unread_count: number;
}

export type IssueStatus = "backlog" | "in_progress" | "review" | "done";
export type IssuePriority = "low" | "medium" | "high" | "urgent";

export interface Issue {
  id: string;
  user_id: string;
  title: string;
  description: string | null;
  status: IssueStatus;
  position: number;
  priority: IssuePriority;
  created_at: string;
  updated_at: string;
}

export interface BoardColumn {
  status: IssueStatus;
  title: string;
  items: Issue[];
}

export interface BoardResponse {
  columns: BoardColumn[];
}

// --- CSV import types ---

export type ImportSource = "jira" | "linear" | "trello";

export interface ImportRowPreview {
  row_number: number;
  title: string;
  description: string | null;
  status: IssueStatus;
  priority: IssuePriority;
  valid: boolean;
  errors: string[];
  warnings: string[];
}

export interface ImportPreviewResponse {
  source: ImportSource;
  detected: boolean;
  total_rows: number;
  valid_rows: number;
  invalid_rows: number;
  columns: string[];
  unmapped_columns: string[];
  rows: ImportRowPreview[];
}

export interface ImportCommitResponse {
  source: ImportSource;
  imported: number;
  skipped: number;
}

export interface User {
  id: string;
  email: string;
  full_name: string | null;
  is_active: boolean;
  is_verified: boolean;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: User;
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
    this.name = "ApiError";
  }
}

let accessToken: string | null = null;
export const setAccessToken = (t: string | null) => {
  accessToken = t;
};
export const getAccessToken = () => accessToken;

interface RequestOptions {
  method?: string;
  body?: unknown;
  withAuth?: boolean;
  retryOn401?: boolean;
}

async function rawRequest(
  path: string,
  { method = "GET", body, withAuth = true }: RequestOptions
): Promise<Response> {
  const headers = new Headers({ "Content-Type": "application/json" });
  if (withAuth && accessToken) {
    headers.set("Authorization", `Bearer ${accessToken}`);
  }
  return fetch(`${API_BASE}${path}`, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
    credentials: "include", // send/receive the refresh cookie
  });
}

async function parseResponse<T>(res: Response): Promise<T> {
  if (res.status === 204) return undefined as T;
  const text = await res.text();
  const data = text ? JSON.parse(text) : null;
  if (!res.ok) {
    const detail =
      (data && (data.detail || data.message)) || `Request failed (${res.status})`;
    throw new ApiError(
      res.status,
      typeof detail === "string" ? detail : JSON.stringify(detail)
    );
  }
  return data as T;
}

const NETWORK_ERROR_MESSAGE =
  "Network error — the API is unreachable. Is the backend running?";

/** Attempt to mint a new access token using the refresh cookie. */
export async function tryRefresh(): Promise<TokenResponse | null> {
  try {
    const res = await rawRequest("/auth/refresh", {
      method: "POST",
      withAuth: false,
    });
    if (!res.ok) {
      setAccessToken(null);
      return null;
    }
    const data = (await res.json()) as TokenResponse;
    setAccessToken(data.access_token);
    return data;
  } catch {
    // Network failure (e.g. backend down). Degrade to unauthenticated instead
    // of throwing an unhandled rejection that crashes the app on load.
    setAccessToken(null);
    return null;
  }
}

export async function apiRequest<T>(
  path: string,
  options: RequestOptions = {}
): Promise<T> {
  const { withAuth = true, retryOn401 = true } = options;
  let res: Response;
  try {
    res = await rawRequest(path, options);
    if (res.status === 401 && withAuth && retryOn401) {
      const refreshed = await tryRefresh();
      if (refreshed) {
        res = await rawRequest(path, options);
      }
    }
  } catch (err) {
    // Translate a raw fetch rejection into a clean, catchable ApiError.
    if (err instanceof ApiError) throw err;
    throw new ApiError(0, NETWORK_ERROR_MESSAGE);
  }
  return parseResponse<T>(res);
}

// --- Auth endpoints ---

export const authApi = {
  signup: (email: string, password: string, full_name: string) =>
    apiRequest<TokenResponse>("/auth/signup", {
      method: "POST",
      body: { email, password, full_name },
      withAuth: false,
      retryOn401: false,
    }),

  login: (email: string, password: string) =>
    apiRequest<TokenResponse>("/auth/login", {
      method: "POST",
      body: { email, password },
      withAuth: false,
      retryOn401: false,
    }),

  logout: () =>
    apiRequest<void>("/auth/logout", {
      method: "POST",
      withAuth: false,
      retryOn401: false,
    }),

  me: () => apiRequest<User>("/auth/me", { method: "GET" }),

  requestPasswordReset: (email: string) =>
    apiRequest<{ detail: string }>("/auth/password-reset/request", {
      method: "POST",
      body: { email },
      withAuth: false,
      retryOn401: false,
    }),

  confirmPasswordReset: (token: string, new_password: string) =>
    apiRequest<{ detail: string }>("/auth/password-reset/confirm", {
      method: "POST",
      body: { token, new_password },
      withAuth: false,
      retryOn401: false,
    }),
};

// --- Notification endpoints ---

export const notificationsApi = {
  list: (params?: { unread_only?: boolean; limit?: number; offset?: number }) => {
    const qs = new URLSearchParams();
    if (params?.unread_only) qs.set("unread_only", "true");
    if (params?.limit != null) qs.set("limit", String(params.limit));
    if (params?.offset != null) qs.set("offset", String(params.offset));
    const query = qs.toString() ? `?${qs}` : "";
    return apiRequest<NotificationListResponse>(`/notifications${query}`);
  },

  unreadCount: () =>
    apiRequest<UnreadCountResponse>("/notifications/unread-count"),

  markRead: (id: string) =>
    apiRequest<Notification>(`/notifications/${id}/read`, { method: "POST" }),

  markAllRead: () =>
    apiRequest<UnreadCountResponse>("/notifications/read-all", { method: "POST" }),

  delete: (id: string) =>
    apiRequest<void>(`/notifications/${id}`, { method: "DELETE" }),
};

// --- Sprint Board (issues) endpoints ---

export const issuesApi = {
  board: () => apiRequest<BoardResponse>("/issues/board"),

  create: (input: {
    title: string;
    status?: IssueStatus;
    priority?: IssuePriority;
    description?: string;
  }) => apiRequest<Issue>("/issues", { method: "POST", body: input }),

  update: (
    id: string,
    input: { title?: string; description?: string; priority?: IssuePriority }
  ) => apiRequest<Issue>(`/issues/${id}`, { method: "PATCH", body: input }),

  /** Persist a drag-and-drop drop: target column + index within that column. */
  move: (id: string, status: IssueStatus, position: number) =>
    apiRequest<Issue>(`/issues/${id}/move`, {
      method: "PATCH",
      body: { status, position },
    }),

  delete: (id: string) =>
    apiRequest<void>(`/issues/${id}`, { method: "DELETE" }),
};

// --- CSV bulk import endpoints ---

export const importsApi = {
  /** Dry-run: map + validate the CSV without writing anything. */
  preview: (csv_text: string, source?: ImportSource | null) =>
    apiRequest<ImportPreviewResponse>("/imports/preview", {
      method: "POST",
      body: { csv_text, source: source ?? null },
    }),

  /** Persist the valid rows as issues on the board. */
  commit: (csv_text: string, source?: ImportSource | null) =>
    apiRequest<ImportCommitResponse>("/imports/commit", {
      method: "POST",
      body: { csv_text, source: source ?? null },
    }),
};
