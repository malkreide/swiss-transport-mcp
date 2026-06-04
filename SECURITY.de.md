# Sicherheitsrichtlinie & Sicherheitslage

[🇬🇧 English Version](SECURITY.md)

`swiss-transport-mcp` wurde gegen den internen MCP-Best-Practice-Audit-Katalog
gehärtet. Dieses Dokument fasst die Sicherheitslage zusammen und dokumentiert die
**akzeptierten Risiken** für Kontrollen, die bewusst auf der Portfolio-/Gateway-Ebene
statt innerhalb dieses einzelnen Servers behandelt werden.

## Schwachstelle melden

Bitte eröffnen Sie ein privates Security Advisory im GitHub-Repository oder
kontaktieren Sie die in `README.md` genannte verantwortliche Person. Erstellen Sie
für ausnutzbare Schwachstellen **keine** öffentlichen Issues.

## Zusammenfassung der Sicherheitslage

Dies ist ein **rein lesender**, **PII-freier** MCP-Server für **öffentliche Open
Data**. Alle 11 Tools fragen ausschliesslich opentransportdata.swiss ab. Bereits
umgesetzte Härtungsmassnahmen:

| Bereich | Kontrolle |
|---|---|
| Egress | HTTPS-erzwungene Allow-List ausschliesslich für `opentransportdata.swiss` (SEC-004/021) |
| TLS | Verifizierung standardmässig aktiv; nur in einer `dev`-Umgebung deaktivierbar (SEC-005) |
| Binding | Netzwerk-Transporte binden standardmässig an `127.0.0.1` (SEC-016) |
| Transport | Streamable HTTP mit CORS, das nur `Mcp-Session-Id` exponiert (SDK-004) |
| Input | Pydantic-v2-Strict-Validierung + XML-Escaping an allen Grenzen (SEC-018) |
| Secrets | Nur Umgebungsvariablen, `.gitignore` schützt `.env`, keine hartcodierten Secrets (ARCH-005/SEC-013) |
| Fehler | Upstream-Antworten werden nach stderr geloggt, niemals an das Modell weitergegeben (OBS-002) |
| Stdout | Reserviert für den JSON-RPC-Stream; Logging fest auf stderr (OBS-004) |
| Tool-Integrität | SHA-256-Tool-Hash-Pinning beim Start + in CI gegen `tool_manifest.json` verifiziert (SEC-022) |

Den vollständigen Bericht finden Sie unter `audits/`, die Härtungshistorie in
`CHANGELOG.md`.

## Akzeptierte Risiken (Kontrollen auf Portfolio-Ebene)

Die folgenden Audit-Prüfungen sind **bewusst nicht** innerhalb dieses Servers
implementiert. Es handelt sich um portfolioweite Belange, die am besten auf einer
MCP-Gateway-/Host-Ebene durchgesetzt werden; das Restrisiko ist hier gering, da der
Server rein lesend ist und nur einen einzigen vertrauenswürdigen Open-Data-Anbieter
erreicht.

Diese sind im
[Risk Acceptance Register](audits/RISK-ACCEPTANCES.md) (RA-001 / RA-002) formell
freigegeben – mit benannter Risikoeigentümerschaft, Entscheidungsdatum,
kompensierenden Kontrollen und Re-Evaluierungs-Auslösern.

### SEC-014 — Tool-Allow-Listing über ein MCP-Gateway

**Status:** akzeptiertes Risiko (Portfolio-Ebene) — siehe RA-001.
Eine Allow-List pro Tool gehört zum MCP-Host/-Gateway, das mehrere Server aggregiert,
nicht zu einem einzelnen Server, der ein festes, rein lesendes Tool-Set exponiert.
Sobald ein zentrales Gateway für das Portfolio eingeführt wird, sollte das
Tool-Allow-Listing dort konfiguriert werden. Bis dahin ist das Risiko begrenzt: Jedes
Tool ist rein lesend und durch die oben genannte Egress-Allow-List eingeschränkt.

### SEC-015 — Pre-Flight-Erkennung von Tool-Poisoning

**Status:** akzeptiertes Risiko (Portfolio-Ebene) — siehe RA-002 — mit lokaler Schutzmassnahme.
Tool-Poisoning (bösartige Tool-Beschreibungen / Rug-Pulls) ist ein Lieferketten- und
Host-seitiges Problem. Die Tool-Definitionen dieses Servers sind versionskontrolliert
und werden aus diesem Repository ausgeliefert; es gibt keine dynamische/entfernte
Tool-Registrierung. Lokal erkennt **SEC-022 Tool-Hash-Pinning** (`tool_manifest.json`)
jegliche Veränderung der Tool-Oberfläche beim Start und in CI. Die serverübergreifende
Poisoning-Erkennung bleibt eine Gateway-/Host-Verantwortung, die auf Portfolio-Ebene
verfolgt wird.

## Re-Evaluierungs-Auslöser

Diese Akzeptanzen sollten neu bewertet werden, falls der Server jemals:

- **Schreib**-Funktionalität erhält oder beginnt, **PII** zu verarbeiten, oder
- Tools **dynamisch** / aus entfernten Quellen registriert, oder
- hinter einem gemeinsamen MCP-Gateway aggregiert wird (dann SEC-014/015 dort umsetzen).
