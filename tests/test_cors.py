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
