## Finding: OBS-004 — stderr für stdio-Server: stdout reserviert für Protocol

| Feld | Wert |
|---|---|
| **Severity** | critical |
| **Status** | open |
| **Server** | `swiss-transport-mcp` |
| **Check-Reference** | `OBS-004` |
| **PDF-Reference** | Sec 6.3 |
| **Audit-Datum** | 2026-06-03 |
| **Auditor** | mcp-audit Skill (automatisiert) |
| **Verification-Status** | `partial` |

### Observed Behavior

- No print() statements anywhere in src/ (grep clean)
- No logging.basicConfig writing to stdout; loggers are unconfigured (NullHandler-equivalent) so stdio stream stays clean

### Gaps (Abweichung vom Best-Practice-Katalog)

- No explicit logging.basicConfig(stream=sys.stderr) — best-practice requires logging be pinned to stderr for stdio transport (Modus 2 pass-pattern not met)

### Remediation

```diff
+import sys
+logging.basicConfig(stream=sys.stderr, level=logging.INFO,
+    format="%(asctime)s %(name)s %(levelname)s: %(message)s")
```
In `server.py` vor `mcp.run()` einfuegen, damit Logging garantiert auf stderr geht und stdout fuer das JSON-RPC-Protokoll reserviert bleibt.

### Effort Estimate

**S** — Logging-Konfiguration ergaenzen.

### Verification After Fix

- Re-Audit dieses Checks (OBS-004) gegen denselben Katalog-Stand (catalog_hash in `audit-meta.json`)
- Wo moeglich: Pytest-Test, der das Anti-Pattern abprueft
