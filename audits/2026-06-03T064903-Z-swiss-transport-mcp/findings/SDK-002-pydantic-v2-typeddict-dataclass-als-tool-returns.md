## Finding: SDK-002 — Pydantic v2 / TypedDict / Dataclass als Tool-Returns

| Feld | Wert |
|---|---|
| **Severity** | medium |
| **Status** | open |
| **Server** | `swiss-transport-mcp` |
| **Check-Reference** | `SDK-002` |
| **PDF-Reference** | Sec 3.1 |
| **Audit-Datum** | 2026-06-03 |
| **Auditor** | mcp-audit Skill (automatisiert) |
| **Verification-Status** | `partial` |

### Observed Behavior

- Pydantic v2 used for tool inputs (server.py:99-205)

### Gaps (Abweichung vom Best-Practice-Katalog)

- Tool returns are hand-serialized json.dumps strings, not Pydantic/TypedDict/dataclass return types → no typed output schema

### Remediation

Tool-Rueckgaben von handgebauten `json.dumps`-Strings auf Pydantic-v2-Modelle/`TypedDict` umstellen, damit das Output-Schema typisiert und stabil ist.

### Effort Estimate

**M** — Typisierte Tool-Returns.

### Verification After Fix

- Re-Audit dieses Checks (SDK-002) gegen denselben Katalog-Stand (catalog_hash in `audit-meta.json`)
- Wo moeglich: Pytest-Test, der das Anti-Pattern abprueft
