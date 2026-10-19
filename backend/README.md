# Expense Tracker backend

Run the Python commands in this guide from `backend/`. The backend reads `backend/.env` independently of the working directory. Docker Compose remains at the project root.

For the full Codex change history, current implementation, setup, tests, and
continuation notes, read [context.md](../context.md).

For a simple technical walkthrough and interview preparation, read
[Project explained](../docs/PROJECT_EXPLAINED.md), including the Jev classifier integration.

A personal expense tracker with a Twilio WhatsApp webhook and individual web
dashboards. Users sign in by sending a one-time command from their own WhatsApp
number. Each browser session can access only that verified number's records.

## React dashboard

A separate React frontend now lives in [`frontend/`](../frontend/README.md), with a
minimal navy, porcelain and muted-brass design, private WhatsApp sign-in, and all
existing dashboard features connected to the API.

```powershell
cd ../frontend
npm ci
npm run dev
```

Open `http://127.0.0.1:5173/` while the backend runs on port 8000. Choose
**Explore a preview** to inspect the read-only illustrative dashboard without
signing in. For the full Docker app, the updated multi-stage backend/Dockerfile builds
React and FastAPI serves it on the existing port after you rebuild the image.
See the [frontend guide](../frontend/README.md) for origin/proxy configuration.

## Individual accounts

Read [Multi-user dashboards and deployment](../docs/MULTI_USER_DASHBOARDS.md) for the
new sign-in flow, additive schema migration, required Twilio configuration,
production database privacy review, and current free hosting options.

The default mode is `DASHBOARD_AUTH_MODE=whatsapp`. Old shared dashboard tokens
are no longer accepted by default. After updating configuration, rebuild the
container with `docker compose -f ../compose.yaml up -d --build backend`.


## Features

- Record expenses and income through WhatsApp, and ask for totals, transaction lists, category totals, and monthly summaries.
- Cancel a pending transaction with `cancel`. Correct records with `edit <id> amount to 500`, `edit <id> date to 2026-10-11`, or `edit <id> category to food`; use `last` instead of an ID. Delete with `delete <id>` or `delete last`; undo with `undo last`.
- Set and inspect monthly budgets through WhatsApp: `Set my food budget to ₹8,000`, `Set my overall budget to ₹20,000`, and `show my budgets`. Budget alerts are returned when a new expense reaches 80% and 100% of a budget.
- Review and edit transactions, view monthly and custom-range reports, compare with the previous calendar month, inspect savings rate and largest expenses, and export transactions as CSV in the dashboard.
- Create weekly, monthly, or yearly recurring items. Choose reminders or automatic transaction recording.
- Preview and import bank statement CSVs and receipt images. CSV rows are reviewed before import and possible duplicates are unchecked by default. Receipt extraction uses a configured vision model and always requires review before import.
- Twilio message IDs are recorded with transactions to prevent webhook retries from creating duplicates. Twilio signatures are required in production when `TWILIO_AUTH_TOKEN` is configured.
- Select Jev or Groq for intent classification. Select local GLiNER2 or Groq for transaction extraction and category classification.

## Local GLiNER2 experiment

The copy now uses `fastino/gliner2-base-v1` locally for transaction extraction,
while Jev handles intent classification. Use your Python 3.12 environment:

```powershell
..\venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Wait for model loading and `Application startup complete`. Stop any existing
server on port 8000 first. See [the local model guide](../docs/LOCAL_GLINER2.md) for
installation, settings, actual test results, WhatsApp examples, and limitations.
The merged `requirements.txt` now contains both backend and local-model
dependencies. The example configuration selects Groq unless changed.

## Setup

Use Python 3.12 (the project venv currently uses 3.12.10).

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
# Only for a new checkout: create .env from .env.example without overwriting existing credentials.
```

Set the required `GROQ_API_KEY` and `DATABASE_URL`. The database tables are created when the app starts; `python create_tables.py` is also available for explicit setup.

Configure `TWILIO_AUTH_TOKEN`, `TWILIO_WHATSAPP_FROM`, and the exact
`TWILIO_WEBHOOK_URL`. Open the dashboard and sign in from your own WhatsApp
number. In production set `ENVIRONMENT=production` and `DASHBOARD_PUBLIC_URL`
to the HTTPS dashboard origin. Existing records retain their WhatsApp user IDs.

For inbound WhatsApp messages, set the Twilio webhook to:

```text
https://<your-host>/webhook/whatsapp
```

Set `TWILIO_AUTH_TOKEN` and the exact public callback URL in `TWILIO_WEBHOOK_URL` to validate signatures. Production mode refuses webhook requests when signature validation has not been configured. To send scheduled WhatsApp reminders, also set `TWILIO_ACCOUNT_SID` and `TWILIO_WHATSAPP_FROM`.

Receipt image import is optional. Set `GROQ_VISION_MODEL` to a vision-capable model available to your Groq account. Without it, bank CSV import and all other features remain available.

## Jev intent classification

