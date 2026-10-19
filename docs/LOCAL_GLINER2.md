> **Directory update:** Python source, scripts, requirements and private configuration now live in `backend/`. Run Python commands below from `backend/`; the existing `venv` is at the project root. Read the [current startup guide](../README.md) first. References to the old root `.env` mean `backend/.env`. Docker Compose runs from the project root and uses `backend/Dockerfile`. Older sections are retained as historical context.

# Local GLiNER2 experiment

Implemented on 18 October 2026 in **expense-tracker - Copy**.

**Current setup update:** the user removed Python 3.15, created a Python 3.12.10
`venv`, and merged dependencies into `requirements.txt`. The separate
`.venv-gliner`/`requirements.local.txt` setup described in the installation history
below is no longer required. Use `venv` and the merged requirements. Dashboard
access now uses [individual WhatsApp sign-in](MULTI_USER_DASHBOARDS.md).

## What runs where?

```text
WhatsApp -> Twilio -> FastAPI
  -> existing commands / pending follow-up handling
  -> Jev intent classification (remote API)
  -> transaction intent: GLiNER2 (local CPU)
       -> amount, purpose, person, date, currency entities
       -> income/expense and spending category classification
       -> deterministic normalization + Pydantic validation
       -> existing transaction/budget services -> database
  -> report intent: existing report flow
  -> TwiML response -> Twilio -> WhatsApp
```

GLiNER2 is a 205M parameter encoder from Hugging Face:
[fastino/gliner2-base-v1](https://huggingface.co/fastino/gliner2-base-v1).
The supported Python API is `gliner2.AutoExtractor`; it uses PyTorch,
Transformers, and Hugging Face downloads underneath. This implementation uses
that API instead of an ordinary `transformers.pipeline` task.

No fine tuning was performed. Entity descriptions and fixed category labels
define a zero-shot schema. Model confidence is a filter, not proof of correctness.

Only transaction field extraction and category classification move locally.
Jev still receives message text for intent classification. Existing category
query parsing, some report parsing, receipt vision, and configured fallback
paths can still use Groq. This is not a completely offline WhatsApp app.

## Environment and startup

The old `venv` uses Python 3.15, for which compatible PyTorch wheels were not
available during setup. A separate **Python 3.12.10** environment was installed
as `.venv-gliner`. The existing environment was retained.

From `D:\Siddhesh\Projects\expense-tracker - Copy`:

```powershell
.\venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Stop an existing server using port 8000 first. If using another port, point ngrok
at that same port. Prefer one server process: each worker/reloader can load a
separate copy of the model into RAM.

Initial installation on another machine:

```powershell
py install 3.12
py -3.12 -m venv .venv-gliner
.\.venv-gliner\Scripts\python.exe -m pip install --upgrade pip
.\.venv-gliner\Scripts\python.exe -m pip install torch --index-url https://download.pytorch.org/whl/cpu
.\.venv-gliner\Scripts\python.exe -m pip install -r requirements.local.txt
```

`py install` requires the Python install manager; otherwise install Python 3.12
using python.org before creating the environment.

The copy's `.env` now selects:

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

On a fresh machine, temporarily set `GLINER2_LOCAL_FILES_ONLY=false` for the first
download. The model is cached under the user's Hugging Face cache, outside Git.
Afterward, true loads the pinned cached snapshot. No Hugging Face key is required
for this public model. Model files use safetensors; no remote model code is enabled.

The backend loads the model during startup, before accepting requests. Expect a
loading delay and wait for `Application startup complete`. Inference runs in a
thread pool, with a lock around the shared model. Four CPU threads are configured.
The inference lock serializes local model requests; this is a small development
deployment, not a load-tested concurrent inference server.

To revert, set `EXTRACTION_PROVIDER=groq` and restart. To explicitly permit cloud
extraction after a local error, set `GLINER2_FALLBACK_TO_GROQ=true` and restart.
With false, ambiguous/local-failure entries return clarification instead of
silently calling Groq or saving a partial transaction batch.

## Test commands

```powershell
python scripts/test_local_extractor.py
python scripts/smoke_test_backend.py
python scripts/check_local_extractor.py "Spent 250 INR on coffee yesterday" --repeat 3
python scripts/check_local_extractor.py --webhook --live-intent "I spent 250 INR on coffee"
python scripts/check_whatsapp_connection.py
```

Run these using your current Python 3.12 `venv`. The local regression tests use fabricated model
responses and do not load weights. The last extractor command uses **real Jev**,
**real GLiNER2**, and an isolated temporary SQLite database. It verifies saved
fields and duplicate delivery protection. Without `--live-intent`, the webhook
checker simulates only the intent decision. Neither mode sends a WhatsApp message
or writes to your real database. Every new CLI process loads the model again;
`--repeat` shows subsequent inference within one process.

For the phone test, keep the backend and `ngrok http 8000` running. Configure the
printed public `/webhook/whatsapp` callback in Twilio using POST. Send:

```text
I spent ₹250 on coffee
Received ₹65,000 salary
Spent ₹250 on coffee yesterday
Paid ₹1,200 for electricity on 15 October 2026
Paid 300 INR for Uber today
```

For two entries, put the coffee and salary sentences on **separate lines** in
one message. Then try `list transactions`, `undo last`, and `cancel` after an
incomplete entry. Actual phone messages create real records, so use undo/delete
when finished. Logs show `Transaction extraction: provider=gliner2` and inference
time. They should not show extraction fallback with the strict local setting.

## Observed results and limits

- The initial coffee run took about 20.1 seconds including imports/model loading;
  its next run took **538 ms** on this machine. This is a single example, not a
  benchmark or a promise about total WhatsApp response time.
- Real extraction correctly handled coffee, salary, yesterday, a full calendar
  date, groceries, Uber, and a two-line coffee/salary batch in manual checks.
- `Paid ₹100` returned a missing purpose, allowing the existing follow-up flow.
- Two separate monetary amounts on one line were rejected rather than guessed.
- Real Jev + local GLiNER2 webhook checks saved coffee and a two-line expense/
  income batch correctly. Replaying each MessageSid did not add duplicates.
- Cold webhook tests took about 15–19 seconds, including local model load. The
  running backend preloads the model so phone requests avoid this specific cost.
- 40 existing smoke tests and 19 local extractor regression tests passed;
  `pip check` found no broken requirements in the new environment.
- Local request and public tunnel health checks passed. These do not establish
  an actual incoming phone message or Twilio delivery.

Use explicit positive numeric amounts (up to two decimal places), English
messages, and one transaction per line or semicolon. Up to 20 lines of 500
characters are accepted. Amounts like `2k`, mixed currencies, multiple numeric
values outside dates, and uncertain income/expense classification are rejected.
Supported explicit currencies are INR, USD, EUR, and GBP; omitted currency defaults
to INR. Numeric dates use day/month/year. Relative dates use Asia/Kolkata.
Category confidence below the configured threshold becomes `other`.

This is an evaluation integration. Wording outside the checked examples can
still be misinterpreted. Span checks prove text provenance, not that the model
selected the correct meaning. Keep reviewing records and collect representative
English/Hinglish examples before judging accuracy against Groq.

Sources: [official model card](https://huggingface.co/fastino/gliner2-base-v1),
[official package and local installation guide](https://github.com/fastino-ai/GLiNER2).
