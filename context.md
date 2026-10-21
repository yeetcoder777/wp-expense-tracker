# Expense Tracker — Codex Handoff Context

Last updated: **19 October 2026**, Asia/Calcutta.

**Latest status:** The active copy now has separate frontend/ and backend/
directories. The React dashboard uses a reversed dark navy/light porcelain theme,
larger typography, an approximately 18% wider sidebar and account-scoped TanStack
Query caching with manual Refresh. Backend code, settings, scripts and Dockerfile
reside in backend/. Read section 0 for the authoritative current state, then the
preserved history for implementation and debugging details. The separate
[TanStack guide](docs/TANSTACK_QUERY_EXPLAINED.md) explains caching and interview
preparation.

This document gives another ChatGPT conversation or developer the context needed
to continue this project. It records the requested features, implemented code,
debugging history, tests, configuration changes, limitations, and next steps.
Descriptions below reflect the current source, rather than every intermediate
version of a file. No passwords, access tokens, API keys, or database credentials
are included.

## 0. Authoritative current snapshot

This section supersedes historical paths, UI/auth descriptions and setup commands.
All earlier sections are preserved for full development history. Historical
verification does not mean the latest source was retested.

### 0.1 Correct workspace and user preferences

- Active project: `D:\Siddhesh\Projects\expense-tracker - Copy`.
- Original: `D:\Siddhesh\Projects\expense-tracker`. Do not edit it for this work.
- Original-folder restoration described later is historical evidence. Its present Git state was not rechecked during this documentation update.
- User wants clean modular code, concrete setup instructions and simple technical explanations suitable for interviews.
- User asked to learn/run Docker themselves. No image builds, pushes or deployments should be performed without subsequent authorization.
- Preserve secret configuration; never include credentials in documentation or Vite variables.
- Do not add/run tests unless asked. Distinguish source inspection, mocked tests, live provider checks and production verification.

### 0.2 Current structure and path translations

```text
expense-tracker - Copy/
  frontend/
    src/
      api/client.js
      auth/AuthContext.jsx, SignIn.jsx
      components/Charts.jsx, TransactionsTable.jsx, UI.jsx
      hooks/useLedger.js
      pages/Overview.jsx, Transactions.jsx, Budgets.jsx, Recurring.jsx, Imports.jsx
      data/demo.js
      lib/format.js
      App.jsx, main.jsx, styles.css
    public/ledger.svg
    legacy/                 Original HTML/CSS/JS fallback
    package.json, package-lock.json, vite.config.js, README.md
    .env.example
    dist/                   Generated React build, ignored
    node_modules/           Installed dependencies, ignored
  backend/
    app/                    APIs, services, DB, schemas, settings
    scripts/                Checks, migrations, regression scripts
    .env                    Private configuration, moved without changing values
    .env.example
    requirements.txt        Merged backend and GLiNER2 dependencies
    requirements.sweepr.txt  Existing alternative requirements file
    create_tables.py, test_intent.py
    Dockerfile, README.md
    logs/                   Ignored GLiNER stdout/stderr
  docs/                     Shared explanations and setup guides
  compose.yaml              Root build context, backend/Dockerfile, backend/.env
  README.md, context.md
  .gitignore, .dockerignore
  high level architecture diagram.png
  venv/                     Existing local Python environment retained in place
```

Old paths in history translate as follows:

| Historical path | Current path |
| --- | --- |
| app/... | backend/app/... |
| scripts/... | backend/scripts/... |
| .env and .env.example at root | backend/.env and backend/.env.example |
| requirements*.txt at root | backend/requirements*.txt |
| Dockerfile at root | backend/Dockerfile |
| app/static/... | frontend/legacy/... |

Shared docs/, frontend/ and root compose.yaml remain at their existing level.
The Python module is still app.main:app, launched from backend/. Root venv was
kept because moving an existing virtual environment can break absolute paths.

### 0.3 Architecture and provider boundaries

```text
WhatsApp -> Twilio -> POST /webhook/whatsapp
                      -> signature / commands / login proof / idempotency
                      -> Jev or Groq intent classification
                      -> GLiNER2 or Groq extraction when needed
                      -> Pydantic -> services -> SQLAlchemy/database
                      -> TwiML reply / configured outbound WhatsApp messages

React -> TanStack Query -> same-origin /api/* -> cookie authentication
                                              -> same scoped services/database

Receipt image -> Groq vision -> validation -> editable preview -> confirmation
FastAPI lifespan -> local model warmup + recurring asyncio worker
```

- Modular monolith, not a set of microservices. Source separation does not create separate databases or auth systems.
- User's current local Python setup is 3.12.10 with merged requirements. Python 3.15 and separate .venv-gliner/requirements.local.txt entries below describe earlier stages.
- Jev is remote intent classification, not general transaction extraction. The user demonstrated a successful strict Jev check.
- Local CPU model uses official gliner2.AutoExtractor, fastino/gliner2-base-v1 and a pinned revision. It was not implemented as transformers.pipeline.
- Compose explicitly sets EXTRACTION_PROVIDER=gliner2, allows model downloads and disables Groq extraction fallback. Pydantic defaults are Groq unless overridden. Do not confuse source defaults, .env values and container overrides.
- GLiNER2 does not read receipt images. Groq still serves explicitly configured vision and other Groq-specific paths.
- SQLAlchemy maps unqualified PostgreSQL URLs to psycopg2. Database credentials are private. Decimal/NUMERIC remain authoritative for financial calculations; currencies are kept separate.

### 0.4 Current implemented features and limits

| Feature | Current behavior | Limit |
| --- | --- | --- |
| WhatsApp transactions | Income/expenses, multiple entries, summaries, SQL totals/lists | Interpretation depends on selected provider and extractor constraints |
| Corrections | Edit/delete by ID or last, undo last, cancel pending input | Undo deletes latest entry, not an edit/recovery history |
| Budgets | Monthly overall/category/currency budgets, 80%/100% thresholds | Outbound delivery requires Twilio and is not guaranteed by recording alerts |
| Reports | Month/custom range, previous month, savings rate, largest expenses | No currency conversion |
| React UI | Overview, Transactions, Budgets, Recurring, Imports | Latest browser/auth end-to-end verification incomplete |
| Transaction review | 25-row pagination, filters, edit/delete/undo | Search is current-page only; CSV export supports dates/currency |
| Recurring | Weekly/monthly/yearly, reminders or auto-record, pause/resume/delete | In-process worker stops with app; no durable queue |
| Bank CSV | UTF-8 aliases, 10 MB / 2,000 rows, editable preview, duplicate flags and confirm | Not universal bank/PDF/Excel parsing |
| Receipt images | JPEG/PNG/WebP, 10 MB, vision extraction capped at 50 entries, review | Requires actual supported Groq vision model; live import not verified |
| Private accounts | WhatsApp proof, browser challenge, polling, HttpOnly session | Requires verified incoming webhook and matching unexpired challenge |
| Explicit preview | Labeled illustrative read-only account | No protected writes/imports/exports or auth bypass |
| Query caching | Freshness/retention, shared queries, invalidation, Refresh | Memory-only, no instant WhatsApp push |

Receipt configuration: during the earlier inspection GROQ_VISION_MODEL was
missing/empty. The user later selected placeholder text
`<a Groq model supporting image input>` in the editor. That is not a valid model
ID. This documentation update did not inspect secret values or verify a live
vision provider. Receipt operation remains conditional on correct configuration.

### 0.5 React redesign, colors, typography and sidebar

- React/Vite application lives in frontend/. Uses TanStack Query v5, Lucide icons, self-hosted DM Sans and Cormorant Garamond. package.json holds ranges; package-lock.json holds resolved packages.
- Original minimal porcelain/navy/brass design was reversed at the user's request. Current canvas/cards are dark navy, text is light; net-position and sign-in story panels are light with navy text.
- Main current tokens: canvas #101922, surface #18232d, text #e1e8ee, brass #cbb580, income #91c9ad, error #edaaa4.
- Explicit font sizes increased approximately 16%; explicit labels have a 12px floor and inputs a 16px base. Responsive overrides remain and can set individual mobile sizes differently.
- Updated controls, dialogs, hover states, chart track/series, wrapping and mobile table overflow for the new colors/type sizes. Retained visible focus and reduced-motion handling.
- Sidebar widened approximately 18%: normal/mobile drawer 228px -> 269px; intermediate breakpoint 210px -> 248px. Desktop content offsets match; mobile main content stays at zero offset.
- Hash navigation, responsive drawer and controlled sign-in phone input remain. Preview is explicit, never silently substituted after backend errors.
- Overview uses actual monthly aggregates and previous-month bars, not invented daily balances. Imports require review/selection before saving.

### 0.6 TanStack Query follow-up update

Full explanation: [TanStack Query explained](docs/TANSTACK_QUERY_EXPLAINED.md).

- One QueryClient at module scope in frontend/src/main.jsx, shared through QueryClientProvider.
- staleTime=5 minutes; gcTime=30 minutes after inactivity. Window-focus and reconnect refetch enabled.
- useLedgerQuery keys data by [account_id, resource, params], gates automatic requests using user/enabled, passes AbortSignal to the API helper and disables ledger automatic retries.
- Fresh same-key requests reuse data. Stale cached data can remain visible while refreshed on mount, focus or reconnect. Crossing staleTime alone does not start a request.
- Successful useLedgerMutation changes invalidate the account prefix. Import confirmation separately does equivalent invalidation. Active matches refresh; inactive matches become stale. No optimistic cache writes/rollback flow.
- Header Refresh invalidates account data. useIsFetching tracks matching requests and disables Refresh while busy.
- Account accept/logout/session expiration cancels queries and clears cache. Cache is memory-only, not persisted in localStorage, and not shared between browser tabs.
- HTTP no-store remains in API fetches/backend responses; application-memory caching is separate from HTTP caching.
- WhatsApp updates appear on Refresh or eligible revalidation. No polling interval, server revision endpoint, SSE, WebSocket or cross-tab query synchronization was added.
- Before this update, ledger staleTime was 30 seconds and default inactive retention applied. Those values are historical.
- No measured latency/request reduction percentage is available. This avoids requests; it does not speed up individual SQL or model operations.

### 0.7 Current auth and privacy versus historical shared tokens

