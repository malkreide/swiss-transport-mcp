"""
OJP Fare – Die Preisauskunft für Schweizer ÖV-Tickets.

Metapher: Stell dir vor, Claude kann nicht nur sagen "Nimm den Zug um 8:02
von Zürich nach Bern", sondern auch gleich "Das kostet CHF 51 mit Halbtax."
Genau das macht diese API.

API-Details:
- Endpoint: POST https://api.opentransportdata.swiss/ojp20
- Format: XML (OJP 2.0 / SIRI-Framework)
- Auth: Bearer Token im Header
- Funktionsweise: 2-Schritt-Prozess:
  1. OJPTripRequest → Reise planen (nutzt bestehende OJP-Integration)
  2. OJPFareRequest → Preis für die geplante Reise abfragen
- RequestorRef muss Suffix enthalten: '_test', '_int' oder '_prod'
- Backend: NOVA-Preissystem der SBB

ACHTUNG: Das Preissystem ist komplex (Halbtax, GA, Zonen, Verbünde).
Die API liefert den regulären Preis. Rabatte sind nicht immer abgebildet.
"""

import xml.etree.ElementTree as ET
from datetime import datetime

from .api_infrastructure import APIError, TransportAPIClient

# OJP 2.0 Namespaces
OJP_NS = {
    "siri": "http://www.siri.org.uk/siri",
    "ojp": "http://www.vdv.de/ojp",
}


async def get_fare_info(
    client: TransportAPIClient,
    origin: str,
    destination: str,
    departure_time: str | None = None,
    requestor_ref: str = "swiss-transport-mcp_prod",
    traveller_class: str = "second",
) -> str:
    """
    Holt Preisinformationen für eine ÖV-Verbindung.

    Args:
        client: Der konfigurierte API-Client
        origin: Abfahrtsort (z.B. "Zürich HB", "8503000")
        destination: Ankunftsort (z.B. "Bern", "8507000")
        departure_time: Abfahrtszeit ISO-Format (Standard: jetzt)
        requestor_ref: Referenz für die API (muss _test/_int/_prod enthalten)
        traveller_class: "first" oder "second"

    Returns:
        Formatierter Text mit Preisinformationen.

    Ablauf:
    1. OJP TripRequest senden → Route berechnen
    2. Aus der Route die Legs (Teilstrecken) extrahieren
    3. OJP FareRequest mit den Trip-Daten senden
    4. Preise aus der Antwort extrahieren und formatieren
    """
    if departure_time is None:
        departure_time = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    # Schritt 1: Trip anfragen (Routenberechnung)
    trip_xml = _build_trip_request(origin, destination, departure_time, requestor_ref)

    try:
        trip_response = await client.post_xml(
            "ojp_fare",
            trip_xml,
            cache_key_params={"type": "trip", "from": origin, "to": destination, "time": departure_time[:13]},
        )
    except APIError as e:
        return f"⚠️ Routenberechnung fehlgeschlagen: {e}"

    # Trips aus der Antwort extrahieren
    trips = _parse_trip_response(trip_response)
    if not trips:
        return (
            f"🔍 Keine Verbindung gefunden von {origin} nach {destination} "
            f"um {departure_time[:16]}. Bitte prüfe die Ortsnamen."
        )

    # Schritt 2: Fare für den ersten Trip anfragen
    first_trip = trips[0]
    fare_xml = _build_fare_request(first_trip, requestor_ref, traveller_class)

    try:
        fare_response = await client.post_xml(
            "ojp_fare",
            fare_xml,
            cache_key_params={"type": "fare", "from": origin, "to": destination, "class": traveller_class},
        )
    except APIError as e:
        # Wenn Fare-Abfrage fehlschlägt, geben wir wenigstens die Route zurück
        return (
            f"🚆 Verbindung gefunden: {origin} → {destination}\n"
            f"{_format_trip_summary(first_trip)}\n"
            f"⚠️ Preisauskunft nicht verfügbar: {e}"
        )

    # Preise extrahieren
    fares = _parse_fare_response(fare_response)

    return _format_fare_result(origin, destination, first_trip, fares, traveller_class)


