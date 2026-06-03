## Finding: SEC-004 — SSRF-Prevention: HTTPS-Enforcement + IP-Blocklisting

| Feld | Wert |
|---|---|
| **Severity** | critical |
| **Status** | open |
| **Server** | `swiss-transport-mcp` |
| **Check-Reference** | `SEC-004` |
| **PDF-Reference** | Sec 4.4 |
| **Audit-Datum** | 2026-06-03 |
| **Auditor** | mcp-audit Skill (automatisiert) |
| **Verification-Status** | `partial` |

### Observed Behavior

- All upstream URLs are hardcoded https:// constants (api_client.py:19-21, api_infrastructure.py:376-410) — no user/LLM-supplied URLs reach the HTTP client
- Tool args are stop names/IDs/coordinates, never URLs (server.py:99-205) → no direct SSRF surface

### Gaps (Abweichung vom Best-Practice-Katalog)

- api_client.py:85,121 — TRANSPORT_SSL_VERIFY=false disables TLS verification (MITM enabler), no guard preventing it in production
- No explicit HTTPS-enforcement / private-IP & metadata-endpoint (169.254.169.254) blocklist helper
- TRANSPORT_CKAN_URL (api_client.py:110) allows operator override of base URL with no scheme validation

### Remediation

1. `TRANSPORT_SSL_VERIFY=false` in Produktion verbieten (z.B. nur erlauben wenn `ENV=dev`).
2. Falls je benutzergesteuerte URLs hinzukommen: `urlparse`-Schema-Check (nur `https`) + Blocklist fuer `169.254.169.254`, `127.0.0.0/8`, RFC-1918.
3. `TRANSPORT_CKAN_URL`-Override gegen Allow-List der opentransportdata.swiss-Hosts validieren.

### Effort Estimate

**M** — Validierungs-Helper + SSL-Guard.

### Verification After Fix

- Re-Audit dieses Checks (SEC-004) gegen denselben Katalog-Stand (catalog_hash in `audit-meta.json`)
- Wo moeglich: Pytest-Test, der das Anti-Pattern abprueft
