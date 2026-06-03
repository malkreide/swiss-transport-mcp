## Finding: SEC-022 — Tool-Hash-Pinning + Namespace-Präfix gegen Rug Pull

| Feld | Wert |
|---|---|
| **Severity** | high |
| **Status** | open |
| **Server** | `swiss-transport-mcp` |
| **Check-Reference** | `SEC-022` |
| **PDF-Reference** | Anhang B4 |
| **Audit-Datum** | 2026-06-03 |
| **Auditor** | mcp-audit Skill (automatisiert) |
| **Verification-Status** | `partial` |

### Observed Behavior

- Namespace prefixing present: core tools transport_*, extension tools get_transport_*/get_train_* (server.py tool names)

### Gaps (Abweichung vom Best-Practice-Katalog)

- No tool-hash-pinning / integrity manifest to detect rug-pull tool redefinition

### Remediation

Namespace-Praefix konsistent halten (alle Tools `transport_*`). Optional Tool-Hash-Manifest pflegen, das die registrierte Tool-Liste/Signaturen pinnt, um Rug-Pull-Redefinition zu erkennen.

### Effort Estimate

**M** — Tool-Integritaet.

### Verification After Fix

- Re-Audit dieses Checks (SEC-022) gegen denselben Katalog-Stand (catalog_hash in `audit-meta.json`)
- Wo moeglich: Pytest-Test, der das Anti-Pattern abprueft
