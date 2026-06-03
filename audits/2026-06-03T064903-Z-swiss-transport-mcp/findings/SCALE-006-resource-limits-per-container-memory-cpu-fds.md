## Finding: SCALE-006 — Resource-Limits per Container (Memory, CPU, FDs)

| Feld | Wert |
|---|---|
| **Severity** | medium |
| **Status** | open |
| **Server** | `swiss-transport-mcp` |
| **Check-Reference** | `SCALE-006` |
| **PDF-Reference** | Sec 5.3 |
| **Audit-Datum** | 2026-06-03 |
| **Auditor** | mcp-audit Skill (automatisiert) |
| **Verification-Status** | `fail` |

### Observed Behavior

- (kein Positiv-Beleg; Anforderung nicht erfuellt)

### Gaps (Abweichung vom Best-Practice-Katalog)

- No per-container resource limits (memory/CPU/FD) defined; no container manifest to attach them to

### Remediation

Im Deployment (Render/Railway bzw. Container-Orchestrierung) Memory-/CPU-/FD-Limits setzen und im README dokumentieren.

### Effort Estimate

**S** — Resource-Limits.

### Verification After Fix

- Re-Audit dieses Checks (SCALE-006) gegen denselben Katalog-Stand (catalog_hash in `audit-meta.json`)
- Wo moeglich: Pytest-Test, der das Anti-Pattern abprueft
