# MCP-Server Audit-Report — `swiss-transport-mcp`

**Audit-Datum:** 2026-06-03
**Skill-Version:** 1.0.0
**Catalog-Version:** v0.5.0 (68 checks)

---

## 1. Executive Summary

Server `swiss-transport-mcp` wurde gegen 44 anwendbare Best-Practice-Checks geprüft. 16 bestanden, 26 Findings dokumentiert (4 critical, 13 high, 9 medium, 0 low). Production-Readiness: NICHT erreicht — blockierend: SEC-016.

**Production-Readiness:** NO

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
| ARCH | 8 | 0 | 3 | 0 | 0 |
| CH | 1 | 0 | 0 | 0 | 0 |
| OBS | 1 | 1 | 3 | 0 | 0 |
| OPS | 2 | 0 | 1 | 0 | 0 |
| SCALE | 0 | 2 | 3 | 0 | 0 |
| SDK | 0 | 0 | 4 | 0 | 0 |
| SEC | 4 | 1 | 8 | 2 | 0 |
| **Total** | **16** | **4** | **22** | **2** | **0** |

---

## 4. Findings-Übersicht

_Policy: `fail-or-partial`_

| ID | Category | Severity | Status |
|---|---|---|---|
| OBS-004 | OBS | critical | partial |
| SEC-004 | SEC | critical | partial |
| SEC-009 | SEC | critical | partial |
| SEC-016 | SEC | critical | fail |
| ARCH-009 | ARCH | high | partial |
| OBS-002 | OBS | high | partial |
| OPS-001 | OPS | high | partial |
| SCALE-001 | SCALE | high | partial |
| SCALE-002 | SCALE | high | partial |
| SCALE-003 | SCALE | high | partial |
| SDK-001 | SDK | high | partial |
| SDK-004 | SDK | high | partial |
| SEC-005 | SEC | high | partial |
| SEC-007 | SEC | high | partial |
| SEC-013 | SEC | high | partial |
| SEC-021 | SEC | high | partial |
| SEC-022 | SEC | high | partial |
| ARCH-008 | ARCH | medium | partial |
| ARCH-012 | ARCH | medium | partial |
| OBS-003 | OBS | medium | partial |
| OBS-006 | OBS | medium | fail |
| SCALE-004 | SCALE | medium | fail |
| SCALE-006 | SCALE | medium | fail |
| SDK-002 | SDK | medium | partial |
| SDK-003 | SDK | medium | partial |
| SEC-008 | SEC | medium | partial |

**Gesamt:** 26 Findings

---

## 5. Detail-Findings

### ARCH-008

## Finding: ARCH-008 — Drei Primitive nutzen: Tools, Resources und Prompts

| Feld | Wert |
|---|---|
| **Severity** | medium |
| **Status** | open |
| **Server** | `swiss-transport-mcp` |
| **Check-Reference** | `ARCH-008` |
| **PDF-Reference** | Anhang A2 |
| **Audit-Datum** | 2026-06-03 |
| **Auditor** | mcp-audit Skill (automatisiert) |
| **Verification-Status** | `partial` |

### Observed Behavior

