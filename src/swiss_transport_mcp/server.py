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
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass
from typing import Any

import anyio
import httpx
from mcp.server.mcpserver import Context, MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from pydantic import BaseModel, ConfigDict, Field
from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware

from . import __version__, api_client, ojp_client
from .api_infrastructure import TransportAPIClient, create_transport_client
from .formation import get_formation_health, get_train_formation
from .logging_config import configure_logging
from .net_security import resolve_ssl_verify
from .occupancy import get_occupancy_for_route, get_occupancy_forecast
from .ojp_fare import get_fare_info
from .siri_sx import get_disruptions
from .tool_integrity import check_tools_against_manifest
from .tracing import configure_tracing

logger = logging.getLogger("swiss-transport-mcp")

# ---------------------------------------------------------------------------
# Server initialization
# ---------------------------------------------------------------------------

# ===========================================================================
# Extension API Client + server lifespan (SDK-001)
# ===========================================================================

_ext_client: TransportAPIClient | None = None


def _build_ext_client() -> TransportAPIClient:
    """Build the extension-API client from the configured keys.

    Missing keys simply leave that API unregistered – the tools return a clean
    "not configured" message instead of crashing.
    """
    return create_transport_client(
        siri_sx_key=os.environ.get("SIRI_SX_API_KEY"),
        occupancy_key=os.environ.get("OCCUPANCY_API_KEY"),
        formation_key=os.environ.get("FORMATION_API_KEY"),
        ojp_fare_key=os.environ.get("OJP_FARE_API_KEY"),
    )


def _get_ext_client() -> TransportAPIClient:
    """Return the lifespan-managed extension client.

    Falls back to a lazily-built singleton if the lifespan has not run (e.g. a
    tool invoked directly in a unit test). The lifespan owns teardown.
    """
    global _ext_client
    if _ext_client is None:
        _ext_client = _build_ext_client()
    return _ext_client


@dataclass
class AppContext:
    """Shared resources made available to tools via the request context."""

    ext_client: TransportAPIClient


@asynccontextmanager
async def app_lifespan(server: MCPServer) -> AsyncIterator[AppContext]:
    """Create and tear down shared resources for the server's lifetime.

    Closes the gap from audit finding SDK-001: previously the extension
    client's httpx session was never closed and every OJP/CKAN call opened a
    throwaway client. Now an ``AsyncExitStack`` owns:

    - a pooled httpx client for the OJP/CKAN path (installed via
      ``api_client.set_shared_client``), and
    - the extension ``TransportAPIClient``,

    and both are closed deterministically on shutdown.
    """
    global _ext_client
    async with AsyncExitStack() as stack:
        # Pooled client for the OJP/CKAN module functions.
        http_client = httpx.AsyncClient(
            verify=resolve_ssl_verify(),
            headers={"User-Agent": f"swiss-transport-mcp/{__version__}"},
        )
        stack.push_async_callback(http_client.aclose)
        api_client.set_shared_client(http_client)
        stack.callback(api_client.clear_shared_client)

        # Extension API client (disruptions / occupancy / fare / formation).
        _ext_client = _build_ext_client()
        stack.push_async_callback(_ext_client.close)
        stack.callback(lambda: globals().__setitem__("_ext_client", None))

        # SEC-022: verify the live tool surface against the pinned manifest.
        check_tools_against_manifest(await server.list_tools())

        logger.info("Server lifespan started: shared HTTP clients ready")
        yield AppContext(ext_client=_ext_client)
        logger.info("Server lifespan shutting down: closing shared HTTP clients")


mcp = MCPServer(
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
    lifespan=app_lifespan,
)


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
# Tool output models (SDK-002)
# ===========================================================================
# The core OJP/CKAN tools return typed Pydantic models instead of hand-built
# json.dumps strings, so the MCP client gets a declared output schema and
# structured content. Each model carries an optional `message` that holds the
# in-band "not found" / error text (preserving the OBS-001 protocol-vs-execution
# error separation). Deeply nested, variable upstream shapes (stops, trip legs,
# resources) stay as `list[dict]` rather than being over-modelled.


