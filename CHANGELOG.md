# Changelog

Alle relevanten Änderungen an diesem Projekt werden hier dokumentiert.
All notable changes to this project are documented here.

## [Unreleased]

### Fixed

- **Die Quelle liefert SLOIDs statt DiDok-Nummern, und die Reiseplanung über
  Ortsnamen war dadurch tot.** Am 2026-08-10 antwortete
  `transport_search_stop` für Zürich HB mit `ch:1:sloid:3000`, wo bis dahin
  `8503000` stand. `ojp_client.is_stop_ref` akzeptierte zwei Formen — reine
  Ziffern und durch Doppelpunkt getrennte Ziffernblöcke — und `ch` und `sloid`
  sind keine Ziffern. Das eine `False` erreichte den Benutzer so:

  ```
  transport_trip_plan(origin="Zürich HB", destination="Basel SBB")
  → trips=[], message="Error: 'ch:1:sloid:3000' is not a stop id."
  ```

  **Die Suche empfahl eine Kennung, die die anderen Werkzeuge ablehnten** —
  exakt der Fall, den der Docstring von `_build_place_ref` als Begründung für
  seine eigene Existenz nennt. Es war eine dritte Kennungsform, mit der er
  nicht gerechnet hatte.

  Gemessen statt vermutet, über den Client des Repos selbst: 62 Ergebnisse zu
  vier Anfragen, jedes davon eine SLOID in einem `StopPlaceRef`, kein einziges
  `siri:StopPointRef` darunter. **Das Element hat sich nicht geändert, nur der
  Wert darin** — die Änderung, die ein Struktur-Diff nicht sieht.

  Die DiDok-Nummer kommt gar nicht mehr mit: Neben der SLOID stehen nur ein
  `PrivateCode` des Systems `EFA` (`108276` für Zürich HB) und ein
  `TopographicPlaceRef` mit der Gemeinde. Die alten Kennungen weiter
  auszugeben war deshalb keine Option, die es gab.

  Drei Stellen, drei Konsequenzen:

  * `is_stop_ref` erkennt die SLOID-Form, Präfix `ch:1:sloid:`
    grossschreibungstolerant, weil die Kennung als blosser String aus einem
    Modell zurückkommt.
  * Die Weiche in `_build_place_ref` musste umgeschrieben werden: Sie hiess
    «Ziffern sind eine Station, Doppelpunkte sind eine Haltekante», und
    `ch:1:sloid:3000` ist eine **Station voller Doppelpunkte**. Unverändert
    wäre sie als `siri:StopPointRef` hinausgegangen — die stille Hälfte dieses
    Fehlers statt der lauten. Die DiDok-Schreibweisen bleiben gültig: Die
    Quelle gibt sie nicht mehr aus, nimmt sie aber weiterhin an.
  * Eine SLOID mit weiteren Gruppen (`ch:1:sloid:3000:0:31`) wurde **nie
    beobachtet** und wird trotzdem als Haltekante geroutet, weil das genau das
    Verhältnis Station-plus-Zusatz der DiDok-Schreibweise ist. Diese Entscheidung
    ist als geschlossen und nicht gemessen gekennzeichnet, im Code wie im Test.

- **Zwei Live-Tests haben etwas anderes gemessen, als ihr Name sagt.**

  `test_live_search_stop_bern_id` prüfte `stop_id == "8507000"` und hat damit
  die Kennung selbst zum Vertrag erklärt. Der Vertrag ist, dass die Suche etwas
  zurückgibt, das die anderen Werkzeuge annehmen; wie die Quelle ihre Halte
  durchnummeriert, ist ihre Sache. Geprüft wird jetzt `is_stop_ref` plus der
  Name — `8507000` hätte beides ebenso bestanden.

  `test_live_quay_id_is_usable_where_the_search_offers_it` erkannte Haltekanten
  an `":" in stop_id`. Seit jede Kennung Doppelpunkte hat, griff der Filter die
  Station Zürich HB und prüfte sie als Kante. Der Test war damit nicht bloss
  rot — er hätte auch grün nichts mehr belegt. Die Kante wird jetzt am Element
  `siri:StopPointRef` im XML erkannt, und der Skip ist wieder ehrlich.

### Changed

