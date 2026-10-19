> **Directory update:** Python source, scripts, requirements and private configuration now live in `backend/`. Run Python commands below from `backend/`; the existing `venv` is at the project root. Read the [current startup guide](../README.md) first. References to the old root `.env` mean `backend/.env`. Docker Compose runs from the project root and uses `backend/Dockerfile`. Older sections are retained as historical context.

# Individual dashboards and deployment

Implemented in `expense-tracker - Copy`, 18 October 2026.

## User experience

Everyone uses the same dashboard URL and the same WhatsApp bot number. Their
records are selected from their verified WhatsApp identity, not a URL parameter.

1. Open the dashboard and enter your own international WhatsApp number.
2. The dashboard creates a short-lived login command, such as `login ABCD...`.
3. Click **Open WhatsApp**, then send that command from the entered number.
4. The signed Twilio webhook approves the request. Return to the original browser.
5. The browser obtains a private, expiring session and loads only your records.
6. Use **Sign out** when finished. Signing out revokes that browser session.

There are no shared dashboard tokens, passwords, email setup, or separate user
Twilio accounts. Sandbox users must first join your Sandbox. Public users message
your registered production business sender. Never send a login code provided by
someone else; only approve a code requested in your own browser.

## Schema and compatibility

Three additive tables:

| Table | Contents |
| --- | --- |
| `dashboard_users` | UUID account ID and unique verified WhatsApp identity |
| `dashboard_login_challenges` | Expected phone, hashed code/browser proof, expiry, approval and consumption |
| `dashboard_sessions` | Hashed opaque session token, account FK and expiry |

Existing transactions, budgets, recurring schedules, imports, and conversations
keep their existing `whatsapp:+...` user IDs. No financial rows are rewritten or
assigned to a new owner. A first verified login creates the account and shows
that number's existing history. Account IDs are not accepted from the browser
as authority to access another user's records.

Authentication uses a random browser-only polling secret separate from the
command sent through WhatsApp. Knowing a command alone cannot claim its browser
session. Approval requires both the expected sender number and a valid Twilio
signature, even in development. Codes expire after five minutes by default and
can be claimed once. Sessions expire after 24 hours by default.

Sessions use HttpOnly, SameSite=Strict cookies. Secure cookies are automatic in
production. Financial writes require a custom request header and validate the
browser Origin when present. API responses are not cached; account changes abort
requests and clear displayed data/import previews. A response account marker
prevents rendering another tab's newly selected account into stale dashboard state.

Login creation is limited by phone, request address, and global database counts.
These are best-effort limits, not an atomic distributed rate limiter; add edge
rate limiting for larger traffic. Proxy clients may share an address. The browser
never stores the opaque session token in localStorage/sessionStorage.

## Configuration

Keep existing Jev, Groq, database, and Twilio credentials. Add/select:

```dotenv
DASHBOARD_AUTH_MODE=whatsapp
DASHBOARD_SESSION_HOURS=24
DASHBOARD_LOGIN_MINUTES=5
TWILIO_WHATSAPP_FROM=whatsapp:+YOUR_BOT_NUMBER
TWILIO_WEBHOOK_URL=https://YOUR_HOST/webhook/whatsapp
```

`TWILIO_AUTH_TOKEN` is required for login. It is the Twilio account auth token
used to validate incoming signatures; do not paste it into a browser or docs.
The configured bot number must be the same one users actually message.

For public hosting:

```dotenv
ENVIRONMENT=production
DASHBOARD_PUBLIC_URL=https://YOUR_HOST
```

Use HTTPS. `DASHBOARD_PUBLIC_URL` is the dashboard origin, without the webhook
path. Configure the exact webhook URL in Twilio using POST. Preserve correct
proxy host/scheme forwarding. Keep backend and dashboard on the same origin;
this implementation intentionally has no permissive cross-origin API access.

`DASHBOARD_API_TOKEN` and `DASHBOARD_USER_ID` are deprecated. They are ignored
in the default WhatsApp mode. Explicit `DASHBOARD_AUTH_MODE=legacy` supports old
local API tooling only; production refuses that mode. The new browser interface
uses WhatsApp sign-in, not the compatibility token flow.

## Apply the update yourself

Use your existing Python 3.12.10 `venv` and merged `requirements.txt`. No new
third-party authentication dependency is needed.

From `expense-tracker - Copy`:

```powershell
python scripts/migrate_dashboard_accounts.py
```