async def get_simple_fare(
    client: TransportAPIClient,
    origin_ref: str,
    destination_ref: str,
    requestor_ref: str = "swiss-transport-mcp_prod",
) -> str:
    """
    Vereinfachte Preisabfrage mit Haltestellennummern (BPUIC/SLOID).

    Nützlich wenn die Haltestellennummern bereits bekannt sind
    (z.B. aus einer vorherigen OJP-Abfrage).

    Gängige Haltestellennummern:
    - Zürich HB: 8503000
    - Bern: 8507000
    - Basel SBB: 8500010
    - Luzern: 8505000
    - Genf: 8501008
    """
    # Direkte Fare-Abfrage ohne vorherigen Trip
    fare_xml = _build_direct_fare_request(origin_ref, destination_ref, requestor_ref)

    try:
        response = await client.post_xml(
            "ojp_fare",
            fare_xml,
            cache_key_params={"type": "direct_fare", "from": origin_ref, "to": destination_ref},
        )
    except APIError as e:
        return f"⚠️ Preisauskunft nicht verfügbar: {e}"

    fares = _parse_fare_response(response)
    if not fares:
        return f"🔍 Keine Preisinformation verfügbar für {origin_ref} → {destination_ref}."

    return _format_simple_fare(origin_ref, destination_ref, fares)


# =============================================================================
# XML-Builder – Baut die OJP-Requests
# =============================================================================

def _build_trip_request(origin: str, destination: str, dep_time: str, requestor_ref: str) -> str:
    """
    Baut einen OJP 2.0 TripRequest als XML.

    Wichtig: UseRealtime = false, weil Preise nicht auf Basis
    von Echtzeitdaten berechnet werden (laut API-Doku).
    """
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<OJP xmlns="http://www.vdv.de/ojp" xmlns:siri="http://www.siri.org.uk/siri" version="2.0">
    <OJPRequest>
        <siri:ServiceRequest>
            <siri:RequestTimestamp>{datetime.now().isoformat()}</siri:RequestTimestamp>
            <siri:RequestorRef>{requestor_ref}</siri:RequestorRef>
            <OJPTripRequest>
                <siri:RequestTimestamp>{datetime.now().isoformat()}</siri:RequestTimestamp>
                <Origin>
                    <PlaceRef>
                        <Name><Text>{origin}</Text></Name>
                    </PlaceRef>
                    <DepArrTime>{dep_time}</DepArrTime>
                </Origin>
                <Destination>
                    <PlaceRef>
                        <Name><Text>{destination}</Text></Name>
                    </PlaceRef>
                </Destination>
                <Params>
                    <NumberOfResults>1</NumberOfResults>
                    <UseRealtimeData>false</UseRealtimeData>
                </Params>
            </OJPTripRequest>
        </siri:ServiceRequest>
    </OJPRequest>
</OJP>"""


def _build_fare_request(trip_data: dict, requestor_ref: str, traveller_class: str) -> str:
    """
    Baut einen OJP 2.0 FareRequest basierend auf Trip-Daten.

    Der FareRequest enthält die Leg-Informationen aus dem TripResult,
    damit das NOVA-Backend den korrekten Preis berechnen kann.
    """
    legs_xml = ""
    for leg in trip_data.get("legs", []):
        origin_ref = leg.get("origin_ref", "")
        dest_ref = leg.get("dest_ref", "")
        dep_time = leg.get("departure", "")
        arr_time = leg.get("arrival", "")

        if origin_ref and dest_ref:
            legs_xml += f"""
                <TripLeg>
                    <LegStart>
                        <StopPointRef>{origin_ref}</StopPointRef>
                    </LegStart>
                    <LegEnd>
                        <StopPointRef>{dest_ref}</StopPointRef>
                    </LegEnd>
                    <ServiceDeparture>
                        <TimetabledTime>{dep_time}</TimetabledTime>
                    </ServiceDeparture>
                    <ServiceArrival>
                        <TimetabledTime>{arr_time}</TimetabledTime>
                    </ServiceArrival>
                </TripLeg>"""

    fare_class = "first" if traveller_class == "first" else "second"

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<OJP xmlns="http://www.vdv.de/ojp" xmlns:siri="http://www.siri.org.uk/siri" version="2.0">
    <OJPRequest>
        <siri:ServiceRequest>
            <siri:RequestTimestamp>{datetime.now().isoformat()}</siri:RequestTimestamp>
            <siri:RequestorRef>{requestor_ref}</siri:RequestorRef>
            <OJPFareRequest>
                <siri:RequestTimestamp>{datetime.now().isoformat()}</siri:RequestTimestamp>
                <TripFareRequest>
                    <Trip>{legs_xml}
                    </Trip>
                    <Params>
                        <FareClass>{fare_class}</FareClass>
                    </Params>
                </TripFareRequest>
            </OJPFareRequest>
        </siri:ServiceRequest>
    </OJPRequest>
</OJP>"""


