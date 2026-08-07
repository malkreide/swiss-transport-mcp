# Changelog

Alle relevanten Änderungen an diesem Projekt werden hier dokumentiert.
All notable changes to this project are documented here.

## [Unreleased]

### Hinzugefuegt — die Live-Suite laeuft geplant, statt nur markiert zu sein

`ci.yml` faehrt `pytest tests/ -m "not live"`. Das ist richtig — ein fremder 503
darf keinen fremden Pull Request rot machen — und es liess die Live-Tests seit
ihrer Entstehung an keiner Stelle laufen. **`-m "not live"` ist kein Ort, an dem
Tests laufen; es ist die Abwesenheit eines solchen.**

Ausgerechnet sie sind die einzigen im Repo, die einer falschen Grundannahme
ueber opentransportdata.swiss widersprechen koennen: Jeder andere Test prueft gegen eine
Fixture, und die Fixture ist aus derselben Annahme geschrieben wie der Code. Bei
`meteoswiss-mcp` fielen am 30.7.2026 beim ersten Lauf seit Monaten drei von sechs
Tests; bei `zh-education-mcp` lief am 3.8.2026 der Code monatelang gegen
umbenannte Feldnamen, ohne dass ein Test rot wurde.

`.github/workflows/live-tests.yml`: montags 05:19 UTC auf einer ungeraden Minute, dazu
`workflow_dispatch`. Der PR-Lauf bleibt unveraendert — dies ist ein
*zusaetzlicher* Lauf, kein Umbau.

**Drei Antworten, nicht zwei.** `if: failure()` kennt rot und nicht rot; ein
gescheitertes `pip install` saehe damit aus wie ein gebrochener Vertrag mit der
Quelle. `scripts/classify_live_run.py` liest deshalb das JUnit-XML und trennt
`clear`, `finding` und `unknown`. Ein `unknown` schliesst nie ein Issue:
zuzumachen hiesse zu behaupten, der Vergleich sei gelaufen.

Der Fall, der die Einordnung noetig macht, ist der uebersprungene Lauf: pytest
endet mit 0, wenn jeder Test uebersprungen wurde. `tests - skipped == 0` ist
deshalb `unknown` — gemessen am 7.8.2026 an `swiss-transport-mcp`, wo ohne
`TRANSPORT_API_KEY` alle sechs Live-Tests uebersprungen werden und ein
Exit-Code-Check gruen gemeldet haette.

Die Einordnung steht in einem Skript mit eigenem Test, nicht in einem
`run:`-Block: Sie entscheidet, ob ein Issue auf- oder zugeht, und das ist der
einzige Teil des Workflows, der etwas behauptet.

Ein Issue mit stabilem Titel-Praefix und Label `upstream` wird kommentiert statt
verdoppelt. Die pytest-Ausgabe geht ueber `env` ins Skript, nicht ueber `${ }`
— sie ist fremder Text, der sonst in einem JavaScript-Template-Literal landet.

Kadenz und Zustaendigkeit stehen in CONTRIBUTING (beide Sprachen). Gemessen mit
`live_schedule_probe` aus `mcp-continuous-auditor`: vorher `LIVE_UNSCHEDULED`,
jetzt `LIVE_SCHEDULED`.

### Added

- **Retry-Politik gegenüber opentransportdata.swiss** (ARCH-014), in einem
  gemeinsamen Kern (`retry.py`) für alle vier Aufrufstellen: `ojp_request`,
  `ckan_request` sowie `TransportAPIClient.get` und `.post_xml`.

  Bisher gab es keine — obwohl der Docstring von `TransportAPIClient`
  «Fehlerbehandlung (Retries, Timeouts, HTTP-Fehler)» versprach. Ein einzelner
  Netzwerkfehler, ein Timeout oder ein 503 beendete den Tool-Aufruf.

  Wiederholt werden Netzwerkfehler, Timeouts, 5xx und 429 — vier Versuche. Ein
  4xx ausser 429 scheitert weiterhin sofort; ebenso jeder `ValueError`. Das
  betrifft namentlich den 403-Pfad von CKAN: Die Meldung nennt das fehlende
  Abo im API-Manager und ist damit das, was den Fehler behebbar macht — sie
  darf nicht hinter einem generischen Retry verschwinden.

