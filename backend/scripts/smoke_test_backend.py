"""Run: python scripts/smoke_test_backend.py

Exercises WhatsApp message flows through FastAPI and a temporary SQLite database.
Groq intent/extraction results are simulated; no live LLM or Twilio calls are made.
The running backend and its database are untouched. Exit code is nonzero on failure.
Use unittest's -v/-q flags or a test name to select output/detail and individual tests.
"""

import json
import io
from contextlib import ExitStack, redirect_stdout
from datetime import timedelta
from decimal import Decimal
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from uuid import uuid4
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
temporary = tempfile.TemporaryDirectory(prefix="expense-smoke-")
os.environ.update(
    DATABASE_URL="sqlite:///" + (Path(temporary.name) / "test.db").as_posix(),
    GROQ_API_KEY="test-key",
    TWILIO_AUTH_TOKEN="",
    TWILIO_ACCOUNT_SID="",
    TWILIO_WHATSAPP_FROM="",
    TWILIO_WEBHOOK_URL="",
    ENVIRONMENT="development",
    DASHBOARD_API_TOKEN="smoke-dashboard-token",
    DASHBOARD_USER_ID="whatsapp:+10000000000",
    INTENT_CLASSIFIER="groq",
    TYPESAFE_API_KEY="",
    EXTRACTION_PROVIDER="groq",
    DASHBOARD_AUTH_MODE="legacy",
)

from fastapi.testclient import TestClient
from twilio.request_validator import RequestValidator
from app.config import settings
from app.main import app
from app.db.database import Base, engine, SessionLocal, database_url_with_driver
from app.db.models import TransactionDB, ConversationState
from app.services import llm_service
from app.services.date_service import get_today, get_last_month_range
from app.services.transaction_service import save_transaction
from app.schemas.transaction import Transaction
from test_intent_classifier import IntentClassifierTests

ITEMS = [
    dict(transaction_type="expense", amount=250, currency="INR", purpose="coffee", category="food"),
    dict(transaction_type="income", amount=65000, currency="INR", purpose="salary", category="salary"),
]


