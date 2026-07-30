"""CORS configuration tests for the network transports (SDK-004)."""

import pytest
from starlette.middleware.cors import CORSMiddleware
from starlette.testclient import TestClient

from swiss_transport_mcp import server

# ---------------------------------------------------------------------------
# Origin resolution
# ---------------------------------------------------------------------------

def test_default_origin_is_claude_ai():
    assert server._resolve_cors_origins(env={}) == ["https://claude.ai"]


def test_origins_from_comma_separated_env():
    origins = server._resolve_cors_origins(
        env={"MCP_CORS_ORIGINS": "https://a.test, https://b.test"}
    )
    assert origins == ["https://a.test", "https://b.test"]


def test_blank_env_falls_back_to_default():
    assert server._resolve_cors_origins(env={"MCP_CORS_ORIGINS": "  "}) == [
        "https://claude.ai"
    ]


def test_wildcard_origin_supported():
    assert server._resolve_cors_origins(env={"MCP_CORS_ORIGINS": "*"}) == ["*"]


# ---------------------------------------------------------------------------
# Middleware wiring
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("transport", ["streamable-http", "sse"])
def test_app_has_cors_exposing_session_id(transport):
    app = server._build_http_app(transport, ["https://claude.ai"])
    cors = [m for m in app.user_middleware if m.cls is CORSMiddleware]
    assert len(cors) == 1
    kwargs = cors[0].kwargs
    assert "Mcp-Session-Id" in kwargs["expose_headers"]
    assert kwargs["allow_origins"] == ["https://claude.ai"]
    # MCP uses Authorization/session headers, not cookies → credentials off.
    assert kwargs["allow_credentials"] is False


# ---------------------------------------------------------------------------
# Preflight behaviour (end to end through the built app)
# ---------------------------------------------------------------------------

def test_preflight_allows_configured_origin_and_rejects_others():
    # One TestClient session: the StreamableHTTP session manager can only be
    # run once per instance, so both checks share a single lifespan.
    app = server._build_http_app("streamable-http", ["https://claude.ai"])
    with TestClient(app) as client:
        allowed = client.options(
            "/mcp",
            headers={
                "Origin": "https://claude.ai",
                "Access-Control-Request-Method": "POST",
            },
        )
        denied = client.options(
            "/mcp",
            headers={
                "Origin": "https://evil.test",
                "Access-Control-Request-Method": "POST",
            },
        )
    assert allowed.headers.get("access-control-allow-origin") == "https://claude.ai"
    # The attacker origin must never be echoed back as allowed.
    assert denied.headers.get("access-control-allow-origin") != "https://evil.test"


# ---------------------------------------------------------------------------
# mcp 2.x per-app kwargs (were mutable settings in 1.x)
# ---------------------------------------------------------------------------

def test_endpoint_path_constants_match_sdk_defaults():
    """The startup log line prints these paths; the app uses the SDK defaults.

    mcp 2.x removed ``sse_path`` / ``streamable_http_path`` from
    ``MCPServer.settings``, so the log line reads local constants now. If the
    SDK ever changes its defaults, the log would quietly point at the wrong
    URL — this test is what notices.
    """
    import inspect

    from mcp.server.mcpserver import MCPServer

    sse_default = inspect.signature(MCPServer.sse_app).parameters["sse_path"].default
    http_default = (
        inspect.signature(MCPServer.streamable_http_app)
        .parameters["streamable_http_path"]
        .default
    )
    assert server._SSE_PATH == sse_default
    assert server._STREAMABLE_HTTP_PATH == http_default


def test_settings_no_longer_carries_the_migrated_fields():
    """The 1.x read/write path is gone — loudly, not silently."""
    for field in ("sse_path", "streamable_http_path", "stateless_http", "host", "port"):
        assert not hasattr(server.mcp.settings, field)
        with pytest.raises(ValueError, match=f'has no field "{field}"'):
            setattr(server.mcp.settings, field, "x")


def test_stateless_reaches_the_streamable_http_app(monkeypatch):
    """SCALE-002/003: stateless is an app kwarg in 2.x, not a setting.

    It is a value that can silently go missing during migration — the app
    still builds, it just quietly regains per-session state. So the kwarg
    itself is asserted.
    """
    captured: dict = {}
    real = type(server.mcp).streamable_http_app

    def _spy(self, **kwargs):
        captured.update(kwargs)
        return real(self, **kwargs)

    monkeypatch.setattr(type(server.mcp), "streamable_http_app", _spy)
    server._build_http_app("streamable-http", ["https://claude.ai"], stateless=True)
    assert captured["stateless_http"] is True


def test_bind_host_is_passed_through_to_the_app(monkeypatch):
    """A 0.0.0.0 bind must not inherit the SDK's loopback-only allow-list.

    mcp 2.x auto-enables DNS-rebinding protection with ``127.0.0.1:*`` when
    ``host`` looks like localhost. Leaving ``host`` at its default while
    uvicorn binds 0.0.0.0 would answer every real request with HTTP 421, so
    the bind address has to travel into the app.
    """
    captured: dict = {}
    real = type(server.mcp).streamable_http_app

    def _spy(self, **kwargs):
        captured.update(kwargs)
        return real(self, **kwargs)

    monkeypatch.setattr(type(server.mcp), "streamable_http_app", _spy)
    server._build_http_app(
        "streamable-http", ["https://claude.ai"], host="0.0.0.0"  # noqa: S104
    )
    assert captured["host"] == "0.0.0.0"  # noqa: S104
