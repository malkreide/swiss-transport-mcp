"""Swiss Transport MCP Server – 10 Tools für den Schweizer ÖV.

MCP Server for Swiss public transport data from opentransportdata.swiss.
Provides journey planning (OJP), real-time departures, disruptions (SIRI-SX),
occupancy forecasts, ticket prices (OJP Fare), train formations,
stop search, and dataset catalog access via the Model Context Protocol.

Metapher: Der bestehende Server war ein Navigationsgerät (Route von A nach B).
Jetzt ist es ein VOLLSTÄNDIGES Reiseinformationssystem:
Navigation + Störungsmeldungen + Auslastung + Preise + Zugformation.

API keys required: Get free keys at https://api-manager.opentransportdata.swiss/
Set TRANSPORT_API_KEY (unified) or individual keys per API.

Extension APIs (optional – kein Crash wenn Keys fehlen):
- SIRI_SX_API_KEY      → Störungsmeldungen
- OCCUPANCY_API_KEY    → Belegungsprognose
- FORMATION_API_KEY    → Zugformation
- OJP_FARE_API_KEY     → Preisauskunft
"""

import json
import logging
import os
from typing import Any

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, ConfigDict, Field

from . import api_client, ojp_client
from .api_infrastructure import create_transport_client
from .formation import get_formation_health, get_train_formation
from .occupancy import get_occupancy_for_route, get_occupancy_forecast
from .ojp_fare import get_fare_info
from .siri_sx import get_disruptions

logger = logging.getLogger("swiss-transport-mcp")

# ---------------------------------------------------------------------------
# Server initialization
# ---------------------------------------------------------------------------

mcp = FastMCP(
    "swiss_transport_mcp",
    instructions=(
        "Swiss public transport data server with 10 tools. "
        "Provides journey planning, real-time departures, disruptions, "
        "occupancy forecasts, ticket prices, train formations, stop search, "
        "and transport dataset catalog for all of Switzerland via opentransportdata.swiss. "
        "Use transport_search_stop to find stop IDs, then use those IDs "
        "for departures, trip planning, or ticket prices. "
        "Extension tools (disruptions, occupancy, prices, formations) require "
        "separate API keys – they return helpful messages if not configured."
    ),
)


# ===========================================================================
# Extension API Client (lazy initialization)
# ===========================================================================

_ext_client = None


def _get_ext_client():
    """Lazy Initialization des Extension-API-Clients.

    Warum lazy? Weil der MCP-Server beim Start schnell bereit sein muss.
    Die API-Konfiguration wird erst geprüft, wenn ein Tool tatsächlich
    aufgerufen wird. Fehlende Keys → Tool gibt saubere Fehlermeldung.
    """
    global _ext_client
    if _ext_client is None:
        _ext_client = create_transport_client(
            siri_sx_key=os.environ.get("SIRI_SX_API_KEY"),
            occupancy_key=os.environ.get("OCCUPANCY_API_KEY"),
            formation_key=os.environ.get("FORMATION_API_KEY"),
            ojp_fare_key=os.environ.get("OJP_FARE_API_KEY"),
        )
    return _ext_client


def _check_api(api_name: str, env_var: str) -> str | None:
    """Prüft ob ein API-Key konfiguriert ist."""
    key = os.environ.get(env_var)
    if not key:
        return (
            f"⚠️ {api_name} ist nicht konfiguriert.\n"
            f"Setze die Umgebungsvariable {env_var} mit deinem API-Key.\n"
            f"API-Key erstellen: https://api-manager.opentransportdata.swiss/"
        )
    return None


# ===========================================================================
# Input models – Core Tools (OJP + CKAN)
# ===========================================================================

