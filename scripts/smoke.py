from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from common import print_check


BASE_URL = os.environ.get("SELF_HOSTED_BASE_URL", "http://localhost")
EMAIL = os.environ.get("SELF_HOSTED_BOOTSTRAP_EMAIL", "admin@example.com")
PASSWORD = os.environ.get("SELF_HOSTED_BOOTSTRAP_PASSWORD", "")


def request(path: str, *, method: str = "GET", token: str | None = None, body: dict | None = None) -> tuple[int, dict | None]:
    data = None
    headers = {}
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(f"{BASE_URL}{path}", method=method, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            raw = response.read().decode()
            return response.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        return exc.code, None


checks: list[tuple[str, str, str]] = []
status, _ = request("/health")
checks.append(("PASS" if status == 200 else "FAIL", "health", f"/health {status}"))

token = None
if PASSWORD:
    status, body = request("/api/auth/local/login", method="POST", body={"email": EMAIL, "password": PASSWORD})
    token = body.get("token") if status == 200 and isinstance(body, dict) else None
    checks.append(("PASS" if token else "FAIL", "local login", f"/api/auth/local/login {status}"))
else:
    checks.append(("WARN", "local login", "SELF_HOSTED_BOOTSTRAP_PASSWORD not set"))

for name, path, method in [
    ("me", "/api/me", "GET"),
    ("license", "/api/admin/self-hosted/license", "GET"),
    ("diagnostics", "/api/admin/self-hosted/diagnostics", "GET"),
    ("backups", "/api/admin/self-hosted/backups", "GET"),
    ("updates", "/api/admin/self-hosted/update-check", "POST"),
]:
    if not token:
        checks.append(("WARN", name, "token not configured"))
        continue
    status, _ = request(path, method=method, token=token, body={"channel": "stable"} if method == "POST" else None)
    checks.append(("PASS" if status == 200 else "FAIL", name, f"{path} {status}"))

for check in checks:
    print_check(*check)

if any(status == "FAIL" for status, _, _ in checks):
    raise SystemExit(1)

print("\nSELF_HOSTED_SMOKE_OK")
