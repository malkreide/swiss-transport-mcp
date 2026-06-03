## Finding: SEC-016 — 0.0.0.0-Binding-Prevention (NeighborJack)

| Feld | Wert |
|---|---|
| **Severity** | critical |
| **Status** | open |
| **Server** | `swiss-transport-mcp` |
| **Check-Reference** | `SEC-016` |
| **PDF-Reference** | Sec 4 (Empirie 2025) |
| **Audit-Datum** | 2026-06-03 |
| **Auditor** | mcp-audit Skill (automatisiert) |
| **Verification-Status** | `fail` |

### Observed Behavior

- server.py:947 — host = os.environ.get("MCP_HOST", "0.0.0.0") binds SSE listener to ALL interfaces by default

### Gaps (Abweichung vom Best-Practice-Katalog)

- Default MUST be 127.0.0.1 for local; 0.0.0.0 only via explicit opt-in for container deployment (NeighborJack exposure on shared networks)

### Remediation

```diff
-        host = os.environ.get("MCP_HOST", "0.0.0.0")
+        # Lokal sicher per Default; 0.0.0.0 nur explizit fuer Container
+        host = os.environ.get("MCP_HOST", "127.0.0.1")
```
1. Default-Host auf `127.0.0.1` setzen.
2. Im Deployment (Render/Railway) `MCP_HOST=0.0.0.0` explizit als Env-Var setzen.
3. README-Deployment-Sektion entsprechend dokumentieren.

### Effort Estimate

**S** — eine Zeile in `server.py`.

### Verification After Fix

- Re-Audit dieses Checks (SEC-016) gegen denselben Katalog-Stand (catalog_hash in `audit-meta.json`)
- Wo moeglich: Pytest-Test, der das Anti-Pattern abprueft
