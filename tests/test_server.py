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
import xml.etree.ElementTree as ET

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
    """Der Treffer muss referenzierbar sein — nicht eine bestimmte Nummer tragen.

    Stand hier `== "8507000"`. Am 10.8.2026 antwortete die Quelle mit
    `ch:1:sloid:7000`, und der Test fiel — zu Recht, aber aus dem falschen
    Grund: Er hat die Kennung selbst zum Vertrag erklaert. Der Vertrag ist,
    dass die Suche etwas zurueckgibt, das die anderen Werkzeuge annehmen. Wie
    die Quelle ihre Halte durchnummeriert, ist ihre Sache.

    Das ist die Lehre aus dem Fehlschlag und nicht sein Zudecken: `is_stop_ref`
    haette `8507000` genauso bestanden, und die Zeile darunter faengt weiterhin
    den Fall ab, dass die Suche nach «Bern» irgendwo anders landet.
    """
    xml = ojp_client.build_location_request("Bern", limit=3)
    response = await api_client.ojp_request(xml)
    locations = ojp_client.parse_location_response(response)
    assert locations
    stop_id = locations[0].get("stop_id", "")
    assert ojp_client.is_stop_ref(stop_id), f"{stop_id!r} ist keine referenzierbare Kennung"
    assert "Bern" in locations[0].get("name", "")
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

    **Die Kante wird am Element erkannt, nicht am Doppelpunkt.** Vorher stand
    hier `":" in stop_id` — richtig, solange Stationen `8503000` hiessen und
    Kanten `8503000:0:31`. Seit die Quelle SLOIDs liefert, hat *jede* Kennung
    Doppelpunkte, und der Filter griff sich die Station Zuerich HB und pruefte
    sie als Kante. Der Test war damit nicht bloss rot: Er hat etwas anderes
    gemessen, als sein Name sagt, und haette auch gruen nichts mehr belegt.

    Am 10.8.2026 lieferte die Quelle zu vier Anfragen 62 Ergebnisse und darunter
    keine einzige Kante. Der Skip ist also der erwartete Ausgang — und er ist
    jetzt ehrlich: uebersprungen wird, wenn wirklich keine da ist.
    """
    xml = ojp_client.build_location_request("Zürich HB", limit=20)
    raw = await api_client.ojp_request(xml)

    # Direkt am XML, weil `stop_id` die Herkunft nicht mehr verraet: Der Parser
    # legt StopPlaceRef und siri:StopPointRef in dasselbe Feld.
    root = ET.fromstring(raw)
    quay_refs = [
        (el.text or "").strip()
        for el in root.iter("{http://www.siri.org.uk/siri}StopPointRef")
        if (el.text or "").strip()
    ]
    if not quay_refs:
        pytest.skip("Quelle liefert zu dieser Anfrage keine Haltekanten")

    stop_id = quay_refs[0]
    assert ojp_client.is_stop_ref(stop_id), f"{stop_id} nicht als Kennung erkannt"
    assert "<siri:StopPointRef>" in ojp_client.build_stop_event_request(stop_id, limit=3)