- Current default uses WhatsApp authentication and HttpOnly SameSite=Strict cookies, with production Secure handling. Early bearer token/sessionStorage descriptions are historical legacy behavior.
- Legacy mode is explicit development compatibility. Backend authentication/ownership checks enforce isolation; cache keys only help prevent UI mix-ups.
- Additive auth models: DashboardUser, DashboardLoginChallenge and DashboardSession. Financial user IDs remain WhatsApp sender identities.
- New auth tables get PostgreSQL RLS and revoked browser-role grants. Existing financial grants were not automatically rewritten.
- Automatic approval review rejected an earlier broad existing-table grant rewrite; it never executed. Current production startup does a conservative read-only existing-table privacy check that can require operator review.
- API helper sends X-Ledger-Request, checks X-Ledger-Account and handles structured errors/25-second timeout. Backend CSP and API no-store remain.
- Repeated login/complete HTTP 202 indicates pending approval. Check ngrok/Twilio delivery, signatures, number/browser match and challenge expiry.
- Legacy phone input bug was a programmatic form-reset/filter/401 loop; its fix remains in frontend/legacy. React uses controlled state for the phone field.

### 0.8 Current startup, environment and Docker

Backend terminal, starting at the copy root:

```powershell
.\venv\Scripts\Activate.ps1
cd backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Frontend terminal, starting at the root:

```powershell
cd frontend
npm ci
npm run dev
```

- Vite: http://127.0.0.1:5173/; health: http://127.0.0.1:8000/health; API docs: /docs.
- Backend settings resolve backend/.env relative to config.py, independent of current working directory. Do not create another secret-bearing root/frontend .env copy.
- Optional frontend/.env.local can set API_PROXY_TARGET for another backend port and public VITE_WHATSAPP_NUMBER for the convenience link. VITE_ variables are public.
- Vite forwards /api to :8000. DASHBOARD_PUBLIC_URL must match the browser origin or be unset for inferred dev origin. Keep localhost/127.0.0.1 consistent.
- Run ngrok http 8000. Twilio must POST to the current public HTTPS URL plus /webhook/whatsapp. Setting .env does not update Twilio Console.
- Python helpers now run from backend/: python scripts/check_whatsapp_connection.py; python scripts/check_intent_classifier.py; python scripts/check_local_extractor.py; python scripts/smoke_test_backend.py. These are instructions, not new execution claims.

Docker commands from the root, for the user to run:

```powershell
docker compose up -d --build backend
docker compose logs -f backend
```

Compose uses root build context, backend/Dockerfile and backend/.env. Retains
127.0.0.1:8000 publication and named gliner-model-cache volume. Dockerfile uses a
Node build stage and Python workdir /app/backend, with built React assets at
/app/frontend/dist and fallback at /app/frontend/legacy. Final runtime does not
include Node/node_modules. Nested secrets/artifacts are excluded from build context.

Direct image command: docker build -f backend/Dockerfile -t expense-tracker:local .
A rebuild/restart is needed for changed source; existing containers are unchanged.
FastAPI selects React dist if present at startup. Existing dist may predate latest
cache/theme changes until rebuilt. Restart old local Python processes at new paths.

### 0.9 Verification ledger: do not overstate completion

| Work | Recorded evidence | Not established by that evidence |
| --- | --- | --- |
| Initial feature expansion | Historical isolated SQLite/mocked checks | Current live database/Twilio behavior |
| Jev | Historical 40-test combined suite, user strict Jev output | Guaranteed current provider availability/latency |
| GLiNER2 | Historical 19 extractor checks, 40 smoke checks, selected live inference/webhook checks | All languages/inputs or new auth/React coverage |
| Multi-user auth | Source implemented; older smoke configuration kept legacy-compatible | New real-user login fully verified |
| Initial React | npm installation/build passed; preview root HTTP 200 | Screenshot review or working real-user session |
| Cache/theme/sidebar updates | Source edits/review | Fresh production build, browser regression or benchmark |
| Directory split | Python AST syntax and git whitespace inspection | Live app import/startup, image rebuild or migration |
| This documentation update | Cross-checked current source/history | Any new test/provider/deployment result |

Browser visual review was blocked by unavailable automation/URL verification.
No screenshots were verified. Temporary preview helpers were stopped. Recent
review did not perform real imports or prove CSV/receipt end-to-end behavior.

The user separately built/ran Docker earlier and attempted Hub pushes, reporting
upload timeouts/retries with existing layers. Do not claim Codex published an
image or that the latest source was pushed. Older free-hosting research is dated,
not a verified current deployment plan. No public deployment is established.

### 0.10 Guide map and next work

- README.md: current folders, startup and Docker instructions.
- backend/README.md: detailed backend configuration/features/scripts, relative to backend/.
- frontend/README.md: proxy/auth-origin setup, UI scope, build and cache notes.
- docs/PROJECT_EXPLAINED.md: project architecture/interview reference.
- docs/LOCAL_GLINER2.md: local model integration and earlier evidence.
- docs/MULTI_USER_DASHBOARDS.md: login, privacy boundary and deployment considerations.
- docs/TANSTACK_QUERY_EXPLAINED.md: notebook analogy, exact hooks/settings, trade-offs and interview Q&A.
- Sections 1-24 below retain full prior feature/debugging history, followed by later changes under section 24.

Outstanding before claiming public readiness: verify real-user login and account
ownership; review existing Supabase exposure; configure a real vision model if
needed; rebuild assets/container; verify webhook/import/recurring flows with
appropriate authorization. These are remaining verification/setup items, not
work completed during this documentation refresh.

## 1. Read this first: the correct working folder

**The active project is:**

```text
D:\Siddhesh\Projects\expense-tracker - Copy
```

The separate original folder is:

```text
D:\Siddhesh\Projects\expense-tracker
```

Codex initially implemented changes in the original folder because that was the
workspace provided to the session. The user later clarified that their terminal
and development work were in `expense-tracker - Copy`.

At the user's request, Codex:

1. Restored its changes to tracked source files in the original folder.
2. Removed the feature files, scripts, dashboard, README, and documentation it
   had added in that original folder.
3. Preserved the user's pre-existing category-intent additions in
   `app/services/llm_service.py` and their untracked `requirements.sweepr.txt`.
4. Applied the features and fixes to the copy folder, preserving the copy's
   existing dependency changes and its original small smoke-check script.
5. Verified the updated copy with its own `venv`.

The original folder was checked again while preparing this handoff. Its Git
status showed only the pre-existing `llm_service.py` change and untracked
`requirements.sweepr.txt`. The remaining LLM diff adds `category_query` and
`category_list_query` to the existing intent prompt.

Do future edits in the **copy folder**. An editor tab with an absolute path into
the original folder can be stale; that happened repeatedly during this session.
The correct backend import path is `app.main:app`; the copy has no
`backend/api.py` module.

## 2. What the user asked for

The existing application was a WhatsApp expense tracker. The user requested all
six feature groups below, implemented with clean, modular code:

1. Correct, delete, and undo transactions, plus cancel incomplete conversations.
2. Monthly overall/category budgets and spending threshold alerts.
3. Custom-range reports, previous-month comparisons, savings rate, largest
   expenses, and CSV export.
4. A browser dashboard and general transaction APIs.
5. Recurring payments and reminders.
6. Receipt-image and bank-statement CSV imports with duplicate detection.

They subsequently requested debugging help, complete message-flow tests, an
interview explanation, an assessment of Jev for classification, and this handoff.

## 3. Current architecture and stack

> **Historical scope:** Original overview before Jev/local extraction and React. Section 0 describes current architecture.

The application is a **modular monolith**, with a WhatsApp interface and a static
browser dashboard sharing backend services.

```text
WhatsApp -> Twilio -> POST /webhook/whatsapp -> validation/commands/services
                                              |
                                              +-> Groq when interpretation is needed
                                              +-> SQLAlchemy -> relational database
                                              +-> TwiML XML reply -> Twilio

Browser dashboard -> authenticated /api/... -> the same database/services

FastAPI lifespan -> recurring asyncio task -> checks schedules every minute
```

| Technology | Current use |
| --- | --- |
| Python | Backend implementation |
| FastAPI and Uvicorn | HTTP routes, dependency injection, application server |
| Pydantic | Request/extraction schemas and validation |
| pydantic-settings, python-dotenv | Configuration from environment and `.env` |
| SQLAlchemy | ORM models, queries, sessions, transactions |
| PostgreSQL | Supported application database |
| SQLite | Isolated regression-test database |
| psycopg2-binary | Explicit default PostgreSQL driver used by database setup |
| Twilio SDK | WhatsApp webhook responses, signatures, outbound notifications |
| Groq SDK | Optional/fallback intent classification, field extraction, optional receipt vision |
| TypeSafe SDK | Jev Choice-based intent classification, confidence gating |
| python-multipart | Form and upload handling |
| HTML/CSS/plain JavaScript | Responsive dashboard and spending bars |
| Fetch API | Browser-to-backend requests |
| asyncio | In-process recurring worker |
| unittest, unittest.mock, FastAPI TestClient | Automated regression tests |
| ngrok | Public tunnel for local WhatsApp development |

The copy already had `sqlalchemy` and `psycopg[binary]` in requirements before
migration. Those were preserved; `psycopg2-binary` was added to match the explicit
driver. Both driver packages are currently declared. No npm frontend framework
or package installation was introduced by these changes.

## 4. Feature-by-feature implementation

### 4.1 Transaction corrections, deletion, undo, and cancel

Implemented in `transaction_command_service.py`, `transaction_service.py`, the
webhook, and the transaction dashboard/API.

Examples:

```text
Show my recent transactions
edit 12 amount to 300
edit 12 date to 2026-10-17
edit 12 category to food
edit 12 purpose to lunch
edit last amount to 300
delete 12
delete last
undo last
cancel
```

- Explicit commands are parsed with regular expressions before AI classification.
- Targets accept an ID, `#ID`, or `last` where supported.
- Amounts must be positive, fit the database precision, and have at most two decimals.
- Dates use ISO `YYYY-MM-DD`; text fields have database-compatible length limits.
- Record lookups are scoped to the requesting user.
- Deletion also handles import references and clears recurring execution references.
- `undo`, `undo last`, and `undo last transaction` delete the latest recorded entry.
- Undo is **not** an edit history or a way to restore a deleted record.
- Cancel aliases include `cancel transaction`, `discard`, `stop`, and `never mind`.

### 4.2 Incomplete conversations

`ConversationState` stores a serialized partial transaction and the field being
requested. Currently, missing-purpose detection drives follow-up questions.

```text
User: Spent ₹100
Bot: What was the purpose?
User: Tea
```

- State is persisted in the database, rather than only process memory.
- Pending state expires after 24 hours.
- Commands are processed before treating the message as a pending answer.
  Therefore `cancel` no longer becomes a saved transaction purpose.
- Follow-up values are revalidated through `Transaction` before saving.

### 4.3 Multiple transactions in one WhatsApp message

This was added while fixing a real extraction error:

```text
I spent ₹250 on coffee
Received ₹65000 salary
```

- `extract_transactions()` returns a list of validated `Transaction` objects.
- It accepts a single transaction object, a top-level list, or an object with a
  `transactions` array, and flattens nested list shapes.
