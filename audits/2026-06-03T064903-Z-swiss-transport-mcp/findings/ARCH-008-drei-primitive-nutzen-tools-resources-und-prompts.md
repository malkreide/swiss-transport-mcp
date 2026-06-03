## Finding: ARCH-008 — Drei Primitive nutzen: Tools, Resources und Prompts

| Feld | Wert |
|---|---|
| **Severity** | medium |
| **Status** | open |
| **Server** | `swiss-transport-mcp` |
| **Check-Reference** | `ARCH-008` |
| **PDF-Reference** | Anhang A2 |
| **Audit-Datum** | 2026-06-03 |
| **Auditor** | mcp-audit Skill (automatisiert) |
| **Verification-Status** | `partial` |

### Observed Behavior

- Tools primitive (11 @mcp.tool) and Resources primitive (transport://datasets, transport://info — server.py:884,898) both used

### Gaps (Abweichung vom Best-Practice-Katalog)

- Prompts primitive (@mcp.prompt) not used — only 2 of 3 MCP primitives present

### Remediation

Mindestens einen `@mcp.prompt` hinzufuegen (z.B. 'Schulreise planen'-Prompt-Template), um alle drei MCP-Primitive (Tools/Resources/Prompts) zu nutzen.

### Effort Estimate

**S** — Prompts-Primitive ergaenzen.

### Verification After Fix

- Re-Audit dieses Checks (ARCH-008) gegen denselben Katalog-Stand (catalog_hash in `audit-meta.json`)
- Wo moeglich: Pytest-Test, der das Anti-Pattern abprueft
