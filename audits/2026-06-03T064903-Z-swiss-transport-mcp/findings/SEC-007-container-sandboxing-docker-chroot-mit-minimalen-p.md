## Finding: SEC-007 — Container-Sandboxing: Docker / chroot mit minimalen Privilegien

| Feld | Wert |
|---|---|
| **Severity** | high |
| **Status** | open |
| **Server** | `swiss-transport-mcp` |
| **Check-Reference** | `SEC-007` |
| **PDF-Reference** | Sec 4.5 |
| **Audit-Datum** | 2026-06-03 |
| **Auditor** | mcp-audit Skill (automatisiert) |
| **Verification-Status** | `partial` |

### Observed Behavior

- Managed-platform sandboxing implied by Render deployment model (README.md:152)

### Gaps (Abweichung vom Best-Practice-Katalog)

- No Dockerfile / container definition in repo → no explicit minimal-privilege, non-root, or chroot sandboxing for the cloud path

### Remediation

Multi-Stage-Dockerfile hinzufuegen: non-root User, minimal base image (`python:3.12-slim`), nur noetige Dependencies, `--read-only`-faehig. Render/Railway auf das Image umstellen.

### Effort Estimate

**M** — Dockerfile mit Haertung.

### Verification After Fix

- Re-Audit dieses Checks (SEC-007) gegen denselben Katalog-Stand (catalog_hash in `audit-meta.json`)
- Wo moeglich: Pytest-Test, der das Anti-Pattern abprueft
