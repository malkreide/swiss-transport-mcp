## Finding: ARCH-009 — Tool Annotations: readOnlyHint, destructiveHint, idempotentHint, openWorldHint

| Feld | Wert |
|---|---|
| **Severity** | high |
| **Status** | open |
| **Server** | `swiss-transport-mcp` |
| **Check-Reference** | `ARCH-009` |
| **PDF-Reference** | Anhang A5 |
| **Audit-Datum** | 2026-06-03 |
| **Auditor** | mcp-audit Skill (automatisiert) |
| **Verification-Status** | `partial` |

### Observed Behavior

- 6 core tools declare full annotations

### Gaps (Abweichung vom Best-Practice-Katalog)

- 5 extension tools still use bare @mcp.tool() without readOnlyHint/etc (server.py:781,822,889,938,992) — not addressed in remediation

### Remediation

Die fuenf Extension-Tools (`get_transport_disruptions`, `get_train_occupancy`, `get_ticket_price`, `get_train_composition`, `check_transport_api_status`) mit dem gleichen `annotations={...}`-Block wie die Core-Tools versehen (`readOnlyHint=True`, `destructiveHint=False`, `idempotentHint` je nach Echtzeit-Charakter, `openWorldHint=True`).

### Effort Estimate

**S** — Annotations an 5 Tools ergaenzen.

### Verification After Fix

- Re-Audit dieses Checks (ARCH-009) gegen denselben Katalog-Stand (catalog_hash in `audit-meta.json`)
- Wo moeglich: Pytest-Test, der das Anti-Pattern abprueft