- A missing transaction date defaults to today's date in the application's
  date service, which uses Asia/Kolkata.
- Complete batches are saved together, with one processed-webhook marker.
- Incomplete batches prompt the user to send transactions separately and do
  not silently save just one item.
- The original singular `extract_transaction()` remains as a compatibility wrapper
  and requires exactly one extracted transaction.

### 4.4 Budgets and threshold alerts

Examples:

```text
Set my food budget to ₹1000
Set my overall budget to ₹20000
show my budgets
How much is left in my food budget?
```

- Monthly budgets are scoped to user, category, and currency.
- Overall budgets use the internal category `all`.
- SQL aggregation counts expenses in the current month and matching currency.
- Alerts trigger at 80% and 100% when expenses are recorded/evaluated.
- Alert records track `(budget_id, period_start, threshold)` to prevent repeated
  recording of the same monthly threshold.
- Updating a budget resets its recorded alert thresholds.
- WhatsApp entry alerts are included in the reply; dashboard/import/recurring
  paths can use the outbound notification service.
- Outbound delivery requires the Twilio account settings; saving an alert record
  does not guarantee external delivery succeeded.

### 4.5 Reports, summaries, and CSV export

- Current-month and selected-month reports with previous calendar-month comparison.
- Custom inclusive date ranges.
- Income, expenses, net balance, savings rate, category totals, and five largest expenses.
- SQL `SUM`, grouping, date filtering, sorting, and limits provide report results.
- Money uses backend `Decimal` and SQL `NUMERIC(12, 2)`.
- Currencies are kept separate; there is no currency conversion.
- Savings rate is currently zero if income is zero.
- Expense change percentage is absent if previous spending is zero.
- CSV export supports date/currency filters and protects exported text from common
  spreadsheet formula prefixes.
- Existing WhatsApp totals, income queries, category queries, lists, and monthly
  summaries are supported through the query service.

### 4.6 Web dashboard

> **Historical scope:** Initial plain-JavaScript/shared-token dashboard. React and WhatsApp cookie sessions supersede this UI. Legacy files now live in frontend/legacy/.

- Served by FastAPI at `/` from `app/static/`.
- Responsive HTML/CSS and plain JavaScript; category bars are HTML/CSS.
- Report period and currency selection, category spending, largest expenses,
  transaction filters, record corrections, deletion, undo, and CSV export.
- Budget controls, recurring schedule controls, and import review UI.
- JavaScript sends bearer-authenticated `fetch()` requests to JSON endpoints.
- Token stored in browser `sessionStorage`.
- Server uses `hmac.compare_digest` to compare the configured bearer token.
- The dashboard is bound to one configured `DASHBOARD_USER_ID`; clients do not
  choose an arbitrary owner through API parameters.
- Missing dashboard configuration produces 503; missing/incorrect token produces 401.

### 4.7 Recurring payments and reminders

- Weekly, monthly, and yearly intervals.
- Configurable due date, reminder lead time, and automatic recording versus reminders.
- Schedule API supports listing, creation, pause/resume, and deletion.
- FastAPI lifespan starts/cancels an asyncio worker.
- Worker checks schedules every 60 seconds and uses `asyncio.to_thread` for its
  synchronous processing pass.
- Anchored day/month handling supports short months and leap dates.
- PostgreSQL `FOR UPDATE SKIP LOCKED` helps separate workers claim schedules.
- Unique execution record per schedule/date adds duplicate protection.
- SQLite should use one app worker; its locking behavior differs from PostgreSQL.
- The worker records an eligible due occurrence and advances to a future date;
  it does not reconstruct every missed historical occurrence.
- The worker stops when the application stops. There is no durable external queue.
- Notifications use Twilio's outbound messages API; ordinary webhook replies use TwiML.

### 4.8 Bank statement CSV imports

- UTF-8/UTF-8-BOM CSV parsing with common header aliases.
- Supports date, description, amount/type, or separate debit/credit columns,
  optional currency, category, and counterparty.
- Supports ISO and common date formats and normalized decimal amounts.
- Amount-only rows default to expenses; income needs a recognized type/credit field.
- Maximum 2,000 rows per file; import request schema limits confirmed transactions.
- Preview includes valid entries, row errors, and possible-duplicate flags.
- Confirmation persists reviewed entries. Imports are committed per accepted row,
  rather than guaranteeing whole-file atomicity.
- SHA-256 fingerprints use normalized type, amount, currency, date, category,
  description, and counterparty.
- Duplicate checks consider existing import fingerprints, existing transactions,
  and repeated entries within the same preview.
- Possible duplicates are unchecked by default in the UI, and skipping can be
  disabled explicitly. Occurrence numbers allow intentional repeated imports.
- This is field-based matching, not fuzzy bank-transaction reconciliation.

Basic format:

```csv
date,description,amount,type,currency,category
2026-10-17,Coffee,250,debit,INR,food
2026-10-17,Salary,65000,credit,INR,salary
```

### 4.9 Receipt image imports

- Dashboard accepts JPEG, PNG, and WebP; upload size limit is 10 MB.
- Image bytes are encoded and sent to the configured Groq vision model.
- Extracted entries are validated and shown in a required review step before saving.
- The receipt path caps extracted items at 50.
- Vision model must be configured separately through `GROQ_VISION_MODEL`.
- There is no standalone Tesseract integration or PDF statement parser.
- WhatsApp image messages receive dashboard import guidance; direct WhatsApp
  image processing was not implemented.

## 5. Webhook processing and security changes

The current webhook sequence is:

1. Validate form/signature as applicable.
2. Check the inbound `MessageSid` against processed messages.
3. Handle media guidance.
4. Handle explicit transaction/budget commands.
5. Resolve a pending conversation if one exists.
6. Classify intent through the configured Jev/Groq classifier.
7. Route report/list queries to deterministic Python/SQL.
8. Extract and validate new transaction fields if needed.
9. Save complete entries, evaluate budgets, and return TwiML XML.

Important implementation changes:

- Transaction batches and their message marker commit in the same database transaction.
- Database uniqueness backs up duplicate detection when requests race.
- Explicit edit/delete/budget commands also use processed-message protection, but
  their marker is committed before the operation; see limitations below.
- Twilio's `X-Twilio-Signature` is checked with `RequestValidator` whenever an
  auth token is configured.
- In production, missing signature configuration rejects the webhook with 503.
- In development, validation is skipped when no Twilio auth token is configured.
- Signature checking uses `TWILIO_WEBHOOK_URL` if set, otherwise the request URL.
- Middleware logs request arrival before form/signature rejection and logs the
  resulting status. Exceptions log a traceback with message ID context.
- No rate limiting, user registration, JWT authentication, or role system was added.

## 6. Database changes

| Table/model | Purpose or change |
| --- | --- |
| `transactions` / `TransactionDB` | Original transaction records; added user/date and user/created indexes; SQLite-compatible ID variant |
| `conversation_states` / `ConversationState` | Original persisted pending state; now expires after 24 hours; SQLite-compatible ID variant |
| `processed_webhooks` / `ProcessedWebhook` | New unique Twilio message marker |
| `budgets` / `Budget` | New user/category/currency budget; unique on that combination |
| `budget_alerts` / `BudgetAlert` | New monthly threshold tracking; unique budget/period/threshold |
| `recurring_payments` / `RecurringPayment` | New schedule definition and next run date |
| `recurring_executions` / `RecurringExecution` | New unique schedule/date execution and optional transaction reference |
| `imported_transactions` / `ImportedTransaction` | New fingerprint, occurrence, source name, and transaction reference |

`database_url_with_driver()` normalizes plain `postgresql://` and `postgres://`
URLs to `postgresql+psycopg2://`, matching the installed driver. Explicit driver
URLs are preserved. `pool_pre_ping=True` checks pooled connection health.

FastAPI startup imports the model module and calls `Base.metadata.create_all()`.
The copy's existing `create_tables.py` remains usable: importing its model module
registers all model classes. It was not necessary to reproduce an earlier cosmetic
import change made in the original folder.

There is no Alembic migration setup. `create_all()` creates missing tables but does
not migrate existing table schemas. Do not reset or drop the user's application
database to apply changes. The rollback in the original folder was a source-file
rollback, not a rollback of any previously created remote database tables.

## 7. API reference for the implemented routes

