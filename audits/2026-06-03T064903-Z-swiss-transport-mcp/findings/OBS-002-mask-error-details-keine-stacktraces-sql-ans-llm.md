## Finding: OBS-002 — Mask Error Details: keine Stacktraces / SQL ans LLM

| Feld | Wert |
|---|---|
| **Severity** | high |
| **Status** | open |
| **Server** | `swiss-transport-mcp` |
| **Check-Reference** | `OBS-002` |
| **PDF-Reference** | Sec 6.2 |
| **Audit-Datum** | 2026-06-03 |
| **Auditor** | mcp-audit Skill (automatisiert) |
| **Verification-Status** | `partial` |

### Observed Behavior

- handle_api_error maps status codes to friendly messages (api_client.py:151-163)

### Gaps (Abweichung vom Best-Practice-Katalog)

- Raw upstream response bodies are forwarded to the LLM: api_client.py:163 and api_infrastructure.py:257,317 include e.response.text[:200..300] — may leak internal error/stacktrace detail

### Remediation

`e.response.text[:200]`/`[:300]` aus den Fehlermeldungen in `api_client.py:163` und `api_infrastructure.py:257,317` entfernen oder durch generische Meldung + interne (stderr) Log-Zeile ersetzen. Dem LLM nur Status-Code + Klartext-Kategorie zurueckgeben.

### Effort Estimate

**S** — Upstream-Text nicht weiterreichen.

### Verification After Fix

- Re-Audit dieses Checks (OBS-002) gegen denselben Katalog-Stand (catalog_hash in `audit-meta.json`)
- Wo moeglich: Pytest-Test, der das Anti-Pattern abprueft