- **`live-tests.yml` prüft den Schlüssel jetzt zuerst, statt ihn erraten zu
  lassen.** Ein Lauf von Hand am 2026-08-10 ohne gesetztes `TRANSPORT_API_KEY`
  endete mit:

  ```
  Live-Suite: unknown
  alle 7 Test(s) uebersprungen — meist ein fehlendes Secret oder eine nicht
  erfuellte Vorbedingung. Geprueft wurde nichts
  ```

  Das Urteil ist richtig und bleibt es: pytest endet mit `0`, wenn sich jeder
  Test übersprungen hat, und `classify_live_run.py` liest deshalb das JUnit-XML
  statt des Exit-Codes. Genau dafür wurde es geschrieben.

  Nur kann der Klassifikator aus dem XML nicht sehen, **welche** Vorbedingung
  gefehlt hat — ein fehlendes Secret und eine umbenannte Marke sehen dort
  identisch aus. Also nennt er beide, und der Leser sucht sich die Antwort über
  Workflow, Testdatei und Klassifikator zusammen.

  Der fehlende Schlüssel ist der eine Fall, den man **vorher** kennen kann. Eine
  Gate ganz vorne prüft `secrets.TRANSPORT_API_KEY` und nennt ihn beim Namen,
  bevor Checkout, Installation und Suite überhaupt laufen.

  Sie ersetzt die Einordnung nicht — sie kommt ihr nur in diesem einen Fall
  zuvor. Timeout, gescheitertes `pip install`, umbenannte Marke: alles fällt
  weiterhin dort an und wird dort `unknown`.

  Am Issue ändert der früh rote Job nichts, und das ist richtig: `unknown`
  öffnet und schliesst ebenfalls keines. Ein Lauf ohne Vergleich darf keinen
  behaupten — in beide Richtungen. Der Workflow läuft ausserdem nur auf
  `schedule` und `workflow_dispatch`, nie auf `pull_request`; ein Fork ohne
  Secrets kann an dieser Gate also nicht scheitern.

### Fixed