All `/api/...` endpoints below require the configured dashboard bearer token.
The webhook has Twilio-specific validation instead.

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/` | Static dashboard |
| GET | `/health` | Basic application health response |
| GET | `/docs` | Generated API documentation |
| GET | `/openapi.json` | OpenAPI schema |
| POST | `/webhook/whatsapp` | Twilio WhatsApp event handler |
| GET | `/api/transactions` | User-scoped list and filters |
| GET | `/api/transactions/currencies` | Available currencies |
| GET | `/api/transactions/{transaction_id}` | Read one owned transaction |
| PATCH | `/api/transactions/{transaction_id}` | Correct selected fields |
| DELETE | `/api/transactions/{transaction_id}` | Delete an owned transaction |
| POST | `/api/transactions/undo` | Delete the latest entry |
| GET | `/api/transactions/export/csv` | Export filtered records |
| GET | `/api/budgets` | List budgets with current usage |
| POST | `/api/budgets` | Create/update a budget |
| DELETE | `/api/budgets/{budget_id}` | Delete a budget and its alerts |
| GET | `/api/reports/monthly` | Month report and previous-month comparison |
| GET | `/api/reports/range` | Custom-range report |
| GET | `/api/recurring` | List schedules |
| POST | `/api/recurring` | Create a schedule |
| PATCH | `/api/recurring/{payment_id}` | Pause/resume a schedule |
| DELETE | `/api/recurring/{payment_id}` | Delete schedule/execution records |
| POST | `/api/imports/csv/preview` | Parse CSV without saving transactions |
| POST | `/api/imports/receipt/preview` | Extract receipt for review |
| POST | `/api/imports/confirm` | Save reviewed import entries |

Transaction list filters include start/end date, category, type, currency, limit,
and offset. The API caps `limit` at 500; the dashboard currently requests 200.
The list endpoint is not a complete full-text search implementation.
Custom-range reports require `start_date` and `end_date`; monthly reports accept
year/month and currency. There is no general transaction POST endpoint; entry
creation currently comes through WhatsApp, confirmed imports, or recurring execution.

## 8. File inventory and responsibilities

> **Historical scope:** Inventory before directory separation. Section 0 gives current paths.

### Existing files updated in the copy

| File | Changes |
| --- | --- |
| `.env.example` | Document dashboard, Twilio, and optional vision settings |
| `.env` | Added generated dashboard token and matching WhatsApp user identity; secrets omitted here |
| `requirements.txt` | Preserved existing SQLAlchemy/psycopg additions and added psycopg2-binary |
| `app/config.py` | Added dashboard, Twilio, and vision settings |
| `app/main.py` | Register feature routers, startup table creation, recurring lifecycle, request logging, static dashboard |
| `app/db/database.py` | Explicit PostgreSQL driver normalization |
| `app/db/models.py` | New feature tables, constraints, indexes, compatible IDs |
| `app/schemas/transaction.py` | Monetary precision, field bounds, currency normalization |
| `app/services/llm_service.py` | Multi-entry normalization, singular compatibility wrapper, receipt vision extraction; preserved category intent additions |
| `app/services/conversation_service.py` | Pending-state expiration |
| `app/services/transaction_service.py` | Optional deferred commit, owned record lookup/deletion, currency-separated totals and summaries |
| `app/api/webhook.py` | Command handling, batch persistence, duplicate protection, signature checks, routing and diagnostics; read-only report formatting extracted into a service |
| `scripts/smoke_test_backend.py` | Expanded isolated regression suite replacing the small check at this path |

### New files in the copy

| File | Responsibility |
| --- | --- |
| `app/api/auth.py` | Dashboard bearer-token validation and fixed owner dependency |
| `app/api/transactions.py` | Transaction list/read/edit/delete/undo/export APIs |
| `app/api/budgets.py` | Budget CRUD/usage APIs |
| `app/api/reports.py` | Report endpoints |
| `app/api/recurring.py` | Schedule endpoints |
| `app/api/imports.py` | Preview/confirm file import endpoints |
| `app/schemas/features.py` | Feature request/response schemas |
| `app/services/transaction_command_service.py` | Deterministic correction/delete/undo/cancel parsing |
| `app/services/budget_command_service.py` | Deterministic budget command parsing |
| `app/services/budget_service.py` | Monthly aggregation and threshold records |
| `app/services/report_service.py` | Date-range reports and month comparison |
| `app/services/recurring_service.py` | Date advancement, reminders, execution records, polling worker |
| `app/services/import_service.py` | CSV parsing, fingerprints, duplicate checks, import persistence |
| `app/services/notification_service.py` | Configurable outbound Twilio delivery |
| `app/services/whatsapp_query_service.py` | Read-only WhatsApp query routing and formatting |
| `app/static/index.html` | Dashboard structure/forms |
| `app/static/dashboard.css` | Responsive dashboard styling and category bars |
| `app/static/dashboard.js` | Dashboard data requests, rendering, controls, import review |
| `scripts/check_whatsapp_connection.py` | Local backend/ngrok/public health diagnostics |
| `scripts/check_running_backend.py` | Preserved copy of the user's original lightweight smoke checker |
| `README.md` | Setup, features, import format, diagnostics, links |
| `docs/PROJECT_EXPLAINED.md` | Simple technical/interview guide and implemented Jev classifier explanation |
| `context.md` | This full handoff |

An untracked `high level architecture diagram.png` was visible when this handoff
was prepared. Codex did not create it in this conversation; preserve it as user work.

## 9. Testing implemented and verification history

The smoke suite grew from four initial regressions, to 20 message-flow checks,
to **23 tests after migration into the copy**. It was run successfully with the
copy folder's own virtual-environment Python. JavaScript syntax and Git whitespace
checks also passed during the migration work.

Tests use:

- Temporary on-disk SQLite database, not the real configured database.
- Environment overrides inside the test process; the real `.env` is not rewritten.
- Mocked Groq completions/intent results and mocked receipt extraction.
- Mocked outbound notifications for recurring execution checks.
- FastAPI TestClient for real handler/API execution.
- Database assertions as well as response assertions.
- Explicit worker calls for recurring tests; the normal lifespan polling task
  does not run during the suite.

The 23 test cases cover:

1. Dashboard authorization, CSV import preview/confirm, duplicate import handling,
   range/month reports, edit, export, delete, and undo.
2. Recurring automatic payment records once despite repeated worker passes.
3. Receipt preview saves nothing until confirmation.
4. Individual expense/income messages.
5. Missing-purpose follow-up completion.
6. Cancellation and repeated cancellation without an entry.
7. Incomplete batches save nothing.
8. Amount/date/category/purpose edits, including ID and `last` targets.
9. Invalid edits preserve existing data.
10. Delete/undo and missing targets.
11. Repeated delete message does not remove another entry.
12. Other users cannot edit/delete/read the owner's records.
13. Budget setup, remaining amounts, 80%/100% alerts, and repeat suppression.
14. Invalid budget amounts.
15. All supported expense periods/lists, including previous month and recent records.
16. Income queries across all-time/today/week/month.
17. Monthly summary and category queries.
18. Currency separation.
19. Unknown-message and media guidance.
20. PostgreSQL driver selection.
21. Supported extraction response shapes, including nested lists.
22. Batch transaction persistence and repeated webhook delivery.
23. Signature validation and missing form fields.

Do not interpret these results as measured live NLP accuracy or proof of Twilio
delivery. The suite does not test real OCR quality, real Groq/Jev interpretation,
PostgreSQL lock concurrency, or a browser-driven end-to-end UI session.

## 10. Debugging history and what was actually established

### Requests were sent to `/` instead of the webhook

The user initially saw `POST / ... 404`. The registered handler is
`POST /webhook/whatsapp`; the public callback needs that complete path.

### Two entries caused a Pydantic list-versus-object error

The logged message contained coffee spending and salary income together. The
initial extractor passed the entire JSON list to a singular Transaction validator.
Batch extraction/persistence and nested list normalization were added.
Early advice that repeated errors were necessarily stale code was too strong:
a stale/wrong process was plausible, but logs alone were not conclusive.

### The original and copied folders caused confusion

The user was launching code from the copy while Codex edits were initially in
the original folder. This explained why those edits could fail to affect their
running app. The user explicitly requested rollback of the original and migration
of all updates into the copy. That migration and rollback are complete.

### No WhatsApp request appeared; ngrok showed zero connections

The screenshot showed an online tunnel forwarding to localhost:8000 with zero
connections. That showed no traffic had reached that tunnel at that point.
Possible causes included callback configuration, a changed public host, using
the wrong sender/Sandbox, or missing Sandbox membership.

The diagnostic script was added to distinguish these from backend route failures.
Codex could not inspect Twilio Console settings because credentials were absent
at the time of diagnosis. End-to-end user-phone delivery was not confirmed.

### Missing dependencies and PostgreSQL driver mismatch

Runtime investigation found no active backend/tunnel and a selected Python
environment missing SQLAlchemy. Requirements were installed. Startup then failed
because a plain PostgreSQL URL selected `psycopg` while the declared dependency
at that stage was `psycopg2-binary`.

Explicit driver selection fixed this. The copy's venv later received the declared
dependencies too. Packages installed earlier in the global Python environment
were not uninstalled as part of the source-directory rollback.

### Live local/public connectivity was verified at one earlier point

Before folder migration, Codex started a backend and ngrok and verified local
health, public health, and a public POST reaching the webhook. A probe without
message fields returned the expected 422 without creating records.

This was a connectivity test, not a real WhatsApp message test. It was also before
the code migration; do not treat that historical process as the currently active
copy backend. The later connection check found the backend and tunnel stopped.
Recheck current state rather than assuming either is still running.

### Windows socket error and wrong application import

The user ran `uvicorn backend.api:app --reload` in the copy and saw WinError 10013.
At that time an earlier Codex-started backend occupied port 8000. The copy also
did not contain `backend/api.py`. The correct command uses `app.main:app`.
The historical PID is not a stable identifier; inspect current ownership before
stopping a process.

### Dashboard variables were missing from the real copy `.env`

Codex added a securely generated `DASHBOARD_API_TOKEN` and set
`DASHBOARD_USER_ID` to the exact WhatsApp sender from the user's logs. No secret
values were printed. The original folder's `.env` was not edited.
The real copy `.env` was not replaced with the example file.

## 11. Configuration reference

> **Historical scope:** Early settings. Current auth/providers and backend/.env location are in section 0 and backend/app/config.py.

Settings currently load `.env` relative to the process working directory. Run
commands from the copy root to avoid using the wrong file.

| Variable | Purpose |
| --- | --- |
| `APP_NAME` | Application label |
| `ENVIRONMENT` | Development/production behavior, including webhook validation requirements |
| `GROQ_API_KEY` | Required application setting for Groq |
| `GROQ_MODEL` | Text model; code default is `openai/gpt-oss-20b`, actual deployment override may differ |
| `DATABASE_URL` | Required database connection string |
| `DASHBOARD_API_TOKEN` | Secret used for dashboard bearer authentication |
| `DASHBOARD_USER_ID` | Exact Twilio `From` identity, for example `whatsapp:+<country-code><number>` |
| `TWILIO_ACCOUNT_SID` | Outbound Twilio account |
| `TWILIO_AUTH_TOKEN` | Inbound signature verification and outbound authentication |
| `TWILIO_WHATSAPP_FROM` | Configured Sandbox/business sender with `whatsapp:` prefix |
| `TWILIO_WEBHOOK_URL` | Exact public callback used when validating a signature |
| `GROQ_VISION_MODEL` | Optional receipt extraction model supporting images |
| `INTENT_CLASSIFIER` | Select `jev` or `groq` for intent routing |
| `TYPESAFE_API_KEY` | TypeSafe credential for real Jev calls |
| `JEV_MODEL` | Versioned Jev model, default `jev-1.14.0` |
| `JEV_TIMEOUT_SECONDS` | Positive Jev HTTP-operation timeout, default 4 seconds |
| `JEV_MIN_CONFIDENCE` | Minimum accepted Jev confidence, default 0.6 |
| `JEV_FALLBACK_TO_GROQ` | Fall back on missing key/errors/uncertainty; default true |

`TWILIO_WEBHOOK_URL` does not register a callback with Twilio. Save the URL on the
correct sender/Sandbox in Twilio Console, set method POST, and save the setting.
ngrok's host can change; use the currently active tunnel rather than an old URL.
Do not put production secret values or full personal sender details in this document.

## 12. Running and testing from the correct folder

> **Historical scope:** Commands before the split. Use section 0.8 and README.md; run Python from backend/.

Backend terminal:

```powershell
cd "D:\Siddhesh\Projects\expense-tracker - Copy"
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python scripts/smoke_test_backend.py
python -m uvicorn app.main:app --reload --port 8000
```

Another terminal:

```powershell
ngrok http 8000
```

Diagnostics terminal, from the copy root with the venv active:

```powershell
python scripts/check_whatsapp_connection.py
```

If PowerShell activation is unavailable, invoke `venv\Scripts\python.exe` directly.
The diagnostic script checks local health and route registration, discovers local
ngrok HTTPS tunnels, prints the full callback, checks configured URL mismatches,
and probes public health. It does not send a WhatsApp message or create transactions.

Useful URLs:

- Dashboard: `http://127.0.0.1:8000/`
- Health: `http://127.0.0.1:8000/health`
- API docs: `http://127.0.0.1:8000/docs`
- ngrok request inspector: `http://127.0.0.1:4040`
- Twilio callback: `https://<active-public-host>/webhook/whatsapp`, method POST

