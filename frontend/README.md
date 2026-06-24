# TeamSync Frontend (Next.js)

Auth UI for TeamSync: login, signup, forgot/reset password, and a protected dashboard.

## Stack
Next.js 14 (App Router) · React 18 · TypeScript.

## Quick start
```bash
cd frontend
npm install
cp .env.local.example .env.local        # NEXT_PUBLIC_API_URL=http://localhost:8000
npm run dev                             # http://localhost:3000
```
Run the [backend](../backend/README.md) on :8000 first.

## Pages
| Route | Purpose |
|-------|---------|
| `/login` | Log in |
| `/signup` | Create account |
| `/forgot-password` | Request a reset link |
| `/reset-password?token=…` | Set a new password (link from the reset email) |
| `/dashboard` | **Protected** — requires a valid session |

## How auth works on the client
- **Access token** is held in memory (`lib/api.ts`) — not in `localStorage` — to limit
  XSS exposure. It's attached as `Authorization: Bearer …`.
- **Refresh token** is an httpOnly cookie the browser sends automatically
  (`credentials: "include"`). On page load, `AuthProvider` calls `/auth/refresh` to
  restore the session; API calls that hit a 401 transparently refresh once and retry.
- **Logout** calls the API to revoke the session and clears in-memory state.

## Protected routes
Protection is **client-side** (`components/protected-route.tsx`): the dashboard
redirects to `/login` unless authenticated. This is the correct pattern here because
the API is on a separate origin and the refresh cookie is httpOnly + origin-scoped, so
Next.js middleware can't read it. For middleware/edge-level gating, front the API with
a same-origin BFF (Next route handlers proxying to FastAPI) so the session cookie is
same-origin — a planned enhancement, not needed for the MVP.

## Build
```bash
npm run build      # type-checks and compiles all routes
```
<!-- cd verify Wed, Jun 24, 2026 10:45:25 PM -->
