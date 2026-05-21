# Updates

Community uses the public stable release channel.

Always run a backup and dry-run before applying an update:

```bash
bun run self-hosted:backup
bun run self-hosted:update --manifest releases/community-manifest.json --dry-run
```

Apply requires:

- manifest `edition=community`
- real sha256 image digests
- valid Ed25519 signature in production
- compatible extension manifests
- backup when migrations require one

```bash
bun run self-hosted:update --manifest releases/community-manifest.json --apply
```

The update CLI writes `.self-hosted/docker-compose.release.yml` with
digest-pinned images, pulls those images, starts the release, runs migrations,
and then launches the smoke test.