Do not overwrite an existing `.env` with `Copy-Item .env.example .env`.
That README command is for first-time setup only. Restart the backend after
configuration changes; Python source reload does not guarantee settings reload.

## 13. Manual WhatsApp verification messages

These create/change real records in the configured database, unlike the isolated tests.

```text
I spent ₹250 on coffee
Received ₹65000 salary
Show my recent transactions
edit last amount to 300
edit last category to food
edit last date to 2026-10-17
edit last purpose to lunch
delete last
undo last
Set my food budget to ₹1000
Set my overall budget to ₹20000
show my budgets
How much is left in my food budget?
How much did I spend today?
How much did I spend yesterday?
How much did I spend this week?
How much did I spend this month?
How much did I spend last month?
Show my monthly summary
How much did I earn this month?
```

For cancel, send `Spent ₹100`, wait for the purpose question, then send `cancel`.
For a batch, put the coffee and salary lines in one WhatsApp message. Use the
dashboard for schedule creation, custom-range comparisons, exports, and imports.

## 14. Interview explanation and Jev discussion

The user found the first architectural explanation difficult and requested a
simple but technical Markdown guide. Codex created `docs/PROJECT_EXPLAINED.md`
with examples, a flow diagram, terminology, interview answers, feature mechanisms,
debugging lessons, limitations, and next steps, linked from the README.

The user asked whether TypeSafe AI's **Jev** could be used only for classification.
Official TypeSafe documentation was checked on 17 October 2026:

- https://docs.typesafe.ai/primitives/choice
- https://docs.typesafe.ai/patterns/intent-routing
- https://docs.typesafe.ai/confidence

The original proposed design (subsequently implemented; see section 19) was to preserve deterministic commands/pending handling, use
Jev to choose an existing intent label, retain Groq for free-form field extraction,
and route reports directly to Python/SQL. Handle uncertain decisions and failures
explicitly, and benchmark real labeled messages before switching.

**Historical state when the guide was first written:** Jev was not integrated.
That changed with the implementation in section 19. Typed outputs still do not
prove semantic correctness; confidence is not guaranteed accuracy. No real-model
accuracy or application-specific latency/cost improvement has been measured.

## 15. Known limitations and sensible next work

> **Historical scope:** Historical assessment; section 0 and later implementation supersede completed items.

These should be explained honestly in another chat or interview:

1. Dashboard authentication is one configured account with a static token, not
   a full user-registration/login/role system.
2. Undo deletes the latest entry; there is no audit history, soft delete, or
   general reversal mechanism.
3. Explicit command message claims and their updates need a common transaction
   to close the crash window. Pending-state updates also involve separate commits.
4. Notification delivery has no durable outbox/queue or exactly-once guarantee.
5. The scheduler depends on a live app process and does not recreate all missed runs.
6. SQLAlchemy/model API calls inside an async webhook are synchronous and can
   block the event loop. Production concurrency needs deliberate improvement.
7. `.env` lookup depends on CWD; source folder, venv, and process must agree.
8. Schema changes need a migration strategy such as Alembic.
9. Dependency versions are not pinned. Both PostgreSQL driver packages are
   declared, although plain URLs use psycopg2 explicitly.
10. SQLite/mock tests do not prove real PostgreSQL concurrency or NLP accuracy.
11. Receipt parsing requires user review and a supported model, not just an API key.
12. Duplicate imports are heuristic field matching and can flag legitimate repeats.
13. The webhook catches processing exceptions and returns a friendly TwiML message
    with HTTP 200. Monitor processing errors as well as transport status.
14. The health endpoint is basic application health; it is not a full readiness
    check of every external provider and the database.
15. The dashboard requests a limited transaction page; complete full-text search,
    a full pagination UX, and browser end-to-end tests are not provided.
16. Pending conversations currently treat non-command messages as the requested
    answer. Cancel works, but arbitrary new entries during a pending turn need
    more conversational disambiguation.
17. Some `last` selections sort only by creation time; an ID tie-breaker is worth
    adding consistently for records created in the same timestamp.

Recommended next work: confirm live WhatsApp delivery in the copy, exercise
dashboard flows with controlled data, evaluate real model interpretation, then
prioritize atomic command handling, migrations, authentication, and durable workers.

## 16. Working preferences and instructions for the next assistant

- The user wants implementation, not repeated suggestions or permission prompts.
- They value clean, modular code and explanations that are simple but technical.
- Use `expense-tracker - Copy` explicitly for all project commands and edits.
- Preserve the original folder's restored state and pre-existing user work.
- Preserve the copy's real `.env` and never reproduce secrets in chat/handoff files.
- Do not claim a mocked regression test proves live WhatsApp or model behavior.
- Check the actual process, working directory, and tunnel before diagnosing stale code.
- Do not assume past backend/tunnel sessions are still active.
- No commits, PRs, production deployment, or pushes were performed by Codex in
  this conversation. Many feature files remain untracked until the user reviews
  and commits them. Do not assume `git diff` alone includes all new files.
- This handoff is a snapshot, not automatic memory. Update it after subsequent
  material implementation changes, or ask the coding assistant to do so.

## 17. Suggested message when sharing this document with another ChatGPT chat

> I continued my WhatsApp expense-tracker project in Codex. Please read the
> attached context.md as the handoff. The current code is in
> D:\Siddhesh\Projects\expense-tracker - Copy. The original folder was restored.
> The six feature groups and Jev/Groq classification are implemented, and 40
> offline tests pass. Live Jev needs a locally configured TypeSafe key; Groq
> remains responsible for extraction and optional fallback. Distinguish mocked test
> results from live integration behavior. Use the current source files to confirm
> details before making further changes, and preserve my existing .env secrets.

Attach/upload this file or paste its contents in that conversation. A web chat
does not receive local files merely because they exist on this computer. If code
changes are requested there, also provide the relevant current source files.

## 18. Follow-up: resolved startup DNS failure — 17 October 2026

The user shared a Uvicorn startup traceback from the copy folder. During
`Base.metadata.create_all()`, PostgreSQL connection setup failed with
`could not translate host name ...supabase.co to address`.

Read-only investigation found that the configured Supabase direct hostname
resolved to an IPv6 address and had no IPv4 A record. Subsequent checks succeeded:

- Default DNS resolution returned the IPv6 address family.
- A TCP connection to the configured database port was reachable over IPv6.
- Database authentication and a read-only `SELECT 1` succeeded.
- The running backend's `/health` returned HTTP 200.

The user confirmed the app was working and attributed the earlier failure to
internet connection issues. Treat this incident as resolved transient network
connectivity. No application-code, database-URL, schema, or driver changes were
made for this incident. IPv4 session pooling was researched as a possible option
but was not applied or needed to resolve this reported failure. This check did
not independently establish end-to-end WhatsApp delivery.


## 19. Jev classifier integration — 17 October 2026

The user explicitly requested Jev integration after the design discussion.
Implementation was made only in `expense-tracker - Copy`.

### Implemented behavior

- Added `app/services/intent_registry.py` with all 21 existing supported intent
  labels and their descriptions. Both provider results must use a supported label.
- Added `app/services/intent_classifier_service.py` with a validated internal
  `IntentClassification` result: label, provider, optional confidence, and fallback reason.
- `llm_service.detect_intent()` is the compatibility entry point and delegates to
  the classifier service. The original classifier is `detect_intent_groq()`.
- Jev uses the official SDK's Choice question, selected from the registry.
  The request state contains only the supplied message; classification does not
  send database records or perform financial actions.
- Jev only classifies intent. Groq still extracts transaction fields, category/time
  filters, and receipt data. Explicit commands and pending replies bypass classification.
- Default model is pinned to `jev-1.14.0`; SDK dependency is `typesafe-sdk==0.7.5`.
  SDK dependencies were installed in the copy's venv (including httpx2).
- Jev HTTP timeout is configurable, SDK retries are disabled, and its context
  manager closes the provider client after the call.
- Missing key, SDK errors/timeouts, malformed/unsupported responses, and confidence
  below the configured minimum fall back to Groq when enabled.
- With fallback disabled, those cases return `unknown` with provider `none`.
- A confident `unknown` choice is preserved rather than triggering fallback.
- Confidence must be finite and within [0, 1]; the default minimum of 0.6 is an
  initial policy, not an empirically calibrated accuracy guarantee.
- Logs include provider/intent/confidence or fallback reason, without raw messages,
  response bodies, credentials, or raw provider errors.
- The webhook invokes classification through `run_in_threadpool`. Existing other
  synchronous database/extraction work is not made fully asynchronous by this change.

### Configuration

Added settings to `app/config.py`, `.env.example`, and missing names in the real
copy `.env`, preserving pre-existing values:

```dotenv
INTENT_CLASSIFIER=jev
TYPESAFE_API_KEY=
JEV_MODEL=jev-1.14.0
JEV_TIMEOUT_SECONDS=4
JEV_MIN_CONFIDENCE=0.6
JEV_FALLBACK_TO_GROQ=true
```

The Settings class defaults to `groq` when no provider is configured; the copy's
`.env` and example select Jev. The key was absent during initial implementation. The user subsequently
configured access and verified a live strict-mode call (section 20). A missing
key still causes Groq fallback when that option is enabled.
Groq credentials remain necessary for extraction and fallback. Never invent or
publish an API key, and restart the backend after editing configuration.

### Verification and new scripts

- Added `scripts/test_intent_classifier.py`: 15 offline unit/adapter tests.
- Added two webhook integration tests to `scripts/smoke_test_backend.py`, proving
  Jev routing with Groq extraction, and Jev report routing directly to SQL.
- The combined smoke suite now runs **40 passing tests** (previous 23 plus 17).
- The adapter tests run the installed real SDK with `httpx2.MockTransport`, checking
  the endpoint, state, Choice criteria, model, and response parsing. They cover
  confidence boundaries, missing keys, 401/429/503 responses, timeout, invalid
  responses, strict mode, provider selection, and configuration validation.
- Existing tests force an offline configuration to avoid real external calls.
- Added `scripts/check_intent_classifier.py` for a real one-message check without
  database writes. `--strict-jev` forces Jev and disables fallback so a Groq answer
  cannot masquerade as Jev success:

```powershell
python scripts/check_intent_classifier.py --strict-jev "How much did I spend this month?"
```

