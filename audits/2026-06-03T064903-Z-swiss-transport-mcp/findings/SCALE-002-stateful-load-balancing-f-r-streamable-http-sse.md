## Finding: SCALE-002 — Stateful Load Balancing für Streamable HTTP / SSE

| Feld | Wert |
|---|---|
| **Severity** | high |
| **Status** | open |
| **Server** | `swiss-transport-mcp` |
| **Check-Reference** | `SCALE-002` |
| **PDF-Reference** | Sec 5.2 |
| **Audit-Datum** | 2026-06-03 |
| **Auditor** | mcp-audit Skill (automatisiert) |
| **Verification-Status** | `partial` |

### Observed Behavior

- Single-instance Render deployment documented (README.md:152-156)

### Gaps (Abweichung vom Best-Practice-Katalog)

- No stateful/sticky load-balancing strategy documented for multi-instance SSE scale-out (session affinity undefined)

### Remediation

Falls Multi-Instance geplant: Sticky-Sessions / shared Session-Store (Redis) festlegen. Solange Single-Instance: explizit als Constraint im README dokumentieren.

### Effort Estimate

**M** — Skalierungsstrategie dokumentieren.

### Verification After Fix

- Re-Audit dieses Checks (SCALE-002) gegen denselben Katalog-Stand (catalog_hash in `audit-meta.json`)
- Wo moeglich: Pytest-Test, der das Anti-Pattern abprueft
