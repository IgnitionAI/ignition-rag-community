from __future__ import annotations

import datetime as dt
import hashlib
import json
import pathlib
import subprocess
import urllib.request

from common import ROOT, backup_dir, compose, compose_env_file, print_check, read_env


def sha256(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def container_id(service: str) -> str:
    result = compose(["ps", "-q", service], capture=True)
    value = result.stdout.strip()
    if not value:
        raise RuntimeError(f"Could not resolve container for {service}")
    return value


env = read_env()
now = dt.datetime.now(dt.timezone.utc)
backup_id = "ignition-" + now.isoformat().replace("+00:00", "Z").replace(":", "-").replace(".", "-")
target = backup_dir() / backup_id
target.mkdir(parents=True, exist_ok=False)

print_check("PASS", "backup", str(target))

git_revision = subprocess.run(
    ["git", "rev-parse", "HEAD"],
    cwd=ROOT,
    text=True,
    capture_output=True,
    check=False,
).stdout.strip()

compose_services = subprocess.run(
    ["docker", "compose", "--env-file", str(compose_env_file()), "config", "--services"],
    cwd=ROOT,
    text=True,
    capture_output=True,
    check=False,
).stdout.splitlines()

postgres_user = env.get("POSTGRES_USER", "ignitionai")
postgres_db = env.get("POSTGRES_DB", "ignitionai")
postgres_dump = target / "postgres.dump"
with postgres_dump.open("wb") as out:
    subprocess.run(
        [
            "docker",
            "compose",
            "--env-file",
            str(compose_env_file()),
            "exec",
            "-T",
            "postgres",
            "pg_dump",
            "-U",
            postgres_user,
            "-d",
            postgres_db,
            "-Fc",
        ],
        cwd=ROOT,
        stdout=out,
        check=True,
    )

qdrant_dir = target / "qdrant"
qdrant_dir.mkdir()
qdrant_base = env.get("QDRANT_PUBLIC_URL", "http://localhost:6333").rstrip("/")
collections = json.load(urllib.request.urlopen(f"{qdrant_base}/collections", timeout=30))["result"]["collections"]
qdrant_entries = []
for item in collections:
    name = item["name"]
    snapshot = json.load(urllib.request.urlopen(urllib.request.Request(f"{qdrant_base}/collections/{name}/snapshots?wait=true", method="POST"), timeout=120))["result"]["name"]
    data = urllib.request.urlopen(f"{qdrant_base}/collections/{name}/snapshots/{snapshot}", timeout=300).read()
    filename = f"{name}.snapshot"
    (qdrant_dir / filename).write_bytes(data)
    qdrant_entries.append({"collection": name, "snapshot": snapshot, "file": filename})
(qdrant_dir / "manifest.json").write_text(json.dumps({"collections": qdrant_entries}, indent=2) + "\n")

minio_container = container_id("minio")
subprocess.run(
    [
        "docker",
        "run",
        "--rm",
        "--volumes-from",
        minio_container,
        "-v",
        f"{target}:/backup",
        "alpine:3.20",
        "tar",
        "-C",
        "/data",
        "-czf",
        "/backup/minio-data.tar.gz",
        ".",
    ],
    check=True,
)

redacted = {k: ("<redacted>" if any(part in k for part in ["SECRET", "PASSWORD", "TOKEN", "KEY", "DATABASE_URL"]) else v) for k, v in env.items()}
(target / "env.redacted.json").write_text(json.dumps(redacted, indent=2) + "\n")

release_override = ROOT / ".self-hosted" / "docker-compose.release.yml"
if release_override.exists():
    release_dir = target / "release"
    release_dir.mkdir()
    (release_dir / "docker-compose.release.yml").write_text(release_override.read_text())

checksums = {str(path.relative_to(target)): sha256(path) for path in target.rglob("*") if path.is_file() and path.name != "manifest.json"}
(target / "manifest.json").write_text(json.dumps({
    "schemaVersion": 1,
    "id": backup_id,
    "createdAt": dt.datetime.now(dt.timezone.utc).isoformat(),
    "distributionRevision": git_revision or None,
    "version": env.get("IGNITION_VERSION"),
    "providers": {
        "edition": env.get("IGNITION_EDITION"),
        "auth": env.get("AUTH_PROVIDER"),
        "billing": env.get("BILLING_PROVIDER"),
        "email": env.get("EMAIL_PROVIDER"),
        "storage": "s3" if env.get("S3_ENABLED") == "true" else "disabled",
        "vector": "qdrant",
    },
    "composeServices": compose_services,
    "components": {
        "postgres": "postgres.dump",
        "qdrant": "qdrant/manifest.json",
        "minio": "minio-data.tar.gz",
        "env": "env.redacted.json",
    },
    "checksums": checksums,
}, indent=2) + "\n")

print(f"SELF_HOSTED_BACKUP_OK {backup_id}")
