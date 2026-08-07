"""Unit tests for the OJP XML client — request builders, parsers, helpers.

Pure/offline: no network, no API key. Every check is a real `assert` so a
regression makes pytest fail (not a swallowed print like the old suite).
"""

import pytest

from swiss_transport_mcp import ojp_client
from swiss_transport_mcp.ojp_client import (
    OJP,
    SIRI,
    _build_place_ref,
    _escape_xml,
    _parse_duration,
    build_location_coord_request,
    build_location_request,
    build_stop_event_request,
    build_trip_request,
    parse_location_response,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def test_escape_xml_neutralises_metacharacters():
    raw = "Z<urich> & \"Bern\" 'HB'"
    escaped = _escape_xml(raw)
    assert "<" not in escaped and ">" not in escaped
    assert "&amp;" in escaped
    assert "&quot;" in escaped
    assert "&apos;" in escaped
    assert "&lt;urich&gt;" in escaped


def test_escape_xml_blocks_injection_payload():
    # A free-text value must not be able to inject a new XML element.
    payload = "</Text></LocationName><Evil>boom</Evil>"
    escaped = _escape_xml(payload)
    assert "<Evil>" not in escaped
    assert "&lt;Evil&gt;" in escaped


def test_build_place_ref_numeric_id_uses_stopplaceref():
    ref = _build_place_ref("8503000")
    assert ref == "<StopPlaceRef>8503000</StopPlaceRef>"


def test_build_place_ref_refuses_a_name():
    # OJP 2.0 has no name-only place reference; `PlaceRefGroup` wants one of six
    # real reference elements. This used to build `<LocationName>` -- the OJP 1.0
    # spelling -- and the resulting request quietly matched nothing. Held
    # against the recorded schema in test_ojp_contract.py.
    with pytest.raises(ValueError):
        _build_place_ref("Zürich HB & Co <x>")


def test_parse_duration_formats():
    assert _parse_duration("PT1H30M") == "1h 30min"
    assert _parse_duration("PT45M") == "45min"
    assert _parse_duration("PT2H") == "2h"
    assert _parse_duration("PT55M42S") == "55min"
    assert _parse_duration("PT30S") == "30s"


# ---------------------------------------------------------------------------
# Request builders
# ---------------------------------------------------------------------------


def test_build_location_request_embeds_escaped_query():
    xml = build_location_request("Zürich HB", limit=5)
    assert "Zürich HB" in xml
    assert 'version="2.0"' in xml
    assert OJP in xml


def test_build_location_request_escapes_injection():
    xml = build_location_request("</foo><Inject/>", limit=3)
    assert "<Inject/>" not in xml
    assert "&lt;Inject/&gt;" in xml


def test_build_stop_event_request_numeric_ref():
    xml = build_stop_event_request("8503000", stop_name="Zürich HB", limit=5)
    assert "<StopPlaceRef>8503000</StopPlaceRef>" in xml
    assert "Zürich HB" in xml


def test_build_trip_request_contains_both_endpoints():
    xml = build_trip_request("8503000", "8507000", limit=2)
    assert "8503000" in xml
    assert "8507000" in xml
    assert "OJPTripRequest" in xml


def test_build_location_coord_request_inserts_coords():
    xml = build_location_coord_request(latitude=47.3769, longitude=8.5417, limit=4)
    assert "47.3769" in xml
    assert "8.5417" in xml


# ---------------------------------------------------------------------------
# Response parser
# ---------------------------------------------------------------------------
#
# Diese Antwort ist **ausgedacht**, nicht aufgezeichnet: Die OJP-Schnittstelle
# verlangt einen Bearer-Token, den CI nicht hat — gemessen in
# `fixtures/upstream_auth_probe.json`, begruendet in `fixtures/PROVENANCE.md`.
# Sie kann dem Parser deshalb nicht widersprechen; sie zeigt nur, dass er tut,
# was ihr Autor erwartet hat.
#
# Was widersprechen kann, ist der aufgezeichnete OJP-2.0-Vertrag: siehe
# `test_ojp_contract.py`. Die Form unten folgt ihm bewusst — Pflichtfelder
# `Name` und `Complete` sind da, `siri:ServiceDelivery` steht im
# SIRI-Namensraum, und die Wurzel traegt `version="2.0"`. Die alte Fassung
# hatte nichts davon.


def _location_fixture() -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<OJP xmlns="{OJP}" xmlns:siri="{SIRI}" version="2.0">
  <OJPResponse>
    <siri:ServiceDelivery>
      <OJPLocationInformationDelivery>
        <PlaceResult>
          <Place>
            <StopPlace>
              <StopPlaceRef>8503000</StopPlaceRef>
              <StopPlaceName><Text>Zürich HB</Text></StopPlaceName>
            </StopPlace>
            <Name><Text>Zürich HB</Text></Name>
            <GeoPosition>
              <siri:Longitude>8.5417</siri:Longitude>
              <siri:Latitude>47.3769</siri:Latitude>
            </GeoPosition>
            <Mode><PtMode>rail</PtMode></Mode>
            <Mode><PtMode>bus</PtMode></Mode>
          </Place>
          <Complete>true</Complete>
          <Probability>0.95</Probability>
        </PlaceResult>
      </OJPLocationInformationDelivery>
    </siri:ServiceDelivery>
  </OJPResponse>
</OJP>"""


def test_parse_location_response_extracts_fields():
    locations = parse_location_response(_location_fixture())
    assert len(locations) == 1
    loc = locations[0]
    assert loc["stop_id"] == "8503000"
    assert loc["name"] == "Zürich HB"
    assert loc["latitude"] == 47.3769
    assert loc["longitude"] == 8.5417
    assert loc["match_quality"] == 0.95
    assert "rail" in loc["transport_modes"]
    assert "bus" in loc["transport_modes"]


def test_parse_location_response_empty_on_no_results():
    empty = f'<OJP xmlns="{OJP}" xmlns:siri="{SIRI}"></OJP>'
    assert parse_location_response(empty) == []


def test_public_parser_symbols_exist():
    # Guard against accidental API renames the rest of the server relies on.
    for name in (
        "parse_location_response",
        "parse_stop_event_response",
        "parse_trip_response",
    ):
        assert hasattr(ojp_client, name)
