# Ledger React frontend

A separate React + Vite application for the existing WhatsApp expense tracker.
Source lives entirely in `frontend/`; existing FastAPI services and cookie-based
WhatsApp login remain the source of truth.

## Run locally

Use Node.js 22.12+ (Node 24 is used by the Docker build). From the copy project:

```powershell
cd frontend
npm ci
npm run dev
```

Open **http://127.0.0.1:5173/**. Keep your existing backend on port 8000.
The Vite server proxies `/api` to `http://127.0.0.1:8000`; the browser uses one
origin and HttpOnly cookies. No permissive CORS or auth bypass was added.

If the backend uses another port, create `frontend/.env.local` containing:

```dotenv
API_PROXY_TARGET=http://127.0.0.1:8001
```

Restart Vite after changing that file. This variable configures only the dev
proxy. Do not copy `backend/.env` into the frontend. Any `VITE_` variable is
public. Optional `VITE_WHATSAPP_NUMBER` is your public bot number, digits only;
it enables the record-on-WhatsApp link after sign-in. Login itself uses the bot
link returned by the backend, so this public convenience setting is optional.

For local development, leave backend `DASHBOARD_PUBLIC_URL` unset or set it to
exactly the frontend origin you use (for example `http://127.0.0.1:5173`). An
unrelated production URL will correctly fail the backend Origin check. Do not
mix `localhost` and `127.0.0.1` during one session. Twilio's callback still points
to the public backend `/webhook/whatsapp`, not the Vite development port.

## View the design without an account

On the sign-in screen, click **Explore a preview**. This is explicitly labeled
read-only illustrative data. It never grants a real session and cannot write,
delete, export, or import records. Leave preview to sign in to your real account.
The application does not silently substitute preview data after a backend error.

## What's connected

- WhatsApp login start, bounded polling, expiry, account lookup, and sign-out.
- Monthly SQL reports, previous-month comparison, savings, category spending,
  recent transactions, largest expenses, and custom date ranges.
- Transactions with server pagination, date/type/category/currency filters,
  correction dialogs, deletion, undo, and date-range CSV export.
- Current-month budgets with creation/updating, deletion, and progress.
- Recurring schedules with creation, pause/resume, and deletion.
- CSV/receipt upload, preview editing, explicit row selection, duplicate review,
  and confirmation before import.

Search is explicitly **within the current transaction page**, not a claim of
server-wide search. CSV export uses dates and currency because those are the
backend export endpoint's supported filters. It does not silently claim to apply
category/type/text filters. No exchange-rate conversions are invented.

Amounts sent to the backend stay strings; authoritative financial calculations
remain in Python/SQL. JavaScript numbers are used only for chart layout/display.
Mutation responses invalidate that account's cached queries. Account changes
cancel queries and clear cached data; financial responses carry an account marker.

## Production assets and Docker

```powershell
npm run build
```

This creates ignored `frontend/dist/`. At backend startup FastAPI serves this
folder if its `index.html` exists; otherwise it uses `frontend/legacy/` as a fallback.
Navigation uses URL fragments so there is no server-side history fallback needed.
Fonts are self-hosted build assets, compatible with the existing same-origin CSP.

The `backend/Dockerfile` now has a Node frontend-build stage. The Python runtime image
receives only the built assets, not Node or node_modules. Rebuild it yourself:

```powershell
# From the copy project's root, not frontend/
docker compose up -d --build backend
```

After startup open **http://127.0.0.1:8000/** (or your published host port).
No Docker command, image push, or public deployment was run during this redesign.

## Structure

```text
src/
  api/client.js          Fetch, error handling, CSRF header, account checks, CSV
  auth/                  Cookie-session state and WhatsApp sign-in
  components/            Buttons, dialogs, feedback, charts, tables
  hooks/useLedger.js     Account-scoped server queries and mutations
  pages/                 Overview, transactions, budgets, recurring, imports
  data/demo.js           Explicit read-only illustration data
  lib/format.js          Money/date display and category definitions
  App.jsx                Workspace shell and navigation
  styles.css             Navy/porcelain/brass tokens and responsive layouts
```

React, TanStack Query, Lucide icons, and self-hosted DM Sans/Cormorant Garamond
fonts are installed with an npm lockfile. No new backend dependency is needed.

## Validation boundary

The production build succeeded, and the local preview returned HTTP 200. Browser
visual review could not be completed because the browser controller could not
verify its current URL and stopped. No tests or real-user login, financial writes,
imports, WhatsApp messages, or Docker rebuilds were run during this change.


### Dashboard query caching update

- React Query keeps financial query results fresh for 5 minutes and retains inactive results for 30 minutes in memory.
- Returning to the same account and filters within 5 minutes reuses the result without another query. Stale cached results remain visible while refreshed on mount, window focus, or network reconnection.
- Existing successful edits, deletes, budget changes, recurring changes and confirmed imports invalidate account queries. Active views refresh; inactive views refresh when reopened.
- Added an accessible Refresh dashboard data button to invalidate the current account cache on demand, useful after WhatsApp entries.
- Cache keys remain account- and filter-specific. Sign-out/account changes clear the cache. No financial records are persisted in localStorage. A browser reload fetches again.
- External WhatsApp/database changes are not pushed instantly. The next stale revalidation or manual Refresh retrieves them; no background interval polling or server revision endpoint was added.
- No tests, Docker commands, or database mutations were run for this change.


## Backend directory

FastAPI source, scripts, requirements and private configuration now live in `../backend/`. Start Python from that directory; see [the project guide](../README.md). The Vite proxy and API URLs are unchanged.


## TanStack Query and dashboard caching

Read [TanStack Query explained](../docs/TANSTACK_QUERY_EXPLAINED.md) for the notebook analogy, current implementation, technical details and interview preparation.
