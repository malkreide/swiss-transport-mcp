"""
Train Formation Service – Der Röntgenblick in den Zug.

Metapher: Stell dir vor, du stehst am Bahnsteig und kannst durch
die Wände schauen: Wo ist die 1. Klasse? Wo der Speisewagen?
Wo kann ich mit dem Rollstuhl einsteigen? Genau das liefert diese API.

API-Details:
- REST-API seit Herbst 2024
- Base URL: https://api.opentransportdata.swiss/formation/v2
- Format: JSON (endlich kein XML!)
- Auth: Bearer Token im Header
- Endpoints:
  * /formations_stop_based – Formation pro Haltestelle (kompakt)
  * /formations_vehicle_based – Formation pro Fahrzeug (detailliert)
  * /formations_full – Beides kombiniert (gross!)
  * /health – Systemstatus
- Parameter: evu, operationDate, trainNumber
- Erlaubte EVU: BLSP, SBBP, MBC, OeBB, RhB, SOB, THURBO, TPF, TRN, VDBB, ZB

WICHTIG: operationDate kann nur HEUTE sein (wegen Echtzeit-CUS-Daten).
Für vehicle_based: bis 3 Tage in die Zukunft.
"""

from datetime import date
from typing import Optional
from .api_infrastructure import TransportAPIClient, APIError, NotFoundError

# EVU-Mapping: Kürzel → Vollname
EVU_MAP = {
    "BLSP": "BLS",
    "SBBP": "SBB",
    "MBC": "MBC (Morges–Bière–Cossonay)",
    "OeBB": "Oensingen-Balsthal-Bahn",
    "RhB": "Rhätische Bahn",
    "SOB": "Schweizerische Südostbahn",
    "THURBO": "Thurbo",
    "TPF": "Transports publics fribourgeois",
    "TRN": "TransN (Transports Neuchâtelois)",
    "VDBB": "Appenzeller Bahnen",
    "ZB": "Zentralbahn",
}

# Fahrzeugtyp → Menschenlesbar (aus der API-Doku)
VEHICLE_TYPES = {
    "1": "🟦 1. Klasse",
    "2": "🟩 2. Klasse",
    "12": "🟦🟩 1./2. Klasse",
    "CC": "🛏️ Liegewagen",
    "FA": "👨‍👩‍👧 Familienwagen",
    "WL": "🛌 Schlafwagen",
    "WR": "🍽️ Restaurant/Speisewagen",
    "W1": "🍽️🟦 Speise+1. Klasse",
    "W2": "🍽️🟩 Speise+2. Klasse",
    "LK": "🚂 Lokomotive",
    "D": "📦 Gepäckwagen",
    "F": "⬜ Fiktiver Wagen",
    "K": "⬜ Klassenlos",
    "X": "❌ Abgestellt",
}

# Angebote → Menschenlesbar
AMENITIES = {
    "BHP": "♿ Rollstuhlplatz",
    "BZ": "💼 Businesszone",
    "FZ": "👨‍👩‍👧 Familienzone",
    "KW": "🍼 Kinderwagenplatz",
    "NF": "🦽 Niederflureinstieg",
    "VH": "🚲 Velostellplatz",
    "VR": "🚲📋 Veloplatz (reservierungspflichtig)",
}


