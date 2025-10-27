HubSpot integration notes
========================

Required HubSpot token scopes
-----------------------------

- The CI and CLI require a HubSpot token with at least the following scope(s):
  - crm.objects.contacts.read

CI secret
---------

- Name: `CLIENTS_TOML_B64` (base64-encoded single-line contents of `clients.toml`).
- Do NOT commit plaintext `clients.toml` or `clients.toml.b64`.

Per-client tokens
-----------------

- You may supply a `hubspot_token` per client in `clients.toml`. The CLI validates per-client tokens and will fall back to the global token if the per-client token does not validate.

Troubleshooting
---------------

- If your CI run shows `HubSpot API listing failed` or `Invalid request`, verify the token scopes and that the token is a private app token (not an OAuth app with limited scopes).
- Locally you can validate a token:

```bash
export HUBSPOT_TOKEN=pat-xxxx
python -c "from ada import hubspot; print(len(hubspot.list_owners()))"
```
