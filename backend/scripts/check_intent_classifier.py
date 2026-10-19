"""Classify one message using the configured provider, without database writes."""

import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import settings
from app.services.intent_classifier_service import classify_intent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("message", help="A message to classify (sent to the provider API)")
    parser.add_argument("--strict-jev", action="store_true", help="Require Jev and disable Groq fallback")
    args = parser.parse_args()
    if args.strict_jev:
        settings.intent_classifier = "jev"
        settings.jev_fallback_to_groq = False
    try:
        result = classify_intent(args.message)
    except Exception as exc:
        print(f"Classification failed ({type(exc).__name__}). Check provider credentials/connectivity.", file=sys.stderr)
        return 1
    print(result.model_dump_json(indent=2))
    return int(result.provider == "none")


if __name__ == "__main__":
    raise SystemExit(main())
