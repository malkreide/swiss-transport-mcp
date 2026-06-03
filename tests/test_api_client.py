"""HTTP-layer tests for api_client, mocked with respx (no real network).

These replace the old live-only integration tests for the request/response
plumbing: they assert the client sends the right auth header, hits the right
URL, and maps upstream errors correctly — all offline and key-free.
"""

import httpx
import pytest
import respx

from swiss_transport_mcp.api_client import (
    CKAN_API_URL,
    OJP_V2_URL,
    ckan_request,
    handle_api_error,
    ojp_request,
)
from swiss_transport_mcp.net_security import EgressNotAllowedError

# ---------------------------------------------------------------------------
# ojp_request (XML POST)
# ---------------------------------------------------------------------------

@respx.mock
async def test_ojp_request_posts_with_bearer_and_returns_text(monkeypatch):
    monkeypatch.setenv("TRANSPORT_API_KEY", "secret-key")
    route = respx.post(OJP_V2_URL).mock(
        return_value=httpx.Response(200, text="<OJP>ok</OJP>")
    )
    result = await ojp_request("<request/>")
    assert result == "<OJP>ok</OJP>"
    assert route.called
    sent = route.calls.last.request
    assert sent.headers["Authorization"] == "Bearer secret-key"
    assert sent.headers["Content-Type"] == "application/xml"


async def test_ojp_request_without_key_raises(monkeypatch):
    monkeypatch.delenv("TRANSPORT_API_KEY", raising=False)
    monkeypatch.delenv("TRANSPORT_OJP_API_KEY", raising=False)
    with pytest.raises(ValueError, match="OJP API key"):
        await ojp_request("<request/>")


@respx.mock
async def test_ojp_request_raises_on_http_error(monkeypatch):
    monkeypatch.setenv("TRANSPORT_API_KEY", "k")
    respx.post(OJP_V2_URL).mock(return_value=httpx.Response(500, text="boom"))
    with pytest.raises(httpx.HTTPStatusError):
        await ojp_request("<request/>")


# ---------------------------------------------------------------------------
# ckan_request (JSON GET)
# ---------------------------------------------------------------------------

@respx.mock
async def test_ckan_request_success_returns_result(monkeypatch):
    monkeypatch.setenv("TRANSPORT_API_KEY", "k")
    respx.get(f"{CKAN_API_URL}/package_list").mock(
        return_value=httpx.Response(200, json={"success": True, "result": ["a", "b"]})
    )
    result = await ckan_request("package_list")
    assert result == ["a", "b"]


@respx.mock
async def test_ckan_request_403_gives_subscription_hint(monkeypatch):
    monkeypatch.setenv("TRANSPORT_API_KEY", "k")
    respx.get(f"{CKAN_API_URL}/package_show").mock(return_value=httpx.Response(403))
    with pytest.raises(ValueError, match="403"):
        await ckan_request("package_show", {"id": "x"})


@respx.mock
async def test_ckan_request_unsuccessful_payload_raises(monkeypatch):
    monkeypatch.setenv("TRANSPORT_API_KEY", "k")
    respx.get(f"{CKAN_API_URL}/package_search").mock(
        return_value=httpx.Response(
            200, json={"success": False, "error": {"message": "bad query"}}
        )
    )
    with pytest.raises(ValueError, match="bad query"):
        await ckan_request("package_search", {"q": "x"})


async def test_ckan_request_rejects_offsite_base_url_override(monkeypatch):
    # SEC-021: TRANSPORT_CKAN_URL must not be able to redirect egress to an
    # arbitrary host. A non-allowlisted override is refused before any request.
    monkeypatch.setenv("TRANSPORT_API_KEY", "k")
    monkeypatch.setenv("TRANSPORT_CKAN_URL", "https://example.test/ckan")
    with pytest.raises(EgressNotAllowedError):
        await ckan_request("package_list")


@respx.mock
async def test_ckan_request_allows_onsite_base_url_override(monkeypatch):
    # An override that stays on an allowlisted host is permitted.
    monkeypatch.setenv("TRANSPORT_API_KEY", "k")
    monkeypatch.setenv("TRANSPORT_CKAN_URL", "https://api.opentransportdata.swiss/ckan-api")
    route = respx.get("https://api.opentransportdata.swiss/ckan-api/package_list").mock(
        return_value=httpx.Response(200, json={"success": True, "result": []})
    )
    await ckan_request("package_list")
    assert route.called


# ---------------------------------------------------------------------------
# handle_api_error mapping
# ---------------------------------------------------------------------------

def _status_error(code: int) -> httpx.HTTPStatusError:
    request = httpx.Request("GET", "https://x")
    response = httpx.Response(code, text="detail", request=request)
    return httpx.HTTPStatusError("err", request=request, response=response)


@pytest.mark.parametrize(
    "code,needle",
    [(401, "Authentication"), (403, "forbidden"), (429, "Rate limit"), (500, "Server error")],
)
def test_handle_api_error_status_messages(code, needle):
    msg = handle_api_error(_status_error(code))
    assert needle.lower() in msg.lower()


def test_handle_api_error_timeout():
    msg = handle_api_error(httpx.TimeoutException("slow"))
    assert "timed out" in msg.lower()


def test_handle_api_error_valueerror_passthrough():
    msg = handle_api_error(ValueError("no key"))
    assert "no key" in msg