class StopSearchResult(BaseModel):
    """Result of transport_search_stop."""

    query: str | None = None
    count: int = 0
    stops: list[dict[str, Any]] = []
    hint: str | None = None
    message: str | None = None


class NearbyStopsResult(BaseModel):
    """Result of transport_nearby_stops."""

    latitude: float | None = None
    longitude: float | None = None
    count: int = 0
    nearby_stops: list[dict[str, Any]] = []
    hint: str | None = None
    message: str | None = None


class DeparturesResult(BaseModel):
    """Result of transport_departures."""

    stop_id: str | None = None
    stop_name: str | None = None
    type: str | None = None
    count: int = 0
    departures: list[dict[str, Any]] = []
    hint: str | None = None
    message: str | None = None


class TripPlanResult(BaseModel):
    """Result of transport_trip_plan."""

    origin: str | None = None
    destination: str | None = None
    count: int = 0
    trips: list[dict[str, Any]] = []
    hint: str | None = None
    message: str | None = None


class DatasetSearchResult(BaseModel):
    """Result of transport_search_datasets."""

    query: str | None = None
    total_found: int = 0
    showing: int = 0
    datasets: list[dict[str, Any]] = []
    hint: str | None = None
    message: str | None = None


class DatasetDetailResult(BaseModel):
    """Result of transport_get_dataset."""

    id: str | None = None
    title: str | None = None
    description: str | None = None
    organization: str | None = None
    license: str | None = None
    tags: list[str] = []
    last_modified: str | None = None
    url: str | None = None
    resources: list[dict[str, Any]] = []
    message: str | None = None


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
async def transport_search_stop(params: SearchStopInput) -> StopSearchResult:
    """Search for Swiss public transport stops and stations by name.

    Searches across all Swiss public transport stops (train stations,
    tram/bus stops, boat stations). Returns stop IDs needed for
    transport_departures and transport_trip_plan.

    Returns:
        Matching stops with id, name, coordinates, and transport modes.
    """
    try:
        xml_request = ojp_client.build_location_request(
            query=params.query,
            limit=params.limit,
        )
        xml_response = await api_client.ojp_request(xml_request)

        error = ojp_client.parse_error_response(xml_response)
        if error:
            return StopSearchResult(query=params.query, message=f"OJP Error: {error}")

        locations = ojp_client.parse_location_response(xml_response)

        if not locations:
            return StopSearchResult(
                query=params.query,
                message=f"No stops found for '{params.query}'. Try a broader search term.",
            )

        return StopSearchResult(
            query=params.query,
            count=len(locations),
            stops=locations,
            hint="Use the 'stop_id' value with transport_departures or transport_trip_plan.",
        )

    except Exception as e:
        return StopSearchResult(query=params.query, message=api_client.handle_api_error(e))


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
async def transport_nearby_stops(params: SearchStopByCoordInput) -> NearbyStopsResult:
    """Find public transport stops near a geographic location.

    Useful for finding stops near a school, address, or point of interest.
    Swiss coordinates only (lat 45–48.5, lon 5.5–10.8).

    Returns:
        Nearby stops with id, name, coordinates, and distance info.
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
            return NearbyStopsResult(
                latitude=params.latitude,
                longitude=params.longitude,
                message=f"OJP Error: {error}",
            )

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
            return NearbyStopsResult(
                latitude=params.latitude,
                longitude=params.longitude,
                message="No stops found near these coordinates.",
            )

        return NearbyStopsResult(
            latitude=params.latitude,
            longitude=params.longitude,
            count=len(unique_locations),
            nearby_stops=unique_locations,
            hint="Use 'stop_id' with transport_departures or transport_trip_plan.",
        )

    except Exception as e:
        return NearbyStopsResult(
            latitude=params.latitude,
            longitude=params.longitude,
            message=api_client.handle_api_error(e),
        )


# ---------------------------------------------------------------------------
# Resolving a name to a stop id
# ---------------------------------------------------------------------------


class PlaceNotResolved(ValueError):
    """A place name that no stop could be found for.

    A ``ValueError`` on purpose: ``handle_api_error`` passes those through with
    their own text, so the caller reads "No stop found for 'Zueri HB'" and not
    a masked generic message. The distinction matters -- "I could not find that
    place" and "there is no connection" are different answers.
    """


async def _resolve_place(ref: str) -> tuple[str, str]:
    """Turn a stop id *or* a place name into ``(stop_id, display_name)``.

    OJP 2.0 has no name-only place reference: a ``PlaceRef`` must carry one of
    six real reference elements (``PlaceRefGroup``), and free text is not among
    them. The previous code sent ``<LocationName>`` -- the OJP 1.0 spelling,
    dropped in 2.0 -- so every request built from a name asked for nothing and
    the tool reported "no trips found". A failure that looks like an answer.

    The tools document that names work, so the fix is to make that true rather
    than withdraw it: resolve the name the way the caller would have to, with
    one location lookup, and take the best match. When nothing matches, say so
    with the name in it -- an empty trip list reads as "there is no connection"
    rather than "I could not find that place".

    What counts as an id is `ojp_client.is_stop_ref`, not a local rule: station
    ids (``8503000``) and quay ids (``8503000:0:31``) both come back from
    `transport_search_stop`, and a second copy of the test here would drift into
    looking up a place named "8503000:0:31".
    """
    if ojp_client.is_stop_ref(ref):
        return ref, ref

    xml_response = await api_client.ojp_request(ojp_client.build_location_request(ref, limit=1))
    error = ojp_client.parse_error_response(xml_response)
    if error:
        raise PlaceNotResolved(f"Could not look up '{ref}': {error}")

    locations = ojp_client.parse_location_response(xml_response)
    if not locations or not locations[0].get("stop_id"):
        raise PlaceNotResolved(
            f"No stop found for '{ref}'. Use transport_search_stop to find the exact name."
        )
    return locations[0]["stop_id"], locations[0].get("name") or ref


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
async def transport_departures(params: DeparturesInput, ctx: Context) -> DeparturesResult:
    """Get upcoming departures or arrivals at a Swiss public transport stop.

    Shows real-time information including delays when available.
    Like a digital departure board at a train station.

    Use transport_search_stop first to get the stop_id.

    Returns:
        Departures with line, destination, scheduled time, real-time time,
        delay, and platform.
    """
    try:
        await ctx.info(f"Fetching {params.event_type}s for stop {params.stop_id}")
        stop_id, resolved_name = await _resolve_place(params.stop_id)
        xml_request = ojp_client.build_stop_event_request(
            stop_ref=stop_id,
            stop_name=params.stop_name or resolved_name,
            dep_arr_time=params.time,
            limit=params.limit,
            event_type=params.event_type,
        )
        xml_response = await api_client.ojp_request(xml_request)

        error = ojp_client.parse_error_response(xml_response)
        if error:
            return DeparturesResult(
                stop_id=params.stop_id,
                stop_name=params.stop_name or params.stop_id,
                type=params.event_type,
                message=f"OJP Error: {error}",
            )

        events = ojp_client.parse_stop_event_response(xml_response)

        if not events:
            return DeparturesResult(
                stop_id=params.stop_id,
                stop_name=params.stop_name or params.stop_id,
                type=params.event_type,
                message=f"No {params.event_type}s found for stop {params.stop_id}.",
            )

        return DeparturesResult(
            stop_id=params.stop_id,
            stop_name=params.stop_name or params.stop_id,
            type=params.event_type,
            count=len(events),
            departures=events,
        )

    except Exception as e:
        return DeparturesResult(
            stop_id=params.stop_id,
            stop_name=params.stop_name or params.stop_id,
            type=params.event_type,
            message=api_client.handle_api_error(e),
        )


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
async def transport_trip_plan(params: TripPlanInput, ctx: Context) -> TripPlanResult:
    """Plan a journey between two locations in Switzerland.

    Works like the SBB app: enter origin and destination (stop IDs or
    place names), get multiple trip options with transfers, durations,
    and transport modes.

    For best results, use stop IDs from transport_search_stop.
    Place names (addresses) also work but may be slower.

    Returns:
        Trip options, each with legs (individual journey segments),
        total duration, number of transfers, and transport modes used.
    """
    try:
        await ctx.info(f"Planning trip {params.origin} → {params.destination}")
        origin_id, origin_name = await _resolve_place(params.origin)
        destination_id, destination_name = await _resolve_place(params.destination)
        xml_request = ojp_client.build_trip_request(
            origin_ref=origin_id,
            destination_ref=destination_id,
            origin_name=origin_name,
            destination_name=destination_name,
            dep_time=params.time,
            limit=params.limit,
        )
        xml_response = await api_client.ojp_request(xml_request)

        error = ojp_client.parse_error_response(xml_response)
        if error:
            return TripPlanResult(
                origin=params.origin,
                destination=params.destination,
                message=f"OJP Error: {error}",
            )

        trips = ojp_client.parse_trip_response(xml_response)

        if not trips:
            return TripPlanResult(
                origin=params.origin,
                destination=params.destination,
                message=(
                    f"No trips found from '{params.origin}' to '{params.destination}'. "
                    "Try using stop IDs instead of names."
                ),
            )

        return TripPlanResult(
            origin=params.origin,
            destination=params.destination,
            count=len(trips),
            trips=trips,
            hint="Each trip contains legs: 'timed' = public transport, 'walk' = walking, 'transfer' = platform change.",
        )

    except Exception as e:
        return TripPlanResult(
            origin=params.origin,
            destination=params.destination,
            message=api_client.handle_api_error(e),
        )


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
async def transport_search_datasets(params: DatasetSearchInput) -> DatasetSearchResult:
    """Search the Swiss transport open data catalog (~90 datasets).

    Find datasets about timetables, real-time data, GTFS feeds,
    accessibility info, traffic counters, and more from
    opentransportdata.swiss.

    Returns:
        Matching datasets with name, description, formats, and download URLs.
    """
    try:
        result = await api_client.ckan_request(
            "package_search",
            params={"q": params.query, "rows": params.limit},
        )

        datasets = []
        for pkg in api_client.ckan_results(result):
            ds: dict[str, Any] = {
                "id": pkg.get("name"),
                "title": pkg.get("title"),
                "description": (pkg.get("notes", "") or "")[:300],
                "organization": pkg.get("organization", {}).get("title", ""),
                "formats": list(
                    {
                        r.get("format", "").upper()
                        for r in pkg.get("resources", [])
                        if r.get("format")
                    }
                ),
                "last_modified": pkg.get("metadata_modified", ""),
                "url": f"https://data.opentransportdata.swiss/dataset/{pkg.get('name')}",
            }
            datasets.append(ds)

        return DatasetSearchResult(
            query=params.query,
            total_found=result.get("count", 0),
            showing=len(datasets),
            datasets=datasets,
            hint="Use 'id' with transport_get_dataset for full details and download links.",
        )

    except Exception as e:
        return DatasetSearchResult(query=params.query, message=api_client.handle_api_error(e))


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
async def transport_get_dataset(params: DatasetDetailInput) -> DatasetDetailResult:
    """Get full details of a specific transport dataset.

    Returns metadata, description, all available resources (files/APIs)
    with download URLs and formats.

    Use transport_search_datasets first to find the dataset ID.

    Returns:
        Full dataset metadata, resources with URLs, and format info.
    """
    try:
        pkg = await api_client.ckan_request(
            "package_show",
            params={"id": params.dataset_id},
        )

        resources = []
        for r in pkg.get("resources", []):
            resources.append(
                {
                    "name": r.get("name") or r.get("description", ""),
                    "format": r.get("format", ""),
                    "url": r.get("url", ""),
                    "size": r.get("size"),
                    "last_modified": r.get("last_modified", ""),
                }
            )

        return DatasetDetailResult(
            id=pkg.get("name"),
            title=pkg.get("title"),
            description=pkg.get("notes", ""),
            organization=pkg.get("organization", {}).get("title", ""),
            license=pkg.get("license_title", ""),
            tags=[t.get("name") for t in pkg.get("tags", [])],
            last_modified=pkg.get("metadata_modified", ""),
            url=f"https://data.opentransportdata.swiss/dataset/{pkg.get('name')}",
            resources=resources,
        )

    except Exception as e:
        return DatasetDetailResult(message=api_client.handle_api_error(e))


# ===========================================================================
# EXTENSION TOOLS 7-10: SIRI-SX, Occupancy, Fare, Formation
# ===========================================================================

# ---------------------------------------------------------------------------
# Tool 7: Störungsmeldungen (SIRI-SX)
# ---------------------------------------------------------------------------


@mcp.tool(
    annotations={
        "title": "Current Disruptions (SIRI-SX)",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": False,  # live disruption feed changes over time
        "openWorldHint": True,
    },
)
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


@mcp.tool(
    annotations={
        "title": "Train Occupancy Forecast",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": False,  # forecast updates over time
        "openWorldHint": True,
    },
)
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


@mcp.tool(
    annotations={
        "title": "Ticket Price (OJP Fare)",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,  # fares are stable intra-day
        "openWorldHint": True,
    },
)
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


@mcp.tool(
    annotations={
        "title": "Train Formation",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,  # composition stable for a given train/day
        "openWorldHint": True,
    },
)
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


@mcp.tool(
    annotations={
        "title": "API Status Check",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": False,  # reflects live connectivity
        "openWorldHint": True,
    },
)
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
        lines.append("\n💡 API-Keys erstellen: https://api-manager.opentransportdata.swiss/")

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
        return json.dumps(
            {
                "total": len(result) if isinstance(result, list) else 0,
                "datasets": result,
                "catalog_url": "https://data.opentransportdata.swiss/dataset/",
            },
            ensure_ascii=False,
            indent=2,
        )
    except Exception as e:
        return api_client.handle_api_error(e)


@mcp.resource("transport://info")
async def server_info() -> str:
    """Information about this MCP server and available APIs."""
    return json.dumps(
        {
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
        },
        ensure_ascii=False,
        indent=2,
    )


# ===========================================================================
# MCP Prompts (ARCH-008: use all three primitives – tools, resources, prompts)
# ===========================================================================


@mcp.prompt(title="Plan a school / group trip")
def plan_group_trip(
    origin: str,
    destination: str,
    group_size: str = "20",
    arrival_time: str = "",
) -> str:
    """Guided prompt for planning a Swiss public-transport group outing.

    Produces an instruction that steers the model through the right tools:
    resolve stops, check disruptions, plan the journey, and consider occupancy.
    """
    when = f" arriving by {arrival_time}" if arrival_time else ""
    return (
        f"Plan a public-transport trip for a group of {group_size} from "
        f"'{origin}' to '{destination}'{when} in Switzerland.\n\n"
        "Please:\n"
        "1. Use transport_search_stop to resolve both locations to stop IDs.\n"
        "2. Use transport_trip_plan for the best connection (mind transfers for a group).\n"
        "3. Use get_transport_disruptions to check for disruptions on the route.\n"
        "4. Optionally use get_train_occupancy to gauge how full the trains will be.\n"
        "Summarise the recommended departure, duration, transfers, and any warnings."
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

# Transport aliases → canonical MCPServer transport names.
_TRANSPORT_ALIASES = {
    "http": "streamable-http",
    "streamable_http": "streamable-http",
    "streamablehttp": "streamable-http",
}
# Transports that bind a network listener (need host/port).
_NETWORK_TRANSPORTS = frozenset({"streamable-http", "sse"})
# Endpoint paths, used for the startup log line. mcp 2.x removed sse_path and
# streamable_http_path from MCPServer.settings; they are per-app kwargs whose
# defaults these mirror. This server does not override them, so the log line
# stays accurate — a test pins the pair against the SDK defaults.
_SSE_PATH = "/sse"
_STREAMABLE_HTTP_PATH = "/mcp"


def _resolve_transport(env: dict[str, str] | None = None) -> str:
    """Resolve the canonical transport name from MCP_TRANSPORT.

    Defaults to ``stdio``. Accepts ``http``/``streamable_http`` as aliases for
    ``streamable-http`` (the recommended cloud transport). ``sse`` is still
    accepted but deprecated.
    """
    env = os.environ if env is None else env
    raw = env.get("MCP_TRANSPORT", "stdio").strip().lower()
    return _TRANSPORT_ALIASES.get(raw, raw)


def _resolve_http_bind(env: dict[str, str] | None = None) -> tuple[str, int]:
    """Resolve (host, port) for a network transport from environment.

    Default host is 127.0.0.1: a locally started server must NOT bind to all
    interfaces automatically (NeighborJack protection on public Wi-Fi). For
    container/cloud deployment set MCP_HOST=0.0.0.0 explicitly – there binding
    to all interfaces is intended.
    """
    env = os.environ if env is None else env
    host = env.get("MCP_HOST", "127.0.0.1")
    port = int(env.get("MCP_PORT", env.get("PORT", "8000")))
    return host, port


def _resolve_stateless(env: dict[str, str] | None = None) -> bool:
    """Whether to run Streamable HTTP statelessly (SCALE-002/003).

    Enabled with ``MCP_STATELESS=1``. Stateless mode keeps no per-session state
    server-side, so a load balancer can route any request to any instance
    without sticky sessions / ``Mcp-Session-Id`` affinity.
    """
    env = os.environ if env is None else env
    return env.get("MCP_STATELESS", "").strip().lower() in ("1", "true", "yes", "on")


def _resolve_cors_origins(env: dict[str, str] | None = None) -> list[str]:
    """Resolve the allowed CORS origins for browser clients (SDK-004).

    Defaults to ``https://claude.ai``. Override with ``MCP_CORS_ORIGINS`` as a
    comma-separated list, or ``*`` to allow any origin (logged as a warning).
    """
    env = os.environ if env is None else env
    raw = env.get("MCP_CORS_ORIGINS", "https://claude.ai").strip()
    origins = [o.strip() for o in raw.split(",") if o.strip()]
    return origins or ["https://claude.ai"]


def _resolve_allowed_hosts(env: dict[str, str] | None = None) -> list[str]:
    """Resolve the inbound Host allow-list (SEC-005).

    ``MCP_ALLOWED_HOSTS`` is a comma-separated list of the names this server is
    reachable under, port included where it matters, e.g.
    ``fahrplan.example.ch:8080``. Empty by default.
    """
    env = os.environ if env is None else env
    raw = env.get("MCP_ALLOWED_HOSTS", "").strip()
    return [h.strip() for h in raw.split(",") if h.strip()]


def _build_transport_security(
    host: str, port: int, origins: list[str], env: dict[str, str] | None = None
) -> TransportSecuritySettings | None:
    """Host/Origin allow-list for the network transports (SEC-005).

    Guards against DNS rebinding: a page on the operator's network resolves its
    own name to this server's address and talks to it from the browser. The
    check asks under *which name* the server was addressed, which no CORS rule
    and no token can answer — the attacking page is a legitimate browser
    context.

    Three cases, in the order decided:

    - ``MCP_ALLOWED_HOSTS`` set — that list, compared verbatim (so an entry
      carries its port), plus loopback so container health checks keep working.
    - loopback bind, no list — loopback only. This is what the SDK infers from a
      loopback ``host`` anyway; stating it makes the protection independent of
      that inference.
    - non-loopback bind, no list — ``None``: unchanged behaviour, the check
      stays off and the caller warns.

    The last case is deliberately not a guess. On ``0.0.0.0`` the reachable name
    is unknowable in-process, and a wrong guess is exactly the HTTP 421 this
    server's ``host`` kwarg exists to avoid.
    """
    allowed = _resolve_allowed_hosts(env)
    loopback = {f"127.0.0.1:{port}", f"localhost:{port}", f"[::1]:{port}"}
    if allowed:
        hosts = set(allowed) | loopback
    elif host in ("127.0.0.1", "localhost", "::1"):
        hosts = loopback | {f"{host}:{port}"}
    else:
        return None

    # Configured CORS origins must pass the transport check too, otherwise the
    # server rejects precisely the browser clients CORS was opened for —
    # claude.ai by default here. ``*`` is not expressible: origins are compared
    # literally, so copying it across would add an entry that permits nothing.
    allowed_origins = {o for o in origins if o != "*"}
    allowed_origins |= {f"http://{h}" for h in hosts}
    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=sorted(hosts),
        allowed_origins=sorted(allowed_origins),
    )


def _build_http_app(
    transport: str,
    origins: list[str],
    host: str = "127.0.0.1",
    stateless: bool = False,
    port: int = 8080,
) -> Starlette:
    """Build the Starlette app for a network transport with CORS applied.

    Exposing the ``Mcp-Session-Id`` response header is required so browser
    clients (claude.ai) can read it for session continuity (SDK-004). The
    MCPServer-configured lifespan (pooled clients, SDK-001) is preserved because
    it is baked into the app returned here.

    ``host``, ``stateless`` and ``transport_security`` are per-app kwargs in mcp
    2.x — in 1.x they were mutable settings. ``host`` must be the address
    uvicorn actually binds: 2.x auto-enables a loopback-only DNS-rebinding
    allow-list when ``host`` looks like localhost, so leaving it at the default
    while binding 0.0.0.0 would reject every real request with HTTP 421.

    The allow-list is passed explicitly rather than left to that inference —
    see :func:`_build_transport_security`.
    """
    security = _build_transport_security(host, port, origins)
    if security is None:
        logger.warning(
            "Binding %s without MCP_ALLOWED_HOSTS: Host/Origin validation is "
            "off and left to whatever fronts this server. Set MCP_ALLOWED_HOSTS "
            "to the names it is reachable under (e.g. 'fahrplan.example.ch:%d') "
            "to enforce it here as well (SEC-005).",
            host,
            port,
        )
    if transport == "sse":
        app = mcp.sse_app(host=host, transport_security=security)
    else:
        app = mcp.streamable_http_app(
            host=host, stateless_http=stateless, transport_security=security
        )
    if "*" in origins:
        logger.warning("MCP_CORS_ORIGINS=* allows ANY origin – avoid in production.")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["Mcp-Session-Id"],
    )
    return app


async def _serve_http(
    transport: str, host: str, port: int, origins: list[str], stateless: bool = False
) -> None:
    """Serve a network transport via uvicorn with the CORS-wrapped app."""
    import uvicorn

    app = _build_http_app(transport, origins, host=host, stateless=stateless, port=port)
    config = uvicorn.Config(app, host=host, port=port, log_level=mcp.settings.log_level.lower())
    await uvicorn.Server(config).serve()


def main():
    """Run the MCP server.

    Transport mode is controlled by environment variables:
    - MCP_TRANSPORT=streamable-http (or "http") → recommended cloud transport
    - MCP_TRANSPORT=sse → legacy HTTP/SSE (deprecated)
    - MCP_TRANSPORT=stdio (default) → local subprocess for Claude Desktop

    Eselsbrücke: "Stdio für den Laptop, Streamable HTTP für die Cloud."
    """
    # Logging strikt auf stderr (OBS-004); LOG_FORMAT=json → structured (OBS-003).
    configure_logging()
    # Optional OpenTelemetry tracing (OBS-006) – no-op unless OTEL_TRACES_ENABLED.
    configure_tracing()

    transport = _resolve_transport()

    if transport in _NETWORK_TRANSPORTS:
        host, port = _resolve_http_bind()
        origins = _resolve_cors_origins()
        stateless = False
        if transport == "sse":
            logger.warning("MCP_TRANSPORT=sse is deprecated; use 'streamable-http' (or 'http').")
            path = _SSE_PATH
        else:
            path = _STREAMABLE_HTTP_PATH
            # SCALE-002/003: stateless mode removes server-side session state,
            # so instances need no sticky load balancing / session-affinity
            # routing — any instance can serve any request. mcp 2.x takes it as
            # an app kwarg, so it travels down to _build_http_app instead of
            # being written onto mcp.settings first.
            stateless = _resolve_stateless()
            if stateless:
                logger.info(
                    "Streamable HTTP in STATELESS mode: no sticky LB / "
                    "Mcp-Session-Id edge routing required for horizontal scale-out."
                )
        logger.info(
            f"Starting {transport} server on http://{host}:{port}{path} (CORS origins: {origins})"
        )
        anyio.run(lambda: _serve_http(transport, host, port, origins, stateless))
    elif transport == "stdio":
        mcp.run()
    else:
        logger.error(
            "Unknown MCP_TRANSPORT=%r; falling back to stdio. "
            "Valid values: stdio, streamable-http (http), sse.",
            transport,
        )
        mcp.run()


if __name__ == "__main__":
    main()
