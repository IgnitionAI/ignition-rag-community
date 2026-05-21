# IgnitionRAG Community

Free self-hosted distribution for IgnitionRAG.

This repository is not the product core. It contains the Docker Compose
distribution, operational scripts, release manifests, and supported extension
folders. The core product is shipped as public versioned container images.

## Quickstart

```bash
cp .env.example .env
bun run self-hosted:doctor
docker compose up -d
bun run self-hosted:smoke
```

Open the app:

```text
http://localhost/sign-in
```

Default bootstrap credentials come from `.env`. Change
`SELF_HOSTED_BOOTSTRAP_PASSWORD` before using the instance outside local dev.

## What Community Allows

- Free self-hosted use, including production.
- Full product features with BYOK or local providers.
- Public stable updates.
- Local plugins, themes, custom connectors, and compose overrides.

## What Community Does Not Include

- Paid support, SLA, onboarding, or hotfix priority.
- White-label resale or resale as a managed service without a commercial
  agreement.
- IgnitionAI-hosted LLM, embedding, email, auth, or billing keys.

## Operations

```bash
bun run self-hosted:doctor
bun run self-hosted:backup
bun run self-hosted:update --manifest releases/community-manifest.json --dry-run
bun run self-hosted:update --manifest releases/community-manifest.json --apply
bun run self-hosted:restore --backup <backup-id> --confirm <backup-id>
```

Production `--apply` requires a signed release manifest with real sha256 image
digests and a local backup when the manifest requires one.
