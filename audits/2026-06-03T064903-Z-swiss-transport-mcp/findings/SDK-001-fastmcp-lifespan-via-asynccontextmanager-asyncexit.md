## Finding: SDK-001 — FastMCP Lifespan via @asynccontextmanager + AsyncExitStack

| Feld | Wert |
|---|---|
| **Severity** | high |
| **Status** | open |
| **Server** | `swiss-transport-mcp` |
| **Check-Reference** | `SDK-001` |
| **PDF-Reference** | Sec 3.1 |
| **Audit-Datum** | 2026-06-03 |
| **Auditor** | mcp-audit Skill (automatisiert) |
| **Verification-Status** | `partial` |

### Observed Behavior

- Extension client created lazily and reused (server.py:_get_ext_client)

### Gaps (Abweichung vom Best-Practice-Katalog)

- No FastMCP lifespan via @asynccontextmanager + AsyncExitStack; the httpx AsyncClient in TransportAPIClient has close() (api_infrastructure.py:323) but is never invoked — connections not cleanly torn down on shutdown
- api_client.py opens a fresh httpx.AsyncClient per request (api_client.py:86,122) instead of a lifespan-managed pooled client

### Remediation

Einen `@asynccontextmanager`-Lifespan mit `AsyncExitStack` einrichten, der EINEN gepoolten `httpx.AsyncClient` erstellt und beim Shutdown sauber schliesst. `api_client.py` von Per-Request-Clients auf den geteilten Client umstellen; `TransportAPIClient.close()` im Lifespan-Teardown aufrufen.

### Effort Estimate

**M** — FastMCP Lifespan einfuehren.

### Verification After Fix

- Re-Audit dieses Checks (SDK-001) gegen denselben Katalog-Stand (catalog_hash in `audit-meta.json`)
- Wo moeglich: Pytest-Test, der das Anti-Pattern abprueft
