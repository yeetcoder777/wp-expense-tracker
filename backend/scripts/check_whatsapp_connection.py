"""Read-only checks for the backend and the local ngrok agent."""

import argparse
import json
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]


def read_json(url):
    request = Request(url, headers={"ngrok-skip-browser-warning": "1"})
    with urlopen(request, timeout=5) as response:
        return json.load(response)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    failures = 0
    try:
        health = read_json(args.backend.rstrip("/") + "/health")
        if health.get("status") != "ok":
            raise ValueError("Unexpected health response")
        paths = read_json(args.backend.rstrip("/") + "/openapi.json")["paths"]
        if "post" not in paths.get("/webhook/whatsapp", {}):
            raise ValueError("Server does not expose POST /webhook/whatsapp")
        print("PASS: Backend is running and exposes the WhatsApp webhook.")
    except (OSError, ValueError, KeyError) as exc:
        print(f"FAIL: Backend check failed ({type(exc).__name__}).")
        print("Start from the backend folder: python -m uvicorn app.main:app --port 8000")
        failures += 1

    try:
        tunnels = read_json("http://127.0.0.1:4040/api/tunnels")["tunnels"]
        https_tunnels = [t for t in tunnels if t["public_url"].startswith("https://")]
        if not https_tunnels:
            raise ValueError("No HTTPS tunnel")
    except (OSError, ValueError, KeyError):
        print("FAIL: No active local ngrok HTTPS tunnel. Run: ngrok http 8000")
        return 1

    configured = dotenv_values(ROOT / ".env").get("TWILIO_WEBHOOK_URL")
    for tunnel in https_tunnels:
        public_url = tunnel["public_url"].rstrip("/")
        callback = public_url + "/webhook/whatsapp"
        print(f"Twilio incoming-message webhook (POST): {callback}")
        if configured and configured != callback:
            print("FAIL: TWILIO_WEBHOOK_URL in .env differs from this callback URL.")
            failures += 1
        try:
            if read_json(public_url + "/health").get("status") != "ok":
                raise ValueError("Unexpected public health response")
            print("PASS: Public tunnel reaches a healthy backend.")
        except (HTTPError, URLError, ValueError, OSError):
            print("FAIL: Public tunnel cannot reach backend health. Check its target port.")
            failures += 1
    print("Set the callback in Twilio Console; changing .env does not configure Twilio.")
    print("If no WhatsApp POST appears at http://127.0.0.1:4040, check the sender's")
    print("incoming webhook and Sandbox membership. Health probes above are not WhatsApp messages.")
    return int(bool(failures))


if __name__ == "__main__":
    raise SystemExit(main())
