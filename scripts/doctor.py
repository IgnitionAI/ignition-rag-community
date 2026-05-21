from __future__ import annotations

import shutil
import subprocess

from common import ROOT, backup_dir, print_check, read_env


def command_exists(command: str) -> bool:
    return shutil.which(command) is not None


env = read_env()
checks = [
    ("PASS" if (ROOT / ".env").exists() else "WARN", "environment", ".env exists" if (ROOT / ".env").exists() else "copy .env.example to .env"),
    ("PASS" if command_exists("docker") else "FAIL", "docker", "docker command available"),
    ("PASS" if command_exists("python3") else "FAIL", "python", "python3 command available"),
    ("PASS" if env.get("DEPLOYMENT_MODE") == "self_hosted" else "FAIL", "deployment mode", f"DEPLOYMENT_MODE={env.get('DEPLOYMENT_MODE', '')}"),
    ("PASS" if env.get("IGNITION_EDITION") == "community" else "FAIL", "edition", f"IGNITION_EDITION={env.get('IGNITION_EDITION', '')}"),
    ("PASS" if env.get("AUTH_PROVIDER") in {"local", "sso"} else "WARN", "auth provider", f"AUTH_PROVIDER={env.get('AUTH_PROVIDER', '')}"),
    ("PASS" if env.get("BILLING_PROVIDER") == "none" else "FAIL", "billing provider", f"BILLING_PROVIDER={env.get('BILLING_PROVIDER', '')}"),
    ("PASS" if env.get("EMAIL_PROVIDER") in {"none", "smtp"} else "WARN", "email provider", f"EMAIL_PROVIDER={env.get('EMAIL_PROVIDER', '')}"),
    ("PASS" if len(env.get("ENCRYPTION_KEY", "")) >= 32 else "FAIL", "encryption key", "ENCRYPTION_KEY length >= 32"),
    ("PASS", "license", "Community edition does not require a license"),
    ("PASS", "backup dir", str(backup_dir())),
]

try:
    subprocess.run(["docker", "compose", "--env-file", ".env.example", "config"], cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
    checks.append(("PASS", "compose config", "docker compose config is valid"))
except Exception as exc:
    checks.append(("FAIL", "compose config", str(exc)))

for status, name, detail in checks:
    print_check(status, name, detail)

if any(status == "FAIL" for status, _, _ in checks):
    raise SystemExit(1)

print("\nSELF_HOSTED_DOCTOR_OK")
