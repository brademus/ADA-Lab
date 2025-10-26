# ADA (Consultant Mode)

This repository contains ADA, a small audit tool for HubSpot contact data. Consultant Mode adds multi-client batch audits with a master dashboard.

## Consultant Mode (quick)

1. Provide a clients config file (`clients.toml` or `clients.yaml`) with per-client sections. Example (local-only; do NOT commit secrets):

```toml
[client_acme_corp]
name = "Acme Corporation"
hubspot_token = "pat-xxxxxxxxxxxxxxxxx"

[client_initech]
name = "Initech"
hubspot_token = "pat-yyyyyyyyyyyyyyyy"
```

2. Run a single-client audit (no network pull):

```bash
python cli.py audit --client acme_corp --config clients.toml --skip-pull
```

3. Run batch audits for all clients (CI style):

```bash
python cli.py audit --all --config clients.toml --out-root audits
```

After a run, per-client outputs appear in `audits/<slug>/` and a master dashboard is written to `audits/index.html` when running `--all`.

## CI integration

CI will hydrate `clients.toml` from a Base64 repository secret named `CLIENTS_TOML_B64` and run the batch audits. To create the secret locally (Linux/macOS):

```bash
base64 -w0 clients.toml > clients.toml.b64   # Linux
# macOS: base64 clients.toml | tr -d '\n' > clients.toml.b64

# Then add as a repo secret (recommended via gh CLI):
gh secret set CLIENTS_TOML_B64 --body "$(cat clients.toml.b64)" --repo brademus/ADA-Lab
```

The GitHub Actions workflow decodes that secret and runs:

```bash
python cli.py audit --all --config clients.toml --limit 5000 --out-root audits
```

Artifacts: the workflow uploads `audits/**` as the `ada-audits` artifact.

## Notes
- `clients.toml` is intentionally ignored in `.gitignore` for local usage — CI must supply it via `CLIENTS_TOML_B64`.
- If a client audit fails, the run continues for other clients and the error is written to `audits/<slug>/error.txt`; the dashboard will mark that client as FAILED.
