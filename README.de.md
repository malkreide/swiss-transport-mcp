[🇬🇧 English Version](README.md)

> 🇨🇭 **Teil des [Swiss Public Data MCP Portfolios](https://github.com/malkreide)**

# 🚆 swiss-transport-mcp

![Version](https://img.shields.io/badge/version-1.0.0-blue)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![MCP](https://img.shields.io/badge/MCP-Model%20Context%20Protocol-purple)](https://modelcontextprotocol.io/)
[![Datenquelle](https://img.shields.io/badge/Daten-opentransportdata.swiss-red)](https://opentransportdata.swiss/)
![CI](https://github.com/malkreide/swiss-transport-mcp/actions/workflows/ci.yml/badge.svg)

> MCP-Server, der KI-Modelle mit dem Schweizer ÖV-System verbindet – Routenplanung, Echtzeit-Abfahrten, Störungen, Auslastung, Ticketpreise, Zugformation und Open Data von [opentransportdata.swiss](https://opentransportdata.swiss/).

---

## Übersicht

**swiss-transport-mcp** gibt KI-Assistenten wie Claude ein vollständiges Schweizer Reiseinformationssystem – nicht nur Fahrpläne, sondern auch Echtzeit-Störungsmeldungen, Auslastungsprognosen, Ticketpreise und eine vollständige Zugformationsansicht. Alles über eine einzige, standardisierte MCP-Schnittstelle zugänglich.

Die verschiedenen APIs von opentransportdata.swiss sprechen unterschiedliche Protokolle – OJP 2.0 (XML/SOAP), SIRI-SX (XML), REST/JSON. Dieser Server übersetzt alles in sauberes JSON für das KI-Modell und agiert als mehrsprachiger Protokoll-Dolmetscher.

**Anker-Demo-Abfrage:** *«Plane einen Schulausflug für 25 Schülerinnen und Schüler von Zürich zum Technorama in Winterthur – prüfe Störungen und finde die beste Abfahrt.»*

---

## Funktionen

- 🗺️ **Routenplanung** (A → B mit Umsteigen, Dauer, Verkehrsmittel) via OJP 2.0
- 🕐 **Echtzeit-Abfahrtstafeln** mit Verspätungen und Gleisinformationen
- 🔍 **Haltestellensuche** nach Name oder Koordinaten
- 🚨 **Live-Störungsmeldungen** (Ausfälle, Sperrungen) via SIRI-SX
- 📊 **Auslastungsprognosen** für Züge (SBB, BLS, Thurbo, SOB)
- 💰 **Ticketpreise** mit Klassenauswahl
- 🚃 **Zugformation** – Wagen, Klassen, Ausstattung, Barrierefreiheit
- 📦 **Open-Data-Katalog** – rund 90 Transport-Datensätze via CKAN
- 🔑 **Graceful Degradation** – Server startet mit Kern-Tools, auch ohne optionale API-Keys
- ☁️ **Dual Transport** – stdio für Claude Desktop, Streamable HTTP/SSE für Cloud-Deployment

---

## Voraussetzungen

- Python 3.11+
- Kostenloser API-Key von [api-manager.opentransportdata.swiss](https://api-manager.opentransportdata.swiss/) (Mindestabo: **OJP 2.0**)
- Optional: weitere Keys für SIRI-SX, Auslastung, Formation, OJP Fare

---

## Installation

```bash
# Repository klonen
git clone https://github.com/malkreide/swiss-transport-mcp.git
cd swiss-transport-mcp

# Installieren
pip install -e .
```

Oder mit `uvx` (ohne dauerhafte Installation):

```bash
uvx swiss-transport-mcp
```

---

## Schnellstart

```bash
# Minimalen API-Key setzen (OJP Kern-Tools)
export TRANSPORT_API_KEY=dein_key_hier

# Server starten (stdio-Modus für Claude Desktop)
swiss-transport-mcp
```

Sofort in Claude Desktop ausprobieren:

> *«Nächste Abfahrten ab Zürich Stadelhofen?»*
> *«Wie komme ich von Wädenswil nach Bern mit dem Zug?»*

---

## Konfiguration

### Umgebungsvariablen

| Variable | API | Erforderlich |
|---|---|---|
| `TRANSPORT_API_KEY` | Unified Key für OJP + CKAN | ✅ (oder Einzelkeys) |
| `TRANSPORT_OJP_API_KEY` | OJP 2.0 Journey Planner | Optional (Override) |
| `TRANSPORT_CKAN_API_KEY` | CKAN-Datenkatalog | Optional (separates Abo) |
| `SIRI_SX_API_KEY` | Störungsmeldungen (SIRI-SX) | Optional |
| `OCCUPANCY_API_KEY` | Auslastungsprognose | Optional |
| `FORMATION_API_KEY` | Zugformation | Optional |
| `OJP_FARE_API_KEY` | Ticketpreise (OJP Fare) | Optional |

> APIs ohne Key werden still deaktiviert – der Server startet problemlos mit den 6 Kern-Tools.

### Claude Desktop Konfiguration

**Minimal (nur Kern-Tools):**

```json
{
  "mcpServers": {
    "swiss-transport": {
      "command": "swiss-transport-mcp",
      "env": {
        "TRANSPORT_API_KEY": "dein_key_hier"
      }
    }
  }
}
```

**Voll ausgestattet (alle 11 Tools):**

```json
{
  "mcpServers": {
    "swiss-transport": {
      "command": "swiss-transport-mcp",
      "env": {
        "TRANSPORT_API_KEY": "dein_ojp_key_hier",
        "SIRI_SX_API_KEY": "dein_siri_key_hier",
        "OCCUPANCY_API_KEY": "dein_occupancy_key_hier",
        "FORMATION_API_KEY": "dein_formation_key_hier",
        "OJP_FARE_API_KEY": "dein_fare_key_hier"
      }
    }
  }
}
```

**Pfad zur Konfigurationsdatei:**
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

### Cloud-Deployment (SSE für Browser-Zugriff)

Für den Einsatz via **claude.ai im Browser** (z.B. auf verwalteten Arbeitsplätzen ohne lokale Software-Installation):

**Render.com (empfohlen):**
1. Repository auf GitHub pushen/forken
2. Auf [render.com](https://render.com): New Web Service → GitHub-Repo verbinden
3. Render erkennt `render.yaml` automatisch
4. Umgebungsvariablen im Render-Dashboard setzen
5. In claude.ai unter Settings → MCP Servers eintragen: `https://your-app.onrender.com/sse`

**Docker:**
```bash
docker build -t swiss-transport-mcp .
docker run -p 8000:8000 \
  -e TRANSPORT_API_KEY=xxx \
  -e SIRI_SX_API_KEY=xxx \
  swiss-transport-mcp
```

> 💡 *«stdio für den Entwickler-Laptop, SSE für den Browser.»*

---

## Verfügbare Tools

### Kern-Tools (OJP 2.0 / CKAN)

| Tool | Beschreibung | Datenquelle |
|---|---|---|
| `transport_search_stop` | Haltestellen nach Name suchen | OJP 2.0 |
| `transport_nearby_stops` | Haltestellen in der Nähe finden (Koordinaten) | OJP 2.0 |
| `transport_departures` | Echtzeit-Abfahrtstafel mit Verspätungen & Gleisen | OJP 2.0 |
| `transport_trip_plan` | Routenplanung A → B mit Umsteigen, Dauer, Verkehrsmittel | OJP 2.0 |
| `transport_search_datasets` | Open-Data-Katalog durchsuchen (~90 Datensätze) | CKAN¹ |
| `transport_get_dataset` | Details zu einem Datensatz abrufen | CKAN¹ |

¹ *CKAN-Tools erfordern ein separates Abo im [API-Manager](https://api-manager.opentransportdata.swiss/).*

### Erweiterungs-Tools (optionale API-Keys)

| Tool | Beschreibung | Datenquelle |
|---|---|---|
| `get_transport_disruptions` | 🚨 Aktuelle Störungen, Zugausfälle, Streckensperrungen | SIRI-SX |
| `get_train_occupancy` | 📊 Auslastungsprognose für Züge | Occupancy JSON |
| `get_ticket_price` | 💰 Ticketpreise für Verbindungen | OJP Fare |
| `get_train_composition` | 🚃 Wagenreihung, Klassen, Ausstattung, Barrierefreiheit | Formation REST |
| `check_transport_api_status` | 🔍 Systemstatus aller konfigurierten APIs | Alle |

### Beispiel-Abfragen

| Abfrage | Tool |
|---|---|
| *«Nächste Züge ab Zürich Stadelhofen?»* | `transport_departures` |
| *«Schulreise für 25 Schüler von Zürich nach Winterthur Technorama planen»* | `transport_trip_plan` |
| *«Gibt es Störungen zwischen Zürich und Bern?»* | `get_transport_disruptions` |
| *«Wie voll ist der IC 1009 heute?»* | `get_train_occupancy` |
| *«Was kostet ein Ticket von Wädenswil nach Bern?»* | `get_ticket_price` |
| *«Hat der IC 708 einen Speisewagen?»* | `get_train_composition` |
| *«Welche Haltestellen sind in der Nähe der Langstrasse 100?»* | `transport_nearby_stops` |

---

## Architektur

```
┌─────────────────┐     ┌───────────────────────────┐     ┌──────────────────────────┐
│   Claude / KI   │────▶│   Swiss Transport MCP     │────▶│  opentransportdata.swiss  │
│   (MCP Host)    │◀────│   (MCP Server)            │◀────│                          │
└─────────────────┘     │                           │     │  OJP 2.0  (XML/SOAP)     │
                        │  11 Tools · 2 Resources   │     │  SIRI-SX  (XML)          │
                        │  Stdio | SSE              │     │  CKAN     (REST/JSON)    │
                        │                           │     │  Occupancy(REST/JSON)    │
                        │  Kern:                    │     │  Formation(REST/JSON)    │
                        │   api_client + ojp_client │     │  OJP Fare (XML/SOAP)     │
                        │  Erweiterung:             │     └──────────────────────────┘
                        │   siri_sx, occupancy,     │
                        │   ojp_fare, formation     │
                        └───────────────────────────┘
```

### Infrastruktur-Komponenten

| Komponente | Metapher | Funktion |
|---|---|---|
| RateLimiter | Türsteher | Begrenzt API-Aufrufe pro Zeitfenster |
| SimpleCache | Wandtafel | Speichert Antworten für wiederholte Anfragen |
| APIClient | Telefonzentrale | Verwaltet Auth, Redirects, Fehler zentral |
| APIConfig | Visitenkarte | Key, URL, Limits pro API |

### Caching-Strategie

| API | Cache-TTL | Begründung |
|---|---|---|
| SIRI-SX | 120s | Störungen ändern sich nicht sekündlich |
| Auslastung | 300s | Prognosen sind tagesbasiert |
| Formation | 600s | Zugzusammensetzung ist für den Tag stabil |
| OJP Fare | 1800s | Preise ändern sich selten untertags |

---

## Projektstruktur

```
swiss-transport-mcp/
├── src/swiss_transport_mcp/   # Hauptpaket
│   ├── server.py              # FastMCP-Server, Tool-Definitionen
│   ├── api_client.py          # Kern-OJP + CKAN-Client
│   ├── ojp_client.py          # OJP 2.0 XML/SOAP-Parser
│   ├── api_infrastructure.py  # RateLimiter, SimpleCache, APIClient
│   ├── siri_sx.py             # Störungsmeldungen
│   ├── occupancy.py           # Auslastungsprognosen
│   ├── ojp_fare.py            # Ticketpreise
│   └── formation.py           # Zugformation
├── tests/                     # Testsammlung
├── Dockerfile                 # Container für Cloud-Deployment
├── render.yaml                # Render.com One-Click-Deployment
├── pyproject.toml             # Build-Konfiguration (hatchling)
├── CHANGELOG.md
├── CONTRIBUTING.md
├── LICENSE
├── README.md                  # Englische Hauptversion
└── README.de.md               # Diese Datei (Deutsch)
```

---

## Bekannte Einschränkungen

- **OJP Fare:** Rabatte (Halbtax, GA, Verbundsabos) sind nicht immer abgebildet
- **Formation:** Stop-based-Daten nur für HEUTE verfügbar (Echtzeit-Abhängigkeit)
- **Auslastung:** Nur SBB, BLS, Thurbo und SOB – keine Privatbahnen
- **SIRI-SX:** Liefert ALLE Störungen der Schweiz → Parameter `filter_text` verwenden
- **CKAN:** Erfordert ein separates Abo im API-Manager

---

## Tests

```bash
# Unit-Tests (kein API-Key erforderlich)
PYTHONPATH=src pytest tests/ -m "not live"

# Integrationstests (API-Key erforderlich)
TRANSPORT_API_KEY=xxx pytest tests/ -m "live"
```

---

## Changelog

Siehe [CHANGELOG.md](CHANGELOG.md)

---

## Lizenz

MIT-Lizenz – siehe [LICENSE](LICENSE)

---

## Autor

Hayal Oezkan · [github.com/malkreide](https://github.com/malkreide)

---

## Credits & Verwandte Projekte

- **Daten:** [opentransportdata.swiss](https://opentransportdata.swiss/) – Bundesamt für Verkehr (BAV)
- **Protokoll:** [Model Context Protocol](https://modelcontextprotocol.io/) – Anthropic / Linux Foundation
- **Verwandt:** [zurich-opendata-mcp](https://github.com/malkreide/zurich-opendata-mcp) – MCP-Server für Zürcher Stadtdaten
- **Portfolio:** [Swiss Public Data MCP Portfolio](https://github.com/malkreide)
