"""
Belegungsprognose (Occupancy Forecast) – Der Crowd-Radar deines MCP-Servers.

Metapher: Stell dir vor, du schaust morgens aus dem Fenster und siehst,
ob der Bus voll ist, bevor du zur Haltestelle gehst. Genau das macht
diese API – aber für jeden Zug in der Schweiz, drei Monate im Voraus.

API-Details:
- Datenquelle: CAPRE-System der SBB
- Format: JSON-Dateien, pro Betriebstag und Betreiber
- Download: https://data.opentransportdata.swiss/dataset/occupancy-forecast-json-dataset
- Betreiber: SBB (11), BLS (33), Thurbo (65), SOB (82)
- Auslastungsstufen: lowOccupancy, fewSeatsAvailable, standingRoomOnly, unknown
- Aufgeteilt nach: 1. Klasse und 2. Klasse pro Abschnitt

WICHTIG: Die Belegungsdaten sind statische JSON-Downloads, keine Live-API.
Die Dateien werden täglich aktualisiert. Wir laden sie via CKAN-API
und cachen sie lokal, um Rate Limits zu schonen.
"""

import json
from datetime import datetime, date
from typing import Optional
from .api_infrastructure import TransportAPIClient, APIError

# Betreiber-Mapping: Code → Name
OPERATOR_MAP = {
    "11": "SBB",
    "33": "BLS",
    "65": "Thurbo AG",
    "82": "SOB (Schweizerische Südostbahn)",
}

# Auslastungsstufen: maschinenlesbar → menschenlesbar
OCCUPANCY_LABELS = {
    "lowOccupancy": "🟢 Wenig belegt – genügend Sitzplätze",
    "fewSeatsAvailable": "🟡 Mässig belegt – noch einzelne Sitzplätze",
    "standingRoomOnly": "🔴 Stark belegt – nur noch Stehplätze",
    "unknown": "⚪ Keine Prognose verfügbar",
}

# CKAN Dataset-URLs für die JSON-Variante
OCCUPANCY_DATASET = "occupancy-forecast-json-dataset"


async def get_occupancy_forecast(
    client: TransportAPIClient,
    train_number: str,
    operation_date: Optional[str] = None,
    operator_ref: str = "11",
) -> str:
    """
    Holt die Auslastungsprognose für einen bestimmten Zug.
    
    Args:
        client: Der konfigurierte API-Client
        train_number: Zugnummer (z.B. "1009", "IC 1", "S3 12345")
        operation_date: Betriebstag im Format YYYY-MM-DD (Standard: heute)
        operator_ref: Betreiber-Code ("11"=SBB, "33"=BLS, "65"=Thurbo, "82"=SOB)
    
    Returns:
        Formatierter Text mit Auslastungsprognose pro Streckenabschnitt.
    
    Ablauf:
    1. Lade die JSON-Datei für den gewünschten Betreiber + Tag
    2. Suche den Zug anhand der Zugnummer
    3. Formatiere die Auslastung pro Abschnitt als lesbaren Text
    """
    if operation_date is None:
        operation_date = date.today().isoformat()

    # Zugnummer bereinigen: "IC 1009" → "1009", "S3 12345" → "12345"
    clean_number = _clean_train_number(train_number)

    try:
        data = await _fetch_occupancy_data(client, operator_ref, operation_date)
    except APIError as e:
        return f"⚠️ Auslastungsprognose konnte nicht geladen werden: {e}"
    except Exception as e:
        return f"⚠️ Fehler beim Laden der Auslastungsdaten: {e}"

    if data is None:
        return (
            f"⚠️ Keine Auslastungsdaten verfügbar für Betreiber "
            f"{OPERATOR_MAP.get(operator_ref, operator_ref)} am {operation_date}."
        )

    # Zug suchen
    train = _find_train(data, clean_number)
    if train is None:
        # Fallback: Bei allen Betreibern suchen
        if operator_ref == "11":
            for alt_op in ["33", "65", "82"]:
                try:
                    alt_data = await _fetch_occupancy_data(client, alt_op, operation_date)
                    if alt_data:
                        train = _find_train(alt_data, clean_number)
                        if train:
                            operator_ref = alt_op
                            break
                except Exception:
                    continue

    if train is None:
        return (
            f"🔍 Zug {train_number} (Nummer: {clean_number}) nicht gefunden in den "
            f"Auslastungsdaten. Mögliche Gründe:\n"
            f"- Die Zugnummer könnte anders geschrieben sein\n"
            f"- Der Zug gehört zu einem anderen Betreiber "
            f"(aktuell gesucht: {OPERATOR_MAP.get(operator_ref, operator_ref)})\n"
            f"- Für diesen Zug gibt es keine Prognose"
        )

    return _format_occupancy(train, train_number, operator_ref, operation_date)


