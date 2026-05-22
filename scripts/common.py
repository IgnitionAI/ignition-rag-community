from __future__ import annotations

import json
import os
import pathlib
import subprocess
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]


def env_path() -> pathlib.Path:
    return ROOT / ".env"


def compose_env_file() -> pathlib.Path:
    path = env_path()
    return path if path.exists() else ROOT / ".env.example"


def read_env() -> dict[str, str]:
    path = compose_env_file()
    values: dict[str, str] = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key] = value
    values.update({
        key: value
        for key, value in os.environ.items()
        if key.startswith(("IGNITION_", "SELF_HOSTED_", "BACKUP_", "QDRANT_", "S3_", "POSTGRES_", "DATABASE_"))
    })
    return values


def backup_dir() -> pathlib.Path:
    configured = read_env().get("BACKUP_DIR", "./backups")
    path = pathlib.Path(configured)
    return path if path.is_absolute() else ROOT / path


def compose(args: list[str], *, capture: bool = False, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["docker", "compose", "--env-file", str(compose_env_file()), *args],
        cwd=ROOT,
        text=True,
        capture_output=capture,
        check=check,
    )


def compose_with_release(args: list[str], *, capture: bool = False, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "docker",
            "compose",
            "--env-file",
            str(compose_env_file()),
            "-f",
            "docker-compose.yml",
            "-f",
            ".self-hosted/docker-compose.release.yml",
            *args,
        ],
        cwd=ROOT,
        text=True,
        capture_output=capture,
        check=check,
    )


def load_json(path: pathlib.Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def latest_backup() -> pathlib.Path | None:
    root = backup_dir()
    if not root.exists():
        return None
    backups = sorted([p for p in root.iterdir() if p.is_dir() and p.name.startswith("ignition-")], reverse=True)
    return backups[0] if backups else None


def print_check(status: str, name: str, detail: str) -> None:
    print(f"{status.ljust(4)}  {name.ljust(24)}  {detail}")
