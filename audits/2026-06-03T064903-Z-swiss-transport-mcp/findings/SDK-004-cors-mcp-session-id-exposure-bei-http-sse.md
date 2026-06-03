## Finding: SDK-004 — CORS Mcp-Session-Id Exposure bei HTTP/SSE

| Feld | Wert |
|---|---|
| **Severity** | high |
| **Status** | open |
| **Server** | `swiss-transport-mcp` |
| **Check-Reference** | `SDK-004` |
| **PDF-Reference** | Sec 3.1 |
| **Audit-Datum** | 2026-06-03 |
| **Auditor** | mcp-audit Skill (automatisiert) |
| **Verification-Status** | `partial` |

### Observed Behavior

- SSE transport enabled for browser/claude.ai access (README.md:148-156)

### Gaps (Abweichung vom Best-Practice-Katalog)

- No explicit CORS configuration exposing Mcp-Session-Id header for cross-origin browser clients (relies on framework defaults, unverified)

### Remediation

Fuer den SSE/HTTP-Pfad CORS so konfigurieren, dass `Mcp-Session-Id` via `expose_headers` fuer Browser-Clients sichtbar ist; erlaubte Origins (z.B. claude.ai) explizit setzen.

### Effort Estimate

**S** — CORS explizit konfigurieren.

### Verification After Fix

- Re-Audit dieses Checks (SDK-004) gegen denselben Katalog-Stand (catalog_hash in `audit-meta.json`)
- Wo moeglich: Pytest-Test, der das Anti-Pattern abprueft