async def get_occupancy_for_route(
    client: TransportAPIClient,
    departure_station: str,
    arrival_station: str,
    operation_date: Optional[str] = None,
) -> str:
    """
    Sucht Auslastungsdaten für eine bestimmte Strecke (alle Betreiber).
    
    Nützlich wenn man die Zugnummer nicht kennt, aber die Strecke.
    Beispiel: "Wie voll sind Züge von Zürich HB nach Bern heute?"
    
    Limitierung: Durchsucht nur SBB-Daten, da die grössten Datensätze.
    Für BLS/Thurbo/SOB müsste man alle Dateien laden → zu viel Traffic.
    """
    if operation_date is None:
        operation_date = date.today().isoformat()

    dep_lower = departure_station.lower()
    arr_lower = arrival_station.lower()

    results = []

    for operator_ref in ["11", "33"]:  # SBB + BLS als Hauptbetreiber
        try:
            data = await _fetch_occupancy_data(client, operator_ref, operation_date)
            if not data or "trains" not in data:
                continue

            for train in data["trains"]:
                sections = train.get("sections", [])
                stations = [s.get("departureStationName", "").lower() for s in sections]
                stations.append(sections[-1].get("destinationStationName", "").lower() if sections else "")

                # Prüfe ob Abfahrt und Ankunft in der Route vorkommen
                dep_found = any(dep_lower in st for st in stations)
                arr_found = any(arr_lower in st for st in stations)

                if dep_found and arr_found:
                    # Nur relevante Abschnitte extrahieren
                    relevant = _filter_sections(sections, dep_lower, arr_lower)
                    if relevant:
                        results.append({
                            "train_number": train.get("trainNumber", "?"),
                            "operator": OPERATOR_MAP.get(operator_ref, operator_ref),
                            "sections": relevant,
                        })

            if len(results) >= 10:
                break

        except Exception:
            continue

    if not results:
        return (
            f"🔍 Keine Auslastungsprognosen gefunden für die Strecke "
            f"{departure_station} → {arrival_station} am {operation_date}."
        )

    lines = [
        f"📊 Auslastungsprognose {departure_station} → {arrival_station} "
        f"am {_format_date(operation_date)}:\n"
    ]

    for r in results[:8]:  # Max 8 Züge, um Kontext zu schonen
        lines.append(f"🚆 Zug {r['train_number']} ({r['operator']}):")
        for s in r["sections"]:
            dep_time = s.get("departureTime", "")
            dep_name = s.get("departureStationName", "?")
            dest_name = s.get("destinationStationName", "?")
            occ = _get_worst_occupancy(s)
            lines.append(f"  {dep_time} {dep_name} → {dest_name}: {occ}")
        lines.append("")

    return "\n".join(lines)


# =============================================================================
# Interne Hilfsfunktionen
# =============================================================================

async def _fetch_occupancy_data(
    client: TransportAPIClient,
    operator_ref: str,
    operation_date: str,
) -> Optional[dict]:
    """
    Lädt die Belegungsdaten für einen Betreiber und Tag.
    
    Die Daten werden über die CKAN-API als JSON-Ressource geladen.
    Jede Datei ist benannt nach: {operatorRef}_{operationDate}.json
    
    Da die Dateien gross sein können (mehrere MB für SBB), 
    nutzen wir aggressives Caching (TTL: 5 Minuten).
    """
    # Die CKAN-API nutzen, um die richtige Ressource zu finden
    # Format der Dateinamen: z.B. "11_2026-02-28.json"
    resource_url = (
        f"https://data.opentransportdata.swiss/dataset/"
        f"{OCCUPANCY_DATASET}/resource_search"
        f"?query=name:{operator_ref}_{operation_date}"
    )

    try:
        result = await client.get(
            "occupancy",
            path=f"/action/package_show",
            params={"id": OCCUPANCY_DATASET},
            cache_ttl_override=300,
        )

        if isinstance(result, dict) and result.get("success"):
            resources = result.get("result", {}).get("resources", [])
            target_name = f"{operator_ref}_{operation_date}"

            for resource in resources:
                name = resource.get("name", "")
                url = resource.get("url", "")
                if target_name in name and url.endswith(".json"):
                    # Datei direkt herunterladen
                    import httpx
                    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as dl_client:
                        resp = await dl_client.get(url)
                        resp.raise_for_status()
                        return resp.json()

        return None

    except Exception as e:
        # Fallback: Direkte URL versuchen
        try:
            direct_url = (
                f"https://data.opentransportdata.swiss/dataset/"
                f"{OCCUPANCY_DATASET}/download/{operator_ref}_{operation_date}.json"
            )
            import httpx
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as dl_client:
                resp = await dl_client.get(direct_url)
                if resp.status_code == 200:
                    return resp.json()
        except Exception:
            pass
        return None


