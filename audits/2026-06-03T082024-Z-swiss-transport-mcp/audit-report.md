# MCP-Server Audit-Report — `swiss-transport-mcp`

**Audit-Datum:** 2026-06-03
**Skill-Version:** 1.0.0
**Catalog-Version:** v0.5.0 (68 checks)

---

## 1. Executive Summary

Server `swiss-transport-mcp` wurde gegen 44 anwendbare Best-Practice-Checks geprüft. 37 bestanden, 5 Findings dokumentiert (1 critical, 4 high, 0 medium, 0 low). Production-Readiness: erreicht.

**Production-Readiness:** YES

---

## 2. Profil-Snapshot

| Feld | Wert |
|---|---|
| Server-Name | `swiss-transport-mcp` |
| Audit-Datum | 2026-06-03 |
| Skill-Version | 1.0.0 |
| Catalog-Version | v0.5.0 (68 checks) |

---

## 3. Applicability

### Status pro Kategorie

| Kategorie | Pass | Fail | Partial | Todo | N/A |
|---|---|---|---|---|---|
| ARCH | 10 | 0 | 1 | 0 | 0 |
| CH | 1 | 0 | 0 | 0 | 0 |
| OBS | 5 | 0 | 0 | 0 | 0 |
| OPS | 3 | 0 | 0 | 0 | 0 |
| SCALE | 3 | 0 | 2 | 0 | 0 |
| SDK | 4 | 0 | 0 | 0 | 0 |
| SEC | 11 | 0 | 2 | 2 | 0 |
| **Total** | **37** | **0** | **5** | **2** | **0** |

---

## 4. Findings-Übersicht

_Policy: `fail-or-partial`_

| ID | Category | Severity | Status |
|---|---|---|---|
| SEC-009 | SEC | critical | partial |
| ARCH-009 | ARCH | high | partial |
| SCALE-002 | SCALE | high | partial |
| SCALE-003 | SCALE | high | partial |
| SEC-022 | SEC | high | partial |

**Gesamt:** 5 Findings

---

## 5. Detail-Findings

### ARCH-009

## Finding: ARCH-009 — Tool Annotations: readOnlyHint, destructiveHint, idempotentHint, openWorldHint

| Feld | Wert |
|---|---|
| **Severity** | high |
| **Status** | open |
| **Server** | `swiss-transport-mcp` |
| **Check-Reference** | `ARCH-009` |
| **PDF-Reference** | Anhang A5 |
| **Audit-Datum** | 2026-06-03 |
| **Auditor** | mcp-audit Skill (automatisiert) |
| **Verification-Status** | `partial` |

### Observed Behavior

- 6 core tools declare full annotations

### Gaps (Abweichung vom Best-Practice-Katalog)

- 5 extension tools still use bare @mcp.tool() without readOnlyHint/etc (server.py:781,822,889,938,992) — not addressed in remediation

### Remediation

Die fuenf Extension-Tools (`get_transport_disruptions`, `get_train_occupancy`, `get_ticket_price`, `get_train_composition`, `check_transport_api_status`) mit dem gleichen `annotations={...}`-Block wie die Core-Tools versehen (`readOnlyHint=True`, `destructiveHint=False`, `idempotentHint` je nach Echtzeit-Charakter, `openWorldHint=True`).

### Effort Estimate

**S** — Annotations an 5 Tools ergaenzen.

### Verification After Fix

- Re-Audit dieses Checks (ARCH-009) gegen denselben Katalog-Stand (catalog_hash in `audit-meta.json`)
- Wo moeglich: Pytest-Test, der das Anti-Pattern abprueft


### SCALE-002

## Finding: SCALE-002 — Stateful Load Balancing für Streamable HTTP / SSE

| Feld | Wert |
|---|---|
| **Severity** | high |
| **Status** | open |
| **Server** | `swiss-transport-mcp` |
| **Check-Reference** | `SCALE-002` |
| **PDF-Reference** | Sec 5.2 |
| **Audit-Datum** | 2026-06-03 |
| **Auditor** | mcp-audit Skill (automatisiert) |
| **Verification-Status** | `partial` |

### Observed Behavior

- Single-instance deployment documented

### Gaps (Abweichung vom Best-Practice-Katalog)

- No multi-instance sticky-session / shared session-store strategy documented (deferred; not needed at current single-instance scale)

### Remediation

Falls Multi-Instance geplant: Sticky-Sessions / shared Session-Store (Redis) festlegen. Solange Single-Instance: explizit als Constraint im README dokumentieren.

### Effort Estimate

**M** — Skalierungsstrategie dokumentieren.

### Verification After Fix

