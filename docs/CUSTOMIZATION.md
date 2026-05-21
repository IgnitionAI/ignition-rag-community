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
  "name": "customer-theme",
  "type": "theme",
  "version": "1.0.0",
  "compatibility": {
    "minCore": "2026.05.0",
    "maxCore": "2026.12.0",
    "extensionApi": "1.0"
  }
}
```

Direct source patches inside core images are outside the automatic update
contract.