def _clean_train_number(raw: str) -> str:
    """
    Bereinigt die Zugnummer.
    
    Beispiele:
    - "IC 1009" → "1009"
    - "S3 12345" → "12345"
    - "IR 36 1234" → "1234"
    - "1009" → "1009"
    """
    import re
    # Entferne gängige Zugtyp-Präfixe
    cleaned = re.sub(r'^(IC|IR|RE|S\d*|EC|EN|TGV|ICE|RJX)\s*\d*\s*', '', raw.strip(), flags=re.IGNORECASE)
    # Wenn nur Zahlen übrig: gut. Sonst: Original-Zahl extrahieren
    numbers = re.findall(r'\d+', cleaned or raw)
    return numbers[-1] if numbers else raw.strip()


def _find_train(data: dict, train_number: str) -> Optional[dict]:
    """Findet einen Zug in den Belegungsdaten."""
    for train in data.get("trains", []):
        if str(train.get("trainNumber", "")) == train_number:
            return train
    return None


def _filter_sections(sections: list, dep_lower: str, arr_lower: str) -> list:
    """Filtert nur die relevanten Streckenabschnitte."""
    relevant = []
    started = False
    for s in sections:
        dep_name = s.get("departureStationName", "").lower()
        dest_name = s.get("destinationStationName", "").lower()
        if dep_lower in dep_name:
            started = True
        if started:
            relevant.append(s)
        if arr_lower in dest_name:
            break
    return relevant


def _get_worst_occupancy(section: dict) -> str:
    """
    Gibt die schlechteste Auslastung eines Abschnitts zurück.
    
    Logik: Wenn 2. Klasse "standingRoomOnly" ist, ist das die
    relevante Info, auch wenn die 1. Klasse noch Platz hat.
    Die meisten Reisenden fahren 2. Klasse.
    """
    forecasts = section.get("expectedDepartureOccupancy", [])
    worst = "unknown"
    severity = {"standingRoomOnly": 3, "fewSeatsAvailable": 2, "lowOccupancy": 1, "unknown": 0}

    for fc in forecasts:
        level = fc.get("occupancyLevel", "unknown")
        fare_class = fc.get("fareClass", "")
        label = OCCUPANCY_LABELS.get(level, f"⚪ {level}")

        if fare_class == "secondClass":
            return f"{label} (2. Klasse)"

        if severity.get(level, 0) > severity.get(worst, 0):
            worst = level

    return OCCUPANCY_LABELS.get(worst, f"⚪ {worst}")


def _format_occupancy(train: dict, display_name: str, operator_ref: str, op_date: str) -> str:
    """Formatiert die Auslastung eines Zuges als lesbaren Text."""
    sections = train.get("sections", [])
    operator = OPERATOR_MAP.get(operator_ref, operator_ref)

    lines = [
        f"📊 Auslastungsprognose Zug {display_name} ({operator}) "
        f"am {_format_date(op_date)}:\n"
    ]

    for s in sections:
        dep_time = s.get("departureTime", "?")
        dep_name = s.get("departureStationName", "?")
        dest_name = s.get("destinationStationName", "?")
        forecasts = s.get("expectedDepartureOccupancy", [])

        lines.append(f"  🕐 {dep_time}  {dep_name} → {dest_name}")

        for fc in forecasts:
            fare_class = "1. Klasse" if fc.get("fareClass") == "firstClass" else "2. Klasse"
            level = fc.get("occupancyLevel", "unknown")
            label = OCCUPANCY_LABELS.get(level, f"⚪ {level}")
            lines.append(f"    {fare_class}: {label}")

        lines.append("")

    lines.append(
        "💡 Tipp: Die Prognose basiert auf historischen Daten. "
        "Bei Grossveranstaltungen oder Feiertagen kann die tatsächliche "
        "Auslastung abweichen."
    )

    return "\n".join(lines)


def _format_date(date_str: str) -> str:
    """Formatiert ISO-Datum ins Schweizer Format."""
    try:
        d = date.fromisoformat(date_str)
        weekdays = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
        return f"{weekdays[d.weekday()]}, {d.strftime('%d.%m.%Y')}"
    except (ValueError, TypeError):
        return date_str
