# Customization

Automatic updates assume the product core inside the container images is not
modified.

Supported customization surfaces:

- `.env`
- `docker-compose.override.yml`
- `plugins/`
- `themes/`
- `custom-connectors/`
- external services through API, SDK, or MCP

Extensions should include an `ignition-extension.json` manifest:

```json
{
  "id": "customer-theme",
  "name": "customer-theme",
  "type": "theme",
  "version": "1.0.0",
  "compatibility": {
    "minCore": "2026.05.0",
    "maxCore": "2026.12.0",
    "extensionApi": "1.0"
  },
  "hooks": [{ "name": "theme.tokens" }]
}
```

V1 extension hooks are explicit and declarative. Community does not execute
arbitrary plugin code. Supported hooks:

- `admin.diagnostics.card` for plugin metadata visible in self-hosted diagnostics.
- `theme.tokens` for theme token packs.
- `customConnector.registry` for custom connector registration.

Custom connectors must declare connector metadata:

```json
{
  "id": "acme-crm-extension",
  "name": "Acme CRM Connector",
  "type": "custom-connector",
  "version": "1.0.0",
  "compatibility": {
    "extensionApi": "1.0"
  },
  "hooks": [{ "name": "customConnector.registry" }],
  "connector": {
    "id": "acme-crm",
    "name": "Acme CRM",
    "protocol": "http",
    "baseUrlEnv": "ACME_CRM_BASE_URL"
  }
}
```

To assert that a mounted extension is visible during smoke tests:

```bash
SELF_HOSTED_SMOKE_EXPECT_EXTENSION=customer-theme bun run self-hosted:smoke
```

Direct source patches inside core images are outside the automatic update
contract.
