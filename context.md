# Expense Tracker — Codex Handoff Context

Last updated: **17 October 2026**, Asia/Calcutta.

**Latest status:** Jev intent classification is now implemented with configurable
Groq fallback. Extraction stays on Groq. The combined offline suite passes 40 tests.
The user has now verified a real strict-mode Jev call: `month_total`, provider
`jev`, confidence `1.0`, and no fallback. Section 20 records the evidence;
section 19 describes the implementation and supersedes the earlier proposal history.

This document gives another ChatGPT conversation or developer the context needed
to continue this project. It records the requested features, implemented code,
debugging history, tests, configuration changes, limitations, and next steps.
Descriptions below reflect the current source, rather than every intermediate
version of a file. No passwords, access tokens, API keys, or database credentials
are included.

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
