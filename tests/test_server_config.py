"""Tool input-validation tests (SEC-018) and regression guards for the
critical audit fixes (SEC-016 host binding, OBS-004 stdout hygiene).
"""

from pathlib import Path

import pytest
from pydantic import ValidationError

from swiss_transport_mcp import server
from swiss_transport_mcp.server import (
    DeparturesInput,
    SearchStopByCoordInput,
    SearchStopInput,
    TripPlanInput,
    _resolve_http_bind,
    _resolve_transport,
)

SRC_DIR = Path(server.__file__).parent


# ---------------------------------------------------------------------------
# SEC-018 — input validation at tool boundaries
# ---------------------------------------------------------------------------

def test_search_stop_accepts_valid():
    m = SearchStopInput(query="Bern", limit=5)
    assert m.query == "Bern"
    assert m.limit == 5


def test_search_stop_rejects_short_query():
    with pytest.raises(ValidationError):
        SearchStopInput(query="x")


def test_search_stop_rejects_unknown_field():
    # extra="forbid" must reject smuggled-in fields.
    with pytest.raises(ValidationError):
        SearchStopInput(query="Bern", evil="payload")


def test_search_stop_limit_bounds():
    with pytest.raises(ValidationError):
        SearchStopInput(query="Bern", limit=0)
    with pytest.raises(ValidationError):
        SearchStopInput(query="Bern", limit=21)


def test_coord_bounds_enforced_to_switzerland():
    # Inside the CH bounding box → OK.
    SearchStopByCoordInput(latitude=47.0, longitude=8.0)
    # Outside (e.g. London) → rejected.
    with pytest.raises(ValidationError):
        SearchStopByCoordInput(latitude=51.5, longitude=-0.12)


def test_departures_event_type_pattern():
    assert DeparturesInput(stop_id="8503000", event_type="arrival").event_type == "arrival"
    with pytest.raises(ValidationError):
        DeparturesInput(stop_id="8503000", event_type="DROP TABLE")


def test_trip_requires_both_endpoints():
    TripPlanInput(origin="A", destination="B")
    with pytest.raises(ValidationError):
        TripPlanInput(origin="", destination="B")


# ---------------------------------------------------------------------------
# SEC-016 — network listener must default to loopback
# ---------------------------------------------------------------------------

def test_http_bind_defaults_to_loopback():
    host, port = _resolve_http_bind(env={})
    assert host == "127.0.0.1"
    assert port == 8000


def test_http_bind_respects_explicit_host_for_containers():
    host, _ = _resolve_http_bind(env={"MCP_HOST": "0.0.0.0"})
    assert host == "0.0.0.0"


def test_http_bind_port_from_env_and_platform_port():
    assert _resolve_http_bind(env={"MCP_PORT": "9000"})[1] == 9000
    # Cloud platforms inject PORT; honoured as fallback.
    assert _resolve_http_bind(env={"PORT": "10000"})[1] == 10000


# ---------------------------------------------------------------------------
# SCALE-001 — transport resolution (Streamable HTTP is the cloud default)
# ---------------------------------------------------------------------------

def test_transport_defaults_to_stdio():
    assert _resolve_transport(env={}) == "stdio"


@pytest.mark.parametrize("value", ["http", "streamable-http", "streamable_http", "HTTP"])
def test_transport_http_aliases_map_to_streamable_http(value):
    assert _resolve_transport(env={"MCP_TRANSPORT": value}) == "streamable-http"


def test_transport_sse_preserved_for_legacy():
    assert _resolve_transport(env={"MCP_TRANSPORT": "sse"}) == "sse"


def test_transport_unknown_passed_through_for_main_to_handle():
    # main() logs an error and falls back to stdio for unknown values.
    assert _resolve_transport(env={"MCP_TRANSPORT": "carrier-pigeon"}) == "carrier-pigeon"


# ---------------------------------------------------------------------------
# OBS-004 — stdout reserved for the JSON-RPC stream (no stray print())
# ---------------------------------------------------------------------------

def test_no_print_statements_in_src():
    offenders = []
    for py in SRC_DIR.rglob("*.py"):
        for i, line in enumerate(py.read_text(encoding="utf-8").splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("print(") or " print(" in f" {stripped}":
                offenders.append(f"{py.name}:{i}")
    assert not offenders, f"print() pollutes stdout on stdio transport: {offenders}"
