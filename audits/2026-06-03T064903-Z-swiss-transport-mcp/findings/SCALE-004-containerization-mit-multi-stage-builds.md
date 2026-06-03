## Finding: SCALE-004 — Containerization mit Multi-Stage-Builds

| Feld | Wert |
|---|---|
| **Severity** | medium |
| **Status** | open |
| **Server** | `swiss-transport-mcp` |
| **Check-Reference** | `SCALE-004` |
| **PDF-Reference** | Sec 5.3 |
| **Audit-Datum** | 2026-06-03 |
| **Auditor** | mcp-audit Skill (automatisiert) |
| **Verification-Status** | `fail` |

### Observed Behavior

- (kein Positiv-Beleg; Anforderung nicht erfuellt)

### Gaps (Abweichung vom Best-Practice-Katalog)

- No Dockerfile / multi-stage container build present despite documented cloud deployment

### Remediation

Multi-Stage-Dockerfile + `.dockerignore` hinzufuegen (deckt sich mit SEC-007).

### Effort Estimate

**M** — Containerization.

### Verification After Fix

- Re-Audit dieses Checks (SCALE-004) gegen denselben Katalog-Stand (catalog_hash in `audit-meta.json`)
- Wo moeglich: Pytest-Test, der das Anti-Pattern abprueft
