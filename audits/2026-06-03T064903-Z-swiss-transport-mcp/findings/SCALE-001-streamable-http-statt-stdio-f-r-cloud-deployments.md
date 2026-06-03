## Finding: SCALE-001 — Streamable HTTP statt stdio für Cloud-Deployments

| Feld | Wert |
|---|---|
| **Severity** | high |
| **Status** | open |
| **Server** | `swiss-transport-mcp` |
| **Check-Reference** | `SCALE-001` |
| **PDF-Reference** | Sec 5.1 |
| **Audit-Datum** | 2026-06-03 |
| **Auditor** | mcp-audit Skill (automatisiert) |
| **Verification-Status** | `partial` |

### Observed Behavior

- Cloud path exists and avoids raw stdio for browser access (server.py:946-950)

### Gaps (Abweichung vom Best-Practice-Katalog)

- Uses legacy SSE transport (mcp.run(transport="sse"), server.py:950) instead of the current Streamable HTTP transport recommended for cloud deployments

### Remediation

`mcp.run(transport="sse", ...)` auf den aktuellen Streamable-HTTP-Transport des MCP-SDK umstellen; SSE gilt als Legacy. Deployment-Doku in README aktualisieren.

### Effort Estimate

**M** — Transport auf Streamable HTTP migrieren.

### Verification After Fix

- Re-Audit dieses Checks (SCALE-001) gegen denselben Katalog-Stand (catalog_hash in `audit-meta.json`)
- Wo moeglich: Pytest-Test, der das Anti-Pattern abprueft