async def get_train_formation(
    client: TransportAPIClient,
    train_number: str,
    evu: str = "SBBP",
    operation_date: Optional[str] = None,
    detail_level: str = "stop_based",
) -> str:
    """
    Holt die Zugzusammensetzung für einen bestimmten Zug.
    
    Args:
        client: Der konfigurierte API-Client
        train_number: Zugnummer (z.B. "2806", "1009")
        evu: Eisenbahnverkehrsunternehmen (z.B. "SBBP", "BLSP", "RhB")
        operation_date: Betriebstag YYYY-MM-DD (Standard: heute)
        detail_level: "stop_based" (kompakt) oder "vehicle_based" (detailliert)
    
    Returns:
        Formatierter Text mit Zugzusammensetzung, Wagenreihung und Ausstattung.
    """
    if operation_date is None:
        operation_date = date.today().isoformat()

    # EVU validieren
    evu_upper = evu.upper()
    if evu_upper not in EVU_MAP:
        available = ", ".join(f"{k} ({v})" for k, v in EVU_MAP.items())
        return (
            f"⚠️ Unbekanntes EVU '{evu}'. Verfügbare Eisenbahnunternehmen:\n{available}"
        )

    # Zugnummer bereinigen
    import re
    clean_number = re.sub(r'[^\d]', '', train_number)
    if not clean_number:
        return f"⚠️ Ungültige Zugnummer: '{train_number}'. Bitte nur die Nummer angeben (z.B. '2806')."

    # Endpoint wählen
    endpoint_map = {
        "stop_based": "/formations_stop_based",
        "vehicle_based": "/formations_vehicle_based",
        "full": "/formations_full",
    }
    endpoint = endpoint_map.get(detail_level, "/formations_stop_based")

    params = {
        "evu": evu_upper,
        "operationDate": operation_date,
        "trainNumber": clean_number,
    }

    try:
        data = await client.get("formation", path=endpoint, params=params)
    except NotFoundError:
        return (
            f"🔍 Keine Formationsdaten gefunden für Zug {train_number} "
            f"({EVU_MAP.get(evu_upper, evu_upper)}) am {operation_date}.\n"
            f"Mögliche Gründe:\n"
            f"- Der Zug fährt nicht an diesem Tag\n"
            f"- Die Zugnummer gehört zu einem anderen EVU\n"
            f"- Formationsdaten sind nur für heute verfügbar"
        )
    except APIError as e:
        return f"⚠️ Formationsdaten konnten nicht abgerufen werden: {e}"

    if isinstance(data, str):
        # Manchmal kommt Text statt JSON → Fehler
        return f"⚠️ Unerwartete Antwort vom Formation Service: {data[:200]}"

    return _format_formation(data, train_number, evu_upper, operation_date, detail_level)


async def get_formation_health(client: TransportAPIClient) -> str:
    """Prüft den Systemstatus des Formation Service."""
    try:
        data = await client.get("formation", path="/health", use_cache=False)
        if isinstance(data, dict):
            status = data.get("status", "unknown")
            return f"Formation Service Status: {status}"
        return f"Formation Service Status: {data}"
    except APIError as e:
        return f"⚠️ Formation Service nicht erreichbar: {e}"


def _format_formation(
    data: dict,
    display_name: str,
    evu: str,
    op_date: str,
    detail_level: str,
) -> str:
    """Formatiert die Formation als lesbaren Text."""
    lines = [
        f"🚆 Zugformation {display_name} ({EVU_MAP.get(evu, evu)}) "
        f"am {_format_date(op_date)}:\n"
    ]

    # Meta-Informationen
    meta = data.get("trainMetaInformation", {})
    if meta:
        train_type = meta.get("trainType", "")
        line = meta.get("lineText", "")
        if train_type or line:
            lines.append(f"  Zugtyp: {train_type} {line}".strip())

    formation_meta = data.get("formationMetaInformation", {})
    if formation_meta:
        num_vehicles = formation_meta.get("numberOfVehicles", "?")
        lines.append(f"  Anzahl Fahrzeuge: {num_vehicles}")
    lines.append("")

    # Stop-based: Formation pro Haltestelle
    scheduled_stops = data.get("scheduledStops", [])
    if scheduled_stops:
        lines.append("📍 Haltestellen und Formation:")
        for stop in scheduled_stops:
            stop_info = _format_stop(stop)
            lines.append(stop_info)
        lines.append("")

    # Vehicle-based: Details pro Fahrzeug
    vehicles = data.get("formationVehicles", data.get("vehicles", []))
    if vehicles and detail_level in ("vehicle_based", "full"):
        lines.append("🚃 Fahrzeugdetails:")
        for v in vehicles:
            vehicle_info = _format_vehicle(v)
            lines.append(vehicle_info)
        lines.append("")

    # Formationskurzstring (wenn vorhanden)
    for stop in scheduled_stops:
        short_string = stop.get("formationShortString", "")
        if short_string:
            lines.append(f"📐 Formationskurzstring: {short_string}")
            lines.append(_explain_formation_string(short_string))
            break  # Nur einmal anzeigen

    # Zusammenfassung der Ausstattung
    all_amenities = _collect_amenities(data)
    if all_amenities:
        lines.append("\n🎯 Ausstattung in diesem Zug:")
        for amenity in sorted(all_amenities):
            label = AMENITIES.get(amenity, amenity)
            lines.append(f"  {label}")

    return "\n".join(lines)


