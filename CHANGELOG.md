# Changelog

Alle relevanten Änderungen an diesem Projekt werden hier dokumentiert.
All notable changes to this project are documented here.

## [Unreleased]

### Security & hardening (MCP best-practice audit)

- **SEC-016:** SSE/HTTP listener now defaults to `127.0.0.1` (NeighborJack fix).
- **SEC-004/005/021:** HTTPS-enforced egress allow-list (`opentransportdata.swiss`
  only) and a TLS-verify guard (`TRANSPORT_SSL_VERIFY=false` honoured only in a
  dev environment via `MCP_ENV`).
- **SDK-004:** CORS for the HTTP transport, exposing `Mcp-Session-Id`, origins
  configurable via `MCP_CORS_ORIGINS` (default `https://claude.ai`).
- **OBS-002:** upstream error bodies are logged to stderr, no longer forwarded
  to the model.

### Reliability & SDK

- **SCALE-001:** cloud transport migrated from legacy SSE to Streamable HTTP
  (endpoint `/mcp`); SSE kept as a deprecated fallback.
- **SDK-001:** FastMCP lifespan with a pooled HTTP client and deterministic
  teardown; **SDK-002:** typed Pydantic tool outputs; **SDK-003:** Context
  progress on long-running tools.
- **OBS-003/004:** logging pinned to stderr with an optional JSON format
  (`LOG_FORMAT=json`, RFC 5424 severity).
- **OBS-006:** opt-in OpenTelemetry tracing (`otel` extra +
  `OTEL_TRACES_ENABLED=1`); spans around upstream HTTP calls, no-op by default.

### Tooling, packaging & docs

- **OPS-001:** assertion-based test suite with respx mocking.
- **SEC-007 / SCALE-004 / SCALE-006:** multi-stage non-root Dockerfile,
  `.dockerignore`, and `docker-compose.yml` with resource limits.
- **ARCH-008:** added the `plan_group_trip` prompt (all three MCP primitives).
- **ARCH-012:** capped `mcp`/`httpx`/`pydantic` to their current major versions.
- **SEC-008/SEC-009:** documented pre-install consent and safe operation of the
  no-auth HTTP transport.
- **SEC-014/SEC-015:** formally accepted as residual risk in the
  [Risk Acceptance Register](audits/RISK-ACCEPTANCES.md) (RA-001/RA-002) —
  named owner, decision date, compensating controls and re-evaluation triggers;
  cross-referenced from `SECURITY.md`.
- **ARCH-009:** annotations added to the five extension tools (all tools now
  declare `readOnlyHint` and friends).
- **SEC-022:** SHA-256 tool-hash pinning (`tool_manifest.json`) verified at
  startup and in CI to detect tool-surface drift / rug-pulls.
- **SCALE-002/003:** `MCP_STATELESS=1` runs Streamable HTTP statelessly,
  removing the sticky-load-balancing requirement for horizontal scale-out.

## [0.2.0] – 2026-03-01

### Erweiterung: 5 neue Tools / Extension: 5 new tools

Das Erweiterungsmodul wurde vollständig in den Hauptserver integriert. Aus 6 Tools werden 11.

**🚨 Störungsmeldungen (SIRI-SX):**
- `get_transport_disruptions` – Aktuelle Zugausfälle, Verspätungen, Streckensperrungen
- Filtert nach Text, Sprache (DE/FR/IT/EN), begrenzte Resultate

**📊 Auslastungsprognose:**
- `get_train_occupancy` – Belegungsprognose nach Zugnummer oder Strecke
- Unterstützt SBB, BLS, Thurbo, SOB

**💰 Preisauskunft (OJP Fare):**
- `get_ticket_price` – Ticketpreise für Verbindungen (1./2. Klasse)

**🚃 Zugformation:**
- `get_train_composition` – Wagenreihung, Klassen, Ausstattung, Sektoren
- Modi: stop_based, vehicle_based, full

**🔍 Systemstatus:**
- `check_transport_api_status` – Prüft Konfiguration und Erreichbarkeit aller APIs

**🏗️ Architektur:**
- Neue Infrastruktur-Schicht: Rate Limiting, Caching, Multi-API Client
- Lazy Initialization: Erweiterungs-Client wird erst bei Bedarf erstellt
- Graceful Degradation: Fehlende Keys → hilfreiche Meldung, kein Crash
- Unterstützt 6 verschiedene API-Protokolle in einem Server

**📝 Dokumentation:**
- README erweitert mit allen 11 Tools und Erweiterungs-Dokumentation
- .env.example mit allen API-Keys
- Beispielkonfigurationen für Claude Desktop (minimal und vollständig)

## [0.1.0] – 2026-02-28

### Erster Release / Initial Release

**🚆 4 OJP-Tools (Open Journey Planner 2.0):**
- `transport_search_stop` – Haltestellen suchen nach Name
- `transport_nearby_stops` – Nächste Haltestellen per Koordinaten
- `transport_departures` – Echtzeit-Abfahrtstafel mit Verspätungen & Gleisen
- `transport_trip_plan` – Routenplanung A → B mit Umstiegen

**📦 2 CKAN-Tools (Datenkatalog):**
- `transport_search_datasets` – Datenkatalog durchsuchen (~90 Datensätze)
- `transport_get_dataset` – Details zu einem Datensatz abrufen

**🏗️ Architektur:**
- Dual-Transport: Stdio (lokal) + SSE (Cloud/Browser)
- OJP 2.0 XML/SOAP → sauberes JSON für das LLM
- Pydantic-Validierung mit Schweizer Koordinaten-Bounds
- Robustes Error-Handling mit nutzerfreundlichen Meldungen
- Dockerfile + render.yaml für Render.com-Deployment
- GitHub Actions CI (Lint + Tests auf Python 3.11/3.12)

**📝 Dokumentation:**
- Bilinguale README (DE/EN)
- CONTRIBUTING Guide
- .env.example mit allen Konfigurationsoptionen