def _build_direct_fare_request(origin_ref: str, destination_ref: str, requestor_ref: str) -> str:
    """Baut einen vereinfachten FareRequest nur mit Start/Ziel."""
    dep_time = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<OJP xmlns="http://www.vdv.de/ojp" xmlns:siri="http://www.siri.org.uk/siri" version="2.0">
    <OJPRequest>
        <siri:ServiceRequest>
            <siri:RequestTimestamp>{datetime.now().isoformat()}</siri:RequestTimestamp>
            <siri:RequestorRef>{requestor_ref}</siri:RequestorRef>
            <OJPFareRequest>
                <siri:RequestTimestamp>{datetime.now().isoformat()}</siri:RequestTimestamp>
                <StaticFareRequest>
                    <Origin>
                        <StopPointRef>{origin_ref}</StopPointRef>
                    </Origin>
                    <Destination>
                        <StopPointRef>{destination_ref}</StopPointRef>
                    </Destination>
                    <DepartureTime>{dep_time}</DepartureTime>
                </StaticFareRequest>
            </OJPFareRequest>
        </siri:ServiceRequest>
    </OJPRequest>
</OJP>"""


# =============================================================================
# XML-Parser – Liest die OJP-Antworten
# =============================================================================

def _parse_trip_response(xml_text: str) -> list[dict]:
    """Parst die OJP TripDelivery und extrahiert Trips."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []

    trips = []

    # Suche TripResult in verschiedenen Namespace-Varianten
    for trip_result in _find_all_elements(root, "TripResult"):
        trip = {"legs": [], "summary": ""}

        for leg in _find_all_elements(trip_result, "TripLeg"):
            leg_data = _extract_leg(leg)
            if leg_data:
                trip["legs"].append(leg_data)

        # Zusammenfassung
        duration = _find_text(trip_result, "Duration")
        transfers = _find_text(trip_result, "Transfers")
        trip["duration"] = duration
        trip["transfers"] = transfers

        if trip["legs"]:
            trips.append(trip)

    return trips


def _extract_leg(leg_element: ET.Element) -> dict | None:
    """Extrahiert ein Leg (Teilstrecke) aus dem TripResult."""
    origin_name = _find_text(leg_element, "LegStart") or _find_deep_text(leg_element, "LegStart", "Name")
    dest_name = _find_text(leg_element, "LegEnd") or _find_deep_text(leg_element, "LegEnd", "Name")
    origin_ref = _find_deep_text(leg_element, "LegStart", "StopPointRef") or ""
    dest_ref = _find_deep_text(leg_element, "LegEnd", "StopPointRef") or ""
    departure = _find_deep_text(leg_element, "ServiceDeparture", "TimetabledTime") or ""
    arrival = _find_deep_text(leg_element, "ServiceArrival", "TimetabledTime") or ""
    line = _find_text(leg_element, "PublishedLineName") or _find_text(leg_element, "Name") or ""
    mode = _find_text(leg_element, "PtMode") or ""

    return {
        "origin": origin_name,
        "destination": dest_name,
        "origin_ref": origin_ref,
        "dest_ref": dest_ref,
        "departure": departure,
        "arrival": arrival,
        "line": line,
        "mode": mode,
    }


def _parse_fare_response(xml_text: str) -> list[dict]:
    """
    Parst die OJP FareDelivery und extrahiert Preise.

    Die Antwort enthält FareProducts mit:
    - FareProductName: z.B. "Einzelbillett"
    - Price/Amount: z.B. "51.00"
    - Price/Currency: "CHF"
    - FareClass: "first" oder "second"
    - ValidFor: Gültigkeitsdauer
    """
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []

    fares = []

    for fare_result in _find_all_elements(root, "FareResult"):
        for product in _find_all_elements(fare_result, "FareProduct"):
            fare = {
                "name": _find_text(product, "FareProductName") or _find_text(product, "Name") or "Ticket",
                "amount": _find_text(product, "Amount") or _find_text(product, "Price") or "?",
                "currency": _find_text(product, "Currency") or "CHF",
                "fare_class": _find_text(product, "FareClass") or "",
                "validity": _find_text(product, "ValidFor") or "",
            }
            fares.append(fare)

    # Auch direkt nach Price-Elementen suchen (alternative Struktur)
    if not fares:
        for price_el in _find_all_elements(root, "Price"):
            amount = _find_text(price_el, "Amount") or ""
            currency = _find_text(price_el, "Currency") or "CHF"
            if amount:
                fares.append({
                    "name": "Einzelbillett",
                    "amount": amount,
                    "currency": currency,
                    "fare_class": "",
                    "validity": "",
                })

    return fares


