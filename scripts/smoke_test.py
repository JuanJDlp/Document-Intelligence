"""Live acceptance smoke test. Prints step names/statuses only."""

import os
import secrets
import time
from pathlib import Path
from uuid import uuid4
import httpx


def run():
    base = os.environ.get("SMOKE_BASE_URL", "")
    if not base.startswith("https://"):
        raise RuntimeError("Set SMOKE_BASE_URL to the CloudFront HTTPS URL")
    with httpx.Client(base_url=base.rstrip("/"), timeout=30) as client:

        def step(name, method, route, expected, **kwargs):
            response = client.request(method, "/api/v1" + route, **kwargs)
            print(f"{name}: HTTP {response.status_code}")
            if response.status_code != expected:
                raise RuntimeError("Smoke step failed: " + name)
            return response.json() if expected != 204 else None

        step("health", "GET", "/health", 200)
        identity = {
            "email": f"smoke+{uuid4()}@example.com",
            "password": secrets.token_urlsafe(24) + "1",
            "full_name": "Synthetic Smoke User",
        }
        step("register", "POST", "/auth/register", 201, json=identity)
        auth = step(
            "login",
            "POST",
            "/auth/login",
            200,
            json={k: identity[k] for k in ("email", "password")},
        )
        client.headers["Authorization"] = "Bearer " + auth["token"]
        sample = Path(__file__).resolve().parents[1] / "samples/receipts/receipt.pdf"
        with sample.open("rb") as stream:
            document = step(
                "upload",
                "POST",
                "/documents",
                202,
                files={"file": ("receipt.pdf", stream, "application/pdf")},
            )
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            detail = step("poll", "GET", "/documents/" + document["document_id"], 200)
            if detail["processing"]["status"] in ("COMPLETED", "PARTIAL", "FAILED"):
                if detail["processing"]["status"] == "FAILED" or "extracted_data" not in (
                    detail.get("result") or {}
                ):
                    raise RuntimeError("Processing failed")
                break
            time.sleep(3)
        else:
            raise RuntimeError("Processing timed out")
        step("logout", "POST", "/auth/logout", 204)


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:
        print("Smoke failed:", type(exc).__name__)
        raise SystemExit(1) from None
