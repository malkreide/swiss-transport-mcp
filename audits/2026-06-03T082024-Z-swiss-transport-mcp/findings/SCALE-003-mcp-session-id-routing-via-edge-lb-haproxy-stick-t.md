## Finding: SCALE-003 — Mcp-Session-Id Routing via Edge-LB (HAProxy Stick-Tables)

| Feld | Wert |
|---|---|
| **Severity** | high |
| **Status** | open |
| **Server** | `swiss-transport-mcp` |
| **Check-Reference** | `SCALE-003` |
| **PDF-Reference** | Sec 5.2 |
| **Audit-Datum** | 2026-06-03 |
| **Auditor** | mcp-audit Skill (automatisiert) |
| **Verification-Status** | `partial` |

### Observed Behavior

- Single-instance → no edge-LB routing required today

### Gaps (Abweichung vom Best-Practice-Katalog)

- No Mcp-Session-Id edge routing for horizontal scale-out (deferred until multi-instance)

### Remediation

Bei horizontaler Skalierung `Mcp-Session-Id`-basiertes Routing am Edge-LB (HAProxy Stick-Tables o.ae.) einrichten. Aktuell als nicht-anwendbar (Single-Instance) dokumentieren.

### Effort Estimate

**M** — Edge-Routing definieren (nur bei Scale-out).

### Verification After Fix

- Re-Audit dieses Checks (SCALE-003) gegen denselben Katalog-Stand (catalog_hash in `audit-meta.json`)
- Wo moeglich: Pytest-Test, der das Anti-Pattern abprueft
