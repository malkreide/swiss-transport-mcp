"""Live integration tests against the real opentransportdata.swiss APIs.

These are marked `live` and therefore SKIPPED in CI (which runs
`pytest -m "not live"`). Run them locally with a real key:

    TRANSPORT_API_KEY=xxx pytest tests/test_server.py -m live

Offline unit coverage lives in test_ojp_client.py, test_api_infrastructure.py,
test_api_client.py and test_server_config.py. Unlike the previous suite, every
assertion here is a real `assert` — a failure fails the test instead of being
swallowed by a print().
"""

import os

import pytest

from swiss_transport_mcp import api_client, ojp_client, server

pytestmark = pytest.mark.live

_HAS_KEY = bool(os.environ.get("TRANSPORT_API_KEY") or os.environ.get("TRANSPORT_OJP_API_KEY"))
_needs_key = pytest.mark.skipif(not _HAS_KEY, reason="Set TRANSPORT_API_KEY to run live tests")


@_needs_key
async def test_live_search_stop_zurich():
    xml = ojp_client.build_location_request("Zürich HB", limit=5)
    response = await api_client.ojp_request(xml)
    locations = ojp_client.parse_location_response(response)
    assert locations, "expected at least one location"
    assert any("Zürich" in loc.get("name", "") for loc in locations)
    assert "stop_id" in locations[0]
    assert "latitude" in locations[0]


@_needs_key
async def test_live_search_stop_bern_id():
    xml = ojp_client.build_location_request("Bern", limit=3)
    response = await api_client.ojp_request(xml)
    locations = ojp_client.parse_location_response(response)
    assert locations
    assert locations[0].get("stop_id") == "8507000"
    assert "rail" in locations[0].get("transport_modes", [])


@_needs_key
async def test_live_nearby_stops():
    xml = ojp_client.build_location_coord_request(latitude=47.3769, longitude=8.5417, limit=5)
    response = await api_client.ojp_request(xml)
    locations = ojp_client.parse_location_response(response)
    assert locations


@_needs_key
async def test_live_departures_zurich():
    xml = ojp_client.build_stop_event_request("8503000", stop_name="Zürich HB", limit=5)
    response = await api_client.ojp_request(xml)
    events = ojp_client.parse_stop_event_response(response)
    assert events
    assert "line" in events[0] or "destination" in events[0]


@_needs_key
async def test_live_trip_zurich_bern_by_id():
    xml = ojp_client.build_trip_request("8503000", "8507000", limit=2)
    response = await api_client.ojp_request(xml)
    trips = ojp_client.parse_trip_response(response)
    assert trips
    assert trips[0].get("legs")
    assert "duration" in trips[0]


class _Ctx:
    """Gerade so viel Context, wie `transport_trip_plan` benutzt."""

    async def info(self, *_args, **_kwargs) -> None:
        return None


@_needs_key
async def test_live_trip_by_name():
    """Ortsnamen gehen jetzt durch die Aufloesung, nicht durch den Rumpfbauer.

    Frueher rief dieser Test `build_trip_request("Zürich HB", ...)` direkt auf.
    Der baute daraus `<LocationName>` — die OJP-1.0-Schreibweise —, und die
    Quelle antwortete mit einer leeren Trefferliste. Seit `_build_place_ref`
    einen Namen ablehnt, faellt derselbe Aufruf sogar **bevor** irgendein
    HTTP-Aufruf passiert: ein hausgemachter Fehlschlag, den
    `classify_live_run.py` als `finding` gegen die Quelle eingeordnet haette.
    Ein Live-Test, der ohne die Quelle faellt, misst nichts und beschuldigt
    trotzdem jemanden.

    Geprueft wird deshalb der Weg, den das Werkzeug wirklich geht.
    """
    result = await server.transport_trip_plan(
        server.TripPlanInput(origin="Zürich HB", destination="Basel SBB", limit=2), _Ctx()
    )
    assert result.trips, f"keine Reise gefunden: {result.message}"
    assert result.trips[0].get("legs")


@_needs_key
async def test_live_quay_id_is_usable_where_the_search_offers_it():
    """Was `transport_search_stop` anbietet, muessen die anderen Werkzeuge annehmen.

    Eine Haltekante kommt als `siri:StopPointRef` (`8503000:0:31`) zurueck. Kann
    die Abfahrtstafel so eine Kennung nicht verwerten, empfiehlt die Suche
    Werte, die nirgends funktionieren.
    """
    xml = ojp_client.build_location_request("Zürich HB", limit=10)
    locations = ojp_client.parse_location_response(await api_client.ojp_request(xml))
    quays = [loc for loc in locations if ":" in str(loc.get("stop_id", ""))]
    if not quays:
        pytest.skip("Quelle liefert zu dieser Anfrage keine Haltekanten")

    stop_id = quays[0]["stop_id"]
    assert ojp_client.is_stop_ref(stop_id), f"{stop_id} nicht als Kennung erkannt"
    assert "<siri:StopPointRef>" in ojp_client.build_stop_event_request(stop_id, limit=3)
