# 🚆 Swiss Transport MCP Server

**MCP Server für Schweizer ÖV-Daten | MCP Server for Swiss Public Transport Data**

[![MCP](https://img.shields.io/badge/MCP-Model%20Context%20Protocol-purple.svg)](https://modelcontextprotocol.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Data Source](https://img.shields.io/badge/Data-opentransportdata.swiss-red.svg)](https://opentransportdata.swiss/)

> Verbindet KI-Modelle mit dem Schweizer ÖV-System – Fahrpläne, Echtzeit-Abfahrten, Routenplanung, Störungsmeldungen, Auslastungsprognosen, Ticketpreise, Zugformationen und Open Data von [opentransportdata.swiss](https://opentransportdata.swiss/).
>
> Connects AI models to the Swiss public transport system – timetables, real-time departures, journey planning, disruptions, occupancy forecasts, ticket prices, train formations and open data.
> Part of the [Swiss Public Data MCP Portfolio](https://github.com/malkreide/swiss-public-data-mcp)

---

## 🇩🇪 Deutsch

### Was ist das?

Dieser MCP-Server ist die **Brücke zwischen KI und dem Schweizer ÖV**. Er ermöglicht es KI-Assistenten wie Claude, direkt auf Fahrplandaten, Echtzeit-Abfahrten, Routenplanung und vieles mehr zuzugreifen.

**Metapher:** Deine KI bekommt nicht nur ein GA (Generalabonnement) für Daten – sie bekommt ein **vollständiges Reiseinformationssystem**: Navigation + Störungsmeldungen + Auslastungsanzeige + Preisrechner + Zugformation. Alles über eine standardisierte Schnittstelle.

**Technisches Detail:** Die APIs von opentransportdata.swiss sprechen verschiedene Dialekte – OJP 2.0 (XML/SOAP), SIRI-SX (XML), REST/JSON. Dieser Server übersetzt alles in sauberes JSON für die KI. Ein «Dolmetscher», der mehrere Protokoll-Sprachen beherrscht.

### Verfügbare Tools (11)

#### Kern-Tools (OJP / CKAN)

| Tool | Beschreibung | Datenquelle |
|------|-------------|-------------|
| `transport_search_stop` | Haltestellen suchen nach Name (z.B. «Zürich HB») | OJP 2.0 |
| `transport_nearby_stops` | Haltestellen in der Nähe finden (Koordinaten) | OJP 2.0 |
| `transport_departures` | Echtzeit-Abfahrtstafel mit Verspätungen & Gleisen | OJP 2.0 |
| `transport_trip_plan` | Routenplanung A → B mit Umsteigen, Dauer, Verkehrsmittel | OJP 2.0 |
| `transport_search_datasets` | Datenkatalog durchsuchen (~90 Datensätze) | CKAN¹ |
| `transport_get_dataset` | Details zu einem Datensatz abrufen | CKAN¹ |

¹ *CKAN-Tools erfordern ein separates Abo im [API-Manager](https://api-manager.opentransportdata.swiss/). Die 4 OJP-Tools funktionieren unabhängig davon.*

#### Erweiterungstools (eigene API-Keys)

| Tool | Beschreibung | Datenquelle |
|------|-------------|-------------|
| `get_transport_disruptions` | 🚨 Aktuelle Störungen, Zugausfälle, Streckensperrungen | SIRI-SX |
| `get_train_occupancy` | 📊 Auslastungsprognose für Züge | Occupancy JSON |
| `get_ticket_price` | 💰 Ticketpreise für Verbindungen | OJP Fare |
| `get_train_composition` | 🚃 Wagenreihung, Klassen, Ausstattung | Formation REST |
| `check_transport_api_status` | 🔍 Systemstatus aller APIs prüfen | Alle |

> 💡 **Die Erweiterungstools sind optional.** APIs ohne Key sind deaktiviert – der Server startet trotzdem mit den 6 Kern-Tools.

### Anwendungsfälle

- 🎒 **Schulweg-Assistent:** «Wie kommt ein Kind von der Langstrasse 100 zum Schulhaus Limmat?»
- 🚌 **Klassenausflug-Planer:** «Plane eine Reise für 25 Schüler von Zürich zum Technorama in Winterthur»
- ⏱️ **Echtzeit-Abfahrten:** «Nächste Abfahrten ab Zürich Stadelhofen?»
- 📍 **Umgebungssuche:** «Welche Haltestellen sind in der Nähe von meinem Standort?»
- 🚨 **Störungscheck:** «Gibt es Störungen auf der Strecke Zürich–Bern?»
- 📊 **Auslastung:** «Wie voll ist der IC 1009 heute?»
- 💰 **Preisauskunft:** «Was kostet ein Ticket von Wädenswil nach Bern?»
- 🚃 **Zugformation:** «Hat der IC 708 einen Speisewagen?»

### Schnellstart

#### 1. API-Schlüssel holen (kostenlos)

Registriere dich auf [api-manager.opentransportdata.swiss](https://api-manager.opentransportdata.swiss/) und abonniere die gewünschten APIs.

#### 2. Installation & Start

```bash
# Klonen
git clone https://github.com/malkreide/swiss-transport-mcp.git
cd swiss-transport-mcp

# Installieren
pip install -e .

# API-Key setzen (Minimum: OJP für die Kern-Tools)
export TRANSPORT_API_KEY=your_key_here

# Optional: Erweiterungs-Keys setzen
export SIRI_SX_API_KEY=your_key_here
export OCCUPANCY_API_KEY=your_key_here
export FORMATION_API_KEY=your_key_here
export OJP_FARE_API_KEY=your_key_here

# Server starten (Stdio-Modus für Claude Desktop)
swiss-transport-mcp
```

#### 3. Claude Desktop Konfiguration

**Minimal (nur Kern-Tools):**

```json
{
  "mcpServers": {
    "swiss-transport": {
      "command": "swiss-transport-mcp",
      "env": {
        "TRANSPORT_API_KEY": "your_key_here"
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
        "TRANSPORT_API_KEY": "your_ojp_key_here",
        "SIRI_SX_API_KEY": "your_siri_key_here",
        "OCCUPANCY_API_KEY": "your_occupancy_key_here",
        "FORMATION_API_KEY": "your_formation_key_here",
        "OJP_FARE_API_KEY": "your_fare_key_here"
      }
    }
  }
}
```

**Pfad zur Konfigurationsdatei:**
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

### Cloud-Deployment (SSE für Browser-Zugriff)

Für den Zugriff über **claude.ai im Browser** (z.B. auf verwalteten Arbeitsplätzen ohne Software-Installation):

#### Render.com (empfohlen)

1. Repository auf GitHub forken/pushen
2. Auf [render.com](https://render.com) → New Web Service → GitHub-Repo verbinden
3. Render erkennt `render.yaml` automatisch
4. Environment Variables im Render Dashboard setzen
5. In claude.ai unter Settings → MCP Servers die URL eintragen:
   ```
   https://your-app.onrender.com/sse
   ```

#### Docker (lokal oder andere Cloud)

```bash
docker build -t swiss-transport-mcp .
docker run -p 8000:8000 \
  -e TRANSPORT_API_KEY=xxx \
  -e SIRI_SX_API_KEY=xxx \
  -e OCCUPANCY_API_KEY=xxx \
  -e FORMATION_API_KEY=xxx \
  -e OJP_FARE_API_KEY=xxx \
  swiss-transport-mcp
```

> 💡 **Eselsbrücke:** *«Stdio für den Entwickler-Laptop, SSE für den Browser.»*

### Tool-Details: Erweiterungen

#### 🚨 `get_transport_disruptions` – Störungsmeldungen

```
«Gibt es Störungen auf der Strecke Zürich–Bern?»
→ get_transport_disruptions(filter_text="Zürich")
```

| Parameter | Beschreibung | Standard |
|-----------|-------------|----------|
| filter_text | Suchbegriff (Ort, Linie, Strecke) | alle |
| language | DE, FR, IT, EN | DE |
| max_results | Maximale Anzahl (1–50) | 15 |

**API:** SIRI-SX · **Cache:** 120s · **Rate Limit:** 2/min

#### 📊 `get_train_occupancy` – Auslastungsprognose

```
«Wie voll ist der IC 1009 heute?»
→ get_train_occupancy(train_number="1009")

«Wie voll sind Züge von Zürich nach Bern?»
→ get_train_occupancy(departure_station="Zürich HB", arrival_station="Bern")
```

| Parameter | Beschreibung | Standard |
|-----------|-------------|----------|
| train_number | Zugnummer (z.B. «1009») | – |
| departure_station | ODER: Abfahrtsort | – |
| arrival_station | ODER: Ankunftsort | – |
| operation_date | Betriebstag YYYY-MM-DD | heute |
| operator | «11»=SBB, «33»=BLS, «65»=Thurbo | «11» |

**API:** CKAN/Occupancy JSON · **Cache:** 300s · **Rate Limit:** 2/min

#### 💰 `get_ticket_price` – Preisauskunft

```
«Was kostet Wädenswil nach Bern?»
→ get_ticket_price(origin="Wädenswil", destination="Bern")

«Preis 1. Klasse Basel–Genf morgen um 8?»
→ get_ticket_price(origin="Basel SBB", destination="Genf",
                    departure_time="2026-03-01T08:00", travel_class="first")
```

| Parameter | Beschreibung | Standard |
|-----------|-------------|----------|
| origin | Abfahrtsort | *nötig* |
| destination | Ankunftsort | *nötig* |
| departure_time | YYYY-MM-DDTHH:MM | jetzt |
| travel_class | «first» oder «second» | «second» |

**API:** OJP 2.0 Fare · **Cache:** 1800s · **Rate Limit:** 5/min

#### 🚃 `get_train_composition` – Zugformation

```
«Hat der IC 708 einen Speisewagen?»
→ get_train_composition(train_number="708")

«Wo kann ich im BLS-Zug 2806 mit dem Rollstuhl einsteigen?»
→ get_train_composition(train_number="2806", railway_company="BLSP")
```

| Parameter | Beschreibung | Standard |
|-----------|-------------|----------|
| train_number | Zugnummer (nur Nummer) | *nötig* |
| railway_company | SBBP, BLSP, RhB, SOB, THURBO, etc. | «SBBP» |
| operation_date | YYYY-MM-DD (nur heute für stop_based) | heute |
| show_details | «stop_based», «vehicle_based», «full» | «stop_based» |

**API:** Formation REST · **Cache:** 600s · **Rate Limit:** 5/min

---

## 🇬🇧 English

### What is this?

This MCP server connects AI models to the **Swiss public transport system**. It provides journey planning, real-time departures, stop search, disruption alerts, occupancy forecasts, ticket prices, train formations, and access to the transport open data catalog from [opentransportdata.swiss](https://opentransportdata.swiss/).

**Metaphor:** Think of it as giving your AI a complete Swiss travel information system – not just a timetable, but also disruption alerts, crowd forecasts, ticket prices, and a train X-ray view.

**Technical detail:** The various APIs use different protocols – OJP 2.0 (XML/SOAP), SIRI-SX (XML), REST/JSON. This server translates everything into clean JSON for the AI model.

### Available Tools (11)

#### Core Tools (OJP / CKAN)

| Tool | Description | Data Source |
|------|-------------|-------------|
| `transport_search_stop` | Search stops/stations by name | OJP 2.0 |
| `transport_nearby_stops` | Find nearby stops by coordinates | OJP 2.0 |
| `transport_departures` | Real-time departure board with delays & platforms | OJP 2.0 |
| `transport_trip_plan` | Plan a journey A → B with transfers | OJP 2.0 |
| `transport_search_datasets` | Search the data catalog (~90 datasets) | CKAN¹ |
| `transport_get_dataset` | Get full details of a dataset | CKAN¹ |

¹ *CKAN tools require a separate subscription in the [API Manager](https://api-manager.opentransportdata.swiss/). The 4 OJP tools work independently.*

#### Extension Tools (separate API keys)

| Tool | Description | Data Source |
|------|-------------|-------------|
| `get_transport_disruptions` | 🚨 Current disruptions, cancellations, closures | SIRI-SX |
| `get_train_occupancy` | 📊 Occupancy forecast for trains | Occupancy JSON |
| `get_ticket_price` | 💰 Ticket prices for connections | OJP Fare |
| `get_train_composition` | 🚃 Train formation, classes, amenities | Formation REST |
| `check_transport_api_status` | 🔍 Health check all APIs | All |

> 💡 **Extension tools are optional.** APIs without keys are disabled – the server starts fine with just the 6 core tools.

### Quick Start

1. **Get API key** (free): Register at [api-manager.opentransportdata.swiss](https://api-manager.opentransportdata.swiss/) and subscribe to **OJP 2.0**
2. **Install & run:**
   ```bash
   git clone https://github.com/malkreide/swiss-transport-mcp.git
   cd swiss-transport-mcp
   pip install -e .
   export TRANSPORT_API_KEY=your_key_here
   swiss-transport-mcp
   ```

### Claude Desktop Configuration

```json
{
  "mcpServers": {
    "swiss-transport": {
      "command": "swiss-transport-mcp",
      "env": {
        "TRANSPORT_API_KEY": "your_key_here"
      }
    }
  }
}
```

### Cloud Deployment (SSE for browser access)

```bash
docker build -t swiss-transport-mcp .
docker run -p 8000:8000 -e TRANSPORT_API_KEY=xxx swiss-transport-mcp
```

Then add as remote MCP server in claude.ai: `https://your-host.onrender.com/sse`

See `render.yaml` for one-click Render.com deployment.

---

## 🏗️ Architecture

```
┌─────────────────┐     ┌───────────────────────────┐     ┌─────────────────────────┐
│   Claude / AI   │────▶│   Swiss Transport MCP     │────▶│  opentransportdata.swiss │
│   (MCP Host)    │◀────│   (MCP Server)            │◀────│                         │
└─────────────────┘     │                           │     │  OJP 2.0  (XML/SOAP)    │
                        │  11 Tools · 2 Resources   │     │  SIRI-SX  (XML)         │
                        │  Stdio | SSE              │     │  CKAN     (REST/JSON)   │
                        │                           │     │  Occupancy(REST/JSON)   │
                        │  Kern:                    │     │  Formation(REST/JSON)   │
                        │   api_client + ojp_client │     │  OJP Fare (XML/SOAP)    │
                        │  Erweiterung:             │     └─────────────────────────┘
                        │   api_infrastructure      │
                        │   + siri_sx, occupancy,   │
                        │     ojp_fare, formation   │
                        └───────────────────────────┘
```

### Infrastruktur-Konzepte (Erweiterungsmodule)

| Komponente | Metapher | Funktion |
|------------|----------|----------|
| RateLimiter | Türsteher | Begrenzt API-Aufrufe pro Zeitfenster |
| SimpleCache | Wandtafel | Speichert Antworten für wiederholte Fragen |
| APIClient | Telefonzentrale | Verwaltet Auth, Redirects, Fehler zentral |
| APIConfig | Visitenkarte | Key, URL, Limits pro API |

### Caching-Strategie

| API | Cache-TTL | Begründung |
|-----|-----------|------------|
| SIRI-SX | 120s | Störungen ändern sich nicht sekündlich |
| Occupancy | 300s | Prognosen sind tagesbasiert |
| Formation | 600s | Zugzusammensetzung ist für den Tag stabil |
| OJP Fare | 1800s | Preise ändern sich selten untertags |

## 🔑 API Keys

Kostenlose API-Keys auf [api-manager.opentransportdata.swiss](https://api-manager.opentransportdata.swiss/).

| Variable | API | Erforderlich |
|----------|-----|-------------|
| `TRANSPORT_API_KEY` | Unified Key für OJP + CKAN | ✅ (oder einzelne Keys) |
| `TRANSPORT_OJP_API_KEY` | OJP 2.0 Journey Planner | Optional (Override) |
| `TRANSPORT_CKAN_API_KEY` | CKAN Datenkatalog | Optional (separates Abo) |
| `SIRI_SX_API_KEY` | Störungsmeldungen (SIRI-SX) | Optional |
| `OCCUPANCY_API_KEY` | Auslastungsprognose | Optional |
| `FORMATION_API_KEY` | Zugformation | Optional |
| `OJP_FARE_API_KEY` | Ticketpreise (OJP Fare) | Optional |

> 💡 **Tipp:** Sie können auch nur einzelne Erweiterungs-Keys setzen. APIs ohne Key sind deaktiviert – der Server startet trotzdem mit den Kern-Tools.

## 📦 Data Sources

| Quelle | Beschreibung | Protokoll |
|--------|-------------|-----------|
| **OJP 2.0** | Fahrplanauskunft, Haltestellensuche, Abfahrten | XML/SOAP via `api.opentransportdata.swiss/ojp20` |
| **CKAN** | Datenkatalog mit ~90 Transport-Datensätzen | REST/JSON via `api.opentransportdata.swiss/ckan-api` |
| **SIRI-SX** | Störungsmeldungen (alle Schweizer ÖV) | XML via SIRI-SX API |
| **Occupancy** | Belegungsprognosen (SBB, BLS, Thurbo, SOB) | REST/JSON |
| **Formation** | Zugformationen und Wagenreihung | REST/JSON |
| **OJP Fare** | Ticketpreise | XML/SOAP via OJP 2.0 |

## ⚠️ Bekannte Einschränkungen

- **OJP Fare:** Rabatte (Halbtax, GA, Verbundsabos) sind nicht immer abgebildet
- **Formation:** Stop-based Daten nur für HEUTE verfügbar (wegen Echtzeitdaten)
- **Occupancy:** Nur SBB, BLS, Thurbo und SOB – keine Privatbahnen
- **SIRI-SX:** Die XML-Antwort enthält ALLE Störungen der Schweiz → Filter nutzen!
- **CKAN:** Erfordert ein separates Abo im API-Manager

## 🧪 Testing

```bash
# Unit Tests (kein API-Key nötig)
python tests/test_integration.py

# Integrationstests (API-Key erforderlich)
TRANSPORT_API_KEY=xxx python tests/test_integration.py
```

## 🤝 Contributing

Beiträge sind willkommen! Siehe [CONTRIBUTING.md](CONTRIBUTING.md) für Details.

## 📜 License

MIT – see [LICENSE](LICENSE)

## 🙏 Credits

- **Daten:** [opentransportdata.swiss](https://opentransportdata.swiss/) – Bundesamt für Verkehr (BAV)
- **Protokoll:** [Model Context Protocol](https://modelcontextprotocol.io/) – Anthropic / Linux Foundation
- **Siehe auch:** [Zurich Open Data MCP](https://github.com/malkreide/zurich-opendata-mcp) – unser MCP-Server für Zürcher Stadtdaten
