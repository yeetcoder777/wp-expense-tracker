"""Smoke-test the locally running FastAPI backend using only the stdlib."""

import json
import os
import sys
from urllib.error import HTTPError, URLError
from urllib.request import urlopen


BASE_URL = os.environ.get("BACKEND_URL", "http://127.0.0.1:8000").rstrip("/")


def get_json(path: str) -> dict:
    with urlopen(f"{BASE_URL}{path}", timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> int:
    try:
        health = get_json("/health")
        if health.get("status") != "ok":
            raise ValueError(f"Unexpected health response: {health!r}")

        schema = get_json("/openapi.json")
        webhook = schema.get("paths", {}).get("/webhook/whatsapp", {})
        if "post" not in webhook:
            raise ValueError("POST /webhook/whatsapp is missing from OpenAPI")
    except (HTTPError, URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
        print(f"FAIL: backend smoke test: {exc}", file=sys.stderr)
        return 1

    print(f"PASS: GET {BASE_URL}/health returned status=ok")
    print("PASS: POST /webhook/whatsapp is registered")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