class WebhookRegressionTests(unittest.TestCase):
    sender = "whatsapp:+10000000000"

    def test_jev_classification_keeps_groq_field_extraction(self):
        from app.services.intent_classifier_service import IntentClassification
        result = IntentClassification(label="transaction", provider="jev", confidence=0.9)
        response = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps({"transactions": [ITEMS[0]]})))])
        with patch.object(settings, "intent_classifier", "jev"), patch.object(settings, "typesafe_api_key", "test"), \
             patch("app.services.intent_classifier_service._classify_with_jev", return_value=result) as jev, \
             patch.object(llm_service.client.chat.completions, "create", return_value=response) as groq:
            received = self.client.post("/webhook/whatsapp", data={"From": self.sender, "Body": "I spent 250 on coffee", "MessageSid": "SM-jev-entry"})
        self.assertEqual(received.status_code, 200)
        self.assertIn("Recorded INR 250.00", received.text)
        self.assertEqual(self.count(), 1)
        jev.assert_called_once()
        groq.assert_called_once()

    def test_jev_report_classification_uses_sql_without_groq(self):
        from app.services.intent_classifier_service import IntentClassification
        self.seed()
        result = IntentClassification(label="month_total", provider="jev", confidence=0.9)
        with patch.object(settings, "intent_classifier", "jev"), patch.object(settings, "typesafe_api_key", "test"), \
             patch("app.services.intent_classifier_service._classify_with_jev", return_value=result), \
             patch.object(llm_service.client.chat.completions, "create") as groq:
            response = self.client.post("/webhook/whatsapp", data={"From": self.sender, "Body": "This month's spending?"})
        self.assertIn("INR 250.00", response.text)
        groq.assert_not_called()

    def test_dashboard_import_reports_edit_export_and_delete(self):
        headers = {"Authorization": "Bearer smoke-dashboard-token"}
        self.assertEqual(self.client.get("/").status_code, 200)
        self.assertEqual(self.client.get("/api/transactions").status_code, 401)
        budget = self.client.post("/api/budgets", headers=headers, json={"category": "food", "amount": 1000, "currency": "INR"})
        self.assertEqual(budget.status_code, 200, budget.text)
        day = get_today().isoformat()
        csv = f"date,description,amount,type,currency,category\n{day},coffee,250,debit,INR,food\n{day},salary,65000,credit,INR,salary\n"
        preview = self.client.post("/api/imports/csv/preview", headers=headers, files={"file": ("sample.csv", csv, "text/csv")})
        self.assertEqual(preview.status_code, 200, preview.text)
        payload = {"transactions": preview.json()["transactions"], "source_name": "sample.csv"}
        first = self.client.post("/api/imports/confirm", headers=headers, json=payload)
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(first.json()["imported"], 2)
        second = self.client.post("/api/imports/confirm", headers=headers, json=payload)
        self.assertEqual(second.json()["skipped_duplicates"], 2)
        report = self.client.get("/api/reports/range", headers=headers, params={"start_date": day, "end_date": day})
        self.assertEqual(report.status_code, 200, report.text)
        self.assertEqual(float(report.json()["expenses"]), 250)
        self.assertEqual(float(report.json()["income"]), 65000)
        self.assertEqual(self.client.get("/api/reports/monthly", headers=headers).status_code, 200)
        rows = self.client.get("/api/transactions", headers=headers).json()
        expense = next(row for row in rows if row["transaction_type"] == "expense")
        path = f"/api/transactions/{expense['id']}"
        changed = self.client.patch(path, headers=headers, json={"amount": 300})
        self.assertEqual(changed.status_code, 200, changed.text)
        self.assertEqual(float(changed.json()["amount"]), 300)
        exported = self.client.get("/api/transactions/export/csv", headers=headers)
        self.assertEqual(exported.status_code, 200, exported.text)
        self.assertIn("coffee", exported.text)
        self.assertEqual(self.client.delete(path, headers=headers).status_code, 200)
        self.assertEqual(self.client.post("/api/transactions/undo", headers=headers).status_code, 200)
        self.assertEqual(self.count(), 0)

    def test_recurring_payment_records_once(self):
        from app.services.recurring_service import process_recurring_payments
        headers = {"Authorization": "Bearer smoke-dashboard-token"}
        response = self.client.post("/api/recurring", headers=headers, json={
            "name": "Test rent", "amount": 50, "currency": "INR", "interval": "monthly",
            "next_run_date": get_today().isoformat(), "auto_record": True,
        })
        self.assertEqual(response.status_code, 200, response.text)
        with patch("app.services.recurring_service.send_whatsapp_message", return_value=True), SessionLocal() as db:
            process_recurring_payments(db, get_today())
            process_recurring_payments(db, get_today())
        self.assertEqual(self.count(), 1)
        payment_id = response.json()["id"]
        self.assertEqual(self.client.patch(f"/api/recurring/{payment_id}", headers=headers, json={"is_active": False}).status_code, 200)
        self.assertEqual(self.client.delete(f"/api/recurring/{payment_id}", headers=headers).status_code, 200)

    def test_receipt_requires_review_before_recording(self):
        headers = {"Authorization": "Bearer smoke-dashboard-token"}
        extracted = Transaction(**ITEMS[0], transaction_date=get_today())
        with patch("app.api.imports.extract_receipt_transactions", return_value=[extracted]):
            response = self.client.post("/api/imports/receipt/preview", headers=headers,
                                        files={"file": ("receipt.png", b"mock image", "image/png")})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(response.json()["review_required"])
        self.assertEqual(self.count(), 0)
        confirmation = self.client.post("/api/imports/confirm", headers=headers, json={"transactions": response.json()["transactions"]})
        self.assertEqual(confirmation.status_code, 200, confirmation.text)
        self.assertEqual(self.count(), 1)

    def send_message(self, message, *, intent=None, items=None, category=None,
                     sender=None, sid=None, extra=None):
        """Exercise the real HTTP handler, mocking only language-model results."""
        data = {"From": sender or self.sender, "Body": message,
                "MessageSid": sid or "SM" + uuid4().hex}
        data.update(extra or {})
        with ExitStack() as stack:
            stack.enter_context(redirect_stdout(io.StringIO()))
            detect = stack.enter_context(patch("app.api.webhook.detect_intent"))
            if intent is None:
                detect.side_effect = AssertionError("This command should not need intent detection")
            else:
                detect.return_value = intent
            completion = stack.enter_context(patch.object(llm_service.client.chat.completions, "create"))
            if items is None:
                completion.side_effect = AssertionError("Unexpected model request")
            else:
                completion.return_value = SimpleNamespace(choices=[SimpleNamespace(
                    message=SimpleNamespace(content=json.dumps({"transactions": items})))])
            if category is not None:
                for name in ("extract_category_query", "extract_category_list_query"):
                    stack.enter_context(patch("app.api.webhook." + name, return_value=category))
            response = self.client.post("/webhook/whatsapp", data=data)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIn("xml", response.headers["content-type"])
        reply = "\n".join(ElementTree.fromstring(response.text).itertext())
        self.assertNotIn("Sorry, I couldn't process", reply, f"Message failed: {message}")
        return reply

    def seed(self, *, sender=None, day=None, **values):
        payload = dict(ITEMS[0], transaction_date=day or get_today())
        payload.update(values)
        with SessionLocal() as db:
            return save_transaction(db, sender or self.sender, Transaction(**payload)).id

    def row(self, transaction_id):
        with SessionLocal() as db:
            return db.get(TransactionDB, transaction_id)

    def count(self):
        with SessionLocal() as db:
            return db.query(TransactionDB).count()

    def test_individual_expense_and_income_messages(self):
        for message, item in zip(("I spent ₹250 on coffee", "Received ₹65000 salary"), ITEMS):
            reply = self.send_message(message, intent="transaction", items=[item])
            self.assertIn("Recorded INR", reply)
        with SessionLocal() as db:
            rows = db.query(TransactionDB).order_by(TransactionDB.id).all()
            self.assertEqual([r.amount for r in rows], [Decimal("250"), Decimal("65000")])
            self.assertEqual([r.transaction_type for r in rows], ["expense", "income"])

    def test_missing_purpose_followup(self):
        reply = self.send_message("Spent ₹100", intent="transaction", items=[dict(ITEMS[0], amount=100, purpose=None)])
        self.assertIn("What was the purpose?", reply)
        self.assertEqual(self.count(), 0)
        self.assertIn("for tea", self.send_message("tea"))
        self.assertEqual(self.count(), 1)
        with SessionLocal() as db:
            self.assertEqual(db.query(ConversationState).count(), 0)

    def test_cancel_pending_entry(self):
        self.send_message("Spent ₹100", intent="transaction", items=[dict(ITEMS[0], amount=100, purpose=None)])
        self.assertIn("Cancelled", self.send_message("cancel"))
        self.assertEqual(self.count(), 0)
        self.assertIn("no pending transaction", self.send_message("cancel"))
        with SessionLocal() as db:
            self.assertEqual(db.query(ConversationState).count(), 0)

    def test_incomplete_batch_saves_nothing(self):
        reply = self.send_message("Spent ₹100. Received ₹65000 salary", intent="transaction",
                                  items=[dict(ITEMS[0], purpose=None), ITEMS[1]])
        self.assertIn("separate message", reply)
        self.assertEqual(self.count(), 0)

    def test_edit_amount_date_category_and_purpose(self):
        transaction_id = self.seed()
        edits = [("amount", "300", Decimal("300")),
                 ("date", get_today().isoformat(), get_today()),
                 ("category", "transport", "transport"),
                 ("purpose", "bus fare", "bus fare")]
        for field, value, expected in edits:
            with self.subTest(field=field):
                self.assertIn("Updated transaction", self.send_message(f"edit last {field} to {value}"))
                attr = "transaction_date" if field == "date" else field
                self.assertEqual(getattr(self.row(transaction_id), attr), expected)
        self.assertIn("Updated transaction", self.send_message(f"edit {transaction_id} amount to 500"))
        self.assertEqual(self.row(transaction_id).amount, Decimal("500"))

    def test_invalid_edits_preserve_data(self):
        transaction_id = self.seed()
        for command in ("edit last amount to -1", "edit last amount to 0",
                        "edit last amount to 1.234", "edit last date to 2026-02-30"):
            with self.subTest(command=command):
                self.assertIn("invalid", self.send_message(command))
                self.assertEqual(self.row(transaction_id).amount, Decimal("250"))
                self.assertEqual(self.row(transaction_id).transaction_date, get_today())

    def test_delete_and_undo(self):
        for command in ("delete last", "undo last", "delete {id}"):
            with self.subTest(command=command):
                transaction_id = self.seed()
                reply = self.send_message(command.format(id=transaction_id))
                self.assertTrue("Deleted" in reply or "Undid" in reply)
                self.assertIsNone(self.row(transaction_id))
        self.assertIn("no transaction to undo", self.send_message("undo last"))
        self.assertIn("couldn't find", self.send_message("delete 999999"))

    def test_command_retry_does_not_delete_another_entry(self):
        first = self.seed()
        second = self.seed()
        sid = "SM" + uuid4().hex
        self.send_message(f"delete {first}", sid=sid)
        self.assertIn("already processed", self.send_message(f"delete {first}", sid=sid))
        self.assertIsNotNone(self.row(second))
        self.assertEqual(self.count(), 1)

    def test_other_users_cannot_edit_or_delete_records(self):
        transaction_id = self.seed()
        other = "whatsapp:+10000000001"
        for command in (f"edit {transaction_id} amount to 999", f"delete {transaction_id}"):
            self.assertIn("couldn't find", self.send_message(command, sender=other))
        self.assertEqual(self.row(transaction_id).amount, Decimal("250"))
        reply = self.send_message("Show my recent transactions", intent="recent_transactions", sender=other)
        self.assertNotIn("coffee", reply)

    def test_budgets_and_threshold_alerts(self):
        self.assertIn("don't have any budgets", self.send_message("show my budgets"))
        self.assertIn("1000.00", self.send_message("Set my food budget to ₹1000"))
        self.assertIn("20000.00", self.send_message("Set my overall budget to ₹20000"))
        self.assertIn("Monthly budgets:", self.send_message("show my budgets"))
        self.assertIn("1000.00 left", self.send_message("How much is left in my food budget?"))
        reply = self.send_message("Spent ₹800 on lunch", intent="transaction", items=[dict(ITEMS[0], amount=800)])
        self.assertIn("80% reached", reply)
        self.assertNotIn("100% reached", reply)
        self.assertIn("200.00 left", self.send_message("How much is left in my food budget?"))
        reply = self.send_message("Spent ₹200 on dinner", intent="transaction", items=[dict(ITEMS[0], amount=200)])
        self.assertIn("100% reached", reply)
        self.assertNotIn("80% reached", reply)
        reply = self.send_message("Spent ₹10 on tea", intent="transaction", items=[dict(ITEMS[0], amount=10)])
        self.assertNotIn("% reached", reply)
        self.assertIn("over by INR 10.00", self.send_message("How much is left in my food budget?"))

    def test_invalid_budget(self):
        self.assertIn("positive budget amount", self.send_message("Set my food budget to ₹0"))
        self.assertIn("don't have any budgets", self.send_message("show my budgets"))

    def test_expense_queries_for_every_supported_period(self):
        cases = [
            ("How much did I spend?", "total_expenses", get_today()),
            ("How much did I spend today?", "today_total", get_today()),
            ("Show today's expenses", "today_transactions", get_today()),
            ("How much did I spend yesterday?", "yesterday_total", get_today() - timedelta(days=1)),
            ("Show yesterday's expenses", "yesterday_transactions", get_today() - timedelta(days=1)),
            ("How much did I spend this week?", "week_total", get_today()),
            ("Show this week's expenses", "week_transactions", get_today()),
            ("How much did I spend this month?", "month_total", get_today()),
            ("Show this month's expenses", "month_transactions", get_today()),
            ("How much did I spend last month?", "last_month_total", get_last_month_range()[0]),
            ("Show last month's expenses", "last_month_transactions", get_last_month_range()[0]),
            ("Show my recent transactions", "recent_transactions", get_today()),
        ]
        for message, intent, day in cases:
            with self.subTest(message=message):
                with SessionLocal() as db:
                    db.query(TransactionDB).delete()
                    db.commit()
                self.seed(day=day)
                reply = self.send_message(message, intent=intent)
                self.assertIn("INR 250.00", reply)
                if "transactions" in intent:
                    self.assertIn("coffee", reply)

    def test_income_queries(self):
        self.seed(**ITEMS[1])
        for message, intent in (("How much have I earned?", "total_income"),
                                ("How much did I earn today?", "today_income"),
                                ("How much did I earn this week?", "week_income"),
                                ("How much did I earn this month?", "month_income")):
            with self.subTest(message=message):
                self.assertIn("INR 65000.00", self.send_message(message, intent=intent))

    def test_monthly_summary_and_category_queries(self):
        self.seed()
        self.seed(**ITEMS[1])
        summary = self.send_message("Show my monthly summary", intent="monthly_summary")
        for expected in ("Monthly Summary", "65000.00", "250.00", "64750.00", "Food"):
            self.assertIn(expected, summary)
        for intent, message in (("category_query", "How much did I spend on food this month?"),
                                ("category_list_query", "Show my food expenses this month")):
            reply = self.send_message(message, intent=intent, category={"category": "food", "time_range": "this_month"})
            self.assertIn("INR 250.00", reply)
            self.assertNotIn("65000", reply)

    def test_currencies_are_not_combined(self):
        self.seed()
        self.seed(currency="USD", amount=10)
        reply = self.send_message("How much did I spend?", intent="total_expenses")
        self.assertIn("INR 250.00", reply)
        self.assertIn("USD 10.00", reply)
        self.assertNotIn("260.00", reply)

    def test_unknown_message_and_media_guidance(self):
        self.assertIn("I can record expenses", self.send_message("Hello", intent="unknown"))
        reply = self.send_message("Receipt", extra={"MediaUrl0": "https://example.test/receipt.png", "MediaContentType0": "image/png"})
        self.assertIn("dashboard", reply)
        self.assertEqual(self.count(), 0)

    def test_postgres_driver_matches_installed_dependency(self):
        self.assertEqual(database_url_with_driver("postgresql://localhost/test").drivername, "postgresql+psycopg2")
        self.assertEqual(database_url_with_driver("postgres://localhost/test").drivername, "postgresql+psycopg2")
        self.assertEqual(database_url_with_driver("sqlite:///test.db").drivername, "sqlite")

    def setUp(self):
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)
        # No lifespan worker: schedules and external notification providers stay idle.
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()

    def test_extraction_shapes(self):
        for payload, count in ((ITEMS[0], 1), (ITEMS, 2), ({"transactions": ITEMS}, 2), ([ITEMS], 2)):
            with self.subTest(payload=payload):
                response = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(payload)))])
                with patch.object(llm_service.client.chat.completions, "create", return_value=response):
                    self.assertEqual(len(llm_service.extract_transactions("coffee and salary")), count)

    def test_batch_webhook_and_retry(self):
        response = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(ITEMS)))])
        data = {"From": "whatsapp:+10000000000", "Body": "I spent 250 on coffee\nReceived 65000 salary", "MessageSid": "SM-smoke-batch"}
        with patch("app.api.webhook.detect_intent", return_value="transaction"), patch.object(llm_service.client.chat.completions, "create", return_value=response):
            first = self.client.post("/webhook/whatsapp", data=data)
            self.assertEqual(first.status_code, 200)
            self.assertIn("Recorded transactions:", first.text)
            second = self.client.post("/webhook/whatsapp", data=data)
            self.assertIn("already processed", second.text)
        with SessionLocal() as db:
            rows = db.query(TransactionDB).order_by(TransactionDB.id).all()
            self.assertEqual([float(row.amount) for row in rows], [250, 65000])
            self.assertEqual([row.transaction_type for row in rows], ["expense", "income"])

    def test_signature_and_form_validation(self):
        data = {"From": "whatsapp:+10000000000", "Body": "cancel"}
        callback = "https://example.test/webhook/whatsapp"
        with patch.object(settings, "twilio_auth_token", "test-secret"), patch.object(settings, "twilio_webhook_url", callback):
            self.assertEqual(self.client.post("/webhook/whatsapp", data=data).status_code, 403)
            signature = RequestValidator("test-secret").compute_signature(callback, data)
            valid = self.client.post("/webhook/whatsapp", data=data, headers={"X-Twilio-Signature": signature})
            self.assertEqual(valid.status_code, 200)
            self.assertIn("no pending transaction", valid.text)
        self.assertEqual(self.client.post("/webhook/whatsapp", data={}).status_code, 422)


if __name__ == "__main__":
    try:
        unittest.main(verbosity=2)
    finally:
        engine.dispose()
        temporary.cleanup()
