## Finding: SEC-009 — Session-ID Cryptographic Binding (user_id:session_id)

| Feld | Wert |
|---|---|
| **Severity** | critical |
| **Status** | open |
| **Server** | `swiss-transport-mcp` |
| **Check-Reference** | `SEC-009` |
| **PDF-Reference** | Sec 4.6 |
| **Audit-Datum** | 2026-06-03 |
| **Auditor** | mcp-audit Skill (automatisiert) |
| **Verification-Status** | `partial` |

### Observed Behavior

- No custom session-id generation in code — Mcp-Session-Id handling delegated to the MCP SDK SSE transport (no weak PRNG / timestamp IDs in src/)

### Gaps (Abweichung vom Best-Practice-Katalog)

- auth_model=none → no user-identity binding of session-id possible (<user_id>:<session_id> pattern not implemented)
- SDK session-id entropy not independently verified for the SSE deployment path

### Remediation

1. Solange `auth_model=none`: SSE-Deployment hinter Reverse-Proxy mit Auth oder nur intern erreichbar betreiben.
2. SDK-Version pinnen und verifizieren, dass `Mcp-Session-Id` per `secrets.token_urlsafe(32)`/UUIDv4 generiert wird.
3. Bei Einfuehrung von Auth: Session an validierte `user_id` binden (`<user_id>:<session_id>`).

### Effort Estimate

**M** — abhaengig von Auth-Entscheidung.

### Verification After Fix

- Re-Audit dieses Checks (SEC-009) gegen denselben Katalog-Stand (catalog_hash in `audit-meta.json`)
- Wo moeglich: Pytest-Test, der das Anti-Pattern abprueft
