## Finding: ARCH-012 — protocolVersion-Pinning + CHANGELOG + SDK-Update-Disziplin

| Feld | Wert |
|---|---|
| **Severity** | medium |
| **Status** | open |
| **Server** | `swiss-transport-mcp` |
| **Check-Reference** | `ARCH-012` |
| **PDF-Reference** | Anhang A9 |
| **Audit-Datum** | 2026-06-03 |
| **Auditor** | mcp-audit Skill (automatisiert) |
| **Verification-Status** | `partial` |

### Observed Behavior

- CHANGELOG.md maintained with dated, semver-style entries (CHANGELOG.md:6)

### Gaps (Abweichung vom Best-Practice-Katalog)

- No MCP protocolVersion pinning; mcp[cli]>=1.0.0 is an unbounded floating lower bound (pyproject.toml) → SDK drift risk

### Remediation

MCP-`protocolVersion` explizit pinnen/dokumentieren und `mcp[cli]` mit Obergrenze versehen (z.B. `>=1.0.0,<2.0.0`), um unkontrollierte SDK-Drift zu vermeiden.

### Effort Estimate

**S** — Versionen pinnen.

### Verification After Fix

- Re-Audit dieses Checks (ARCH-012) gegen denselben Katalog-Stand (catalog_hash in `audit-meta.json`)
- Wo moeglich: Pytest-Test, der das Anti-Pattern abprueft
