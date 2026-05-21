# Community Quickstart

## 1. Configure

```bash
cp .env.example .env
```

Set at least:

- `ENCRYPTION_KEY`
- `SELF_HOSTED_BOOTSTRAP_EMAIL`
- `SELF_HOSTED_BOOTSTRAP_PASSWORD`
- BYOK provider keys such as `OPENAI_API_KEY` or local provider settings

Community uses:

- `IGNITION_EDITION=community`
- `BILLING_PROVIDER=none`
- `AUTH_PROVIDER=local`
- `EMAIL_PROVIDER=none`
- `IGNITION_IMAGE_PLATFORM=linux/amd64`

Keep `IGNITION_IMAGE_PLATFORM=linux/amd64` on Apple Silicon. Community V1
images are amd64 images and Docker Desktop runs them through emulation.

## 2. Check

```bash
bun run self-hosted:doctor
```

## 3. Start

```bash
docker compose pull
docker compose up -d
bun run self-hosted:smoke
```

The `migrate` service applies the current schema and bootstraps the local admin
user before the API starts.

## 4. Open

```text
http://localhost/sign-in
```

Use the bootstrap email/password configured in `.env`.
