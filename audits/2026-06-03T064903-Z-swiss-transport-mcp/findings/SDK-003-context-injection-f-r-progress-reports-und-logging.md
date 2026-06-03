## Finding: SDK-003 — Context Injection für Progress Reports und Logging

| Feld | Wert |
|---|---|
| **Severity** | medium |
| **Status** | open |
| **Server** | `swiss-transport-mcp` |
| **Check-Reference** | `SDK-003` |
| **PDF-Reference** | Sec 3.1 |
| **Audit-Datum** | 2026-06-03 |
| **Auditor** | mcp-audit Skill (automatisiert) |
| **Verification-Status** | `partial` |

### Observed Behavior

- Tools are fast single-shot reads where progress reporting is non-critical

### Gaps (Abweichung vom Best-Practice-Katalog)

- No Context (ctx) injection used for progress reports / structured logging on longer OJP trip calculations

### Remediation

Bei laengeren OJP-Trip-Berechnungen `ctx: Context` injizieren und `ctx.info()/ctx.report_progress()` fuer Progress/Logging nutzen.

### Effort Estimate

**S** — Context-Injection.

### Verification After Fix

- Re-Audit dieses Checks (SDK-003) gegen denselben Katalog-Stand (catalog_hash in `audit-meta.json`)
- Wo moeglich: Pytest-Test, der das Anti-Pattern abprueft
