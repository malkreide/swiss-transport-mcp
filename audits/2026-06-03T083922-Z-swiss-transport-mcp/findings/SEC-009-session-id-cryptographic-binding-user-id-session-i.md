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

- SDK generates cryptographically-random Mcp-Session-Id; stateless mode (MCP_STATELESS) removes server-side session state, shrinking the hijacking surface; SECURITY.md documents running behind an auth proxy / trusted network

### Gaps (Abweichung vom Best-Practice-Katalog)

- No user-identity binding of the session id — not possible while auth_model=none. Residual impact negligible: hijacking grants only the same read-only public-data queries. Revisit if auth/PII/write is added.

### Remediation

1. Solange `auth_model=none`: SSE-Deployment hinter Reverse-Proxy mit Auth oder nur intern erreichbar betreiben.
2. SDK-Version pinnen und verifizieren, dass `Mcp-Session-Id` per `secrets.token_urlsafe(32)`/UUIDv4 generiert wird.
3. Bei Einfuehrung von Auth: Session an validierte `user_id` binden (`<user_id>:<session_id>`).

### Effort Estimate

**M** — abhaengig von Auth-Entscheidung.

### Verification After Fix

- Re-Audit dieses Checks (SEC-009) gegen denselben Katalog-Stand (catalog_hash in `audit-meta.json`)
- Wo moeglich: Pytest-Test, der das Anti-Pattern abprueft
