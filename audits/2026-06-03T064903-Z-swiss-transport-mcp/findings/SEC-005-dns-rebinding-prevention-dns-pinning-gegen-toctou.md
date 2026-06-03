## Finding: SEC-005 — DNS-Rebinding-Prevention: DNS-Pinning gegen TOCTOU

| Feld | Wert |
|---|---|
| **Severity** | high |
| **Status** | open |
| **Server** | `swiss-transport-mcp` |
| **Check-Reference** | `SEC-005` |
| **PDF-Reference** | Sec 4.4 |
| **Audit-Datum** | 2026-06-03 |
| **Auditor** | mcp-audit Skill (automatisiert) |
| **Verification-Status** | `partial` |

### Observed Behavior

- Upstream hosts are fixed https:// constants, not user-controlled → DNS-rebinding (TOCTOU) practical risk is low

### Gaps (Abweichung vom Best-Practice-Katalog)

- No DNS-pinning between validation and request; TRANSPORT_SSL_VERIFY=false would compound any rebinding

### Remediation

`TRANSPORT_SSL_VERIFY=false` in Produktion unterbinden. Optional DNS-Pinning der opentransportdata.swiss-Hosts oder fixe IP-Allow-List am Network-Layer.

### Effort Estimate

**M** — DNS-Pinning / SSL-Haertung.

### Verification After Fix

- Re-Audit dieses Checks (SEC-005) gegen denselben Katalog-Stand (catalog_hash in `audit-meta.json`)
- Wo moeglich: Pytest-Test, der das Anti-Pattern abprueft