- **Der Fix vom 2026-08-07 bestätigte `result` und hörte dort auf.** Das
  Katalog-Werkzeug las danach weiter `result.get("results", [])`, und eine
  Strukturänderung eine Ebene tiefer ergab weiterhin eine leere Datensatzliste
  — dieselbe Antwort wie eine korrekte Suche ohne Treffer.

  Dass ein Fix seine eigene Ebene bestätigt und die nächste offen lässt, ist
  die häufigste Form dieses Fehlers: Er **wandert nach unten**, statt zu
  verschwinden.

  Die Lesestelle läuft jetzt über `ckan_results()`, das `results` bestätigt.
  `package_search` liefert den Schlüssel auch bei null Treffern; eine echte
  leere Suche bleibt unverändert.

  Nachtrag zum Portfolio-Durchlauf
  ([`FID-006`](https://github.com/malkreide/mcp-audit-skill/blob/main/checks/FID-006.md)).

### Fixed

- **Zwei CKAN-Stellen schrieben eine Strukturänderung in eine Leermenge um.**

  `api_client.ckan_request` gab `data.get("result", {})` zurück. Fehlt `result`,
  bekam jeder der drei Aufrufer ein leeres Objekt — bei `package_list`, dessen
  `result` eine **Liste** ist, sogar eines vom falschen Typ. Der Ersatzwert war
  also doppelt falsch.

  `occupancy._fetch_occupancy_data` las
  `result.get("result", {}).get("resources", [])`. Die Schleife über die
  Ressourcen lief dann nullmal, die Funktion gab `None` zurück, und der
  Aufrufer las das als «für diesen Betreiber und Tag gibt es keine
  Belegungsdaten». Der Direkt-URL-Fallback im `except`-Zweig wurde dabei
  **nie erreicht**, weil gar keine Ausnahme flog.

  Beide Stellen bestätigen `result` jetzt und werfen sonst
  `UpstreamSchemaError`, mit den tatsächlich vorhandenen Schlüsseln in der
  Meldung. Ein echter CKAN-Fehler (`success: false`) bleibt ein einfacher
  `ValueError`, und `result: []` bleibt ein normales Ergebnis — bestätigt wird
  die Anwesenheit des Schlüssels, nicht sein Inhalt.

  **Was das nicht behebt, und es steht als Kommentar an der Stelle:** Im
  Belegungspfad landet der Strukturfehler im pauschalen `except Exception` und
  löst den Direkt-URL-Fallback aus. Das ist besser als eine leere Schleife,
  beseitigt die Stille aber nicht — schlägt auch der Fallback fehl, steht am
  Ende wieder `None`. Den pauschalen `except`-Zweig zu schärfen ist eine eigene
  Änderung.

  Gefunden im Portfolio-Durchlauf zu
  [`FID-006`](https://github.com/malkreide/mcp-audit-skill/blob/main/checks/FID-006.md)
  am 2026-08-07: Acht Server im Portfolio sprechen mit CKAN, alle acht prüfen
  das `success`-Envelope, sieben defaulteten `result` danach.

### Behoben — jede OJP-Anfrage dieses Servers war ungueltig

Aufgezeichnet wurde am 7.8.2026 der OJP-2.0-Vertrag: das oeffentliche XML-Schema
der CEN-Norm CEN/TS 17118, fester Tag `v2.0`. Fuenf Befunde, alle am
ausgelieferten Code, alle derselben Herkunft — der Server sprach an mehreren
Stellen OJP **1.0**, wo er 2.0 zu sprechen glaubt:

1. **`<n>` statt `<Name>`.** `trip_request.xml` und `stop_event_request.xml`
   trugen in jedem `PlaceRef` ein Element `<n>`, das es in OJP 2.0 nicht gibt —
   und liessen damit `Name` weg, das `PlaceRefGroup` als **Pflicht** fuehrt.
   Betroffen war jede Reise- und jede Abfahrtsanfrage, auch die dokumentierte
   «beste» Variante mit numerischer Haltestellen-Kennung.
2. **`<LocationName>` fuer Ortsnamen.** `_build_place_ref` baute fuer alles
   Nicht-Numerische die OJP-1.0-Schreibweise. In OJP 2.0 gibt es innerhalb eines
   `PlaceRef` ueberhaupt keine Form «finde den Ort, der so heisst». Die Anfrage
   ging trotzdem raus, und `transport_trip_plan` meldete «No trips found from
   'Zürich HB' to 'Bern'» — obwohl die Doku des Werkzeugs Ortsnamen ausdruecklich
   zusichert. Ein Ausfall, der wie eine Antwort aussieht.
3. **`<IncludeRealtimeData>` gibt es nicht.** Beide Anfragen forderten
   Echtzeitdaten mit einem Element, das das Schema nicht kennt; es heisst
   `UseRealtimeData` und ist eine Aufzaehlung (`full`/`explanatory`/`none`),
   kein Boolescher Wert. Die Reihenfolge der uebrigen Parameter stimmte
   ebenfalls nicht — `xs:sequence` ist geordnet.
4. **Nur `StopPlaceName` gelesen.** `PlaceStructure` fuehrt fuer *jede* der fuenf
   Ortsarten ein Pflichtfeld `Name`; nur `StopPlace` hat zusaetzlich einen
   eigenen `StopPlaceName`. Der Parser las allein den und verwarf danach jeden
   Treffer ohne Namen — Haltekanten, Adressen, Ortschaften und POIs fielen
   stillschweigend heraus, und deren Kennung (`siri:StopPointRef`) wurde gar
   nicht erst gesucht.
5. **Fusswege ohne Namen.** `LegStart`/`LegEnd` sind `PlaceRef`s und tragen ihren
   Namen unter `Name`. Der Parser suchte `StopPointName` und `LocationName` —
   das eine steht dort nie, das andere gibt es nicht. Fusswege kamen deshalb
   immer ohne Start- und Zielnamen zurueck.

Behoben. Ortsnamen loest der Server jetzt mit einer Standortabfrage in eine
Kennung auf, statt sie als Text zu senden; ein Name ohne Treffer meldet «No stop
found for …» und nicht mehr «no trips found». «Diesen Ort finde ich nicht» und
«es gibt keine Verbindung» sind verschiedene Aussagen.

**Was diese Befunde nicht sind:** ein Test gegen die laufende Schnittstelle. Sie
stehen gegen die Norm, nicht gegen die Implementierung von
opentransportdata.swiss — wie tolerant die ist, laesst sich ohne Token nicht
messen. Ungueltig ist trotzdem ungueltig.

### Hinzugefuegt — aufgezeichnete Herkunft fuer das, was sich aufzeichnen laesst

Alle vier Quellen verlangen einen Bearer-Token; ohne ihn antworten sie mit 401
bzw. 403 — gemessen, nicht behauptet, und in
`tests/fixtures/upstream_auth_probe.json` festgehalten. Echte Antwort-Fixtures
sind hier also nicht ehrlich moeglich, und `PROVENANCE.md` sagt das
ausdruecklich, statt den handgeschriebenen Payloads ein Datum anzuschreiben, das
nicht stimmt.

Aufzeichenbar ist der Vertrag. `scripts/record_fixtures.py` liest das
OJP-2.0-Schema am festen Tag `v2.0` und schreibt einen **abgeleiteten Index**
(`tests/fixtures/ojp_2_0_contract.json`: 508 Elementnamen, 16 Strukturen, 25
Gruppen, 3 Aufzaehlungen) samt Quell-URL und SHA-256 jeder gelesenen Datei.
`--check` rechnet die Ableitung gegen die Quelle nach.

Das Schema selbst liegt **nicht** im Repo: Das Quell-Repository fuehrt keine
Lizenzdatei, und die zugrunde liegende Norm ist kostenpflichtig. Gruppenverweise
bleiben im Index unaufgeloest — wer sie beim Aufzeichnen aufloest, schreibt seine
eigene Lesart hinein und kann sie danach nicht mehr widerlegen.

`tests/test_ojp_contract.py` und `tests/test_place_resolution.py` halten
Anfragen, Parser und Aufloesung dagegen. Alle neuen Zusicherungen sind
gegengeprueft: mit zurueckgedrehtem Produktivcode fallen sie, und zwar mit dem
Befund im Text.

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
