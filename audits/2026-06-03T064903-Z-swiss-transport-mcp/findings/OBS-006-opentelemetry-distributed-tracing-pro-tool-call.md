## Finding: OBS-006 — OpenTelemetry Distributed Tracing pro Tool-Call

| Feld | Wert |
|---|---|
| **Severity** | medium |
| **Status** | open |
| **Server** | `swiss-transport-mcp` |
| **Check-Reference** | `OBS-006` |
| **PDF-Reference** | Anhang B10 |
| **Audit-Datum** | 2026-06-03 |
| **Auditor** | mcp-audit Skill (automatisiert) |
| **Verification-Status** | `fail` |

### Observed Behavior

- (kein Positiv-Beleg; Anforderung nicht erfuellt)

### Gaps (Abweichung vom Best-Practice-Katalog)

- No OpenTelemetry / distributed tracing instrumentation on tool calls (no otel imports anywhere)

### Remediation

OpenTelemetry-Instrumentierung pro Tool-Call ergaenzen (Span je Tool, Attribute fuer API-Name/Dauer/Status). Optional, je nach Observability-Anforderung.

### Effort Estimate

**L** — OpenTelemetry-Tracing.

### Verification After Fix

- Re-Audit dieses Checks (OBS-006) gegen denselben Katalog-Stand (catalog_hash in `audit-meta.json`)
- Wo moeglich: Pytest-Test, der das Anti-Pattern abprueft