- Tools primitive (11 @mcp.tool) and Resources primitive (transport://datasets, transport://info — server.py:884,898) both used

### Gaps (Abweichung vom Best-Practice-Katalog)

- Prompts primitive (@mcp.prompt) not used — only 2 of 3 MCP primitives present

### Remediation

Mindestens einen `@mcp.prompt` hinzufuegen (z.B. 'Schulreise planen'-Prompt-Template), um alle drei MCP-Primitive (Tools/Resources/Prompts) zu nutzen.

### Effort Estimate

**S** — Prompts-Primitive ergaenzen.

### Verification After Fix

- Re-Audit dieses Checks (ARCH-008) gegen denselben Katalog-Stand (catalog_hash in `audit-meta.json`)
- Wo moeglich: Pytest-Test, der das Anti-Pattern abprueft


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

- server.py:249-551 — 6 core tools declare full annotations (readOnlyHint/destructiveHint/idempotentHint/openWorldHint)

### Gaps (Abweichung vom Best-Practice-Katalog)

- 5 extension tools use bare @mcp.tool() with NO annotations: get_transport_disruptions, get_train_occupancy, get_ticket_price, get_train_composition, check_transport_api_status (server.py:607,648,715,764,818)

### Remediation

Die fuenf Extension-Tools (`get_transport_disruptions`, `get_train_occupancy`, `get_ticket_price`, `get_train_composition`, `check_transport_api_status`) mit dem gleichen `annotations={...}`-Block wie die Core-Tools versehen (`readOnlyHint=True`, `destructiveHint=False`, `idempotentHint` je nach Echtzeit-Charakter, `openWorldHint=True`).

### Effort Estimate

**S** — Annotations an 5 Tools ergaenzen.

### Verification After Fix

- Re-Audit dieses Checks (ARCH-009) gegen denselben Katalog-Stand (catalog_hash in `audit-meta.json`)
- Wo moeglich: Pytest-Test, der das Anti-Pattern abprueft


### ARCH-012

## Finding: ARCH-012 — protocolVersion-Pinning + CHANGELOG + SDK-Update-Disziplin

| Feld | Wert |
|---|---|
| **Severity** | medium |
| **Status** | open |
| **Server** | `swiss-transport-mcp` |
| **Check-Reference** | `ARCH-012` |
| **PDF-Reference** | Anhang A9 |
| **Audit-Datum** | 2026-06-03 |
| **Auditor** | mcp-audit Skill (automatisiert) |
| **Verification-Status** | `partial` |

### Observed Behavior

- CHANGELOG.md maintained with dated, semver-style entries (CHANGELOG.md:6)

### Gaps (Abweichung vom Best-Practice-Katalog)

- No MCP protocolVersion pinning; mcp[cli]>=1.0.0 is an unbounded floating lower bound (pyproject.toml) → SDK drift risk

### Remediation

MCP-`protocolVersion` explizit pinnen/dokumentieren und `mcp[cli]` mit Obergrenze versehen (z.B. `>=1.0.0,<2.0.0`), um unkontrollierte SDK-Drift zu vermeiden.

### Effort Estimate

**S** — Versionen pinnen.

### Verification After Fix

- Re-Audit dieses Checks (ARCH-012) gegen denselben Katalog-Stand (catalog_hash in `audit-meta.json`)
- Wo moeglich: Pytest-Test, der das Anti-Pattern abprueft


### OBS-002

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


### OBS-003

## Finding: OBS-003 — Structured Logging mit RFC 5424 Severity-Stufen

| Feld | Wert |
|---|---|
| **Severity** | medium |
| **Status** | open |
| **Server** | `swiss-transport-mcp` |
| **Check-Reference** | `OBS-003` |
| **PDF-Reference** | Sec 6.3 |
| **Audit-Datum** | 2026-06-03 |
| **Auditor** | mcp-audit Skill (automatisiert) |
| **Verification-Status** | `partial` |

### Observed Behavior

- stdlib logging used with named logger and severity levels (logger.info/debug/warning across modules)

### Gaps (Abweichung vom Best-Practice-Katalog)

- No structured (JSON) logging and no explicit RFC 5424 severity formatting / handler configuration

### Remediation

Auf strukturierte Logs (JSON, z.B. `structlog`) mit RFC-5424-Severity umstellen und Handler explizit konfigurieren (zusammen mit OBS-004 stderr).

### Effort Estimate

**M** — Structured Logging.

### Verification After Fix

- Re-Audit dieses Checks (OBS-003) gegen denselben Katalog-Stand (catalog_hash in `audit-meta.json`)
- Wo moeglich: Pytest-Test, der das Anti-Pattern abprueft


### OBS-004

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


### OBS-006

## Finding: OBS-006 — OpenTelemetry Distributed Tracing pro Tool-Call

| Feld | Wert |
|---|---|
| **Severity** | medium |
| **Status** | open |
| **Server** | `swiss-transport-mcp` |
| **Check-Reference** | `OBS-006` |
| **PDF-Reference** | Anhang B10 |
| **Audit-Datum** | 2026-06-03 |
| **Auditor** | mcp-audit Skill (automatisiert) |
| **Verification-Status** | `fail` |

### Observed Behavior

- (kein Positiv-Beleg; Anforderung nicht erfuellt)

### Gaps (Abweichung vom Best-Practice-Katalog)

- No OpenTelemetry / distributed tracing instrumentation on tool calls (no otel imports anywhere)

### Remediation

OpenTelemetry-Instrumentierung pro Tool-Call ergaenzen (Span je Tool, Attribute fuer API-Name/Dauer/Status). Optional, je nach Observability-Anforderung.

### Effort Estimate

**L** — OpenTelemetry-Tracing.

### Verification After Fix

- Re-Audit dieses Checks (OBS-006) gegen denselben Katalog-Stand (catalog_hash in `audit-meta.json`)
- Wo moeglich: Pytest-Test, der das Anti-Pattern abprueft


### OPS-001

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


### SCALE-001

## Finding: SCALE-001 — Streamable HTTP statt stdio für Cloud-Deployments

| Feld | Wert |
|---|---|
| **Severity** | high |
| **Status** | open |
| **Server** | `swiss-transport-mcp` |
| **Check-Reference** | `SCALE-001` |
| **PDF-Reference** | Sec 5.1 |
| **Audit-Datum** | 2026-06-03 |
| **Auditor** | mcp-audit Skill (automatisiert) |
| **Verification-Status** | `partial` |

### Observed Behavior

- Cloud path exists and avoids raw stdio for browser access (server.py:946-950)

### Gaps (Abweichung vom Best-Practice-Katalog)

- Uses legacy SSE transport (mcp.run(transport="sse"), server.py:950) instead of the current Streamable HTTP transport recommended for cloud deployments

### Remediation

`mcp.run(transport="sse", ...)` auf den aktuellen Streamable-HTTP-Transport des MCP-SDK umstellen; SSE gilt als Legacy. Deployment-Doku in README aktualisieren.

### Effort Estimate

**M** — Transport auf Streamable HTTP migrieren.

### Verification After Fix

- Re-Audit dieses Checks (SCALE-001) gegen denselben Katalog-Stand (catalog_hash in `audit-meta.json`)
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

- Single-instance Render deployment documented (README.md:152-156)

### Gaps (Abweichung vom Best-Practice-Katalog)

- No stateful/sticky load-balancing strategy documented for multi-instance SSE scale-out (session affinity undefined)

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

- Single-instance deployment → no edge-LB routing required today

### Gaps (Abweichung vom Best-Practice-Katalog)

- No Mcp-Session-Id-based edge routing (HAProxy stick-tables / equivalent) defined for horizontal scaling

### Remediation

Bei horizontaler Skalierung `Mcp-Session-Id`-basiertes Routing am Edge-LB (HAProxy Stick-Tables o.ae.) einrichten. Aktuell als nicht-anwendbar (Single-Instance) dokumentieren.

### Effort Estimate

**M** — Edge-Routing definieren (nur bei Scale-out).

### Verification After Fix

- Re-Audit dieses Checks (SCALE-003) gegen denselben Katalog-Stand (catalog_hash in `audit-meta.json`)
- Wo moeglich: Pytest-Test, der das Anti-Pattern abprueft


### SCALE-004

## Finding: SCALE-004 — Containerization mit Multi-Stage-Builds

| Feld | Wert |
|---|---|
| **Severity** | medium |
| **Status** | open |
| **Server** | `swiss-transport-mcp` |
| **Check-Reference** | `SCALE-004` |
| **PDF-Reference** | Sec 5.3 |
| **Audit-Datum** | 2026-06-03 |
| **Auditor** | mcp-audit Skill (automatisiert) |
| **Verification-Status** | `fail` |

### Observed Behavior

- (kein Positiv-Beleg; Anforderung nicht erfuellt)

### Gaps (Abweichung vom Best-Practice-Katalog)

- No Dockerfile / multi-stage container build present despite documented cloud deployment

### Remediation

Multi-Stage-Dockerfile + `.dockerignore` hinzufuegen (deckt sich mit SEC-007).

### Effort Estimate

**M** — Containerization.

### Verification After Fix

- Re-Audit dieses Checks (SCALE-004) gegen denselben Katalog-Stand (catalog_hash in `audit-meta.json`)
- Wo moeglich: Pytest-Test, der das Anti-Pattern abprueft


### SCALE-006

## Finding: SCALE-006 — Resource-Limits per Container (Memory, CPU, FDs)

| Feld | Wert |
|---|---|
| **Severity** | medium |
| **Status** | open |
| **Server** | `swiss-transport-mcp` |
| **Check-Reference** | `SCALE-006` |
| **PDF-Reference** | Sec 5.3 |
| **Audit-Datum** | 2026-06-03 |
| **Auditor** | mcp-audit Skill (automatisiert) |
| **Verification-Status** | `fail` |

### Observed Behavior

- (kein Positiv-Beleg; Anforderung nicht erfuellt)

### Gaps (Abweichung vom Best-Practice-Katalog)

- No per-container resource limits (memory/CPU/FD) defined; no container manifest to attach them to

### Remediation

Im Deployment (Render/Railway bzw. Container-Orchestrierung) Memory-/CPU-/FD-Limits setzen und im README dokumentieren.

### Effort Estimate

**S** — Resource-Limits.

### Verification After Fix

- Re-Audit dieses Checks (SCALE-006) gegen denselben Katalog-Stand (catalog_hash in `audit-meta.json`)
- Wo moeglich: Pytest-Test, der das Anti-Pattern abprueft


### SDK-001

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


### SDK-002

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


### SDK-003

## Finding: SDK-003 — Context Injection für Progress Reports und Logging

| Feld | Wert |
|---|---|
| **Severity** | medium |
| **Status** | open |
| **Server** | `swiss-transport-mcp` |
| **Check-Reference** | `SDK-003` |
| **PDF-Reference** | Sec 3.1 |
| **Audit-Datum** | 2026-06-03 |
| **Auditor** | mcp-audit Skill (automatisiert) |
| **Verification-Status** | `partial` |

### Observed Behavior

- Tools are fast single-shot reads where progress reporting is non-critical

### Gaps (Abweichung vom Best-Practice-Katalog)

- No Context (ctx) injection used for progress reports / structured logging on longer OJP trip calculations

### Remediation

Bei laengeren OJP-Trip-Berechnungen `ctx: Context` injizieren und `ctx.info()/ctx.report_progress()` fuer Progress/Logging nutzen.

### Effort Estimate

**S** — Context-Injection.

### Verification After Fix

- Re-Audit dieses Checks (SDK-003) gegen denselben Katalog-Stand (catalog_hash in `audit-meta.json`)
- Wo moeglich: Pytest-Test, der das Anti-Pattern abprueft


### SDK-004

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


### SEC-004

## Finding: SEC-004 — SSRF-Prevention: HTTPS-Enforcement + IP-Blocklisting

| Feld | Wert |
|---|---|
| **Severity** | critical |
| **Status** | open |
| **Server** | `swiss-transport-mcp` |
| **Check-Reference** | `SEC-004` |
| **PDF-Reference** | Sec 4.4 |
| **Audit-Datum** | 2026-06-03 |
| **Auditor** | mcp-audit Skill (automatisiert) |
| **Verification-Status** | `partial` |

### Observed Behavior

- All upstream URLs are hardcoded https:// constants (api_client.py:19-21, api_infrastructure.py:376-410) — no user/LLM-supplied URLs reach the HTTP client
- Tool args are stop names/IDs/coordinates, never URLs (server.py:99-205) → no direct SSRF surface

### Gaps (Abweichung vom Best-Practice-Katalog)

- api_client.py:85,121 — TRANSPORT_SSL_VERIFY=false disables TLS verification (MITM enabler), no guard preventing it in production
- No explicit HTTPS-enforcement / private-IP & metadata-endpoint (169.254.169.254) blocklist helper
- TRANSPORT_CKAN_URL (api_client.py:110) allows operator override of base URL with no scheme validation

### Remediation

1. `TRANSPORT_SSL_VERIFY=false` in Produktion verbieten (z.B. nur erlauben wenn `ENV=dev`).
2. Falls je benutzergesteuerte URLs hinzukommen: `urlparse`-Schema-Check (nur `https`) + Blocklist fuer `169.254.169.254`, `127.0.0.0/8`, RFC-1918.
3. `TRANSPORT_CKAN_URL`-Override gegen Allow-List der opentransportdata.swiss-Hosts validieren.

### Effort Estimate

**M** — Validierungs-Helper + SSL-Guard.

### Verification After Fix

- Re-Audit dieses Checks (SEC-004) gegen denselben Katalog-Stand (catalog_hash in `audit-meta.json`)
- Wo moeglich: Pytest-Test, der das Anti-Pattern abprueft


### SEC-005

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


### SEC-007

## Finding: SEC-007 — Container-Sandboxing: Docker / chroot mit minimalen Privilegien

| Feld | Wert |
|---|---|
| **Severity** | high |
| **Status** | open |
| **Server** | `swiss-transport-mcp` |
| **Check-Reference** | `SEC-007` |
| **PDF-Reference** | Sec 4.5 |
| **Audit-Datum** | 2026-06-03 |
| **Auditor** | mcp-audit Skill (automatisiert) |
| **Verification-Status** | `partial` |

### Observed Behavior

- Managed-platform sandboxing implied by Render deployment model (README.md:152)

### Gaps (Abweichung vom Best-Practice-Katalog)

- No Dockerfile / container definition in repo → no explicit minimal-privilege, non-root, or chroot sandboxing for the cloud path

### Remediation

Multi-Stage-Dockerfile hinzufuegen: non-root User, minimal base image (`python:3.12-slim`), nur noetige Dependencies, `--read-only`-faehig. Render/Railway auf das Image umstellen.

### Effort Estimate

**M** — Dockerfile mit Haertung.

### Verification After Fix

- Re-Audit dieses Checks (SEC-007) gegen denselben Katalog-Stand (catalog_hash in `audit-meta.json`)
- Wo moeglich: Pytest-Test, der das Anti-Pattern abprueft


### SEC-008

## Finding: SEC-008 — Pre-Configuration Consent für Local-Server-Installation

| Feld | Wert |
|---|---|
| **Severity** | medium |
| **Status** | open |
| **Server** | `swiss-transport-mcp` |
| **Check-Reference** | `SEC-008` |
| **PDF-Reference** | Sec 4.5 |
| **Audit-Datum** | 2026-06-03 |
| **Auditor** | mcp-audit Skill (automatisiert) |
| **Verification-Status** | `partial` |

### Observed Behavior

- Install + Claude Desktop config documented (README.md:56-146)

### Gaps (Abweichung vom Best-Practice-Katalog)

- No explicit pre-configuration consent step for local-server installation documented

### Remediation

Im README einen kurzen Pre-Configuration-Consent-Hinweis ergaenzen (welche Daten der Server abruft, welche Keys er nutzt), bevor der User ihn in Claude Desktop registriert.

### Effort Estimate

**S** — Consent-Hinweis dokumentieren.

### Verification After Fix

- Re-Audit dieses Checks (SEC-008) gegen denselben Katalog-Stand (catalog_hash in `audit-meta.json`)
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

- No custom session-id generation in code — Mcp-Session-Id handling delegated to the MCP SDK SSE transport (no weak PRNG / timestamp IDs in src/)

### Gaps (Abweichung vom Best-Practice-Katalog)

- auth_model=none → no user-identity binding of session-id possible (<user_id>:<session_id> pattern not implemented)
- SDK session-id entropy not independently verified for the SSE deployment path

### Remediation

1. Solange `auth_model=none`: SSE-Deployment hinter Reverse-Proxy mit Auth oder nur intern erreichbar betreiben.
2. SDK-Version pinnen und verifizieren, dass `Mcp-Session-Id` per `secrets.token_urlsafe(32)`/UUIDv4 generiert wird.
3. Bei Einfuehrung von Auth: Session an validierte `user_id` binden (`<user_id>:<session_id>`).

### Effort Estimate

**M** — abhaengig von Auth-Entscheidung.

### Verification After Fix

- Re-Audit dieses Checks (SEC-009) gegen denselben Katalog-Stand (catalog_hash in `audit-meta.json`)
- Wo moeglich: Pytest-Test, der das Anti-Pattern abprueft


### SEC-013

## Finding: SEC-013 — API-Key-Storage: Secret Manager statt Plain-Text Env-Vars

| Feld | Wert |
|---|---|
| **Severity** | high |
| **Status** | open |
| **Server** | `swiss-transport-mcp` |
| **Check-Reference** | `SEC-013` |
| **PDF-Reference** | Sec 4 (Empirie 2025) |
| **Audit-Datum** | 2026-06-03 |
| **Auditor** | mcp-audit Skill (automatisiert) |
| **Verification-Status** | `partial` |

### Observed Behavior

- API keys sourced from environment variables (acceptable production minimum) — api_client.py:28-56

### Gaps (Abweichung vom Best-Practice-Katalog)

- No secret-manager integration (Vault / cloud secret store) recommended for production; plain env-vars only
- No .gitignore guarding a local .env from accidental commit

### Remediation

1. `.gitignore` mit `.env` ergaenzen.
2. Fuer Produktion Secret-Manager (Render/Railway Secrets bzw. Vault) statt Plain-Env empfehlen/dokumentieren.
3. Optional `pydantic.SecretStr` fuer In-Memory-Repraesentation.

### Effort Estimate

**M** — Secret-Management haerten.

### Verification After Fix

- Re-Audit dieses Checks (SEC-013) gegen denselben Katalog-Stand (catalog_hash in `audit-meta.json`)
- Wo moeglich: Pytest-Test, der das Anti-Pattern abprueft


### SEC-016

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


### SEC-021

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

- Namespace prefixing present: core tools transport_*, extension tools get_transport_*/get_train_* (server.py tool names)

### Gaps (Abweichung vom Best-Practice-Katalog)

- No tool-hash-pinning / integrity manifest to detect rug-pull tool redefinition

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

1. **OBS-004** (critical, partial)
2. **SEC-004** (critical, partial)
3. **SEC-009** (critical, partial)
4. **SEC-016** (critical, fail)
5. **ARCH-009** (high, partial)
6. **OBS-002** (high, partial)
7. **OPS-001** (high, partial)
8. **SCALE-001** (high, partial)
9. **SCALE-002** (high, partial)
10. **SCALE-003** (high, partial)
11. **SDK-001** (high, partial)
12. **SDK-004** (high, partial)
13. **SEC-005** (high, partial)
14. **SEC-007** (high, partial)
15. **SEC-013** (high, partial)
16. **SEC-021** (high, partial)
17. **SEC-022** (high, partial)
18. **ARCH-008** (medium, partial)
19. **ARCH-012** (medium, partial)
20. **OBS-003** (medium, partial)
21. **OBS-006** (medium, fail)
22. **SCALE-004** (medium, fail)
23. **SCALE-006** (medium, fail)
24. **SDK-002** (medium, partial)
25. **SDK-003** (medium, partial)
26. **SEC-008** (medium, partial)

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
