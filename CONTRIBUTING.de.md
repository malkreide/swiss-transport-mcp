# Beitragen

[🇬🇧 English Version](CONTRIBUTING.md)

Vielen Dank für Ihr Interesse an diesem Projekt! Beiträge sind willkommen.

## Wie kann ich beitragen?

**Fehler melden:** Erstellen Sie ein [Issue](../../issues) mit einer klaren Beschreibung des Problems, Schritten zur Reproduktion und der erwarteten vs. tatsächlichen Ausgabe.

**Feature vorschlagen:** Beschreiben Sie den Use Case, idealerweise mit einem Bezug zum Schweizer ÖV-Kontext (Schulwege, Klassenausflüge, Barrierefreiheit etc.).

**Code beitragen:**

1. Forken Sie das Repository
2. Erstellen Sie einen Feature-Branch: `git checkout -b feature/mein-feature`
3. Installieren Sie die Dev-Abhängigkeiten: `pip install -e ".[dev]"`
4. Schreiben Sie Tests für Ihre Änderungen
5. Lint prüfen: `ruff check src/ tests/`
6. Commit mit aussagekräftiger Nachricht: `git commit -m "feat: Barrierefreiheitsdaten hinzufügen"`
7. Pull Request erstellen

## Code-Standards

- Python 3.11+, Ruff für Linting
- Docstrings auf Englisch (für internationale Kompatibilität)
- Kommentare und Fehlermeldungen dürfen Deutsch oder Englisch sein
- Alle MCP-Tools müssen `readOnlyHint: True` setzen (nur lesender Zugriff)
- Pydantic-Modelle für alle Tool-Inputs

## API-Keys

Für Integrationstests brauchen Sie einen kostenlosen API-Key von [api-manager.opentransportdata.swiss](https://api-manager.opentransportdata.swiss/). Committen Sie **niemals** API-Keys.

## Lizenz

MIT – siehe [LICENSE](LICENSE)

## Die Live-Suite: wann sie läuft, und wer ein rotes Ergebnis sieht

**Kadenz:** montags 05:19 UTC, dazu jederzeit von Hand über *Actions → Live-Tests → Run
workflow*. Siehe [`.github/workflows/live-tests.yml`](.github/workflows/live-tests.yml).

**Wer es sieht:** Ein roter Lauf öffnet ein Issue mit dem Titel `Live-Tests gegen
opentransportdata.swiss rot …` und dem Label `upstream` — und kommentiert das bestehende, statt
ein zweites aufzumachen. Wird die Suite wieder grün, wird es geschlossen.

**Drei Antworten, nicht zwei.** `scripts/classify_live_run.py` liest das
JUnit-XML statt des Exit-Codes und unterscheidet: `clear` (gelaufen, grün),
`finding` (gelaufen, etwas gefallen) und `unknown` (nicht gelaufen — Installation
gescheitert, null Tests eingesammelt, alle übersprungen). Ein `unknown` schliesst
nie ein Issue: Zuzumachen hiesse zu behaupten, der Vergleich sei gelaufen.

**Secret:** Die Live-Tests brauchen `TRANSPORT_API_KEY`. Fehlt es, überspringt pytest alle sechs und endet mit 0 — der Lauf meldet dann `unknown` statt grün, denn ein nicht gesetztes Secret ist kein grüner Vertrag mit der Quelle, sondern gar keiner.

**Ein roter Live-Lauf heisst nicht zwingend «unser Fehler».** Er heisst: Der
Vertrag mit der Quelle hat sich geändert, oder die Quelle ist gerade aus. Beides
gehört gesehen, nur das Erste gehört gefixt. Bitte den Lauf lesen, bevor der Job
deaktiviert wird — so stirbt dieser Check, und er ist der einzige im Repo, der
einer falschen Grundannahme über opentransportdata.swiss widersprechen kann. Jeder andere Test
prüft gegen eine Fixture, und die Fixture ist aus derselben Annahme geschrieben
wie der Code.

Das ist nicht hypothetisch: Bei `meteoswiss-mcp` fielen am 30.7.2026 beim ersten
Lauf der Live-Suite seit Monaten drei von sechs Tests — der Endpunkt war zwei
Tage zuvor abgeschafft worden, und niemand hatte die Suite gestartet.

Der PR-Lauf bleibt bei `-m "not live"`: Ein fremder 503 darf keinen fremden Pull
Request rot machen.
