"""Typed tool-return tests (SDK-002).

The six core OJP/CKAN tools now return Pydantic models (declared output
schema + structured content) instead of json.dumps strings. These tests call
the tool functions directly with respx-mocked HTTP and assert the model type,
the parsed payload, and that error/not-found paths surface via `message`.

Tools requiring a Context (departures, trip_plan) are exercised at the schema
level in test_tool_schema and via their model in unit tests; here we cover the
four context-free tools end to end.
"""

import asyncio

import httpx
import respx

from swiss_transport_mcp import server
from swiss_transport_mcp.api_client import CKAN_API_URL, OJP_V2_URL
from swiss_transport_mcp.ojp_client import OJP, SIRI
from swiss_transport_mcp.server import (
    DatasetDetailInput,
    DatasetDetailResult,
    DatasetSearchInput,
    DatasetSearchResult,
    NearbyStopsResult,
    SearchStopByCoordInput,
    SearchStopInput,
    StopSearchResult,
    transport_get_dataset,
    transport_nearby_stops,
    transport_search_datasets,
    transport_search_stop,
)


def _location_xml() -> str:
    return f"""<OJP xmlns="{OJP}" xmlns:siri="{SIRI}"><OJPResponse><ServiceDelivery>
      <OJPLocationInformationDelivery><PlaceResult><Place><StopPlace>
      <StopPlaceRef>8503000</StopPlaceRef>
      <StopPlaceName><Text>Zürich HB</Text></StopPlaceName></StopPlace>
      <GeoPosition><siri:Longitude>8.5417</siri:Longitude><siri:Latitude>47.3769</siri:Latitude></GeoPosition>
      <Mode><PtMode>rail</PtMode></Mode></Place></PlaceResult>
      </OJPLocationInformationDelivery></ServiceDelivery></OJPResponse></OJP>"""


@respx.mock
async def test_search_stop_returns_typed_result(monkeypatch):
    monkeypatch.setenv("TRANSPORT_API_KEY", "k")
    respx.post(OJP_V2_URL).mock(return_value=httpx.Response(200, text=_location_xml()))
    result = await transport_search_stop(SearchStopInput(query="Zürich HB"))
    assert isinstance(result, StopSearchResult)
    assert result.query == "Zürich HB"
    assert result.count == 1
    assert result.stops[0]["stop_id"] == "8503000"
    assert result.message is None


@respx.mock
async def test_search_stop_not_found_sets_message(monkeypatch):
    monkeypatch.setenv("TRANSPORT_API_KEY", "k")
    empty = f'<OJP xmlns="{OJP}" xmlns:siri="{SIRI}"></OJP>'
    respx.post(OJP_V2_URL).mock(return_value=httpx.Response(200, text=empty))
    result = await transport_search_stop(SearchStopInput(query="Nirgendwo"))
    assert isinstance(result, StopSearchResult)
    assert result.count == 0
    assert result.stops == []
    assert "No stops found" in result.message


async def test_search_stop_error_path_sets_message(monkeypatch):
    # No API key → ojp_request raises ValueError → handled in-band via message.
    monkeypatch.delenv("TRANSPORT_API_KEY", raising=False)
    monkeypatch.delenv("TRANSPORT_OJP_API_KEY", raising=False)
    result = await transport_search_stop(SearchStopInput(query="Bern"))
    assert isinstance(result, StopSearchResult)
    assert result.count == 0
    assert result.message  # carries the handled error text


@respx.mock
async def test_nearby_stops_typed_and_deduplicated(monkeypatch):
    monkeypatch.setenv("TRANSPORT_API_KEY", "k")
    respx.post(OJP_V2_URL).mock(return_value=httpx.Response(200, text=_location_xml()))
    result = await transport_nearby_stops(
        SearchStopByCoordInput(latitude=47.3769, longitude=8.5417)
    )
    assert isinstance(result, NearbyStopsResult)
    assert result.latitude == 47.3769
    assert result.count == 1


@respx.mock
async def test_search_datasets_typed(monkeypatch):
    monkeypatch.setenv("TRANSPORT_API_KEY", "k")
    payload = {
        "success": True,
        "result": {
            "count": 1,
            "results": [
                {
                    "name": "gtfs",
                    "title": "GTFS Feed",
                    "notes": "desc",
                    "organization": {"title": "SBB"},
                    "resources": [{"format": "zip"}],
                    "metadata_modified": "2026-01-01",
                }
            ],
        },
    }
    respx.get(f"{CKAN_API_URL}/package_search").mock(
        return_value=httpx.Response(200, json=payload)
    )
    result = await transport_search_datasets(DatasetSearchInput(query="gtfs"))
    assert isinstance(result, DatasetSearchResult)
    assert result.total_found == 1
    assert result.datasets[0]["id"] == "gtfs"
    assert "ZIP" in result.datasets[0]["formats"]


@respx.mock
async def test_get_dataset_typed(monkeypatch):
    monkeypatch.setenv("TRANSPORT_API_KEY", "k")
    payload = {
        "success": True,
        "result": {
            "name": "ojp2-0",
            "title": "OJP 2.0",
            "notes": "Journey planner",
            "organization": {"title": "ÖV Schweiz"},
            "license_title": "CC BY 4.0",
            "tags": [{"name": "ojp"}, {"name": "realtime"}],
            "metadata_modified": "2026-02-02",
            "resources": [{"name": "API", "format": "XML", "url": "https://x", "size": None}],
        },
    }
    respx.get(f"{CKAN_API_URL}/package_show").mock(
        return_value=httpx.Response(200, json=payload)
    )
    result = await transport_get_dataset(DatasetDetailInput(dataset_id="ojp2-0"))
    assert isinstance(result, DatasetDetailResult)
    assert result.id == "ojp2-0"
    assert result.license == "CC BY 4.0"
    assert result.tags == ["ojp", "realtime"]
    assert result.resources[0]["format"] == "XML"


# Expected top-level field per core tool — proves the schema describes the
# real structured payload, not the trivial {"result": string} wrapper MCPServer
# generates for plain `-> str` tools.
_CORE_TOOL_FIELDS = {
    "transport_search_stop": "stops",
    "transport_nearby_stops": "nearby_stops",
    "transport_departures": "departures",
    "transport_trip_plan": "trips",
    "transport_search_datasets": "datasets",
    "transport_get_dataset": "resources",
}


def test_core_tools_have_structured_output_schema():
    by_name = {t.name: t for t in asyncio.run(server.mcp.list_tools())}
    for name, field in _CORE_TOOL_FIELDS.items():
        schema = by_name[name].output_schema
        assert schema is not None, name
        props = schema.get("properties", {})
        # Typed model fields are present; not the {"result": string} wrapper.
        assert field in props, f"{name} missing '{field}' in output schema"
        assert "message" in props, f"{name} missing 'message' in output schema"
        assert list(props) != ["result"], f"{name} still a string wrapper"


def test_extension_tools_stay_string_wrapper():
    # Human-readable tools intentionally keep string returns → MCPServer emits the
    # trivial {"result": string} output schema, not a structured one.
    by_name = {t.name: t for t in asyncio.run(server.mcp.list_tools())}
    schema = by_name["get_train_composition"].output_schema
    assert schema is not None
    assert list(schema.get("properties", {})) == ["result"]
    assert schema["properties"]["result"]["type"] == "string"
