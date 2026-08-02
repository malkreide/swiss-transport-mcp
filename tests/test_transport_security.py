"""Inbound Host/Origin allow-list for the network transports (SEC-005).

The counterpart to `test_net_security.py`, which covers where this server may
talk *to*. This one covers under *which name* it may be addressed.

The threat is DNS rebinding: a page on the operator's network resolves its own
hostname to this server's address and then talks to it from the browser. CORS
does not stop it — the request is same-origin from the browser's point of view
— and neither would a token, since the page runs in a context that holds one.
Only the Host check does.

The load-bearing test is **right hostname, wrong port**. `evil.test` alone
proves little: a fallback loopback-only policy rejects that too. Only the
wrong-port case distinguishes a port-exact allow-list from one that lets
everything through.

SSE is asserted on rejections only. An *allowed* host opens an event stream
that never ends, and `TestClient` waits for the ASGI task on exit — so the
positive case runs through Streamable HTTP, where a response completes.
"""

import pytest
from starlette.testclient import TestClient

from swiss_transport_mcp import server

_ORIGINS = ["https://claude.ai"]
_INIT = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-06-18",
        "capabilities": {},
        "clientInfo": {"name": "test", "version": "1"},
    },
}
_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
}


@pytest.fixture(autouse=True)
def _no_inherited_allowlist(monkeypatch):
    monkeypatch.delenv("MCP_ALLOWED_HOSTS", raising=False)


# ---------------------------------------------------------------------------
# Allow-list resolution
# ---------------------------------------------------------------------------


def test_allowed_hosts_default_is_empty():
    assert server._resolve_allowed_hosts(env={}) == []


def test_allowed_hosts_from_comma_separated_env():
    assert server._resolve_allowed_hosts(
        env={"MCP_ALLOWED_HOSTS": "fahrplan.test:8080, alt.test"}
    ) == ["fahrplan.test:8080", "alt.test"]


def test_loopback_bind_is_protected():
    """The SDK infers this from a loopback ``host``; stating it explicitly makes
    the protection independent of that inference."""
    sec = server._build_transport_security("127.0.0.1", 8080, _ORIGINS, env={})
    assert sec is not None
    assert sec.enable_dns_rebinding_protection is True
    assert "127.0.0.1:8080" in sec.allowed_hosts


@pytest.mark.parametrize("host", ["127.0.0.1", "localhost", "::1"])
def test_all_loopback_forms_count_as_local(host):
    assert server._build_transport_security(host, 8080, _ORIGINS, env={}) is not None


def test_public_bind_without_allowlist_stays_off():
    """Unchanged behaviour, and deliberately not a guess.

    On 0.0.0.0 the reachable name is unknowable here, and a wrong guess is
    exactly the HTTP 421 the ``host`` kwarg exists to avoid.
    """
    assert server._build_transport_security("0.0.0.0", 8080, _ORIGINS, env={}) is None


def test_public_bind_with_allowlist_is_protected():
    sec = server._build_transport_security(
        "0.0.0.0", 8080, _ORIGINS, env={"MCP_ALLOWED_HOSTS": "fahrplan.test:8080"}
    )
    assert "fahrplan.test:8080" in sec.allowed_hosts
    # Loopback stays reachable so container health checks keep working.
    assert "127.0.0.1:8080" in sec.allowed_hosts


def test_configured_cors_origins_pass_the_transport_check():
    """Otherwise the transport rejects exactly the browser clients CORS was
    opened for — claude.ai by default here."""
    sec = server._build_transport_security("127.0.0.1", 8080, _ORIGINS, env={})
    assert "https://claude.ai" in sec.allowed_origins


def test_wildcard_origin_is_not_copied():
    """``MCP_CORS_ORIGINS=*`` is supported for CORS but is not expressible as a
    transport origin — compared literally it permits nothing."""
    sec = server._build_transport_security("127.0.0.1", 8080, ["*"], env={})
    assert "*" not in sec.allowed_origins


# ---------------------------------------------------------------------------
# Through the built app
# ---------------------------------------------------------------------------


def _post_init(app, host_header: str) -> int:
    with TestClient(app, raise_server_exceptions=False) as client:
        return client.post(
            "/mcp", headers={**_HEADERS, "Host": host_header}, json=_INIT
        ).status_code