The checker prints the validated result and exits nonzero when classification is
unavailable/declined. A successful strict run should report provider `jev`.
At implementation time, a live response could not be verified because the key
was missing. The later user-provided successful result is recorded in section 20.
Mocked tests do not establish real classifier accuracy, latency, or savings.

Updated README and `docs/PROJECT_EXPLAINED.md` to describe implemented behavior,
activation, fallback, and evaluation limits instead of presenting Jev as merely proposed.
No database migration or original-folder changes were needed for this integration.

Official references checked: TypeSafe's Python SDK, Choice, models, timeout/retry,
response, and confidence documentation at https://docs.typesafe.ai/.


## 20. Live Jev classification verified by the user — 17 October 2026

The user ran the following from the active copy folder with its venv:

```powershell
python scripts/check_intent_classifier.py --strict-jev "How much did I spend this month?"
```

They provided this successful output:

```json
{
  "label": "month_total",
  "provider": "jev",
  "confidence": 1.0,
  "fallback_reason": null
}
```

This verifies real TypeSafe account/model access and correct routing for this one
message. Strict mode disabled Groq fallback, so this result was not produced by
the fallback provider. It did not write database records. This was user-reported
terminal evidence, not another provider call run by Codex.

The earlier missing-key limitation is resolved for this local run. Overall
classification accuracy, latency/cost comparisons, and the full live WhatsApp
path with Jev have not been established by this single check. The next useful
check is restarting the backend and sending the equivalent query on WhatsApp,
then inspecting the Jev provider log and the returned database-backed spending total.
No secret values were collected or included in this handoff.

## 21. Local GLiNER2 integration and real webhook checks — 18 October 2026

### Request, scope, and current selection

The user requested installing `gliner2-base` from Hugging Face, running it locally,
and testing the WhatsApp application. All changes below were made in
`D:\Siddhesh\Projects\expense-tracker - Copy`; the original checkout was not edited.
Earlier sections describing Groq-only transaction extraction are historical.

The active copy `.env` now selects **Jev for intent routing** and **local CPU
GLiNER2 for transaction extraction, income/expense classification, and category
classification**. Existing Jev configuration and secret values were preserved.
This is not an entirely local/offline app: Jev, Twilio, the hosted database,
existing query parsing, receipt vision, and configured fallback still use their
existing services. No model fine tuning was performed.

### Installation and model

- Existing `venv` uses Python 3.15, for which compatible PyTorch wheels were not
  available at installation time. Kept that environment intact.
- Installed Python 3.12.10 using the Python install manager (`py install 3.12`).
- Created separate `.venv-gliner` in the copy and installed CPU PyTorch from
  `https://download.pytorch.org/whl/cpu`, followed by app/local requirements.
- Added `requirements.local.txt`, including `requirements.txt`,
  `gliner2[local]==2.1.0`, Transformers >=4.43,<6, SentencePiece >=0.2,<1,
  protobuf >=5,<8, and dateparser >=1.2,<2. `pip check` passed.
- Added `.venv-gliner/` to `.gitignore`. Model weights remain in the user's
  Hugging Face cache outside the repository.
- Downloaded and loaded `fastino/gliner2-base-v1` (205M parameters) on CPU, pinned
  to revision `f9634218e53580c56edf0de97ca1a7d3f1c2354e`.
- Uses the official `gliner2.AutoExtractor` Python API with PyTorch and
  Transformers underneath, rather than a generic Transformers pipeline.
- Model download allows JSON/tokenizer/SentencePiece/safetensors files;
  executable remote model code is not enabled.

### Modular code changes

1. `app/services/local_extraction_service.py` owns lazy optional imports,
   pinned cached model loading, a reusable CPU model, load/inference locks,
   entity descriptions and fixed category/type labels, source-span validation,
   confidence checks, Decimal amounts, currency checks, and deterministic dates.
   It excludes pronouns like `I` from the merchant/person field.
2. `app/services/transaction_extraction_service.py` selects the provider and
   owns explicit Groq fallback. Strict local errors raise `ExtractionUnavailable`
   with a useful clarification instead of silently writing guessed data.
3. `app/services/llm_service.py`: preserved Groq logic as
   `extract_transactions_groq()`; public `extract_transactions()` delegates to
   the new provider service. Existing callers retain their interface.
4. `app/api/webhook.py`: transaction extraction now runs through
   `run_in_threadpool`; handles `ExtractionUnavailable` by rolling back and
   replying with clarification. Existing intent routing, commands, pending
   purpose flow, writes, budgets, and MessageSid protection remain in use.
5. `app/main.py`: when local extraction is selected, load the model during
   startup with `asyncio.to_thread` before serving requests. A failed local
   startup fails clearly unless explicit Groq fallback is enabled.
6. `app/config.py`: added validated provider, model/revision, cache-only,
   confidence, CPU thread, and fallback settings. Groq remains the default when
   `EXTRACTION_PROVIDER` is absent, preserving compatibility with the old venv.
7. `.env.example` documents local options; copy `.env` enabled the local trial.
   Original `.env` and existing credentials were not changed or printed.
8. `scripts/smoke_test_backend.py` forces `EXTRACTION_PROVIDER=groq` for its
   existing mocked offline tests, independent of the live `.env` selection.

### Configuration now in the copy

```dotenv
EXTRACTION_PROVIDER=gliner2
GLINER2_MODEL_ID=fastino/gliner2-base-v1
GLINER2_REVISION=f9634218e53580c56edf0de97ca1a7d3f1c2354e
GLINER2_LOCAL_FILES_ONLY=true
GLINER2_ENTITY_THRESHOLD=0.4
GLINER2_CLASSIFICATION_THRESHOLD=0.5
GLINER2_NUM_THREADS=4
GLINER2_FALLBACK_TO_GROQ=false
```

Cache-only true was enabled after the download. A fresh machine needs false
for its first download. To revert extraction, set `EXTRACTION_PROVIDER=groq`
and restart. Optional `GLINER2_FALLBACK_TO_GROQ=true` permits cloud extraction
after a local error. The trial leaves extraction fallback disabled so a local
success cannot secretly come from Groq. Jev's existing fallback is separate.

### Constraints and validation

- Accepts up to 20 transactions separated by newline or semicolon, with each
  segment at most 500 characters. All segments must validate before saving.
- Requires an explicit positive numeric amount, at most two decimals. Rejects
  ambiguous amounts, `2k`/lakh/crore-style abbreviations, negative amounts,
  multiple currencies, and extra numeric values outside recognized dates.
- Supported explicit currencies: INR, USD, EUR, GBP. Missing currency uses INR.
- English relative dates use Asia/Kolkata; numeric dates use DMY. Explicit
  today/yesterday/tomorrow and numeric date patterns are recovered even if the
  entity model misses them. Other missed date wording remains a model limitation.
- Low category confidence becomes `other`; uncertain income/expense is declined.
- Missing purpose follows the existing pending transaction flow.
- Span/shape checks cannot prove semantic correctness. English examples passed;
  Hinglish and broad accuracy have not been evaluated.
- One shared model serializes inference. Multiple workers use more memory;
  concurrent throughput and production deployment were not load-tested.

### Scripts and evidence

- Added `scripts/test_local_extractor.py`: **19 passing regression tests**, using
  fabricated outputs without loading weights. Covers normalization, relative
  dates and missed date entities, malformed/mismatched spans, confidence,
  currency ambiguity, amounts/precision, missing purpose, provider selection,
  strict local behavior, and explicit fallback.
- Existing `scripts/smoke_test_backend.py`: **40 passing tests** in the new
  environment. Total across the two commands: **59 passing tests**.
- Added `scripts/check_local_extractor.py`: real local inference, `--repeat` for
  warm timings, and `--webhook` for temporary SQLite webhook integration.
  `--live-intent` additionally uses real Jev with classifier fallback disabled.
  The checker blocks Groq completion calls, verifies saved fields and retry
  protection, disposes the test database, and never sends outbound messages.
- Real model checks succeeded for coffee, salary, yesterday, full calendar date,
  groceries, Uber, missing purpose, and a two-line coffee/salary batch. A line
  containing separate tea and lunch amounts was declined.
- Real Jev plus real local GLiNER2 webhook tests returned HTTP 200, saved the
  expected coffee entry and two-line expense/income batch, and blocked duplicate
  MessageSid delivery. These used temporary SQLite; no synthetic test entries
  were added to the real database.
- First coffee check: about 20.1 seconds including imports/loading; next run:
  about **538 ms**. Cold live-intent webhook checks: about 15–19 seconds including
  local load. These few examples are not a benchmark or a Groq comparison.
  Production startup preload removes model loading from the first message path.
- Both `scripts/check_whatsapp_connection.py` checks passed after starting the
  new server: local route/health and public ngrok health. The configured `.env`
  callback matched the current tunnel callback. No actual phone-originated
  WhatsApp message or Twilio delivery was verified by these automated checks.

### Running server and next step

Stopped the existing copy-folder Python 3.15 Uvicorn reloader and its remaining
worker, which held port 8000 after the parent exited. Started the copy's backend
using `.venv-gliner` Python 3.12 on **127.0.0.1:8000** with no reload flag.
Its log confirmed `Local extractor ready`, `Application startup complete`, and
Uvicorn listening. The existing ngrok tunnel was retained and public health passed.

This helper-started process runs hidden, with ignored logs:
`gliner-backend.stdout.log` and `gliner-backend.stderr.log` in the copy. If it
is still running, stop it before starting another backend on the same port.
The recurring worker still follows normal application startup behavior.

For future manual startup, from the **copy**:

