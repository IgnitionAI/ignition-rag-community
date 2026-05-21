from __future__ import annotations

import argparse
import pathlib
import re
import subprocess

from common import ROOT, compose_with_release, latest_backup, load_json, print_check, read_env

EXTENSION_ROOT_TYPES = {
    "plugins": "plugin",
    "themes": "theme",
    "custom-connectors": "custom-connector",
}

SUPPORTED_EXTENSION_HOOKS = {
    "plugin": {"admin.diagnostics.card"},
    "theme": {"theme.tokens"},
    "custom-connector": {"customConnector.registry"},
}


def validate_manifest(path: pathlib.Path, *, strict: bool) -> tuple[dict, list[tuple[str, str, str]]]:
    checks: list[tuple[str, str, str]] = []
    manifest = load_json(path)
    release = manifest.get("release", {})
    images = manifest.get("images", {})
    signature = manifest.get("signature", {})
    current_edition = read_env().get("IGNITION_EDITION", "community")

    checks.append(("PASS" if manifest.get("schemaVersion") == 1 else "FAIL", "schema", "schemaVersion=1"))
    checks.append(("PASS" if manifest.get("edition") == current_edition else ("FAIL" if strict else "WARN"), "edition", f"manifest={manifest.get('edition')} current={current_edition}"))
    checks.append(("PASS" if release.get("version") else "FAIL", "release", str(release.get("version", "missing"))))

    invalid = []
    for name, image in images.items():
        digest = image.get("digest", "")
        if not re.fullmatch(r"sha256:[a-fA-F0-9]{64}", digest):
            invalid.append(name)
    checks.append(("PASS" if not invalid else ("FAIL" if strict else "WARN"), "image digests", "all sha256 pinned" if not invalid else ", ".join(invalid)))

    signature_value = str(signature.get("value", ""))
    has_signature = (
        signature.get("algorithm") == "ed25519"
        and bool(signature_value)
        and "replace-with" not in signature_value
        and "base64-signature" not in signature_value
        and "placeholder" not in signature_value.lower()
    )
    checks.append(("PASS" if has_signature else ("FAIL" if strict else "WARN"), "signature", "ed25519 signature present" if has_signature else "missing or placeholder signature"))

    requires_backup = bool(manifest.get("migrations", {}).get("requiresBackup"))
    backup = latest_backup()
    checks.append(("PASS" if not requires_backup or backup else ("FAIL" if strict else "WARN"), "backup", backup.name if backup else "required backup missing"))
    checks.append(validate_extensions(release))
    return manifest, checks


def parse_version(value: str) -> tuple[int, ...]:
    return tuple(int(part) for part in re.findall(r"\d+", value))


def compare_versions(left: str, right: str) -> int:
    left_parts = parse_version(left)
    right_parts = parse_version(right)
    length = max(len(left_parts), len(right_parts))
    left_parts = left_parts + (0,) * (length - len(left_parts))
    right_parts = right_parts + (0,) * (length - len(right_parts))
    return (left_parts > right_parts) - (left_parts < right_parts)


def hook_name(value: object) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, dict) and isinstance(value.get("name"), str):
        return str(value["name"])
    return None


def validate_extension_surface(root_name: str, manifest_path: pathlib.Path, extension: dict) -> list[str]:
    invalid: list[str] = []
    expected_type = EXTENSION_ROOT_TYPES[root_name]
    extension_type = extension.get("type")
    extension_name = str(extension.get("name") or manifest_path.parent.name)

    if extension_type != expected_type:
        invalid.append(f"{manifest_path.relative_to(ROOT)}: type must be {expected_type}")

    allowed_hooks = SUPPORTED_EXTENSION_HOOKS.get(str(extension_type), set())
    for hook in extension.get("hooks", []):
        name = hook_name(hook)
        if not name:
            invalid.append(f"{manifest_path.relative_to(ROOT)}: invalid hook declaration")
        elif name not in allowed_hooks:
            invalid.append(f"{manifest_path.relative_to(ROOT)}: unsupported hook {name}")

    if extension_type == "custom-connector":
        connector = extension.get("connector")
        if not isinstance(connector, dict):
            invalid.append(f"{manifest_path.relative_to(ROOT)}: custom connector declaration missing")
        else:
            if not connector.get("id"):
                invalid.append(f"{manifest_path.relative_to(ROOT)}: connector.id is required")
            if not connector.get("name"):
                invalid.append(f"{manifest_path.relative_to(ROOT)}: connector.name is required")
            protocol = connector.get("protocol", "custom")
            if protocol not in {"http", "mcp", "webhook", "custom"}:
                invalid.append(f"{manifest_path.relative_to(ROOT)}: connector.protocol {protocol} is unsupported")

    if extension_type not in SUPPORTED_EXTENSION_HOOKS:
        invalid.append(f"{manifest_path.relative_to(ROOT)}: unsupported extension type for {extension_name}")
    return invalid


