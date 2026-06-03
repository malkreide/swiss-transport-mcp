## Finding: SEC-008 — Pre-Configuration Consent für Local-Server-Installation

| Feld | Wert |
|---|---|
| **Severity** | medium |
| **Status** | open |
| **Server** | `swiss-transport-mcp` |
| **Check-Reference** | `SEC-008` |
| **PDF-Reference** | Sec 4.5 |
| **Audit-Datum** | 2026-06-03 |
| **Auditor** | mcp-audit Skill (automatisiert) |
| **Verification-Status** | `partial` |

### Observed Behavior

- Install + Claude Desktop config documented (README.md:56-146)

### Gaps (Abweichung vom Best-Practice-Katalog)

- No explicit pre-configuration consent step for local-server installation documented

### Remediation

Im README einen kurzen Pre-Configuration-Consent-Hinweis ergaenzen (welche Daten der Server abruft, welche Keys er nutzt), bevor der User ihn in Claude Desktop registriert.

### Effort Estimate

**S** — Consent-Hinweis dokumentieren.

### Verification After Fix

- Re-Audit dieses Checks (SEC-008) gegen denselben Katalog-Stand (catalog_hash in `audit-meta.json`)
- Wo moeglich: Pytest-Test, der das Anti-Pattern abprueft