class SearchStopInput(BaseModel):
    """Input for searching stops/stations."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    query: str = Field(
        ...,
        description="Search text for stop name (e.g., 'Zürich HB', 'Bern Bahnhof', 'Winterthur')",
        min_length=2,
        max_length=200,
    )
    limit: int = Field(
        default=10,
        description="Maximum number of results (1–20)",
        ge=1,
        le=20,
    )


class SearchStopByCoordInput(BaseModel):
    """Input for finding nearby stops by coordinates."""

    model_config = ConfigDict(extra="forbid")

    latitude: float = Field(
        ...,
        description="Latitude (WGS84), e.g. 47.3769 for Zürich HB",
        ge=45.0,
        le=48.5,
    )
    longitude: float = Field(
        ...,
        description="Longitude (WGS84), e.g. 8.5417 for Zürich HB",
        ge=5.5,
        le=10.8,
    )
    limit: int = Field(
        default=10,
        description="Maximum number of results (1–20)",
        ge=1,
        le=20,
    )


class DeparturesInput(BaseModel):
    """Input for fetching departures/arrivals at a stop."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    stop_id: str = Field(
        ...,
        description="Stop ID from transport_search_stop (e.g., '8503000' for Zürich HB). Use transport_search_stop first to find the ID.",
        min_length=1,
    )
    stop_name: str = Field(
        default="",
        description="Optional stop name for display purposes",
    )
    time: str | None = Field(
        default=None,
        description="Departure time in ISO 8601 (e.g., '2026-03-01T08:00:00Z'). Defaults to now.",
    )
    limit: int = Field(
        default=10,
        description="Number of departures to show (1–30)",
        ge=1,
        le=30,
    )
    event_type: str = Field(
        default="departure",
        description="'departure' or 'arrival'",
        pattern=r"^(departure|arrival)$",
    )


class TripPlanInput(BaseModel):
    """Input for planning a journey between two locations."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    origin: str = Field(
        ...,
        description=(
            "Start location. Either a stop ID (e.g., '8503000' for Zürich HB) "
            "or a place name (e.g., 'Langstrasse 100, Zürich'). "
            "Use transport_search_stop first for exact stop IDs."
        ),
        min_length=1,
    )
    destination: str = Field(
        ...,
        description=(
            "End location. Either a stop ID or a place name. "
            "Use transport_search_stop first for exact stop IDs."
        ),
        min_length=1,
    )
    time: str | None = Field(
        default=None,
        description="Departure time in ISO 8601. Defaults to now.",
    )
    limit: int = Field(
        default=5,
        description="Number of trip options (1–6)",
        ge=1,
        le=6,
    )


class DatasetSearchInput(BaseModel):
    """Input for searching the transport data catalog."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    query: str = Field(
        ...,
        description="Search term (e.g., 'gtfs', 'fahrplan', 'realtime', 'ojp', 'parking')",
        min_length=1,
        max_length=200,
    )
    limit: int = Field(
        default=10,
        description="Maximum number of results (1–50)",
        ge=1,
        le=50,
    )