- **`Retry-After` wird gelesen und schlägt die eigene Backoff-Kurve**, in
  beiden Formen nach RFC 9110 §10.2.3 (Sekundenzahl und HTTP-Datum). Ein
  unbrauchbarer Header führt zurück auf die Kurve statt zum Absturz.

- **Backoff ist gestreut (Jitter).** `2**attempt` ist deterministisch: Fällt
  die Quelle aus, während mehrere Clients sie abfragen, laufen deren Retries im
  Gleichtakt und die Last kommt als Welle zurück — genau wenn die Quelle sich
  erholt. Exponentiell `[0.5x, 1.5x]`, auf einem `Retry-After` einseitig
  `[1.0x, 1.25x]`. Deckel von 20 s je Einzelwartezeit, angewandt **nach** dem
  Jittern — die andere Reihenfolge macht den Deckel zu gar keiner Schranke.

- **Gesamtbudget über den ganzen Aufruf: 25 s, für OJP 45 s.** Die Abweichung
  ist begründet und nicht versehentlich: `OJP_TIMEOUT = 45.0` steht seit je im
  Repo, weil Trip-Berechnungen länger dauern. Ein 25-s-Budget hätte legitime
  Verbindungsabfragen abgewürgt, die heute durchgehen — der Retry soll
  Ausfälle überbrücken und nicht funktionierende Anfragen kürzen. Ein Test
  hält beide Werte gegen `MCP_DEFAULT_TIMEOUT` fest.

  Das Budget hängt an einer `asyncio.timeout`-Deadline, nicht am
  httpx-Timeout: httpx begrenzt pro Operation, und sein Read-Timeout beginnt
  mit jedem Chunk von vorn — eine langsam tröpfelnde Antwort würde das Budget
  sonst überdauern, ohne dass ein einzelner Read abläuft.

- **Der Rate-Limiter zählt jeden Versuch, nicht jeden Aufruf.** Ein Retry ist
  eine weitere Abfrage bei der Quelle. Zählte nur der erste, meldete der
  Limiter weniger Verbrauch, als er zugelassen hat — und ausgerechnet ein
  Server, der wegen Überlast 503 sendet, bekäme ungezählte Wiederholungen.

### Fixed

- **Ein aufgebrauchtes Gesamtbudget wäre der Fehlerabbildung entkommen.** Es
  wirft den builtin `TimeoutError`, `TransportAPIClient.get` fing aber nur
  `httpx.TimeoutException` — der rohe Fehler wäre beim Tool angekommen. Die
  Meldung nannte ausserdem ein festes «Timeout nach 30s» und benennt jetzt das
  tatsächlich erschöpfte Budget.

- **Inbound Host/Origin allow-list for the network transports
  (`MCP_ALLOWED_HOSTS`, SEC-005).** Comma-separated, compared verbatim so an
  entry carries its port (e.g. `fahrplan.example.ch:8080`). Anything else is
  answered with 421. Loopback stays allowed so container health checks keep
  working, and the configured `MCP_CORS_ORIGINS` are folded into the
  transport's origin list — otherwise the transport would reject precisely the
  browser clients CORS was opened for, `https://claude.ai` by default. A `*`
  origin is not copied across, since origins are compared literally.

  The counterpart to the egress allow-list this server already had: that one
  decides where it may talk *to*, this one under which name it may be
  *addressed*. The threat is DNS rebinding — a page on the operator's network
  resolves its own hostname to this server's address and talks to it from the
  browser. CORS does not stop it (same-origin from the browser's point of
  view), and a token would not either, since the attacking page runs in a
  context that holds one.

  **No behaviour change without the variable.** On a loopback bind the list is
  now stated explicitly instead of being inferred by the SDK from the bind
  address — same protection, no longer dependent on that inference. On a
  non-loopback bind it stays off and is now logged as such. It is deliberately
  not guessed: on `0.0.0.0` the reachable name is unknowable in-process, and a
  wrong guess is exactly the HTTP 421 the `host` kwarg exists to avoid.

  Both network transports carry it — Streamable HTTP and the deprecated SSE
  path — and the served port now travels into the app builder alongside the
  host, so the allow-list names the port actually served.