def validate_extensions(release: dict) -> tuple[str, str, str]:
    core_version = str(release.get("coreVersion") or release.get("version") or "")
    extension_api = str(release.get("extensionApiVersion") or "")
    invalid: list[str] = []
    checked = 0
    for root_name in EXTENSION_ROOT_TYPES:
        root = ROOT / root_name
        if not root.exists():
            continue
        for extension_dir in sorted(path for path in root.iterdir() if path.is_dir()):
            manifest_path = extension_dir / "ignition-extension.json"
            if not manifest_path.exists():
                invalid.append(f"{extension_dir.relative_to(ROOT)}: missing ignition-extension.json")
                continue
            checked += 1
            try:
                extension = load_json(manifest_path)
            except Exception:
                invalid.append(f"{manifest_path.relative_to(ROOT)}: invalid json")
                continue
            compatibility = extension.get("compatibility", {})
            if not isinstance(compatibility, dict):
                invalid.append(f"{manifest_path.relative_to(ROOT)}: missing compatibility")
                continue
            required_api = compatibility.get("extensionApi")
            min_core = compatibility.get("minCore")
            max_core = compatibility.get("maxCore")
            if required_api and str(required_api) != extension_api:
                invalid.append(f"{manifest_path.relative_to(ROOT)}: extensionApi {required_api} != {extension_api}")
            if min_core and compare_versions(core_version, str(min_core)) < 0:
                invalid.append(f"{manifest_path.relative_to(ROOT)}: minCore {min_core} > {core_version}")
            if max_core and compare_versions(core_version, str(max_core)) > 0:
                invalid.append(f"{manifest_path.relative_to(ROOT)}: maxCore {max_core} < {core_version}")
            invalid.extend(validate_extension_surface(root_name, manifest_path, extension))
    if invalid:
        return ("FAIL", "extensions", "; ".join(invalid))
    return ("PASS", "extensions", f"{checked} manifest(s) compatible")


def write_release_override(manifest: dict) -> pathlib.Path:
    path = ROOT / ".self-hosted" / "docker-compose.release.yml"
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# Generated by scripts/update.py --apply.", "services:"]
    for service, image in manifest["images"].items():
        lines.append(f"  {service}:")
        lines.append(f"    image: {image['repository']}@{image['digest']}")
    path.write_text("\n".join(lines) + "\n")
    return path


parser = argparse.ArgumentParser()
parser.add_argument("--manifest", required=True)
parser.add_argument("--dry-run", action="store_true")
parser.add_argument("--apply", action="store_true")
args = parser.parse_args()

if args.dry_run == args.apply:
    raise SystemExit("Use exactly one of --dry-run or --apply")

manifest_path = pathlib.Path(args.manifest)
if not manifest_path.is_absolute():
    manifest_path = ROOT / manifest_path

manifest, checks = validate_manifest(manifest_path, strict=args.apply)
for check in checks:
    print_check(*check)

if args.dry_run:
    print("\nSELF_HOSTED_UPDATE_DRY_RUN_OK")
    raise SystemExit(0 if all(status != "FAIL" for status, _, _ in checks) else 1)

if any(status != "PASS" for status, _, _ in checks):
    raise SystemExit("\nSELF_HOSTED_UPDATE_APPLY_BLOCKED")

override = write_release_override(manifest)
services = list(manifest["images"].keys())
backup = latest_backup()
print_check("PASS", "release override", str(override))

try:
    compose_with_release(["pull", *services])
    compose_with_release(["up", "-d", "--no-build", *services, "nginx"])
    compose_with_release(["run", "--rm", "api", "bun", "run", "src/db/migrate.ts"])
    subprocess.run(["python3", "scripts/smoke.py"], cwd=ROOT, check=True)
except subprocess.CalledProcessError:
    if backup:
        print(f"\nSELF_HOSTED_UPDATE_FAILED_RESTORE_COMMAND python3 scripts/restore.py --backup {backup.name} --confirm {backup.name}")
    raise

print(f"\nSELF_HOSTED_UPDATE_APPLY_OK {manifest['release']['version']}")
