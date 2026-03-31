"""Swiss Transport MCP Server – Test Suite.

Unit tests run offline, integration tests require TRANSPORT_API_KEY.
Run: TRANSPORT_API_KEY=xxx python tests/test_integration.py
"""

import asyncio
import os
import sys

# Add project to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from swiss_transport_mcp import api_client, ojp_client

# Track results
passed, failed, skipped = 0, 0, 0


def report(name: str, success: bool, detail: str = ""):
    global passed, failed
    if success:
        passed += 1
        print(f"  ✅ {name}: {detail}" if detail else f"  ✅ {name}")
    else:
        failed += 1
        print(f"  ❌ {name}: {detail}")


# ===========================================================================
# Unit Tests (no API key needed)
# ===========================================================================

def test_unit():
    print("🧪 Unit Tests (Offline)")
    print("=" * 50)

    # Test 1: XML templates load correctly
    try:
        from swiss_transport_mcp.ojp_client import (
            build_location_request,
            build_stop_event_request,
            build_trip_request,
        )
        xml = build_location_request("Zürich", limit=5)
        assert "Zürich" in xml
        assert 'version="2.0"' in xml
        assert "http://www.vdv.de/ojp" in xml

        xml2 = build_stop_event_request("8503000", stop_name="Zürich HB")
        assert "8503000" in xml2
        assert "StopPlaceRef" in xml2

        xml3 = build_trip_request("8503000", "8507000")
        assert "8503000" in xml3
        assert "8507000" in xml3
        assert "OJPTripRequest" in xml3

        report("xml_templates", True, "All templates load and format correctly")
    except Exception as e:
        report("xml_templates", False, str(e))

    # Test 2: Duration parser
    try:
        from swiss_transport_mcp.ojp_client import _parse_duration
        assert _parse_duration("PT1H30M") == "1h 30min"
        assert _parse_duration("PT45M") == "45min"
        assert _parse_duration("PT2H") == "2h"
        assert _parse_duration("PT55M42S") == "55min"
        assert _parse_duration("PT30S") == "30s"
        report("duration_parser", True, "All duration formats parsed correctly")
    except Exception as e:
        report("duration_parser", False, str(e))

    # Test 3: Place ref builder
    try:
        from swiss_transport_mcp.ojp_client import _build_place_ref
        ref_id = _build_place_ref("8503000")
        assert "<StopPlaceRef>" in ref_id
        assert "8503000" in ref_id

        ref_name = _build_place_ref("Zürich HB")
        assert "<LocationName>" in ref_name
        assert "Zürich HB" in ref_name
        report("place_ref_builder", True, "Correct XML for IDs and names")
    except Exception as e:
        report("place_ref_builder", False, str(e))

    print()


# ===========================================================================
# Integration Tests (API key required)
# ===========================================================================

async def test_integration():
    api_key = os.environ.get("TRANSPORT_API_KEY") or os.environ.get("TRANSPORT_OJP_API_KEY")

    print("🔗 Integration Tests (Live API)")
    print("=" * 50)

    if not api_key:
        global skipped
        skipped = 9
        print("  ⏭️  Skipped: Set TRANSPORT_API_KEY to run integration tests")
        return

    # Test 4: Search stops
    try:
        xml = ojp_client.build_location_request("Zürich HB", limit=5)
        response = await api_client.ojp_request(xml)
        locations = ojp_client.parse_location_response(response)
        assert len(locations) > 0
        assert any("Zürich" in loc.get("name", "") for loc in locations)
        first = locations[0]
        assert "stop_id" in first
        assert "latitude" in first
        report("search_stop", True, f"Found {len(locations)} stops, first: {first.get('name')}")
    except Exception as e:
        report("search_stop", False, str(e))

    # Test 5: Search stop Bern
    try:
        xml = ojp_client.build_location_request("Bern", limit=3)
        response = await api_client.ojp_request(xml)
        locations = ojp_client.parse_location_response(response)
        assert len(locations) > 0
        bern = locations[0]
        assert bern.get("stop_id") == "8507000"
        modes = bern.get("transport_modes", [])
        assert "rail" in modes
        report("search_stop_bern", True, f"Bern ID={bern['stop_id']}, modes={modes}")
    except Exception as e:
        report("search_stop_bern", False, str(e))

    # Test 6: Nearby stops (Zürich HB coordinates)
    try:
        xml = ojp_client.build_location_coord_request(latitude=47.3769, longitude=8.5417, limit=5)
        response = await api_client.ojp_request(xml)
        locations = ojp_client.parse_location_response(response)
        assert len(locations) > 0
        report("nearby_stops", True, f"Found {len(locations)} stops near Zürich HB")
    except Exception as e:
        report("nearby_stops", False, str(e))

    # Test 7: Departures Zürich HB
    try:
        xml = ojp_client.build_stop_event_request("8503000", stop_name="Zürich HB", limit=5)
        response = await api_client.ojp_request(xml)
        events = ojp_client.parse_stop_event_response(response)
        assert len(events) > 0
        first = events[0]
        assert "line" in first or "destination" in first
        report("departures", True, f"Found {len(events)} departures, first: {first.get('line','')} → {first.get('destination','')}")
    except Exception as e:
        report("departures", False, str(e))

    # Test 8: Trip Zürich → Bern (by ID)
    try:
        xml = ojp_client.build_trip_request("8503000", "8507000", limit=2)
        response = await api_client.ojp_request(xml)
        trips = ojp_client.parse_trip_response(response)
        assert len(trips) > 0
        first = trips[0]
        assert "legs" in first
        assert len(first["legs"]) > 0
        assert "duration" in first
        report("trip_plan", True, f"Found {len(trips)} trips, first: {first['duration']}, {first.get('transfers',0)} transfers, {len(first['legs'])} legs")
    except Exception as e:
        report("trip_plan", False, str(e))

    # Test 9: Trip by name
    try:
        xml = ojp_client.build_trip_request("Zürich HB", "Basel SBB", limit=2)
        response = await api_client.ojp_request(xml)
        trips = ojp_client.parse_trip_response(response)
        assert len(trips) > 0
        report("trip_plan_by_name", True, f"Found {len(trips)} trips by name")
    except Exception as e:
        report("trip_plan_by_name", False, str(e))

    # Test 10-12: CKAN (may fail if key doesn't cover CKAN)
    for test_name, ckan_call in [
        ("ckan_search", lambda: api_client.ckan_request("package_search", {"q": "gtfs", "rows": 5})),
        ("ckan_detail", lambda: api_client.ckan_request("package_show", {"id": "ojp2-0"})),
        ("ckan_list", lambda: api_client.ckan_request("package_list")),
    ]:
        try:
            result = await ckan_call()
            report(test_name, True, f"OK ({type(result).__name__})")
        except Exception as e:
            err_msg = str(e)
            if "403" in err_msg:
                skipped += 1
                print(f"  ⏭️  {test_name}: CKAN API not subscribed (403) – subscribe at api-manager.opentransportdata.swiss")
            else:
                report(test_name, False, err_msg)

    print()


# ===========================================================================
# Main
# ===========================================================================

if __name__ == "__main__":
    print("🚆 Swiss Transport MCP Server – Test Suite")
    print("=" * 50)
    print()

    test_unit()
    asyncio.run(test_integration())

    total = passed + failed
    print("=" * 50)
    status = "✅ ALL PASSED" if failed == 0 else f"⚠️ {failed} FAILED"
    skip_info = f", {skipped} skipped" if skipped else ""
    print(f"📊 Results: {passed} passed, {failed} failed{skip_info} | {status}")
    print("=" * 50)

    sys.exit(1 if failed > 0 else 0)