# =============================================================================
# XML-Hilfsfunktionen (robustes Parsing trotz wechselnder Namespaces)
# =============================================================================

def _find_all_elements(root: ET.Element, tag: str) -> list:
    """Findet alle Elemente mit einem Tag, unabhängig vom Namespace."""
    results = []
    for el in root.iter():
        local_tag = el.tag.split("}")[-1] if "}" in el.tag else el.tag
        if local_tag == tag:
            results.append(el)
    return results


def _find_text(parent: ET.Element, tag: str) -> str:
    """Findet den Text eines Kind-Elements."""
    for el in parent.iter():
        local_tag = el.tag.split("}")[-1] if "}" in el.tag else el.tag
        if local_tag == tag and el.text:
            return el.text.strip()
    return ""


def _find_deep_text(parent: ET.Element, container_tag: str, child_tag: str) -> str:
    """Findet Text in einem verschachtelten Element."""
    for container in parent.iter():
        local_tag = container.tag.split("}")[-1] if "}" in container.tag else container.tag
        if local_tag == container_tag:
            return _find_text(container, child_tag)
    return ""


# =============================================================================
# Formatierung
# =============================================================================

def _format_fare_result(
    origin: str,
    destination: str,
    trip: dict,
    fares: list,
    traveller_class: str,
) -> str:
    """Formatiert das Gesamtergebnis: Route + Preise."""
    lines = [f"💰 Preisauskunft {origin} → {destination}:\n"]

    # Trip-Info
    lines.append(_format_trip_summary(trip))
    lines.append("")

    # Preise
    if fares:
        class_label = "1. Klasse" if traveller_class == "first" else "2. Klasse"
        lines.append(f"🎫 Preise ({class_label}):")
        for f in fares:
            amount = f["amount"]
            currency = f["currency"]
            name = f["name"]
            lines.append(f"  {name}: {currency} {amount}")
            if f["validity"]:
                lines.append(f"    Gültigkeit: {f['validity']}")
    else:
        lines.append("⚠️ Keine Preisinformation vom System erhalten.")

    lines.append("")
    lines.append(
        "💡 Hinweis: Angezeigte Preise sind reguläre Tarife. "
        "Rabatte (Halbtax, GA, Verbundsabos) sind möglicherweise nicht berücksichtigt. "
        "Verbindliche Preise: sbb.ch oder am Schalter."
    )

    return "\n".join(lines)


def _format_simple_fare(origin_ref: str, destination_ref: str, fares: list) -> str:
    """Formatiert eine einfache Preisauskunft."""
    lines = [f"💰 Preisauskunft (Haltestelle {origin_ref} → {destination_ref}):\n"]

    for f in fares:
        lines.append(f"  🎫 {f['name']}: {f['currency']} {f['amount']}")
        if f["fare_class"]:
            lines.append(f"    Klasse: {f['fare_class']}")

    lines.append("")
    lines.append("💡 Verbindliche Preise: sbb.ch oder am Schalter.")
    return "\n".join(lines)


def _format_trip_summary(trip: dict) -> str:
    """Formatiert eine Zusammenfassung des Trips."""
    legs = trip.get("legs", [])
    if not legs:
        return "  Keine Routeninformation verfügbar."

    parts = []
    for leg in legs:
        dep = _format_time(leg.get("departure", ""))
        arr = _format_time(leg.get("arrival", ""))
        origin = leg.get("origin", "?")
        dest = leg.get("destination", "?")
        line = leg.get("line", "")

        line_str = f" ({line})" if line else ""
        parts.append(f"  🚆 {dep} {origin} → {arr} {dest}{line_str}")

    duration = trip.get("duration", "")
    transfers = trip.get("transfers", "")
    meta = []
    if duration:
        meta.append(f"Dauer: {duration}")
    if transfers:
        meta.append(f"Umstiege: {transfers}")

    summary = "\n".join(parts)
    if meta:
        summary += f"\n  ⏱️ {' | '.join(meta)}"

    return summary


def _format_time(time_str: str) -> str:
    """Extrahiert HH:MM aus ISO-Datetime."""
    if not time_str:
        return "?"
    try:
        dt = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
        return dt.strftime("%H:%M")
    except (ValueError, TypeError):
        if "T" in time_str and len(time_str) >= 16:
            return time_str[11:16]
        return time_str