def test_allowlisted_host_is_admitted(monkeypatch):
    monkeypatch.setenv("MCP_ALLOWED_HOSTS", "fahrplan.test:8080")
    app = server._build_http_app("streamable-http", _ORIGINS, host="0.0.0.0", port=8080)
    assert _post_init(app, "fahrplan.test:8080") == 200


def test_foreign_host_is_rejected(monkeypatch):
    monkeypatch.setenv("MCP_ALLOWED_HOSTS", "fahrplan.test:8080")
    app = server._build_http_app("streamable-http", _ORIGINS, host="0.0.0.0", port=8080)
    assert _post_init(app, "evil.test") == 421


def test_right_host_wrong_port_is_rejected(monkeypatch):
    """The load-bearing case — see the module docstring."""
    monkeypatch.setenv("MCP_ALLOWED_HOSTS", "fahrplan.test:8080")
    app = server._build_http_app("streamable-http", _ORIGINS, host="0.0.0.0", port=8080)
    assert _post_init(app, "fahrplan.test:9999") == 421


def test_unconfigured_public_bind_keeps_serving(monkeypatch):
    """No allow-list means no behaviour change: a real hostname on a 0.0.0.0
    bind is still served, exactly as before this setting existed."""
    app = server._build_http_app("streamable-http", _ORIGINS, host="0.0.0.0", port=8080)
    assert _post_init(app, "fahrplan.test:8080") == 200


def test_sse_carries_the_same_allowlist(monkeypatch):
    """Both network transports must be covered, not just the recommended one.

    Asserted on the wiring, not end to end. Measured while mutation-testing: if
    ``sse_app`` loses the allow-list, a GET under a foreign host is *admitted*
    and opens an endless event stream, so an end-to-end assertion would hang
    the suite instead of failing it. The rejection semantics are already proven
    against Streamable HTTP above; both transports go through the same
    transport-security layer, and what differs between them is only whether the
    settings arrive.
    """
    monkeypatch.setenv("MCP_ALLOWED_HOSTS", "fahrplan.test:8080")
    captured: dict = {}
    real = type(server.mcp).sse_app

    def _spy(self, **kwargs):
        captured.update(kwargs)
        return real(self, **kwargs)

    monkeypatch.setattr(type(server.mcp), "sse_app", _spy)
    server._build_http_app("sse", _ORIGINS, host="0.0.0.0", port=8080)
    assert captured["host"] == "0.0.0.0"
    assert "fahrplan.test:8080" in captured["transport_security"].allowed_hosts


def test_the_bind_and_the_allowlist_agree(monkeypatch):
    """The port in the allow-list must be the port actually served.

    ``_build_http_app`` used to take only ``host``; if ``port`` did not travel
    with it, the loopback entries would name a port nobody listens on and
    container health checks would break.
    """
    captured: dict = {}
    real = type(server.mcp).streamable_http_app

    def _spy(self, **kwargs):
        captured.update(kwargs)
        return real(self, **kwargs)

    monkeypatch.setattr(type(server.mcp), "streamable_http_app", _spy)
    server._build_http_app("streamable-http", _ORIGINS, host="127.0.0.1", port=9101)
    assert captured["host"] == "127.0.0.1"
    assert "127.0.0.1:9101" in captured["transport_security"].allowed_hosts


def test_the_served_port_reaches_the_allowlist(monkeypatch):
    """The port must travel the whole way, not just into ``_build_http_app``.

    ``_serve_http`` knows the port and hands it to uvicorn; before this change
    it did not hand it to the app builder, which defaults it. The two would
    then disagree, and the loopback entries would name a port nobody serves —
    silently breaking container health checks. Asserted here at the seam,
    because a test on ``_build_http_app`` alone cannot see it.
    """
    import anyio
    import uvicorn

    captured: dict = {}
    real = type(server.mcp).streamable_http_app

    def _spy(self, **kwargs):
        captured.update(kwargs)
        return real(self, **kwargs)

    class _NoopServer:
        def __init__(self, config):
            self.config = config

        async def serve(self):
            captured["uvicorn_port"] = self.config.port

    monkeypatch.setattr(type(server.mcp), "streamable_http_app", _spy)
    monkeypatch.setattr(uvicorn, "Server", _NoopServer)
    anyio.run(lambda: server._serve_http("streamable-http", "127.0.0.1", 9102, _ORIGINS))

    assert captured["uvicorn_port"] == 9102
    assert "127.0.0.1:9102" in captured["transport_security"].allowed_hosts