class DatasetDetailInput(BaseModel):
    """Input for getting dataset details."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    dataset_id: str = Field(
        ...,
        description="Dataset ID/slug from transport_search_datasets (e.g., 'ojp2-0', 'gtfsrt', 'timetable')",
        min_length=1,
    )


# ===========================================================================
# CORE TOOLS 1-6: OJP + CKAN (Original)
# ===========================================================================

# ---------------------------------------------------------------------------
# Tool 1: Search stops by name
# ---------------------------------------------------------------------------

@mcp.tool(
    name="transport_search_stop",
    annotations={
        "title": "Search Swiss Stops & Stations",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def transport_search_stop(params: SearchStopInput) -> str:
    """Search for Swiss public transport stops and stations by name.

    Searches across all Swiss public transport stops (train stations,
    tram/bus stops, boat stations). Returns stop IDs needed for
    transport_departures and transport_trip_plan.

    Returns:
        JSON list of matching stops with id, name, coordinates, and transport modes.
    """
    try:
        xml_request = ojp_client.build_location_request(
            query=params.query,
            limit=params.limit,
        )
        xml_response = await api_client.ojp_request(xml_request)

        error = ojp_client.parse_error_response(xml_response)
        if error:
            return f"OJP Error: {error}"

        locations = ojp_client.parse_location_response(xml_response)

        if not locations:
            return json.dumps({
                "message": f"No stops found for '{params.query}'. Try a broader search term.",
                "results": [],
            })

        return json.dumps({
            "query": params.query,
            "count": len(locations),
            "stops": locations,
            "hint": "Use the 'stop_id' value with transport_departures or transport_trip_plan.",
        }, ensure_ascii=False, indent=2)

    except Exception as e:
        return api_client.handle_api_error(e)


# ---------------------------------------------------------------------------
# Tool 1b: Search stops by coordinates
# ---------------------------------------------------------------------------

@mcp.tool(
    name="transport_nearby_stops",
    annotations={
        "title": "Find Nearby Stops by Coordinates",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def transport_nearby_stops(params: SearchStopByCoordInput) -> str:
    """Find public transport stops near a geographic location.

    Useful for finding stops near a school, address, or point of interest.
    Swiss coordinates only (lat 45–48.5, lon 5.5–10.8).

    Returns:
        JSON list of nearby stops with id, name, coordinates, and distance info.
    """
    try:
        xml_request = ojp_client.build_location_coord_request(
            latitude=params.latitude,
            longitude=params.longitude,
            limit=params.limit,
        )
        xml_response = await api_client.ojp_request(xml_request)

        error = ojp_client.parse_error_response(xml_response)
        if error:
            return f"OJP Error: {error}"

        locations = ojp_client.parse_location_response(xml_response)

        # Deduplicate by stop_id (OJP may return multiple platforms per stop)
        seen: set[str] = set()
        unique_locations = []
        for loc in locations:
            sid = loc.get("stop_id", "")
            if sid and sid not in seen:
                seen.add(sid)
                unique_locations.append(loc)
            elif not sid:
                unique_locations.append(loc)

        if not unique_locations:
            return json.dumps({
                "message": "No stops found near these coordinates.",
                "results": [],
            })

        return json.dumps({
            "latitude": params.latitude,
            "longitude": params.longitude,
            "count": len(unique_locations),
            "nearby_stops": unique_locations,
            "hint": "Use 'stop_id' with transport_departures or transport_trip_plan.",
        }, ensure_ascii=False, indent=2)

    except Exception as e:
        return api_client.handle_api_error(e)


# ---------------------------------------------------------------------------
# Tool 2: Departures / Arrivals
# ---------------------------------------------------------------------------

@mcp.tool(
    name="transport_departures",
    annotations={
        "title": "Live Departures at a Stop",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": False,  # Results change with time
        "openWorldHint": True,
    },
)
async def transport_departures(params: DeparturesInput) -> str:
    """Get upcoming departures or arrivals at a Swiss public transport stop.

    Shows real-time information including delays when available.
    Like a digital departure board at a train station.

    Use transport_search_stop first to get the stop_id.

    Returns:
        JSON list of departures with line, destination, scheduled time,
        real-time time, delay, and platform.
    """
    try:
        xml_request = ojp_client.build_stop_event_request(
            stop_ref=params.stop_id,
            stop_name=params.stop_name,
            dep_arr_time=params.time,
            limit=params.limit,
            event_type=params.event_type,
        )
        xml_response = await api_client.ojp_request(xml_request)

        error = ojp_client.parse_error_response(xml_response)
        if error:
            return f"OJP Error: {error}"

        events = ojp_client.parse_stop_event_response(xml_response)

        if not events:
            return json.dumps({
                "message": f"No {params.event_type}s found for stop {params.stop_id}.",
                "results": [],
            })

        return json.dumps({
            "stop_id": params.stop_id,
            "stop_name": params.stop_name or params.stop_id,
            "type": params.event_type,
            "count": len(events),
            "departures": events,
        }, ensure_ascii=False, indent=2)

    except Exception as e:
        return api_client.handle_api_error(e)


# ---------------------------------------------------------------------------
# Tool 3: Trip Planning
# ---------------------------------------------------------------------------

@mcp.tool(
    name="transport_trip_plan",
    annotations={
        "title": "Plan a Journey (Swiss ÖV)",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    },
)
async def transport_trip_plan(params: TripPlanInput) -> str:
    """Plan a journey between two locations in Switzerland.

    Works like the SBB app: enter origin and destination (stop IDs or
    place names), get multiple trip options with transfers, durations,
    and transport modes.

    For best results, use stop IDs from transport_search_stop.
    Place names (addresses) also work but may be slower.

    Returns:
        JSON list of trip options, each with legs (individual journey segments),
        total duration, number of transfers, and transport modes used.
    """
    try:
        xml_request = ojp_client.build_trip_request(
            origin_ref=params.origin,
            destination_ref=params.destination,
            dep_time=params.time,
            limit=params.limit,
        )
        xml_response = await api_client.ojp_request(xml_request)

        error = ojp_client.parse_error_response(xml_response)
        if error:
            return f"OJP Error: {error}"

        trips = ojp_client.parse_trip_response(xml_response)

        if not trips:
            return json.dumps({
                "message": f"No trips found from '{params.origin}' to '{params.destination}'. Try using stop IDs instead of names.",
                "results": [],
            })

        return json.dumps({
            "origin": params.origin,
            "destination": params.destination,
            "count": len(trips),
            "trips": trips,
            "hint": "Each trip contains legs: 'timed' = public transport, 'walk' = walking, 'transfer' = platform change.",
        }, ensure_ascii=False, indent=2)

    except Exception as e:
        return api_client.handle_api_error(e)


# ---------------------------------------------------------------------------
# Tool 5: Search datasets
# ---------------------------------------------------------------------------

@mcp.tool(
    name="transport_search_datasets",
    annotations={
        "title": "Search Transport Data Catalog",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def transport_search_datasets(params: DatasetSearchInput) -> str:
    """Search the Swiss transport open data catalog (~90 datasets).

    Find datasets about timetables, real-time data, GTFS feeds,
    accessibility info, traffic counters, and more from
    opentransportdata.swiss.

    Returns:
        JSON list of matching datasets with name, description, formats,
        and download URLs.
    """
    try:
        result = await api_client.ckan_request(
            "package_search",
            params={"q": params.query, "rows": params.limit},
        )

        datasets = []
        for pkg in result.get("results", []):
            ds: dict[str, Any] = {
                "id": pkg.get("name"),
                "title": pkg.get("title"),
                "description": (pkg.get("notes", "") or "")[:300],
                "organization": pkg.get("organization", {}).get("title", ""),
                "formats": list({r.get("format", "").upper() for r in pkg.get("resources", []) if r.get("format")}),
                "last_modified": pkg.get("metadata_modified", ""),
                "url": f"https://data.opentransportdata.swiss/dataset/{pkg.get('name')}",
            }
            datasets.append(ds)

        return json.dumps({
            "query": params.query,
            "total_found": result.get("count", 0),
            "showing": len(datasets),
            "datasets": datasets,
            "hint": "Use 'id' with transport_get_dataset for full details and download links.",
        }, ensure_ascii=False, indent=2)

    except Exception as e:
        return api_client.handle_api_error(e)


# ---------------------------------------------------------------------------
# Tool 6: Get dataset details
# ---------------------------------------------------------------------------

@mcp.tool(
    name="transport_get_dataset",
    annotations={
        "title": "Get Transport Dataset Details",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def transport_get_dataset(params: DatasetDetailInput) -> str:
    """Get full details of a specific transport dataset.

    Returns metadata, description, all available resources (files/APIs)
    with download URLs and formats.

    Use transport_search_datasets first to find the dataset ID.

    Returns:
        JSON with full dataset metadata, resources with URLs, and format info.
    """
    try:
        pkg = await api_client.ckan_request(
            "package_show",
            params={"id": params.dataset_id},
        )

        resources = []
        for r in pkg.get("resources", []):
            resources.append({
                "name": r.get("name") or r.get("description", ""),
                "format": r.get("format", ""),
                "url": r.get("url", ""),
                "size": r.get("size"),
                "last_modified": r.get("last_modified", ""),
            })

        dataset = {
            "id": pkg.get("name"),
            "title": pkg.get("title"),
            "description": pkg.get("notes", ""),
            "organization": pkg.get("organization", {}).get("title", ""),
            "license": pkg.get("license_title", ""),
            "tags": [t.get("name") for t in pkg.get("tags", [])],
            "last_modified": pkg.get("metadata_modified", ""),
            "url": f"https://data.opentransportdata.swiss/dataset/{pkg.get('name')}",
            "resources": resources,
        }

        return json.dumps(dataset, ensure_ascii=False, indent=2)

    except Exception as e:
        return api_client.handle_api_error(e)


# ===========================================================================
# EXTENSION TOOLS 7-10: SIRI-SX, Occupancy, Fare, Formation
# ===========================================================================

# ---------------------------------------------------------------------------
# Tool 7: Störungsmeldungen (SIRI-SX)
# ---------------------------------------------------------------------------

@mcp.tool()
async def get_transport_disruptions(
    filter_text: str = "",
    language: str = "DE",
    max_results: int = 15,
) -> str:
    """Aktuelle Störungsmeldungen im Schweizer öffentlichen Verkehr abrufen.

    Liefert Informationen zu Zugausfällen, Verspätungen, Gleisänderungen,
    Streckensperrungen und anderen Betriebsstörungen.

    Args:
        filter_text: Suchbegriff zum Filtern (z.B. "Zürich", "S-Bahn", "IC 1",
                     "Bern-Thun"). Leer = alle Störungen.
        language: Sprache der Meldungen. DE (Deutsch), FR (Französisch),
                  IT (Italienisch), EN (Englisch).
        max_results: Maximale Anzahl Ergebnisse (1-50). Standard: 15.

    Beispiele:
        - Alle aktuellen Störungen: get_transport_disruptions()
        - Störungen in Zürich: get_transport_disruptions(filter_text="Zürich")
        - S-Bahn Störungen: get_transport_disruptions(filter_text="S-Bahn")
        - Strecke prüfen: get_transport_disruptions(filter_text="Bern")
    """
    error = _check_api("SIRI-SX Störungsmeldungen", "SIRI_SX_API_KEY")
    if error:
        return error

    client = _get_ext_client()
    return await get_disruptions(
        client,
        filter_text=filter_text or None,
        language=language.upper(),
        max_results=min(max_results, 50),
    )


# ---------------------------------------------------------------------------
# Tool 8: Belegungsprognose
# ---------------------------------------------------------------------------

@mcp.tool()
async def get_train_occupancy(
    train_number: str = "",
    departure_station: str = "",
    arrival_station: str = "",
    operation_date: str = "",
    operator: str = "11",
) -> str:
    """Auslastungsprognose für Schweizer Züge abrufen.

    Zeigt, wie voll ein bestimmter Zug voraussichtlich sein wird,
    aufgeteilt nach 1. und 2. Klasse pro Streckenabschnitt.
    Auslastungsstufen: wenig belegt, mässig belegt, nur Stehplätze.

    Zwei Abfragemodi:
    1. Nach Zugnummer: train_number + operator angeben
    2. Nach Strecke: departure_station + arrival_station angeben

    Args:
        train_number: Zugnummer (z.B. "1009", "IC 708").
                      Zugtyp-Präfixe werden automatisch entfernt.
        departure_station: Abfahrtsort für Streckensuche (z.B. "Zürich HB")
        arrival_station: Ankunftsort für Streckensuche (z.B. "Bern")
        operation_date: Betriebstag YYYY-MM-DD (Standard: heute).
                        Prognosen sind bis 3 Monate voraus verfügbar.
        operator: Betreiber-Code. "11"=SBB, "33"=BLS, "65"=Thurbo, "82"=SOB.

    Beispiele:
        - Bestimmter Zug: get_train_occupancy(train_number="1009")
        - BLS-Zug: get_train_occupancy(train_number="2806", operator="33")
        - Strecke: get_train_occupancy(departure_station="Zürich HB", arrival_station="Bern")
    """
    error = _check_api("Belegungsprognose", "OCCUPANCY_API_KEY")
    if error:
        return error

    client = _get_ext_client()
    op_date = operation_date if operation_date else None

    # Modus 1: Nach Zugnummer
    if train_number:
        return await get_occupancy_forecast(
            client,
            train_number=train_number,
            operation_date=op_date,
            operator_ref=operator,
        )

    # Modus 2: Nach Strecke
    if departure_station and arrival_station:
        return await get_occupancy_for_route(
            client,
            departure_station=departure_station,
            arrival_station=arrival_station,
            operation_date=op_date,
        )

    return (
        "Bitte gib entweder eine Zugnummer (train_number) oder "
        "eine Strecke (departure_station + arrival_station) an."
    )


# ---------------------------------------------------------------------------
# Tool 9: OJP Fare Preisauskunft
# ---------------------------------------------------------------------------

@mcp.tool()
async def get_ticket_price(
    origin: str,
    destination: str,
    departure_time: str = "",
    travel_class: str = "second",
) -> str:
    """Ticketpreise für eine ÖV-Verbindung in der Schweiz abfragen.

    Berechnet den Fahrpreis für eine Verbindung inklusive Routeninformation.
    Zeigt reguläre Tarife an. Rabatte (Halbtax, GA) sind möglicherweise
    nicht vollständig berücksichtigt.

    Args:
        origin: Abfahrtsort (z.B. "Zürich HB", "Wädenswil", "Bern")
        destination: Ankunftsort (z.B. "Bern", "Luzern", "Basel SBB")
        departure_time: Abfahrtszeit im Format YYYY-MM-DDTHH:MM
                        (z.B. "2026-03-01T08:00"). Standard: jetzt.
        travel_class: Reiseklasse. "first" = 1. Klasse, "second" = 2. Klasse.

    Beispiele:
        - Einfache Preisabfrage: get_ticket_price(origin="Zürich HB", destination="Bern")
        - Mit Zeitangabe: get_ticket_price(origin="Wädenswil", destination="Luzern",
                                            departure_time="2026-03-01T08:00")
        - 1. Klasse: get_ticket_price(origin="Basel SBB", destination="Genf",
                                       travel_class="first")

    Hinweis: Für verbindliche Preise immer sbb.ch oder den Schalter konsultieren.
    """
    error = _check_api("OJP Fare Preisauskunft", "OJP_FARE_API_KEY")
    if error:
        return error

    client = _get_ext_client()
    dep_time = departure_time if departure_time else None

    return await get_fare_info(
        client,
        origin=origin,
        destination=destination,
        departure_time=dep_time,
        traveller_class=travel_class,
    )


# ---------------------------------------------------------------------------
# Tool 10: Zugformation
# ---------------------------------------------------------------------------

@mcp.tool()
async def get_train_composition(
    train_number: str,
    railway_company: str = "SBBP",
    operation_date: str = "",
    show_details: str = "stop_based",
) -> str:
    """Zugzusammensetzung und Wagenreihung für einen Schweizer Zug abrufen.

    Zeigt die Wagenreihung, Klassen, Sektoren, Ausstattung (Rollstuhlplatz,
    Velohaken, Speisewagen, Familienzone) und Gleisbelegung an.

    Args:
        train_number: Zugnummer (z.B. "2806", "1009", "708").
                      Nur die Nummer, ohne Zugtyp-Präfix.
        railway_company: Eisenbahnunternehmen (EVU). Erlaubt:
                         SBBP (SBB), BLSP (BLS), RhB (Rhätische Bahn),
                         SOB (Südostbahn), THURBO, TPF, TRN, MBC, OeBB, VDBB, ZB.
        operation_date: Betriebstag YYYY-MM-DD. Standard: heute.
                        Wichtig: Stop-based nur für HEUTE verfügbar.
        show_details: Detailgrad. "stop_based" = kompakt (empfohlen),
                      "vehicle_based" = pro Fahrzeug, "full" = alles.

    Beispiele:
        - SBB-Zug: get_train_composition(train_number="1009")
        - BLS-Zug: get_train_composition(train_number="2806", railway_company="BLSP")
        - Detailliert: get_train_composition(train_number="708", show_details="vehicle_based")

    Typische Fragen, die damit beantwortet werden können:
        - "Hat der IC nach Bern einen Speisewagen?"
        - "Wo kann ich mit dem Rollstuhl einsteigen?"
        - "In welchem Sektor hält die 1. Klasse?"
        - "Gibt es Veloplätze im Zug?"
    """
    error = _check_api("Train Formation Service", "FORMATION_API_KEY")
    if error:
        return error

    client = _get_ext_client()
    op_date = operation_date if operation_date else None

    return await get_train_formation(
        client,
        train_number=train_number,
        evu=railway_company.upper(),
        operation_date=op_date,
        detail_level=show_details,
    )


# ===========================================================================
# Bonus-Tool: Systemstatus aller APIs
# ===========================================================================

@mcp.tool()
async def check_transport_api_status() -> str:
    """Prüft den Verbindungsstatus aller konfigurierten Transport-APIs.

    Zeigt an, welche APIs verfügbar sind, ob die API-Keys gültig sind
    und ob die Dienste erreichbar sind.
    """
    lines = ["🔍 Status der Swiss Transport APIs:\n"]

    # Core APIs
    core_apis = [
        ("OJP 2.0 (Fahrplan)", "TRANSPORT_API_KEY"),
        ("CKAN (Datenkatalog)", "TRANSPORT_CKAN_API_KEY"),
    ]
    for name, env_var in core_apis:
        key = os.environ.get(env_var)
        if key:
            lines.append(f"  ✅ {name}: Konfiguriert (Key: ...{key[-4:]})")
        else:
            # Check unified key fallback
            unified = os.environ.get("TRANSPORT_API_KEY")
            if unified and env_var != "TRANSPORT_API_KEY":
                lines.append(f"  ✅ {name}: Via TRANSPORT_API_KEY (Fallback)")
            else:
                lines.append(f"  ❌ {name}: Nicht konfiguriert ({env_var} fehlt)")

    # Extension APIs
    ext_apis = [
        ("SIRI-SX Störungsmeldungen", "SIRI_SX_API_KEY"),
        ("Belegungsprognose", "OCCUPANCY_API_KEY"),
        ("Train Formation Service", "FORMATION_API_KEY"),
        ("OJP Fare Preisauskunft", "OJP_FARE_API_KEY"),
    ]

    configured = 0
    for name, env_var in ext_apis:
        key = os.environ.get(env_var)
        if key:
            lines.append(f"  ✅ {name}: Konfiguriert (Key: ...{key[-4:]})")
            configured += 1
        else:
            lines.append(f"  ❌ {name}: Nicht konfiguriert ({env_var} fehlt)")

    lines.append(f"\n📊 {configured}/{len(ext_apis)} Erweiterungs-APIs konfiguriert.")

    if configured < len(ext_apis):
        lines.append(
            "\n💡 API-Keys erstellen: https://api-manager.opentransportdata.swiss/"
        )

    # Formation Health Check (wenn konfiguriert)
    if os.environ.get("FORMATION_API_KEY"):
        try:
            client = _get_ext_client()
            health = await get_formation_health(client)
            lines.append(f"\n🏥 {health}")
        except Exception as e:
            lines.append(f"\n🏥 Formation Service Health Check fehlgeschlagen: {e}")

    return "\n".join(lines)


# ===========================================================================
# MCP Resources
# ===========================================================================

@mcp.resource("transport://datasets")
async def list_datasets() -> str:
    """List all available transport datasets in the catalog."""
    try:
        result = await api_client.ckan_request("package_list")
        return json.dumps({
            "total": len(result) if isinstance(result, list) else 0,
            "datasets": result,
            "catalog_url": "https://data.opentransportdata.swiss/dataset/",
        }, ensure_ascii=False, indent=2)
    except Exception as e:
        return api_client.handle_api_error(e)


@mcp.resource("transport://info")
async def server_info() -> str:
    """Information about this MCP server and available APIs."""
    return json.dumps({
        "name": "Swiss Transport MCP Server",
        "version": "0.2.0",
        "description": "Complete Swiss public transport data from opentransportdata.swiss",
        "apis": {
            "OJP 2.0": "Journey planning, stop search, departures (XML/SOAP)",
            "CKAN": "Dataset catalog with ~90 transport datasets (REST/JSON)",
            "SIRI-SX": "Real-time disruption alerts (XML) – requires SIRI_SX_API_KEY",
            "Occupancy": "Train occupancy forecasts (JSON) – requires OCCUPANCY_API_KEY",
            "OJP Fare": "Ticket price information (XML/OJP) – requires OJP_FARE_API_KEY",
            "Formation": "Train composition and wagon order (JSON) – requires FORMATION_API_KEY",
        },
        "tools": [
            "transport_search_stop – Find stops by name",
            "transport_nearby_stops – Find stops by coordinates",
            "transport_departures – Live departures at a stop",
            "transport_trip_plan – Plan a journey A→B",
            "transport_search_datasets – Search data catalog",
            "transport_get_dataset – Get dataset details",
            "get_transport_disruptions – Current disruptions (SIRI-SX)",
            "get_train_occupancy – Occupancy forecast for trains",
            "get_ticket_price – Ticket price information (OJP Fare)",
            "get_train_composition – Train formation and wagon order",
            "check_transport_api_status – Check API connection status",
        ],
        "api_key_info": "Get free keys at https://api-manager.opentransportdata.swiss/",
        "data_source": "https://opentransportdata.swiss/",
    }, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    """Run the MCP server.

    Transport mode is controlled by environment variables:
    - MCP_TRANSPORT=sse  → HTTP/SSE for cloud deployment (Render, Railway)
    - MCP_TRANSPORT=stdio (default) → local subprocess for Claude Desktop

    Eselsbrücke: "Stdio für den Laptop, SSE für den Browser."
    """
    transport = os.environ.get("MCP_TRANSPORT", "stdio").lower()

    if transport == "sse":
        host = os.environ.get("MCP_HOST", "0.0.0.0")
        port = int(os.environ.get("MCP_PORT", os.environ.get("PORT", "8000")))
        logger.info(f"Starting SSE server on {host}:{port}")
        mcp.run(transport="sse", host=host, port=port)
    else:
        mcp.run()


if __name__ == "__main__":
    main()
