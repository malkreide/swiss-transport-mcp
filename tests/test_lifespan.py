"""Tests for the server lifespan and pooled HTTP client (SDK-001)."""

import httpx
import respx

from swiss_transport_mcp import api_client, server
from swiss_transport_mcp.api_client import OJP_V2_URL, ojp_request
from swiss_transport_mcp.api_infrastructure import TransportAPIClient


@respx.mock
async def test_ojp_request_reuses_installed_shared_client(monkeypatch):
    monkeypatch.setenv("TRANSPORT_API_KEY", "k")
    respx.post(OJP_V2_URL).mock(return_value=httpx.Response(200, text="<ok/>"))

    shared = httpx.AsyncClient()
    api_client.set_shared_client(shared)
    try:
        out = await ojp_request("<r/>")
        assert out == "<ok/>"
        # A throwaway client would be closed after the call; the pooled one
        # stays open because it is owned by the lifespan, not the request.
        assert shared.is_closed is False
    finally:
        api_client.clear_shared_client()
        await shared.aclose()

    assert api_client._shared_client is None


@respx.mock
async def test_ojp_request_fallback_without_shared_client(monkeypatch):
    # With no pooled client installed, the call still works via a throwaway.
    monkeypatch.setenv("TRANSPORT_API_KEY", "k")
    assert api_client._shared_client is None
    respx.post(OJP_V2_URL).mock(return_value=httpx.Response(200, text="<ok/>"))
    assert await ojp_request("<r/>") == "<ok/>"


async def test_app_lifespan_sets_up_and_tears_down_resources():
    assert api_client._shared_client is None
    assert server._ext_client is None

    async with server.app_lifespan(server.mcp) as appctx:
        # During the server's lifetime the shared resources are live.
        assert isinstance(appctx.ext_client, TransportAPIClient)
        assert api_client._shared_client is not None
        assert api_client._shared_client.is_closed is False
        assert server._ext_client is appctx.ext_client
        pooled = api_client._shared_client
        ext = appctx.ext_client

    # After shutdown everything is closed and reset (SDK-001: no leaked clients).
    assert api_client._shared_client is None
    assert server._ext_client is None
    assert pooled.is_closed is True
    assert ext._client.is_closed is True
