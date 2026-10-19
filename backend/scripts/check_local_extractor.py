"""Run real local inference; optionally exercise the webhook with a temporary database."""

import argparse
from contextlib import ExitStack
import json
import os
from pathlib import Path
import sys
import tempfile
from time import perf_counter
from unittest.mock import patch
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("message", nargs="?", default="I spent 250 INR on coffee")
    parser.add_argument("--webhook", action="store_true", help="Use FastAPI with an isolated temporary database")
    parser.add_argument("--live-intent", action="store_true", help="Also call real Jev in webhook mode (sends text to Jev)")
    parser.add_argument("--repeat", type=int, choices=range(1, 11), default=2, help="Observe first-use and warm inference timings")
    args = parser.parse_args()
    if args.live_intent and not args.webhook:
        parser.error("--live-intent requires --webhook")
    with tempfile.TemporaryDirectory(prefix="gliner-webhook-") as temporary:
        if args.webhook:
            os.environ.update(DATABASE_URL="sqlite:///" + (Path(temporary) / "test.db").as_posix(),
                              TWILIO_AUTH_TOKEN="", TWILIO_ACCOUNT_SID="", TWILIO_WHATSAPP_FROM="")
        from app.config import settings
        settings.extraction_provider = "gliner2"
        settings.gliner2_fallback_to_groq = False
        if args.live_intent:
            settings.intent_classifier = "jev"
            settings.jev_fallback_to_groq = False
            if not (settings.typesafe_api_key or "").strip():
                print("Live intent check needs TYPESAFE_API_KEY.", file=sys.stderr)
                return 1
        from app.services.transaction_extraction_service import extract_transactions
        if not args.webhook:
            for attempt in range(args.repeat):
                started = perf_counter()
                try:
                    rows = extract_transactions(args.message)
                except Exception as exc:
                    print(f"Local extraction failed ({type(exc).__name__}): {exc}", file=sys.stderr)
                    return 1
                print(json.dumps({"provider": "gliner2", "attempt": attempt + 1,
                                  "elapsed_ms": round((perf_counter() - started) * 1000, 1),
                                  "transactions": [row.model_dump(mode="json") for row in rows]}, ensure_ascii=False))
            return 0

        from fastapi.testclient import TestClient
        from app.main import app
        from app.db.database import Base, engine, SessionLocal
        from app.db.models import TransactionDB
        Base.metadata.create_all(engine)
        try:
            with ExitStack() as stack:
                client = TestClient(app)  # No lifespan worker or outbound reminders.
                stack.callback(client.close)
                if not args.live_intent:
                    stack.enter_context(patch("app.api.webhook.detect_intent", return_value="transaction"))
                stack.enter_context(patch("app.services.llm_service.client.chat.completions.create", side_effect=AssertionError("Unexpected Groq call")))
                sid = "SM" + uuid4().hex
                data = {"Body": args.message, "From": "whatsapp:+10000000000", "MessageSid": sid}
                started = perf_counter()
                response = client.post("/webhook/whatsapp", data=data)
                elapsed = round((perf_counter() - started) * 1000, 1)
                retried = client.post("/webhook/whatsapp", data=data)
                with SessionLocal() as db:
                    rows = db.query(TransactionDB).order_by(TransactionDB.id).all()
                    result = [{"amount": str(row.amount), "type": row.transaction_type,
                               "purpose": row.purpose, "category": row.category,
                               "date": row.transaction_date.isoformat()} for row in rows]
                print(json.dumps({"http_status": response.status_code, "reply": response.text,
                                  "elapsed_ms": elapsed, "intent": "live_jev" if args.live_intent else "simulated_transaction",
                                  "extractor": "real_local_gliner2", "saved_test_rows": result,
                                  "duplicate_blocked": "already processed" in retried.text}, ensure_ascii=False))
                return int(not result or response.status_code != 200 or "already processed" not in retried.text)
        finally:
            engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
