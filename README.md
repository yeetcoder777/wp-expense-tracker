# WhatsApp Expense Tracker

A React dashboard and FastAPI backend for private WhatsApp-linked expense tracking.

## Directory structure

```text
expense-tracker - Copy/
  frontend/                React app, npm dependencies, charts and pages
    src/
    public/
    legacy/                Original dashboard used when React is not built
    package.json
  backend/                 Python application and configuration
    app/                   APIs, services, schemas and database models
    scripts/               Checks, migrations and regression scripts
    .env                   Private configuration (ignored by Git and Docker)
    .env.example           Configuration template
    requirements.txt       Backend and local GLiNER2 dependencies
    requirements.sweepr.txt
    create_tables.py
    test_intent.py
    Dockerfile
    README.md
  docs/                    Shared architecture, model and authentication guides
  compose.yaml             Builds and runs the complete app
  context.md               Full development history and handoff context
  venv/                    Existing local Python environment (ignored)
```

## Run locally

### Backend terminal

From this project's root, activate the existing environment and enter backend/:

```powershell
.\venv\Scripts\Activate.ps1
cd backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Wait for `Application startup complete`. Health: http://127.0.0.1:8000/health

For a fresh environment, run `python -m venv .venv`, activate it, and run
`python -m pip install -r backend/requirements.txt` from the project root.
Copy `backend/.env.example` to `backend/.env` only on a new checkout; do not
overwrite existing credentials. Backend configuration now lives in `backend/.env`.

### Frontend terminal

From this project's root:

```powershell
cd frontend
npm ci
npm run dev
```

Open http://127.0.0.1:5173/ . Vite proxies /api to backend port 8000.
Use the same hostname throughout login. [Frontend setup](frontend/README.md)
explains proxy and origin configuration. Financial data is cached per account
and filters. The read-only preview is available without signing in.

## Docker

Run from the project root:

```powershell
docker compose up -d --build backend
```

Compose uses `backend/Dockerfile` with the project root as its build context,
loads `backend/.env` at runtime, builds React, and serves it through FastAPI on
http://127.0.0.1:8000/ . Backend secrets are excluded from the build context.
The named GLiNER model-cache volume is unchanged. Stop a competing local backend
before using the same host port. No Docker operations were run for this restructure.

For a direct image build use `docker build -f backend/Dockerfile -t expense-tracker:local .`.

## Backend scripts

Python helper commands now run from backend/:

```powershell
cd backend
python scripts/check_whatsapp_connection.py
python scripts/check_intent_classifier.py --strict-jev "How much did I spend this month?"
python scripts/smoke_test_backend.py
```

The smoke command is documented for you to run; it was not executed as part of
the directory move. Keep ngrok pointed at backend port 8000 and Twilio pointed
at the public `/webhook/whatsapp` URL. API paths and database schema are unchanged.

## Guides

- [Backend features, configuration and script reference](backend/README.md)
- [React frontend](frontend/README.md)
- [Technical explanation](docs/PROJECT_EXPLAINED.md)
- [Multi-user dashboards](docs/MULTI_USER_DASHBOARDS.md)
- [Local GLiNER2](docs/LOCAL_GLINER2.md)
- [Complete development context](context.md)

Historical commands in context.md describe earlier layouts; use the current
structure section at the top of that file and this README for startup paths.


## TanStack Query and dashboard caching

Read [TanStack Query explained](docs/TANSTACK_QUERY_EXPLAINED.md) for the notebook analogy, current implementation, technical details and interview preparation.
