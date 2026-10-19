"""Offline Jev adapter and fallback tests; no external provider requests."""

import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("GROQ_API_KEY", "test-key")
os.environ.setdefault("DATABASE_URL", "sqlite://")

import httpx2
from typesafe_sdk import TypeSafeClient

from app.config import settings, Settings
from app.services import intent_classifier_service as service
from app.services.intent_registry import INTENT_CRITERIA


class IntentClassifierTests(unittest.TestCase):
    def setUp(self):
        for field, value in {
            "intent_classifier": "jev", "typesafe_api_key": "test-jev-key",
            "jev_model": "jev-1.14.0", "jev_timeout_seconds": 4.0,
            "jev_min_confidence": 0.6, "jev_fallback_to_groq": True,
        }.items():
            context = patch.object(settings, field, value)
            context.start()
            self.addCleanup(context.stop)
        fallback_patch = patch.object(service, "_classify_with_groq", return_value=service.IntentClassification(
            label="transaction", provider="groq",
        ))
        self.fallback = fallback_patch.start()
        self.addCleanup(fallback_patch.stop)
        self.requests = []

    def sdk_factory(self, label="month_total", confidence=0.9, status=200, missing_answer=False):
        def respond(request):
            self.requests.append(request)
            if status != 200:
                return httpx2.Response(status, json={"error": "simulated provider failure"})
            probability = confidence * (1 - 1 / len(INTENT_CRITERIA)) + 1 / len(INTENT_CRITERIA)
            probabilities = {name: (1 - probability) / (len(INTENT_CRITERIA) - 1) for name in INTENT_CRITERIA}
            probabilities[label] = probability
            return httpx2.Response(200, json={
                "model": "jev-1.14.0", "usage": {"input_tokens": 10, "output_tokens": 1},
                "answers": {} if missing_answer else {"intent": {
                    "type": "choice", "choice": label, "confidence": confidence,
                    "probabilities": probabilities,
                }},
            })

        def create(**kwargs):
            self.assertEqual(kwargs["model"], settings.jev_model)
            self.assertEqual(kwargs["timeout"], settings.jev_timeout_seconds)
            self.assertEqual(kwargs["retry"].max_retries, 0)
            return TypeSafeClient(**kwargs, transport=httpx2.MockTransport(respond), compression=False)
        return create

    def test_real_sdk_wire_contract_and_high_confidence_choice(self):
        with patch.object(service, "TypeSafeClient", side_effect=self.sdk_factory()):
            result = service.classify_intent("How much did I spend this month?")
        self.assertEqual((result.label, result.provider), ("month_total", "jev"))
        self.assertEqual(result.confidence, 0.9)
        self.fallback.assert_not_called()
        self.assertEqual(len(self.requests), 1)
        request = self.requests[0]
        self.assertEqual(request.url.path, "/v1/systemone")
        payload = json.loads(request.content)
        self.assertEqual(payload["model"], "jev-1.14.0")
        self.assertEqual(payload["state"], {"message": "How much did I spend this month?"})
        self.assertEqual(payload["questions"]["intent"]["type"], "choice")
        self.assertEqual(set(payload["questions"]["intent"]["criteria"]), set(INTENT_CRITERIA))

    def test_low_confidence_falls_back(self):
        with patch.object(service, "TypeSafeClient", side_effect=self.sdk_factory(confidence=0.2)):
            result = service.classify_intent("My spending?")
        self.assertEqual((result.provider, result.fallback_reason), ("groq", "low_confidence"))
        self.fallback.assert_called_once_with("My spending?")

    def test_exact_confidence_boundary_is_accepted(self):
        with patch.object(service, "TypeSafeClient", side_effect=self.sdk_factory(confidence=0.6)):
            self.assertEqual(service.classify_intent("This month's spending").provider, "jev")
        self.fallback.assert_not_called()

    def test_unknown_choice_is_preserved(self):
        with patch.object(service, "TypeSafeClient", side_effect=self.sdk_factory(label="unknown")):
            self.assertEqual(service.classify_intent("Tell me a joke").label, "unknown")
        self.fallback.assert_not_called()

    def test_missing_key_falls_back_without_sdk_call(self):
        with patch.object(settings, "typesafe_api_key", "  "), patch.object(service, "TypeSafeClient") as sdk:
            self.assertEqual(service.classify_intent("Spent 10").fallback_reason, "missing_key")
        sdk.assert_not_called()

    def test_auth_rate_limit_and_server_errors_fall_back_without_retries(self):
        for status in (401, 429, 503):
            with self.subTest(status=status), patch.object(service, "TypeSafeClient", side_effect=self.sdk_factory(status=status)):
                before = len(self.requests)
                result = service.classify_intent("Spent 10")
                self.assertEqual(result.fallback_reason, "provider_error")
                self.assertEqual(len(self.requests), before + 1)

    def test_timeout_falls_back(self):
        def create(**kwargs):
            def respond(request):
                raise httpx2.ReadTimeout("simulated timeout", request=request)
            return TypeSafeClient(**kwargs, transport=httpx2.MockTransport(respond), compression=False)
        with patch.object(service, "TypeSafeClient", side_effect=create):
            self.assertEqual(service.classify_intent("Spent 10").fallback_reason, "provider_error")

    def test_missing_or_invalid_answer_falls_back(self):
        for factory in (self.sdk_factory(missing_answer=True), self.sdk_factory(label="drop_database")):
            with self.subTest(factory=factory), patch.object(service, "TypeSafeClient", side_effect=factory):
                self.assertEqual(service.classify_intent("Spent 10").fallback_reason, "invalid_response")

    def test_invalid_confidence_is_rejected(self):
        for value in (-0.1, 1.1, float("nan"), float("inf")):
            with self.subTest(value=value), self.assertRaises(ValueError):
                service.IntentClassification(label="transaction", provider="jev", confidence=value)

    def test_strict_mode_declines_instead_of_calling_groq(self):
        with patch.object(settings, "jev_fallback_to_groq", False), patch.object(settings, "typesafe_api_key", None):
            result = service.classify_intent("Spent 10")
        self.assertEqual((result.label, result.provider, result.fallback_reason), ("unknown", "none", "missing_key"))
        self.fallback.assert_not_called()

    def test_strict_mode_declines_uncertainty(self):
        with patch.object(settings, "jev_fallback_to_groq", False), patch.object(service, "TypeSafeClient", side_effect=self.sdk_factory(confidence=0.1)):
            result = service.classify_intent("My spending?")
        self.assertEqual((result.label, result.provider), ("unknown", "none"))
        self.fallback.assert_not_called()

    def test_groq_selection_never_calls_jev(self):
        with patch.object(settings, "intent_classifier", "groq"), patch.object(service, "TypeSafeClient") as sdk:
            self.assertEqual(service.classify_intent("Spent 10").provider, "groq")
        sdk.assert_not_called()

    def test_public_compatibility_entrypoint_uses_classifier(self):
        from app.services.llm_service import detect_intent
        result = service.IntentClassification(label="today_total", provider="jev", confidence=0.9)
        with patch.object(service, "classify_intent", return_value=result):
            self.assertEqual(detect_intent("Today's spending?"), "today_total")

    def test_groq_results_also_require_a_supported_label(self):
        from app.services.llm_service import detect_intent_groq, client
        from types import SimpleNamespace
        response = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='{"intent":"unsupported"}'))])
        with patch.object(client.chat.completions, "create", return_value=response), self.assertRaises(ValueError):
            detect_intent_groq("Anything")

    def test_configuration_rejects_bad_provider_threshold_or_timeout(self):
        for override in ({"intent_classifier": "other"}, {"jev_min_confidence": 1.1}, {"jev_timeout_seconds": 0}):
            with self.subTest(override=override), self.assertRaises(ValueError):
                Settings(_env_file=None, groq_api_key="test", database_url="sqlite://", **override)


if __name__ == "__main__":
    unittest.main(verbosity=2)