The integration uses the official `typesafe-sdk==0.7.5`. Install requirements,
create a key in the [TypeSafe console](https://console.typesafe.ai/), and set:

```dotenv
INTENT_CLASSIFIER=jev
TYPESAFE_API_KEY=your_typesafe_key
JEV_MODEL=jev-1.14.0
JEV_TIMEOUT_SECONDS=4
JEV_MIN_CONFIDENCE=0.6
JEV_FALLBACK_TO_GROQ=true
```

Restart the backend after editing `.env`. The code defaults to Groq if no provider
is configured; the supplied example selects Jev. A blank TypeSafe key with fallback
enabled uses Groq, so that configuration does not prove a live Jev integration call.

Jev selects among the existing 21 intent labels. It does not extract arbitrary
amounts, descriptions, or receipt fields in this application. Groq remains required
for those operations and category/time-range extraction. Explicit commands and
pending conversation answers bypass AI intent classification.

Missing keys, SDK errors/timeouts, invalid responses, and confidence below the
configured minimum fall back to Groq. Set `JEV_FALLBACK_TO_GROQ=false` to decline
with the `unknown` route instead. The 0.6 threshold is a configurable starting
policy, not a measured accuracy guarantee. SDK retries are disabled for this call;
the timeout controls HTTP operations. Classification runs in FastAPI's threadpool.

To verify a real Jev call with fallback disabled, from the project root run:

```powershell
python scripts/check_intent_classifier.py --strict-jev "How much did I spend this month?"
```

This sends the supplied text to the provider but writes no database records.
Expect `provider: "jev"` and a supported label such as `month_total`. A missing
key or declined response exits nonzero with a reason, rather than disguising a
Groq fallback as Jev success. Credentials should be edited locally, not pasted
into chat. For an offline check, run the full smoke suite or:

```powershell
python scripts/test_intent_classifier.py
```

References: [official SDK](https://docs.typesafe.ai/sdk/python),
[Choice](https://docs.typesafe.ai/primitives/choice),
[confidence](https://docs.typesafe.ai/confidence).

Reports keep currencies separate; the app does not convert between currencies. Receipt uploads are reviewed in the dashboard before they are saved. WhatsApp image messages are directed to the dashboard instead of being imported automatically.

The recurring-payment worker starts with the FastAPI application and checks schedules every minute. PostgreSQL row locks prevent multiple app workers from processing the same schedule at once; for SQLite, run one app worker.

Start the app:

```powershell
python -m uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000/` for the dashboard. API documentation is available at `/docs`.

## Troubleshooting WhatsApp delivery

Keep the backend and `ngrok http 8000` running in separate terminals. Then run:

```powershell
python scripts/check_whatsapp_connection.py
```

This checks the local route, discovers the current ngrok HTTPS URL, prints the
complete callback to save in Twilio, and checks public backend health. It does
not send a WhatsApp message or create a transaction. Set the printed callback
in Twilio's incoming-message webhook field using POST. The `.env` setting
`TWILIO_WEBHOOK_URL` is used for signature verification; it does not configure
Twilio's callback. If ngrok shows no incoming WhatsApp POST, check the callback
on the correct sender or Sandbox and confirm your phone has joined that Sandbox.

The backend logs `Webhook arrived` before form and signature validation, followed
by the HTTP status. A 403 indicates signature rejection; a 422 indicates missing
or invalid form fields. Neither status means the request failed to reach the app.

Run the isolated backend regression checks with:

```powershell
python scripts/smoke_test_backend.py
```

These use a temporary SQLite database and simulated Groq responses. The suite checks
expense/income entry, multiple entries, missing-purpose follow-ups, cancellation,
edits, deletion, undo, invalid inputs, budgets and threshold alerts, date-based
queries, income queries, monthly summaries, category queries, currency separation,
user isolation, webhook retries, media guidance, signature validation, and database
driver selection. It does not contact Twilio or modify your real database, and does
not measure live Groq intent/extraction accuracy or actual WhatsApp delivery.
The combined suite now has 40 tests, including Jev SDK transport/response checks,
confidence boundaries, configuration validation, failure fallback/strict mode,
and webhook tests proving that Groq still extracts fields while reports can use
Jev intent routing followed by SQL alone. No real provider APIs are called by tests.

## Bank CSV format

The importer recognizes common header names for date, description, amount, debit, credit, type, currency, category, and person. A basic file can use:

```csv
date,description,amount,type,currency,category
2026-10-01,Groceries,1250.00,debit,INR,food
2026-10-05,Salary,65000.00,credit,INR,salary
```

If a single amount column has no type, rows default to expenses. For income, include a type column (`credit`/`income`) or separate credit and debit columns. Dates accept ISO format and common day/month/year formats.

## Application layout

- `app/api/`: WhatsApp webhook and dashboard API routes.
- `app/services/`: transaction, report, budget, import, notification, and recurring-payment logic.
- `app/db/`: SQLAlchemy models and database session setup.
- `../frontend/legacy/`: original dashboard fallback assets.
