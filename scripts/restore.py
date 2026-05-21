from __future__ import annotations

import argparse
import json
import subprocess
import urllib.error
import urllib.request

from common import ROOT, backup_dir, compose, read_env


def container_id(service: str) -> str:
    result = compose(["ps", "-q", service], capture=True)
    value = result.stdout.strip()
    if not value:
        raise RuntimeError(f"Could not resolve container for {service}")
    return value


parser = argparse.ArgumentParser()
parser.add_argument("--backup", required=True)
parser.add_argument("--confirm", required=True)
args = parser.parse_args()

if args.backup != args.confirm:
    raise SystemExit(f"SELF_HOSTED_RESTORE_CONFIRM_REQUIRED: pass --confirm {args.backup}")

target = backup_dir() / args.backup
if not target.exists():
    raise SystemExit(f"SELF_HOSTED_RESTORE_BACKUP_NOT_FOUND: {args.backup}")

env = read_env()
compose(["stop", "api", "front", "nginx", "crawler", "document-extractor"], check=False)
compose(["up", "-d", "postgres", "qdrant", "minio"])

postgres_user = env.get("POSTGRES_USER", "ignitionai")
postgres_db = env.get("POSTGRES_DB", "ignitionai")
compose(["cp", str(target / "postgres.dump"), "postgres:/tmp/ignition-restore.dump"])
compose(["exec", "-T", "postgres", "dropdb", "-U", postgres_user, "--if-exists", "--force", postgres_db], check=False)
compose(["exec", "-T", "postgres", "createdb", "-U", postgres_user, postgres_db])
compose(["exec", "-T", "postgres", "pg_restore", "-U", postgres_user, "-d", postgres_db, "--no-owner", "/tmp/ignition-restore.dump"])

qdrant_base = env.get("QDRANT_PUBLIC_URL", "http://localhost:6333").rstrip("/")
qdrant_manifest = json.loads((target / "qdrant" / "manifest.json").read_text())
for item in qdrant_manifest.get("collections", []):
    collection = item["collection"]
    try:
        urllib.request.urlopen(urllib.request.Request(f"{qdrant_base}/collections/{collection}?wait=true", method="DELETE"), timeout=120)
    except urllib.error.HTTPError as exc:
        if exc.code != 404:
            raise
    snapshot = target / "qdrant" / item["file"]
    subprocess.run(
        [
            "curl",
            "-fsS",
            "-X",
            "POST",
            f"{qdrant_base}/collections/{collection}/snapshots/upload?wait=true&priority=snapshot",
            "-F",
            f"snapshot=@{snapshot}",
        ],
        check=True,
    )

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
        "sh",
        "-lc",
        "rm -rf /data/* /data/.[!.]* /data/..?* && tar -C /data -xzf /backup/minio-data.tar.gz",
    ],
    check=True,
)

release_backup = target / "release" / "docker-compose.release.yml"
release_path = ROOT / ".self-hosted" / "docker-compose.release.yml"
release_path.parent.mkdir(parents=True, exist_ok=True)
if release_backup.exists():
    release_path.write_text(release_backup.read_text())
elif release_path.exists():
    release_path.unlink()

compose(["up", "-d", "api", "front", "nginx", "crawler", "document-extractor"])
subprocess.run(["python3", "scripts/smoke.py"], cwd=ROOT, check=True)
print(f"SELF_HOSTED_RESTORE_OK {args.backup}")
