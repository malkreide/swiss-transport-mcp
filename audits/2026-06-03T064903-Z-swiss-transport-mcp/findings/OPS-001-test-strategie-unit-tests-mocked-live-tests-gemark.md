## Finding: OPS-001 — Test-Strategie: Unit-Tests mocked + Live-Tests gemarkert

| Feld | Wert |
|---|---|
| **Severity** | high |
| **Status** | open |
| **Server** | `swiss-transport-mcp` |
| **Check-Reference** | `OPS-001` |
| **PDF-Reference** | Anhang C1 |
| **Audit-Datum** | 2026-06-03 |
| **Auditor** | mcp-audit Skill (automatisiert) |
| **Verification-Status** | `partial` |

### Observed Behavior

- tests/test_server.py present with offline unit + live integration split; CI runs pytest -m 'not live' across py3.11-3.13 (.github/workflows/ci.yml)

### Gaps (Abweichung vom Best-Practice-Katalog)

- Tests use print()+global counters, NOT assert — a failing check increments a counter but does not fail pytest, so CI stays green on regressions (tests/test_server.py:18-30)
- respx is declared in dev deps but never used; no HTTP mocking → only 2 test functions, real coverage is thin

### Remediation

1. `print()`+Counter-Muster durch `assert` ersetzen, damit pytest tatsaechlich rot wird.
2. `respx` (bereits Dev-Dep) fuer HTTP-Mocking nutzen → Unit-Tests ohne echten Key/Netz.
3. Coverage auf die Kernmodule (ojp_client, siri_sx, occupancy, fare, formation) ausweiten.

### Effort Estimate

**M** — Tests auf echte Assertions umstellen.

### Verification After Fix

- Re-Audit dieses Checks (OPS-001) gegen denselben Katalog-Stand (catalog_hash in `audit-meta.json`)
- Wo moeglich: Pytest-Test, der das Anti-Pattern abprueft
