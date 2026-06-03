## Finding: OBS-003 — Structured Logging mit RFC 5424 Severity-Stufen

| Feld | Wert |
|---|---|
| **Severity** | medium |
| **Status** | open |
| **Server** | `swiss-transport-mcp` |
| **Check-Reference** | `OBS-003` |
| **PDF-Reference** | Sec 6.3 |
| **Audit-Datum** | 2026-06-03 |
| **Auditor** | mcp-audit Skill (automatisiert) |
| **Verification-Status** | `partial` |

### Observed Behavior

- stdlib logging used with named logger and severity levels (logger.info/debug/warning across modules)

### Gaps (Abweichung vom Best-Practice-Katalog)

- No structured (JSON) logging and no explicit RFC 5424 severity formatting / handler configuration

### Remediation

Auf strukturierte Logs (JSON, z.B. `structlog`) mit RFC-5424-Severity umstellen und Handler explizit konfigurieren (zusammen mit OBS-004 stderr).

### Effort Estimate

**M** — Structured Logging.

### Verification After Fix

- Re-Audit dieses Checks (OBS-003) gegen denselben Katalog-Stand (catalog_hash in `audit-meta.json`)
- Wo moeglich: Pytest-Test, der das Anti-Pattern abprueft
