#!/usr/bin/env python3
"""Smoke-test the running FinGuard Docker stack using Python's standard library.

Usage:
    python scripts/smoke_stack.py
    python scripts/smoke_stack.py --full

--full registers a disposable user and exercises authenticated dashboard + CSV upload.
It changes the local database; use only against a development stack.
"""
import argparse
import io
import json
import secrets
import sys
import time
import urllib.error
import urllib.request

SERVICES = {
    "backend": "http://localhost:8000/health",
    "frontend": "http://localhost:5173/",
    "fraud": "http://localhost:8001/health",
    "forecast": "http://localhost:8002/health",
    "advisor": "http://localhost:8003/health",
}


def request(url, method="GET", data=None, token=None, content_type="application/json"):
    headers = {}
    if data is not None:
        headers["Content-Type"] = content_type
    if token:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    with urllib.request.urlopen(req, timeout=15) as response:
        return response.status, response.read()


def json_request(url, payload, token=None):
    return request(url, "POST", json.dumps(payload).encode(), token)


def check_health(name, url, timeout):
    deadline = time.monotonic() + timeout
    while True:
        try:
            status, raw = request(url)
            if status != 200:
                raise RuntimeError(f"HTTP {status}")
            if name != "frontend":
                body = json.loads(raw)
                if body.get("status") != "ok":
                    raise RuntimeError(f"unexpected health payload: {body}")
            print(f"PASS {name}: {url}")
            return True
        except (urllib.error.URLError, TimeoutError, ValueError, RuntimeError) as exc:
            if time.monotonic() >= deadline:
                print(f"FAIL {name}: {exc}", file=sys.stderr)
                return False
            time.sleep(2)


def full_smoke():
    base = "http://localhost:8000"
    email = "smoke-" + secrets.token_hex(8) + "@example.test"
    password = secrets.token_urlsafe(20)
    status, raw = json_request(base + "/auth/register", {"email": email, "password": password})
    if status != 201:
        raise RuntimeError(f"registration returned {status}")
    token = json.loads(raw)["access_token"]
    status, raw = request(base + "/dashboard", token=token)
    if status != 200 or not isinstance(json.loads(raw), dict):
        raise RuntimeError("authenticated dashboard failed")
    print("PASS auth/register + dashboard")

    csv_data = "timestamp,amount,merchant,txn_type,balance,device,location\n2026-01-01T12:00:00,100.00,Smoke Shop,debit,900.00,smoke-device,smoke-city\n"
    boundary = "finguard" + secrets.token_hex(12)
    multipart = (
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"smoke.csv\"\r\n"
        "Content-Type: text/csv\r\n\r\n" + csv_data + f"\r\n--{boundary}--\r\n"
    ).encode()
    status, raw = request(
        base + "/transactions/upload", "POST", multipart, token,
        f"multipart/form-data; boundary={boundary}"
    )
    result = json.loads(raw)
    if status != 200 or result.get("imported") != 1:
        raise RuntimeError(f"CSV upload failed: {result}")
    print("PASS CSV upload (one synthetic transaction; scoring may remain pending_review)")
    status, raw = request(base + "/transactions", token=token)
    if status != 200 or not isinstance(json.loads(raw), list):
        raise RuntimeError("transaction listing failed")
    print("PASS authenticated transaction listing")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--full", action="store_true", help="Also register a disposable user and upload a synthetic CSV")
    parser.add_argument("--timeout", type=int, default=90, help="Seconds to wait for each service (default: 90)")
    args = parser.parse_args()
    if args.timeout < 0:
        parser.error("--timeout must be nonnegative")
    all_ok = all(check_health(name, url, args.timeout) for name, url in SERVICES.items())
    if not all_ok:
        print("Stack is not healthy; inspect: docker compose ps && docker compose logs --tail=100", file=sys.stderr)
        return 1
    if args.full:
        try:
            full_smoke()
        except (urllib.error.URLError, ValueError, KeyError, RuntimeError) as exc:
            print(f"FAIL full smoke: {exc}", file=sys.stderr)
            return 1
    print("PASS smoke checks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
