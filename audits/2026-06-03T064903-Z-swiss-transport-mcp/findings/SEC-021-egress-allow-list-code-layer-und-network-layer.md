## Finding: SEC-021 — Egress-Allow-List: Code-Layer und Network-Layer

| Feld | Wert |
|---|---|
| **Severity** | high |
| **Status** | open |
| **Server** | `swiss-transport-mcp` |
| **Check-Reference** | `SEC-021` |
| **PDF-Reference** | Anhang B5 + B12 |
| **Audit-Datum** | 2026-06-03 |
| **Auditor** | mcp-audit Skill (automatisiert) |
| **Verification-Status** | `partial` |

### Observed Behavior

- Effective egress limited to hardcoded api.opentransportdata.swiss hosts (api_client.py:19-21, api_infrastructure.py:376-410)

### Gaps (Abweichung vom Best-Practice-Katalog)

- No enforced code-layer egress allow-list (hosts are convention, not validated); TRANSPORT_CKAN_URL override bypasses it; no network-layer egress policy

### Remediation

Code-Layer: feste Allow-List der erlaubten Hosts (`api.opentransportdata.swiss`, `data.opentransportdata.swiss`) gegen die jede ausgehende Anfrage (inkl. `TRANSPORT_CKAN_URL`-Override) geprueft wird. Network-Layer: Egress-Policy im Deployment.

### Effort Estimate

**M** — Egress-Allow-List.

### Verification After Fix

- Re-Audit dieses Checks (SEC-021) gegen denselben Katalog-Stand (catalog_hash in `audit-meta.json`)
- Wo moeglich: Pytest-Test, der das Anti-Pattern abprueft
