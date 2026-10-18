"""Local extractor regression checks. Run using the requirements.local.txt environment."""

from copy import deepcopy
from datetime import date
from decimal import Decimal
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import settings
from app.services import local_extraction_service as local
from app.services import transaction_extraction_service as facade


class LocalExtractorTests(unittest.TestCase):
    def setUp(self):
        self.text = "Spent 250 INR on coffee yesterday"
        self.result = {
            "entities": {name: [self.entity(value)] for name, value in {
                "amount": "250 INR", "purpose": "coffee", "date": "yesterday", "currency": "INR",
            }.items()},
            "transaction_type": {"label": "expense", "confidence": 0.95},
            "category": {"label": "food", "confidence": 0.9},
        }
        clock = patch.object(local, "get_today", return_value=date(2026, 10, 18))
        clock.start()
        self.addCleanup(clock.stop)

    def entity(self, value):
        start = self.text.index(value)
        return {"text": value, "start": start, "end": start + len(value), "confidence": 0.9}

    def test_valid_expense_and_relative_date(self):
        row = local.normalize_local_result(self.text, self.result)
        self.assertEqual((row.amount, row.currency, row.purpose, row.category),
                         (Decimal("250"), "INR", "coffee", "food"))
        self.assertEqual(row.transaction_date, date(2026, 10, 17))

    def test_missing_date_entity_still_resolves_yesterday(self):
        self.result["entities"].pop("date")
        self.assertEqual(local.normalize_local_result(self.text, self.result).transaction_date, date(2026, 10, 17))

    def test_missing_purpose_preserves_followup_flow(self):
        self.result["entities"].pop("purpose")
        self.assertIsNone(local.normalize_local_result(self.text, self.result).purpose)

    def test_low_category_confidence_becomes_other(self):
        self.result["category"]["confidence"] = 0.1
        self.assertEqual(local.normalize_local_result(self.text, self.result).category, "other")

    def test_low_type_confidence_rejected(self):
        self.result["transaction_type"]["confidence"] = 0.1
        with self.assertRaises(ValueError):
            local.normalize_local_result(self.text, self.result)

    def test_extra_missed_amount_rejected(self):
        with self.assertRaises(ValueError):
            local.normalize_local_result(self.text + " and 500 for lunch", self.result)

    def test_mismatched_source_span_rejected(self):
        self.result["entities"]["amount"][0]["text"] = "999"
        with self.assertRaises(ValueError):
            local.normalize_local_result(self.text, self.result)

    def test_out_of_range_source_span_rejected(self):
        self.result["entities"]["amount"][0]["start"] = -100
        with self.assertRaises(ValueError):
            local.normalize_local_result(self.text, self.result)

    def test_nonfinite_confidences_rejected(self):
        for value in (float("nan"), float("inf"), 1.1, -0.1):
            with self.subTest(value=value):
                result = deepcopy(self.result)
                result["entities"]["amount"][0]["confidence"] = value
                with self.assertRaises(ValueError):
                    local.normalize_local_result(self.text, result)

    def test_unknown_category_rejected(self):
        self.result["category"]["label"] = "invented"
        with self.assertRaises(ValueError):
            local.normalize_local_result(self.text, self.result)

    def test_conflicting_currencies_rejected(self):
        with self.assertRaises(ValueError):
            local.normalize_local_result(self.text + " USD", self.result)

    def test_unsupported_currency_rejected(self):
        text = self.text.replace("INR", "AUD")
        result = deepcopy(self.result)
        result["entities"].pop("currency")
        result["entities"]["amount"][0]["text"] = "250 AUD"
        with self.assertRaises(ValueError):
            local.normalize_local_result(text, result)

    def test_negative_amount_rejected(self):
        with self.assertRaises(ValueError):
            local.normalize_local_result(self.text.replace("250", "-250"), self.result)

    def test_abbreviated_and_excess_precision_amounts_rejected(self):
        for amount in ("2k", "2 lakh", "1.234", "-200"):
            with self.subTest(amount=amount), self.assertRaises(ValueError):
                local._normalize_amount(amount)

    def test_rupee_prefix_and_decimal_precision(self):
        self.assertEqual(local._normalize_amount("Rs. 1,250.50"), Decimal("1250.50"))

    def test_malformed_entities_rejected(self):
        for entities in ([], {"amount": ["250"]}, {"amount": "250"}):
            with self.subTest(entities=entities), self.assertRaises(ValueError):
                local.normalize_local_result(self.text, {**self.result, "entities": entities})

    def test_facade_selects_groq_by_default(self):
        with patch.object(settings, "extraction_provider", "groq"), \
                patch("app.services.llm_service.extract_transactions_groq", return_value=[]) as groq:
            self.assertEqual(facade.extract_transactions("test"), [])
            groq.assert_called_once_with("test")

    def test_strict_local_failure_never_uses_groq(self):
        with patch.object(settings, "extraction_provider", "gliner2"), \
                patch.object(settings, "gliner2_fallback_to_groq", False), \
                patch.object(local, "extract_local_transactions", side_effect=ValueError("ambiguous")), \
                patch("app.services.llm_service.extract_transactions_groq") as groq:
            with self.assertRaises(facade.ExtractionUnavailable):
                facade.extract_transactions("test")
            groq.assert_not_called()

    def test_explicit_fallback_uses_groq(self):
        with patch.object(settings, "extraction_provider", "gliner2"), \
                patch.object(settings, "gliner2_fallback_to_groq", True), \
                patch.object(local, "extract_local_transactions", side_effect=RuntimeError("unavailable")), \
                patch("app.services.llm_service.extract_transactions_groq", return_value=[]) as groq:
            self.assertEqual(facade.extract_transactions("test"), [])
            groq.assert_called_once_with("test")


if __name__ == "__main__":
    unittest.main(verbosity=2)
