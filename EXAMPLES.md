# Use Cases & Examples — swiss-transport-mcp

Real-world queries by audience. Alle Tools in diesem Server benötigen einen API-Key (kostenlos bei opentransportdata.swiss beziehbar), der entweder zentral oder pro API konfiguriert wird.

## 🏫 Bildung & Schule
Lehrpersonen, Schulbehörden, Fachreferent:innen

**Planung der Schulreise**
«Wir planen eine Schulreise mit 20 Kindern von Wädenswil in den Zoo Zürich. Wir müssen am 15. Juni um 09:00 Uhr dort sein. Welche Verbindung ist am besten und gibt es auf der Strecke aktuelle Störungen?»
→ `transport_search_stop(query="Wädenswil")`
→ `transport_search_stop(query="Zoo Zürich")`
→ `transport_trip_plan(origin="8503206", destination="8591444", time="2026-06-15T09:00:00Z", limit=3)`
→ `get_transport_disruptions(filter_text="Zürich", language="DE")`
Warum nützlich: Erlaubt Lehrpersonen, komplexe Ausflüge mit Gruppen sicher und zuverlässig zu planen sowie unvorhergesehene Streckensperrungen oder Verspätungen frühzeitig zu erkennen.

**Kostenkalkulation für Exkursionen**
«Was kostet ein Ticket zweiter Klasse für die Fahrt von Bern nach Lausanne für unsere nächste Fachexkursion?»
→ `transport_search_stop(query="Bern")`
→ `transport_search_stop(query="Lausanne")`
→ `get_ticket_price(origin="8507000", destination="8501120", travel_class="second")`
Warum nützlich: Hilft bei der Budgetierung von Klassenausflügen, indem direkt und ohne mühsame Recherche die regulären Ticketpreise für die gewünschte Strecke ermittelt werden.

## 👨‍👩‍👧 Eltern & Schulgemeinde
Elternräte, interessierte Erziehungsberechtigte

**Sicherer Schulweg**
«Welche Haltestellen befinden sich in der Nähe unserer neuen Adresse in Zürich (Lat 47.378, Lon 8.528) und wie oft fahren dort aktuell Busse ab?»
→ `transport_nearby_stops(latitude=47.378, longitude=8.528, limit=3)`
→ `transport_departures(stop_id="8591244", limit=5)`
Warum nützlich: Eltern können rasch prüfen, welche ÖV-Anbindungen sich direkt am Wohnort oder an der Schule befinden und wie verlässlich diese Verbindungen im Alltag sind.

**Ausflugsplanung am Wochenende**
«Hat der InterCity IC 708 heute einen Speisewagen und eine Familienzone, damit wir mit dem Kinderwagen gut Platz finden?»
→ `get_train_composition(train_number="708", railway_company="SBBP", show_details="stop_based")`
Warum nützlich: Bietet Familien grosse Planungssicherheit für Reisen mit viel Gepäck oder Kinderwagen, da die genaue Ausstattung und Wagenreihung schon im Voraus abfragbar ist.

## 🗳️ Bevölkerung & öffentliches Interesse
Allgemeine Öffentlichkeit, politisch und gesellschaftlich Interessierte

**Tägliches Pendeln und Echtzeit-Infos**
«Fahren die Züge ab Zürich Stadelhofen gerade pünktlich oder gibt es Ausfälle?»
→ `transport_search_stop(query="Zürich Stadelhofen")`
→ `transport_departures(stop_id="8503001", limit=10, event_type="departure")`
→ `get_transport_disruptions(filter_text="Stadelhofen", language="DE")`
Warum nützlich: Erleichtert Pendlern den Alltag durch den schnellen Zugriff auf Echtzeit-Abfahrtszeiten und Störungsmeldungen direkt von offiziellen Quellen.

**Auslastung im Stossverkehr meiden**
«Wie voll wird der Zug 1009 heute voraussichtlich in der zweiten Klasse sein?»
→ `get_train_occupancy(train_number="1009", operator="11")`
Warum nützlich: Reisende können überfüllte Züge meiden und ihre Fahrten auf weniger stark frequentierte Verbindungen verlegen, was den Reisekomfort spürbar erhöht.

**Zugang zu offenen Mobilitätsdaten**
«Gibt es im Open-Data-Katalog Datensätze zum Thema Fahrplan oder Parkplätze?»
→ `transport_search_datasets(query="fahrplan", limit=5)`
Warum nützlich: Fördert die Transparenz und ermöglicht interessierten Bürgerinnen und Bürgern den einfachen Zugang zu staatlichen Open-Data-Ressourcen im Verkehrsbereich.

## 🤖 KI-Interessierte & Entwickler:innen
MCP-Enthusiast:innen, Forscher:innen, Prompt Engineers, öffentliche Verwaltung

**Komplexe Cross-Domain-Analyse (Multi-Server)**
«Gibt es offene Datensätze über den öffentlichen Verkehr in Zürich und was sagen die städtischen Daten dazu?»
→ `transport_search_datasets(query="züri", limit=5)`
→ `zurich_search_datasets(query="verkehr")` *(via [zurich-opendata-mcp](https://github.com/malkreide/zurich-opendata-mcp))*
Warum nützlich: Demonstriert die enorme Stärke des Model Context Protocols, wenn verschiedene Datenquellen (nationaler Verkehr und lokale Stadtverwaltung) nahtlos miteinander verknüpft werden.

**Entwicklung von Reise-Dashboards**
«Lade alle Metadaten zum GTFS-Realtime Datensatz herunter, um ein eigenes Dashboard zu bauen.»
→ `transport_search_datasets(query="gtfs-rt", limit=1)`
→ `transport_get_dataset(dataset_id="ch-public-transport-real-time-gtfs")`
Warum nützlich: Entwickler können rasch die genauen URLs und Formate von Datenfeeds extrahieren, ohne sich manuell durch komplexe Web-Portale klicken zu müssen.

## 🔧 Technische Referenz: Tool-Auswahl nach Anwendungsfall

| Ich möchte… | Tool(s) | Auth nötig? |
|---|---|---|
| Eine Haltestelle über den Namen suchen | `transport_search_stop` | Ja |
| Haltestellen nahe einer Adresse (Koordinaten) finden | `transport_nearby_stops` | Ja |
| Die aktuellen Abfahrten einer Station sehen | `transport_departures` | Ja |
| Eine Reise von A nach B planen | `transport_trip_plan` | Ja |
| Störungen und Zugausfälle in Echtzeit prüfen | `get_transport_disruptions` | Ja |
| Die voraussichtliche Auslastung eines Zuges abfragen | `get_train_occupancy` | Ja |
| Den Ticketpreis einer Strecke erfahren | `get_ticket_price` | Ja |
| Sehen, ob ein Zug einen Speisewagen oder Veloplätze hat | `get_train_composition` | Ja |
| Den Open-Data-Katalog nach Datensätzen durchsuchen | `transport_search_datasets` | Ja |
| Die Details und Download-Links eines Datensatzes abrufen | `transport_get_dataset` | Ja |