def _format_stop(stop: dict) -> str:
    """Formatiert eine Haltestelle."""
    stop_point = stop.get("stopPoint", {})
    name = stop_point.get("name", "?")
    sloid = stop_point.get("sloid", "")

    stop_time = stop.get("stopTime", {})
    arr = stop_time.get("arrival", "")
    dep = stop_time.get("departure", "")

    track = stop.get("track", {}).get("text", "")

    time_str = ""
    if arr and dep:
        time_str = f"an {_format_time(arr)} / ab {_format_time(dep)}"
    elif dep:
        time_str = f"ab {_format_time(dep)}"
    elif arr:
        time_str = f"an {_format_time(arr)}"

    track_str = f" | Gleis {track}" if track else ""
    short_str = stop.get("formationShortString", "")
    formation_hint = f" | {short_str}" if short_str else ""

    return f"  📍 {name}: {time_str}{track_str}{formation_hint}"


def _format_vehicle(vehicle: dict) -> str:
    """Formatiert ein einzelnes Fahrzeug."""
    props = vehicle.get("vehicleProperties", vehicle)
    vehicle_type = props.get("vehicleTypeKI", props.get("type", "?"))
    order_number = props.get("orderNumber", "?")

    type_label = VEHICLE_TYPES.get(str(vehicle_type), f"❓ Typ {vehicle_type}")

    amenities_list = props.get("amenities", [])
    amenities_str = ""
    if amenities_list:
        amenity_labels = [AMENITIES.get(a, a) for a in amenities_list]
        amenities_str = f" | {', '.join(amenity_labels)}"

    return f"  Wagen {order_number}: {type_label}{amenities_str}"


def _explain_formation_string(short: str) -> str:
    """
    Erklärt den Formationskurzstring in menschenlesbarer Form.
    
    Beispiel: "A[2,2,WR,1,1,LK]D" bedeutet:
    Sektor A: [2.Kl, 2.Kl, Restaurant, 1.Kl, 1.Kl, Lok] Sektor D
    """
    if not short:
        return ""

    explanation_parts = []
    import re

    # Sektoren finden (einzelne Grossbuchstaben)
    sectors = re.findall(r'[A-Z](?=[[\]]|$)', short)
    if sectors:
        explanation_parts.append(f"  Sektoren: {' bis '.join([sectors[0], sectors[-1]]) if len(sectors) > 1 else sectors[0]}")

    # Fahrzeugtypen zählen
    types_found = re.findall(r'(?:1|2|12|CC|FA|WL|WR|W1|W2|LK|D|F|K|X)', short)
    type_counts = {}
    for t in types_found:
        label = VEHICLE_TYPES.get(t, t)
        type_counts[label] = type_counts.get(label, 0) + 1

    if type_counts:
        explanation_parts.append("  Zusammensetzung: " + ", ".join(
            f"{count}× {label}" for label, count in type_counts.items()
        ))

    # Status-Zeichen
    if ">" in short:
        explanation_parts.append("  ℹ️ Gruppeneinsteiger erwartet")
    if "-" in short:
        explanation_parts.append("  🚫 Teilweise geschlossene Wagen")

    return "\n".join(explanation_parts) if explanation_parts else ""


def _collect_amenities(data: dict) -> set:
    """Sammelt alle verfügbaren Ausstattungsmerkmale im gesamten Zug."""
    amenities = set()

    for key in ("formationVehicles", "vehicles"):
        for v in data.get(key, []):
            props = v.get("vehicleProperties", v)
            for a in props.get("amenities", []):
                amenities.add(a)

    return amenities


def _format_time(time_str: str) -> str:
    """Formatiert ISO-Zeit ins Schweizer Format (HH:MM)."""
    if not time_str:
        return "?"
    try:
        from datetime import datetime
        dt = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
        return dt.strftime("%H:%M")
    except (ValueError, TypeError):
        # Fallback: Nur HH:MM extrahieren
        if "T" in time_str and len(time_str) >= 16:
            return time_str[11:16]
        return time_str


def _format_date(date_str: str) -> str:
    """Formatiert ISO-Datum ins Schweizer Format."""
    try:
        d = date.fromisoformat(date_str)
        weekdays = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
        return f"{weekdays[d.weekday()]}, {d.strftime('%d.%m.%Y')}"
    except (ValueError, TypeError):
        return date_str
