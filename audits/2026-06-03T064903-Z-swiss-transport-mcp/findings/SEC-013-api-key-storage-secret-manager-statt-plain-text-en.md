## Finding: SEC-013 — API-Key-Storage: Secret Manager statt Plain-Text Env-Vars

| Feld | Wert |
|---|---|
| **Severity** | high |
| **Status** | open |
| **Server** | `swiss-transport-mcp` |
| **Check-Reference** | `SEC-013` |
| **PDF-Reference** | Sec 4 (Empirie 2025) |
| **Audit-Datum** | 2026-06-03 |
| **Auditor** | mcp-audit Skill (automatisiert) |
| **Verification-Status** | `partial` |

### Observed Behavior

- API keys sourced from environment variables (acceptable production minimum) — api_client.py:28-56

### Gaps (Abweichung vom Best-Practice-Katalog)

- No secret-manager integration (Vault / cloud secret store) recommended for production; plain env-vars only
- No .gitignore guarding a local .env from accidental commit

### Remediation

1. `.gitignore` mit `.env` ergaenzen.
2. Fuer Produktion Secret-Manager (Render/Railway Secrets bzw. Vault) statt Plain-Env empfehlen/dokumentieren.
3. Optional `pydantic.SecretStr` fuer In-Memory-Repraesentation.

### Effort Estimate

**M** — Secret-Management haerten.

### Verification After Fix

- Re-Audit dieses Checks (SEC-013) gegen denselben Katalog-Stand (catalog_hash in `audit-meta.json`)
- Wo moeglich: Pytest-Test, der das Anti-Pattern abprueft
