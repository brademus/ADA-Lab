.PHONY: test smoke

## Run unit tests quietly
test:
	PYTHONPATH=. pytest -q

## Smoke: run a tiny audit with a synthetic client and HTML-only summary
## Note: local-only; not used in CI.
smoke:
	@echo "[smoke] Preparing synthetic client config and CSV"
	@mkdir -p audits/smoke
	@echo "id,email,firstname,lastname" > audits/smoke/contacts.csv
	@echo "1,alice@example.com,Alice,Smith" >> audits/smoke/contacts.csv
	@echo "2,bob@example.com,Bob,Jones" >> audits/smoke/contacts.csv
	@echo "[client_smoke]" > /tmp/clients.smoke.toml
	@echo "name = \"Smoke\"" >> /tmp/clients.smoke.toml
	@echo "hubspot_token = \"dummy\"" >> /tmp/clients.smoke.toml
	python cli.py audit --client smoke --config /tmp/clients.smoke.toml --limit 5 --out-root audits --skip-pull --html-only
	@echo "[smoke] Dashboard: audits/index.html"