This creates missing tables and protects only the three new authentication
tables on PostgreSQL. It does not rewrite financial records. The backend performs
the same additive setup at startup, before model loading. Use a backend database
role that owns the tables; with Supabase, keep the server-only database URL and
its correct Session pooler credentials.

Then rebuild and replace the Docker container:

```powershell
docker compose up -d --build backend
docker compose logs -f backend
```

Open the dashboard and follow the WhatsApp sign-in instructions. An existing
Docker Hub `v1` image still contains the old application; publish a new image/tag
when you choose to distribute the update.

### Supabase table privacy requires an operator review

New auth tables have RLS enabled and public/anon/authenticated grants revoked.
Existing financial table permissions are deliberately unchanged. Automatic
approval review rejected a broader permission rewrite because other clients
could depend on those existing grants.

Production performs a read-only audit of existing financial tables. It stops if
Supabase browser roles have access without RLS, or existing policies make privacy
ambiguous. This is a conservative guard, not a complete authorization proof.
If it stops, review the listed tables and any other apps using them before
approving a separate permission migration. Do not disable the guard to launch.
No live migration, existing-table permission change, Docker build, deployment,
or authentication test was run during this implementation.

## Free hosting options checked on 18 October 2026

### Keeping local GLiNER2: evaluate Oracle Cloud Always Free

Oracle currently documents an Ampere A1 allowance of 1,500 OCPU-hours and
9,000 GB-hours monthly, equivalent to **2 OCPUs and 12 GB RAM** for Always Free
tenancies, plus an Always Free storage allowance. This is a plausible starting
point for this CPU model; actual latency and concurrency need evaluation.

Select only resources marked Always Free within your account's current limits.
Capacity is not guaranteed, and idle instances may be reclaimed. You manage the
VM, updates, reverse proxy, HTTPS, volumes, and backups yourself. This is not a
managed hosting SLA.

A1 uses ARM64. Your Windows-built image is likely AMD64, so build for ARM64 or
build on the VM; do not assume the current Docker Hub tag runs natively there.
All pinned ML dependencies need ARM-compatible wheels or a supported build.
Architecture compatibility has not been verified here.

Suggested layout: HTTPS reverse proxy -> one Docker backend -> Supabase Session
pooler, with a persistent `/models` volume and runtime secrets. Point Twilio at
`https://YOUR_HOST/webhook/whatsapp`. Set GLiNER2 CPU threads to suit the VM.

Source: https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm

### Render Free: a hosted-extraction demo alternative

Render Free currently has **512 MB RAM** and **0.1 CPU**. That is insufficient
for this GLiNER2 configuration. Its web services sleep after 15 minutes without
traffic and do not support persistent disks. Sleeping also stops the application's
recurring worker and adds cold-start delay to webhook requests.

You could evaluate Render for a small demo with `EXTRACTION_PROVIDER=groq`, no
local-model preload, and Supabase storage. It still needs a memory/build/startup
check and is unsuitable for reliable scheduled reminders. Platform port binding
must follow Render's service configuration.

Sources: https://render.com/docs/compute-plans and https://render.com/docs/free

### Hugging Face Spaces is not an unrestricted free Docker host

Current documentation says creating Docker/Gradio compute Spaces requires a
paid plan. Free Static Spaces cannot run this backend. Do not rely on older
advice describing free Docker Spaces for every account.

Source: https://huggingface.co/docs/hub/spaces-overview

### Hosting cost is separate from messaging cost

Free compute does not make a public WhatsApp service completely free. Twilio
WhatsApp messaging is billed, and Jev/Groq/database services have their own
quotas or charges. Scheduled outbound messages outside WhatsApp's service window
need approved templates and consent; this account update does not implement a
new durable reminder/template system.

Sources: https://www.twilio.com/en-us/whatsapp/pricing and https://www.twilio.com/docs/whatsapp/quickstart

## Validation boundary

Source was reviewed; `git diff --check` was used for patch whitespace. No tests
were added or run in this turn. The previous 59-pass result predates this auth
change and must not be presented as coverage of the new login flow. Before public
use, verify two real accounts, wrong-number/replayed/expired codes, forged webhook
rejection, session expiry/logout, cross-user record access, and account changes
across tabs. Also evaluate costs, rate limits, model accuracy, and concurrent load.


## Phone field appears to reject typing

A frontend reset loop was corrected on 18 October 2026. Account cleanup used to
reset transaction filters, whose reset handler fetched data while signed out and
reopened/reset login after a 401. Cleanup now suppresses those requests and login
preserves typed phone input on repeated errors. Rebuild the container and hard
refresh (Ctrl+Shift+R) to load the correction. The fix does not disable sign-in.
