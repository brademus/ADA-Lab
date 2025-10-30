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

### HTML output mode

By default, `summary.html` is produced by converting Markdown to HTML (using the `markdown` package).
If you prefer a dependency-free HTML page, pass the `--html-only` flag (or legacy alias `--pure-html`) to either `analyze` or `audit`:

```bash
# Analyze a CSV and write a pure-HTML summary (no markdown conversion)
python cli.py analyze --source csv --path contacts.csv --out-dir reports --html-only

# Batch audit clients with pure-HTML summaries
python cli.py audit --all --config clients.toml --limit 5000 --out-root audits --html-only
```

## Tests and dev ergonomics

- Run tests locally:

```bash
make test
```

- Quick smoke (local-only):

```bash
make smoke
```

Synthetic summary fixtures for dashboard tests live under `ada/tests/fixtures/`.

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

## Universal AI Closer (Phase 1)

This release adds a minimal outreach loop for Gmail with human approval required before sending. Key features:

- Per-client outreach config fields in `clients.toml` (example fields: `channel = "gmail"`, `daily_cap`, `quiet_hours`, `brand_voice`, `gmail_user`, `gmail_refresh_token`, `gmail_client_id`, `gmail_client_secret`).
- New CLI group `outreach` with subcommands: `plan`, `draft`, `approve`, `send`, `replies`, `metrics`.
- Drafts and outbox persisted in `audits/<slug>/outbox.sqlite` (uploads to CI artifact). Drafting runs in CI but sending is disabled by default.
- Metrics are stored in `audits/<slug>/outreach_metrics.json` and merged into `summary.json` and the master dashboard.

Safety: this Phase 1 requires manual approval before any message is sent. CI runs `outreach plan` and `outreach draft` to produce artifacts for reviewers.

Example: build plans and draft messages locally:

```bash
python cli.py outreach plan --client acme_corp --config clients.toml --limit 200
python cli.py outreach draft --client acme_corp --config clients.toml --limit 50
```

To approve and send (requires Gmail creds in `clients.toml`):

```bash
python cli.py outreach approve --client acme_corp --config clients.toml --id <message-id>
python cli.py outreach send --client acme_corp --config clients.toml --max 25
```

See `CONTRIBUTING.md` for notes on secrets and CI.

## Notes
-- `clients.toml` is intentionally ignored in `.gitignore` for local usage — CI must supply it via `CLIENTS_TOML_B64`.
- If a client audit fails, the run continues for other clients and the error is written to `audits/<slug>/error.txt`; the dashboard will mark that client as FAILED.