- Re-Audit dieses Checks (SCALE-002) gegen denselben Katalog-Stand (catalog_hash in `audit-meta.json`)
- Wo moeglich: Pytest-Test, der das Anti-Pattern abprueft


### SCALE-003

## Finding: SCALE-003 — Mcp-Session-Id Routing via Edge-LB (HAProxy Stick-Tables)

| Feld | Wert |
|---|---|
| **Severity** | high |
| **Status** | open |
| **Server** | `swiss-transport-mcp` |
| **Check-Reference** | `SCALE-003` |
| **PDF-Reference** | Sec 5.2 |
| **Audit-Datum** | 2026-06-03 |
| **Auditor** | mcp-audit Skill (automatisiert) |
| **Verification-Status** | `partial` |

### Observed Behavior

- Single-instance → no edge-LB routing required today

### Gaps (Abweichung vom Best-Practice-Katalog)

- No Mcp-Session-Id edge routing for horizontal scale-out (deferred until multi-instance)

### Remediation

Bei horizontaler Skalierung `Mcp-Session-Id`-basiertes Routing am Edge-LB (HAProxy Stick-Tables o.ae.) einrichten. Aktuell als nicht-anwendbar (Single-Instance) dokumentieren.

### Effort Estimate

**M** — Edge-Routing definieren (nur bei Scale-out).

### Verification After Fix

- Re-Audit dieses Checks (SCALE-003) gegen denselben Katalog-Stand (catalog_hash in `audit-meta.json`)
- Wo moeglich: Pytest-Test, der das Anti-Pattern abprueft


### SEC-009

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

- Mcp-Session-Id generated by the MCP SDK (cryptographically random); SECURITY.md + README document running the no-auth transport behind an auth proxy / trusted network (PR #9/#10)

### Gaps (Abweichung vom Best-Practice-Katalog)

- No user-identity binding of the session id — not possible while auth_model=none; mitigated by documented deployment guidance rather than code

### Remediation

1. Solange `auth_model=none`: SSE-Deployment hinter Reverse-Proxy mit Auth oder nur intern erreichbar betreiben.
2. SDK-Version pinnen und verifizieren, dass `Mcp-Session-Id` per `secrets.token_urlsafe(32)`/UUIDv4 generiert wird.
3. Bei Einfuehrung von Auth: Session an validierte `user_id` binden (`<user_id>:<session_id>`).

### Effort Estimate

**M** — abhaengig von Auth-Entscheidung.

### Verification After Fix

- Re-Audit dieses Checks (SEC-009) gegen denselben Katalog-Stand (catalog_hash in `audit-meta.json`)
- Wo moeglich: Pytest-Test, der das Anti-Pattern abprueft


### SEC-022

## Finding: SEC-022 — Tool-Hash-Pinning + Namespace-Präfix gegen Rug Pull

| Feld | Wert |
|---|---|
| **Severity** | high |
| **Status** | open |
| **Server** | `swiss-transport-mcp` |
| **Check-Reference** | `SEC-022` |
| **PDF-Reference** | Anhang B4 |
| **Audit-Datum** | 2026-06-03 |
| **Auditor** | mcp-audit Skill (automatisiert) |
| **Verification-Status** | `partial` |

### Observed Behavior

- Namespace prefixing (transport_*/get_transport_*); tools version-controlled, no dynamic registration

### Gaps (Abweichung vom Best-Practice-Katalog)

- No tool-hash-pinning / integrity manifest (not addressed; partially covered by SEC-015 acceptance in SECURITY.md)

### Remediation

Namespace-Praefix konsistent halten (alle Tools `transport_*`). Optional Tool-Hash-Manifest pflegen, das die registrierte Tool-Liste/Signaturen pinnt, um Rug-Pull-Redefinition zu erkennen.

### Effort Estimate

**M** — Tool-Integritaet.

### Verification After Fix

- Re-Audit dieses Checks (SEC-022) gegen denselben Katalog-Stand (catalog_hash in `audit-meta.json`)
- Wo moeglich: Pytest-Test, der das Anti-Pattern abprueft


---

## 6. Remediation-Plan

### Empfohlene Reihenfolge

1. **SEC-009** (critical, partial)
2. **ARCH-009** (high, partial)
3. **SCALE-002** (high, partial)
4. **SCALE-003** (high, partial)
5. **SEC-022** (high, partial)

---

## 7. Audit-Metadata

| Feld | Wert |
|---|---|
| skill_version | `1.0.0` |
| catalog_version | `v0.5.0 (68 checks)` |
| applies_when_dsl_version | `1.0` |
| policy | `fail-or-partial` |
| audit_date | `2026-06-03` |


_Generated by tools/build_report.py — do not edit by hand._