```powershell
.\.venv-gliner\Scripts\Activate.ps1
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Wait for startup to finish; keep ngrok targeting port 8000. Send a message from
the user's phone such as `I spent ₹250 on coffee` or `Received ₹65,000 salary`.
Use separate lines for multiple entries. Inspect `provider=gliner2` extraction
logs and the reply. Those phone messages will create real records; undo/delete
trial entries afterward if desired. Actual phone delivery remains the next
manual check, not an already established result.

Updated `README.md`, this handoff, and `docs/PROJECT_EXPLAINED.md`. Added
`docs/LOCAL_GLINER2.md` with installation, startup, model behavior, settings,
tests, examples, rollback, measured timings, and limitations.
Official sources checked: https://huggingface.co/fastino/gliner2-base-v1 and
https://github.com/fastino-ai/GLiNER2.


## 22. Individual dashboards and deployment guidance — 18 October 2026

### User changes since the local model experiment

The user reported uninstalling Python 3.15, creating a Python 3.12.10 `venv`, and
merging backend/local dependencies into `requirements.txt`. The active copy
contains this merged file; separate `.venv-gliner` setup is historical.

The user created Dockerfile, Compose, and ignore files themselves using guidance.
They ran the Docker backend successfully after switching their Supabase direct
IPv6 connection to the IPv4-capable Session pooler. Logs they provided showed
GLiNER2 ready and application startup complete. They attempted to push
`siddheshtodi/expense-tracker:v1` to Docker Hub, but the provided logs showed
registry commit timeouts; a successful final push was not established here.
These actions were user-performed, not a deployment run by Codex.

### Current request and implemented flow

The user asked for each user to have their own dashboard and for free deployment
options. All code edits were made in `expense-tracker - Copy`; the original
checkout was not edited. Current workspace permissions required reviewed access
to the copy path. No credentials were read into output or changed.

The new default is `DASHBOARD_AUTH_MODE=whatsapp`. Everyone uses the same dashboard
URL and bot number but proves control of their own WhatsApp account:

1. Enter an international phone number in the dashboard.
2. Backend issues a random login command and a separate browser polling secret.
3. Send the command to the bot from that exact WhatsApp number.
4. A signature-verified Twilio callback approves the challenge before pending
   purpose handling or AI classification.
5. Only the originating browser, holding its separate secret, can claim the
   challenge and obtain an HttpOnly session cookie.
6. Financial APIs resolve that cookie to its account's WhatsApp identity.

No passwords, email provider, Supabase Auth keys, or extra auth dependencies are
needed. WhatsApp messaging still incurs provider costs. Sandbox participants
must join first. This is the app's own opaque-session authentication, not JWT.

### Schema and code inventory

- `app/db/models.py`: additive `DashboardUser`, `DashboardLoginChallenge`, and
  `DashboardSession` models. Unique WhatsApp account identity, session-account FK,
  challenge hashes/state/expiry, and lookup/expiry indexes.
- Existing transaction/budget/import/recurring/conversation user IDs stay as
  `whatsapp:+...`. First verified login creates a dashboard account and retains
  that number's history; no financial records are rewritten or reassigned.
- `app/schemas/dashboard_auth.py`: validated E.164 input, strict login request
  bodies, challenge and account response schemas.
- `app/services/dashboard_auth_service.py`: random codes and browser/session
  secrets, SHA-256 hashes at rest, constant-time browser proof check, sender and
  signature checks, expiry, account creation, one-time atomic claim, session
  lookup/revocation, and database-count request limits. Concurrent account creation
  uses a savepoint; conditional challenge consumption prevents double claims.
- `app/api/auth.py`: routes `GET /api/auth/me`, `POST /api/auth/login/start`,
  `POST /api/auth/login/complete` (202 while pending), `POST /api/auth/logout`.
  Financial APIs continue using `require_dashboard_user`, now session-based.
- SameSite=Strict, HttpOnly cookies, production Secure flag, custom request header,
  and Origin checks for browser writes. Tokens are not exposed to JavaScript.
- `app/api/webhook.py`: signature validator returns whether proof was verified.
  Login commands are handled before pending transactions and AI; unsigned
  development requests cannot approve logins. Malformed login commands return
  guidance instead of becoming transaction purposes.
- `app/main.py`: mounts account routes, adds no-store API responses, account marker
  headers and browser security headers. Production refuses legacy shared-token
  mode, explicitly insecure cookies, or absent Twilio validation. Database setup
  happens before model loading. Swagger/ReDoc retain their normal CDN scripts.
- `app/static/dashboard-auth.js`: own-number login UI, WhatsApp link and copy
  command, bounded polling, automatic existing session lookup, and sign out.
- `index.html`, `dashboard.js`, `dashboard.css`: replaced token modal, hid financial
  content until login, cleared old data/forms/previews/toasts on logout or account
  change, aborted stale requests, and checked response account IDs across tabs.
- `app/config.py` and `.env.example`: new auth mode, session hours (default 24),
  challenge minutes (default 5), public dashboard origin, optional cookie Secure
  setting. Existing `.env` untouched. Old token/user settings only work in explicit
  development `legacy` mode; the new UI uses WhatsApp mode.
- `scripts/smoke_test_backend.py`: its existing offline environment explicitly
  selects `legacy` so historical API-token checks retain their meaning. No new
  tests were added or run. This is not coverage of the new account flow.

### Database setup, permission review and safety boundary

Added `app/services/database_setup_service.py` and
`scripts/migrate_dashboard_accounts.py`. They create missing tables, protect only
three new authentication tables with PostgreSQL RLS and revoked browser grants,
and preserve existing financial data and permissions. New tables and protection
are committed together. Existing startup schema creation is routed through this
setup, which also works without PostgreSQL-specific DDL on SQLite.

Automatic approval review rejected an earlier planned startup/migration rewrite
that would revoke PUBLIC/anon/authenticated privileges across existing tables.
Reason: broad persistent permission changes could disrupt other Supabase clients
and were not specifically authorized. That command never executed. The safer
implementation changes only new auth table permissions. Existing financial table
privileges were deliberately left untouched.

Production adds a read-only check for existing Supabase browser access: grants
without RLS or ambiguous existing policies stop startup with table names requiring
operator review. It is intentionally conservative and not a full policy verifier.
Any migration changing existing clients' grants needs a separate explicit review
and approval. No live database migration or grant changes were performed here.
Use a server-only DB role that owns the tables and a correct Session pooler URL.

### Operator actions still needed

Configure Twilio account auth token, correct bot number and exact callback URL.
For production configure `ENVIRONMENT=production` and HTTPS
`DASHBOARD_PUBLIC_URL`. Rebuild the Docker image/container to include the new code:

```powershell
docker compose up -d --build backend
docker compose logs -f backend
```

For an explicit local migration with the activated Python 3.12 venv:

```powershell
python scripts/migrate_dashboard_accounts.py
```

Startup also applies the same additive setup. The migration requires table-owner
privileges; production can stop for an existing-table privacy review. No Docker
build/restart/push or public deployment was performed by Codex in this turn.

### Hosting research and limits

Checked official sources on 18 October 2026:

- Oracle Always Free A1 currently documents 1,500 OCPU-hours / 9,000 GB-hours,
  equivalent to 2 OCPUs / 12 GB RAM for Always Free tenancies. Plausible for a small
  local-GLiNER2 pilot, subject to resource availability, limits and idle reclamation.
  It is ARM64, so existing likely-AMD64 images require an appropriate rebuild and
  dependency compatibility checks. No ARM build or cloud instance was verified.
- Render Free: 512 MB / 0.1 CPU, idle sleep after 15 minutes, no persistent disk.
  Unsuitable for the current local model. A Groq-extraction demo could be evaluated,
  with cold-start, memory and scheduler limitations explicitly retained.
- Current Hugging Face docs require a paid plan to create Docker/Gradio compute
  Spaces; free static hosting cannot run this backend.
- Free hosting does not remove Twilio messaging, external model, or database quota
  costs. WhatsApp template/consent rules and durable reminder work still apply.

Added `docs/MULTI_USER_DASHBOARDS.md` with onboarding, architecture, schema,
configuration, migration/rebuild commands, privacy boundary, hosting sources,
manual acceptance scenarios and unverified limits. Updated README,
PROJECT_EXPLAINED, LOCAL_GLINER2 setup note and this context.

### Validation status

Source/diff review and whitespace checks only. No tests added/run and no live
backend, migration, signed-phone login, browser UI, or cross-user isolation run.
Previous 59-pass evidence belongs to the pre-account version. Before public use,
verify at least two users, cross-user record IDs/exports/imports, wrong sender,
forged signatures, expired/replayed codes, session expiry/logout and tab changes.
The database-count login limits are best effort, not an atomic distributed limiter.
Phone-number reassignment/recovery and broad model/concurrency evaluation remain
operational considerations. The app is not being declared production-ready.


## 23. Frontend phone input reset loop fixed — 18 October 2026

The user reported that the dashboard would not accept typing and clarified that
it was the WhatsApp number field. The running dashboard at 127.0.0.1:8000 was
inspected in an isolated browser tab. The phone input was enabled, editable and
focused, but its value immediately returned to empty after input.

Cause: `showLogin()` dispatched `ledger:signedout`; `clearAccountData()` reset
all financial forms; resetting `transaction-filters` fired its reset handler,
which fetched transactions while signed out. That returned 401 and called
`showLogin()` again, resetting the login form and repeating the cycle.

Changes in the copy only:

- `dashboard.js`: suppress filter reset side effects during programmatic account
  cleanup with a `resettingForms` flag; skip filter reloads while signed out;
  discard scheduled reloads from an old account epoch; refuse financial API calls
  without an account; recheck account epoch after reading API error responses.
- `dashboard-auth.js`: emit signed-out cleanup only when leaving a signed-in
  account; preserve the entered phone on repeated sign-in errors; reset it only
  for an explicit restart/logout or actual account transition; focus the phone
  field when opening the login dialog.
- Root cause identified and source/whitespace reviewed. No regression tests were
  added or run. The running backend still served the old JavaScript when checked
  after editing. The fixed UI has not yet been verified in a rebuilt container.
- No Docker build/restart was performed, respecting the user's earlier request
  to execute Docker commands themselves. They need to run
  `docker compose up -d --build backend`, then hard-refresh the dashboard.

No authentication bypass, database change, WhatsApp message, or credential change
was made for this fix.


## 24. Separate React finance dashboard — 19 October 2026

### Request and scope

The user explicitly invoked `$frontend-design` and requested a separate React JS
frontend folder with a very minimal, appealing, luxurious finance appearance.
Used that skill and the Sites local-only workflow. All changes are in
`D:\Siddhesh\Projects\expense-tracker - Copy`; no original-folder edits,
cloud Site registration, publishing, Docker commands, live database writes, or
WhatsApp sends were performed. Existing user/backend changes were preserved.

### Visual direction

Chosen before implementation: porcelain canvas (#f6f7f9), white surfaces, navy
(#172a3a), muted brass (#a18b5d), slate text, and restrained green for income.
Cormorant Garamond headings/wordmark contrast with DM Sans body and tabular money.
A quiet sidebar and one navy net-position panel establish hierarchy; no decorative
gradient backgrounds or repeating animation system. Mobile navigation, visible
focus styles, reduced motion support, and higher-contrast secondary text included.
Fonts and icons are local build dependencies, not remote CDN resources.

### Frontend structure and dependencies

Added `frontend/` using React JS (.jsx), Vite, TanStack Query, Lucide icons,
Fontsource fonts, and a local Prettier formatter. npm dependencies were installed;
package.json uses actual installed version ranges and package-lock.json locks the
resolved tree. Local Node was 24.21.0; package engines require >=22.12.0. The root
project remains a Python backend; frontend tooling is isolated in this folder.

- `src/api/client.js`: fetch/cookies, CSRF header, timeout/cancellation, structured
  errors, session/account response checks, and CSV downloads.
- `src/auth/`: session provider, sign-in screen with controlled phone input,
  login creation, bounded polling, expiry, WhatsApp link/code copy, and sign out.
  No imperative form reset or unauthenticated transaction-fetch loop.
- `src/hooks/useLedger.js`: account-scoped queries, explicit preview responses,
  protected mutations, and cache invalidation after changes.
- `src/components/`: shared buttons, native dialogs, notifications, loading/error/
  empty states, transaction table/category icons, and data-derived SVG/bar charts.
- `src/pages/`: Overview, Transactions, Budgets, Recurring, and Imports.
- `src/lib/format.js`: money/date display, month bounds, categories/colors.
- `src/data/demo.js`: only the explicitly selected, read-only illustrative data.
- `App.jsx`: sidebar, hash navigation, account identity, period/currency controls,
  record-on-WhatsApp guidance, and preview banner.
- `styles.css`: scoped visual system and mobile/desktop layouts; closed mobile
  navigation is inert and keyboard focus enters navigation when opened.

### API-connected behavior

- Existing WhatsApp cookie-session endpoints stay authoritative. No shared token,
  CORS broadening, auth bypass, new account store, or API credentials in React.
- Overview uses monthly reports for income/spending/net/savings, previous-month
  comparison, category spending, and largest expenses. Recent transactions are
  fetched separately. Custom date-range reports remain available.
- Movement chart compares the actual selected and previous calendar months; it
  does not invent a daily balance series or claim to show a bank account balance.
- Transactions support server-side date/type/category/currency filters and 25-row
  pagination. Text search is explicitly within the current page. Edit amount/date/
  category/purpose, delete, undo, and date-range CSV export use existing APIs.
- CSV export honors dates and currency, which are the backend's supported export
  filters; it does not falsely claim to honor text/type/category filters.
- Budgets are current-month limits (including overall/category), with upsert,
  deletion, progress and remaining/over-limit amounts. No sum of overlapping
  overall/category budgets is shown as a misleading combined limit.
- Recurring supports creation, pause/resume and deletion. Reminders vs auto-record
  are explicit; the UI does not claim that Ledger actually moves bank funds.
- CSV and receipt imports retain review before confirmation. Preview rows allow
  editing and selection; possible duplicates start unselected and only explicitly
  selected duplicates are included. Client limits uploads to 10 MB, matching API.
- Currency options combine transactions, budgets and schedules so a new budget
  currency remains accessible even before the first transaction in that currency.
- Account changes cancel queries and clear caches. API response account markers
  detect stale cross-tab identities. Server sessions remain HttpOnly.
- Money writes use amount strings; JavaScript numbers only control display/charts.

### Explicit design preview

The sign-in screen offers **Explore a preview**. This selects client-only sample
records and shows a persistent read-only/illustrative banner. It does not create
a session, call protected APIs, modify records, or silently mask a backend error.
Writes, deletion, uploads, exports, and custom-range submission are disabled.
Leaving preview returns to normal private sign-in.

### Development and production integration

`npm run dev` listens on loopback port 5173. `/api` proxies to the existing backend
at 127.0.0.1:8000. `changeOrigin: false` preserves Host/Origin matching for existing
backend CSRF validation. An optional local `API_PROXY_TARGET` supports another
backend port. Production `DASHBOARD_PUBLIC_URL` must match the actual browser
origin; never disable origin checks to work around a configuration mismatch.

Optional `VITE_WHATSAPP_NUMBER` is a public bot number for the signed-in convenience
link only. Login uses the backend-provided WhatsApp link. Backend credentials stay
outside the frontend. Do not copy the server .env into frontend variables.

`app/main.py` now serves `frontend/dist` when a built index.html exists; otherwise
it retains `app/static` as a fallback. Hash navigation avoids SPA path fallback
changes. The root Dockerfile adds a Node 24 build stage and copies only dist into
the Python image. Node/node_modules do not enter the runtime image. Git and Docker
ignore rules exclude frontend dependencies/build output. The existing .env secret
exclusion remains. Existing compose service ports are unchanged.

To run the separate frontend from the copy:

```powershell
cd frontend
npm ci
npm run dev
```

Open http://127.0.0.1:5173/ and keep backend port 8000 running. To include the new
UI in Docker, the user runs `docker compose up -d --build backend` from the copy
root, then opens the backend's published port after startup. No such Docker
command was executed during this implementation.

### Validation and limitations

`npm run build` completed successfully after the feature and accessibility
changes. The preview root returned HTTP 200. No tests were added/run. Browser
visual review could not be completed: IAB was unavailable, and the Windows browser
helper stopped because it could not verify the browser URL with enough confidence.
No screenshots or real-user login/mutation verification are claimed. Existing
backend/model test counts do not establish coverage of this React implementation.

Updated README and this context; added `frontend/README.md` with source structure,
run/build/Docker steps, proxy/origin setup, explicit preview boundaries, API scope,
and validation limitations. No cloud deployment or Docker Hub update occurred.


### Dashboard query caching update

- React Query keeps financial query results fresh for 5 minutes and retains inactive results for 30 minutes in memory.
- Returning to the same account and filters within 5 minutes reuses the result without another query. Stale cached results remain visible while refreshed on mount, window focus, or network reconnection.
- Existing successful edits, deletes, budget changes, recurring changes and confirmed imports invalidate account queries. Active views refresh; inactive views refresh when reopened.
- Added an accessible Refresh dashboard data button to invalidate the current account cache on demand, useful after WhatsApp entries.
- Cache keys remain account- and filter-specific. Sign-out/account changes clear the cache. No financial records are persisted in localStorage. A browser reload fetches again.
- External WhatsApp/database changes are not pushed instantly. The next stale revalidation or manual Refresh retrieves them; no background interval polling or server revision endpoint was added.
- No tests, Docker commands, or database mutations were run for this change.


### Dashboard dark palette and larger text

- Reversed the React dashboard palette: dark navy canvas/cards with light text; formerly dark net-position and sign-in story panels use light porcelain with navy text. Brass and semantic income/error accents remain readable.
- Increased explicit desktop/mobile font sizes about 16 percent, with a 12px minimum for labels and 16px inputs. Added wrapping for controls/financial amounts and horizontal table overflow on mobile.
- Updated chart track and series colors for dark backgrounds. Styled native controls/dialogs and retained focus/reduced-motion behavior.
- Changes apply in expense-tracker - Copy only. No tests, live data changes or Docker commands run.


### Sidebar width adjustment

- Increased React sidebar width approximately 18 percent: 228px to 269px on desktop and mobile drawer; 210px to 248px at the intermediate breakpoint. Updated matching desktop content offsets. Mobile content retains zero offset. No tests or Docker commands run.


### Frontend/backend directory separation

- Moved app/, scripts/, requirements.txt, requirements.sweepr.txt, create_tables.py, test_intent.py, .env, .env.example and Dockerfile into backend/ without changing secret contents.
- Moved app/static/ into frontend/legacy/ so the original dashboard fallback also resides with frontend assets.
- Settings resolves backend/.env relative to config.py instead of the working directory. Existing environment-variable overrides continue to work. Script sys.path roots naturally resolve to backend/ after the move.
- FastAPI resolves sibling frontend/dist/ and frontend/legacy/. No API routes, database schema, auth behavior, financial logic or cache policy changed.
- backend/Dockerfile still uses the project root build context and Node multi-stage build; Python workdir is /app/backend, React build is at /app/frontend/dist, legacy assets at /app/frontend/legacy. Compose specifies the new Dockerfile and backend/.env.
- Added recursive Docker exclusions for nested environment files, bytecode and backend logs. Git ignores secrets while allowing environment examples.
- Root README now explains both applications, startup, scripts, Docker and current paths. Preserved detailed backend instructions in backend/README.md, updated frontend guide and annotated existing shared docs for the new layout.
- Kept root venv in place because moving an existing virtual environment can break absolute paths. Kept project-level docs, context, Compose and diagram at root.
- No regression tests, live provider calls, database changes, container builds, image pushes or deployments were performed for this restructure. Existing running processes must be restarted using the new paths.

- Moved previous GLiNER stdout/stderr logs into ignored backend/logs/. Static Python syntax inspection passed without importing app modules or executing tests; live startup and Docker rebuild remain unverified.


## 25. Full handoff refresh and TanStack explanation — 19 October 2026

- Cross-checked current settings, routes/models, auth lifecycle, Query hooks, API helper and Compose source. Preserved all earlier history and recent change notes.
- Added authoritative section 0 covering the latest folder split, provider roles, feature limits, UI/caching changes, authentication, commands, verification ledger and remaining setup. Flagged superseded early paths/shared-token UI.
- Added docs/TANSTACK_QUERY_EXPLAINED.md: notebook analogy, exact implementation, timing, keys, queries/mutations, invalidation, cancellation/isolation, HTTP-cache distinction, WhatsApp limits and interview preparation.
- Linked the guide from root README, frontend README and project explanation. No application behavior or secret values changed.
- No tests, services, provider calls, database changes, Docker commands or deployments were run for this documentation refresh.

## 26. GitHub-facing README and real interface screenshots — 21 October 2026

- Replaced root README with a public project overview: Ledger/WhatsApp Expense Tracker positioning, feature matrix, six screenshot gallery, stack, provider responsibilities, Mermaid architecture, fresh-clone setup, environment reference, Docker, WhatsApp wiring, sample messages, local development, engineering details, source tree, regression/live checks and explicit limits.
- Captured six real JPEG screenshots from the user's running container at localhost:8000, using only the built-in read-only illustrative preview and blank sign-in form. No real login, financial record changes, provider calls or screenshot mockups. Browser navigation is visual evidence of the running interface, not a full authentication/import regression test.
- Saved images and capture provenance in assets/screenshots/, outside ignored /docs/, so GitHub-relative README images can be committed without changing the user's ignore rule. Existing .gitignore edits and frontend/package-lock.json edits were preserved.
- README links only to tracked frontend/backend guides, not ignored docs. Explained Compose's GLiNER2 override, HTTP/application cache distinction through engineering notes, optional receipt vision, input/CSV/search limits and production privacy requirements. No unsupported license, hosted demo, test count or measured-performance claims added.
- No Docker rebuild/restart, tests, commits, pushes or public publication was performed. Existing container was used as requested. The original project and open resume LaTeX were not edited.
## 27. Example bank-statement CSV — 21 October 2026

- Added backend/examples/bank_statement.csv with five fictional October 2026 INR entries using supported date/description/amount/type/currency/category headers: one salary credit and four expense debits.
- Linked it from the public README with preview/confirmation instructions, fixed-date guidance and clarification that confirming writes fictional records into the signed-in account; design preview imports remain disabled.
- No imports, database writes or tests were performed. Changes left uncommitted and unpushed for the user.