- `tests/test_transport_security.py` (17 tests). The load-bearing one is
  **right hostname, wrong port**: `evil.test` alone proves little, because a
  fallback loopback-only policy rejects it too.

## [0.4.0] – 2026-07-30

### Fixed

- **The User-Agent reports the actual package version again.** The published
  `0.3.3` sent `swiss-transport-mcp/1.0` to every upstream — the version string was
  hardcoded and had been left behind by earlier bumps. The version now comes
  from the package metadata, so it can no longer drift from the package.

### Changed

- **Migration auf die `mcp` 2.x Server-API.** Pin `>=1.28.1,<2` → `>=2.0.0,<3`;
  `FastMCP` → `MCPServer` (`mcp.server.mcpserver`). Die Untergrenze ist hart:
  2.0.0 hat `mcp.server.fastmcp` ohne Kompatibilitätsschicht entfernt, dieser
  Code läuft also gar nicht mehr auf 1.x.

  Bestehende Clients sehen keinen Unterschied — der Legacy-`initialize`-Handshake
  deckelt weiterhin bei 2025-11-25. mcp 2.x bedient zusätzlich eine „moderne"
  Per-Request-Envelope-Ära, die 2026-07-28 erreicht; ein 2.x-Client verhandelt
  also die neuere Revision. Kein Bruch, aber auch kein Protokoll-No-op.

- **Die Bind-Adresse erreicht jetzt die App (wäre HTTP 421 geworden).** mcp 2.x
  schaltet automatisch eine DNS-Rebinding-Allow-List `127.0.0.1:*` scharf, wenn
  das `host`-Argument der App loopback-artig aussieht. `_build_http_app()` gab
  keines mit, es blieb also beim Default `127.0.0.1`, während uvicorn an
  `MCP_HOST` band — ein Container auf `0.0.0.0` hätte **jede** echte Anfrage
  abgewiesen. `host` und `stateless` reisen jetzt durch `_serve_http()` in die
  App, beides mit Tests.

- **`stateless_http` ist ein App-Kwarg, keine Setting mehr (SCALE-002/003).**
  `mcp.settings.stateless_http = True` wirft in 2.x `ValueError`; der aufgelöste
  Wert wandert deshalb bis `_build_http_app()` durch.

- **`sse_path` / `streamable_http_path` sind aus `MCPServer.settings`
  verschwunden.** Die Startmeldung liest jetzt lokale Konstanten (`_SSE_PATH`,
  `_STREAMABLE_HTTP_PATH`), festgenagelt von einem Test gegen die SDK-Defaults —
  sonst würde eine künftige SDK-Änderung die geloggte URL still falsch machen.

- **`ToolAnnotations`-Feldnamen.** `test_all_tools_declare_readonly_annotations`
  hat Annotations ohne `by_alias=True` gedumpt und `readOnlyHint` gesucht. 2.x
  hat die Felder auf snake_case umgestellt, der Lookup fand also nichts und
  *jedes* Tool sah wie ein Verstoss aus. Jetzt mit Alias gedumpt, konsistent zu
  `tool_integrity._annotations_dict` — der Alias geht über die Leitung, also ist
  er auch das Richtige zum Prüfen.

  Geprüft: 2 failed / 117 passed / 6 deselected gegen die 1.x-Baseline von
  2 failed / 113 passed — die Differenz sind genau die vier neuen Tests. Beide
  Fehler sind die vorbestehenden `test_tracing`-Fälle (optionale
  OpenTelemetry-Pakete fehlen), unter mcp 1.x identisch nachgeprüft.
  `ruff check src/ tests/` und ein Install in einem frischen venv sind grün.
  **Kein Tool-Vertrag bewegt:** `verify_integrity` gegen das gepinnte
  `tool_manifest.json` meldet `consistent: True`, nichts hinzugefügt, entfernt
  oder geändert.

## [0.3.0] – 2026-06-03

MCP best-practice audit remediation. Audit verification: 41 pass · 0 fail ·
1 partial · 2 accepted-risk (catalog v0.5.0, hash `091f446b…`); production-ready.

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
