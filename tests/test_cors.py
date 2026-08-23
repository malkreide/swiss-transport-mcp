"""SDK-004: the CORS allow-list now names headers instead of a wildcard.

`allow_headers` read `["*", "Mcp-Session-Id"]`, and the wildcard won. Starlette
switches to `allow_all_headers` and mirrors back whatever a browser announces,
so every permitted origin could send any header at all.

The permissiveness is only half the cost. A wildcard also cannot become wrong:
drop a header the protocol needs and nothing turns red. That is why the
portfolio moved to explicit lists — a list is checkable, a wildcard is not.

Real requests against the assembled app, not an inspection of the middleware
stack: asserting that a `CORSMiddleware` object is present would pass with an
empty list, which is precisely the defect.
"""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from swiss_transport_mcp.server import (
    CORS_ALLOW_HEADERS,
    CORS_ROUTING_HEADERS,
    _build_http_app,
)

ORIGIN = "https://client.example"

# Both transports. A control that holds on one and not the other is worse than
# a missing one: it looks enforced.
ENDPOINTS = {"streamable-http": "/mcp", "sse": "/sse"}


@pytest.fixture(params=["streamable-http", "sse"])
def kind(request) -> str:
    return request.param


@pytest.fixture
def client(kind: str) -> TestClient:
    return TestClient(_build_http_app(kind, [ORIGIN]))


def preflight(client: TestClient, kind: str, request_headers: str, method: str = "POST"):
    """Send a preflight.

    `request_headers` is what the browser announces it intends to send. It has
    to ride on the request rather than be read off the response: Starlette
    answers a preflight naming a header it does not allow with **400 and no
    `Access-Control-Allow-Origin`**.
    """
    return client.options(
        ENDPOINTS[kind],
        headers={
            "Origin": ORIGIN,
            "Access-Control-Request-Method": method,
            "Access-Control-Request-Headers": request_headers,
        },
    )


@pytest.mark.parametrize("header", CORS_ALLOW_HEADERS)
def test_every_allow_listed_header_passes_the_preflight(
    client: TestClient, kind: str, header: str
) -> None:
    """One header per request on purpose: announcing all of them at once would
    still pass if only one were allow-listed and Starlette were lenient about
    the rest."""
    resp = preflight(client, kind, header)
    assert resp.status_code == 200, f"preflight announcing {header} was refused"
    assert header.lower() in resp.headers["access-control-allow-headers"].lower()


def test_the_headers_together(client: TestClient, kind: str) -> None:
    """What a browser actually sends: all of them, on the same request."""
    resp = preflight(client, kind, ", ".join(h.lower() for h in CORS_ALLOW_HEADERS))
    assert resp.status_code == 200
    assert resp.headers["access-control-allow-origin"] == ORIGIN


def test_a_header_nobody_allow_listed_is_refused(client: TestClient, kind: str) -> None:
    """The negative control — and the finding itself.

    Without it every test above would pass against the old wildcard just as
    well. It is the only assurance here that tells a list from "anything goes".
    """
    resp = preflight(client, kind, "x-not-allowed")
    assert resp.status_code == 400, "the allow-list still waves everything through"


def test_the_list_names_every_routing_header_the_sdk_reads() -> None:
    """Held against the SDK's own constants rather than a copy of the spec text.
    `mcp.shared.inbound` is what the server actually classifies a request with,
    so a rename there surfaces as a failing test instead of a browser client
    that stops connecting for no visible reason."""
    from mcp.shared.inbound import (
        MCP_METHOD_HEADER,
        MCP_NAME_HEADER,
        MCP_PROTOCOL_VERSION_HEADER,
    )

    allowed = {h.lower() for h in CORS_ALLOW_HEADERS}
    required = {MCP_METHOD_HEADER, MCP_NAME_HEADER, MCP_PROTOCOL_VERSION_HEADER}
    assert required <= allowed, f"not allow-listed: {sorted(required - allowed)}"
    assert {h.lower() for h in CORS_ROUTING_HEADERS} == required


def test_the_list_names_the_resumption_header() -> None:
    """`Last-Event-ID` resumes a dropped SSE stream. Without it only
    reconnection after packet loss breaks — under load, in production, with no
    test saying anything about it."""
    from mcp.server.streamable_http import LAST_EVENT_ID_HEADER

    assert LAST_EVENT_ID_HEADER in {h.lower() for h in CORS_ALLOW_HEADERS}


def test_the_list_names_the_session_header() -> None:
    from mcp.server.streamable_http import MCP_SESSION_ID_HEADER

    assert MCP_SESSION_ID_HEADER in {h.lower() for h in CORS_ALLOW_HEADERS}


def test_no_wildcard_in_the_allow_list() -> None:
    """The regression this guards against was exactly one character."""
    assert "*" not in CORS_ALLOW_HEADERS


async def test_no_tool_declares_an_mcp_param_header() -> None:
    """`Mcp-Param-*` carries a tool argument as an HTTP header, opted into by an
    `x-mcp-header` annotation on the input schema. CORS has no prefix wildcard,
    so the first tool to use one must name that exact header in
    `CORS_ALLOW_HEADERS` or browser clients break on it."""
    from swiss_transport_mcp.server import mcp

    offenders = [t.name for t in await mcp.list_tools() if "x-mcp-header" in str(t.input_schema)]
    assert not offenders, (
        f"{offenders} declare an Mcp-Param-* header — name it in CORS_ALLOW_HEADERS"
    )


def test_a_foreign_origin_is_still_refused(client: TestClient, kind: str) -> None:
    """The header list changes nothing about the origin check."""
    resp = client.options(
        ENDPOINTS[kind],
        headers={
            "Origin": "https://elsewhere.example",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert "access-control-allow-origin" not in resp.headers
