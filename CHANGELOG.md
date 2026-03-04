# Changelog

Alle relevanten Änderungen an diesem Projekt werden hier dokumentiert.
All notable changes to this project are documented here.

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
