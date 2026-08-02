"""Tests for observability hardening: error masking (OBS-002), structured
logging (OBS-003) and the prompt primitive (ARCH-008)."""

import asyncio
import json
import logging
import sys

import httpx

from swiss_transport_mcp import server
from swiss_transport_mcp.api_client import handle_api_error
from swiss_transport_mcp.logging_config import JsonLogFormatter, configure_logging

# ---------------------------------------------------------------------------
# OBS-002 — upstream response bodies must not reach the LLM
# ---------------------------------------------------------------------------


def _status_error(code: int, body: str) -> httpx.HTTPStatusError:
    request = httpx.Request("GET", "https://api.opentransportdata.swiss/x")
    response = httpx.Response(code, text=body, request=request)
    return httpx.HTTPStatusError("err", request=request, response=response)


def test_handle_api_error_masks_upstream_body(caplog):
    secret = "INTERNAL STACKTRACE line 42 token=abc"
    with caplog.at_level(logging.WARNING, logger="swiss-transport-mcp"):
        msg = handle_api_error(_status_error(418, secret))
    # The LLM-facing message must not contain the raw upstream body…
    assert secret not in msg
    assert "418" in msg
    # …but it is logged server-side for diagnosis.
    assert any(secret in r.getMessage() for r in caplog.records)


def test_handle_api_error_known_codes_unchanged():
    assert "401" in handle_api_error(_status_error(401, "x"))
    assert "Rate limit" in handle_api_error(_status_error(429, "x"))


# ---------------------------------------------------------------------------
# OBS-003 — structured logging with RFC 5424 severity
# ---------------------------------------------------------------------------


def test_json_formatter_maps_rfc5424_severity():
    fmt = JsonLogFormatter()
    cases = {
        logging.CRITICAL: 2,
        logging.ERROR: 3,
        logging.WARNING: 4,
        logging.INFO: 6,
        logging.DEBUG: 7,
    }
    for level, severity in cases.items():
        record = logging.LogRecord("x", level, __file__, 1, "msg", None, None)
        payload = json.loads(fmt.format(record))
        assert payload["severity"] == severity
        assert payload["level"] == logging.getLevelName(level)
        assert payload["message"] == "msg"


def test_configure_logging_json_vs_text():
    json_handler = configure_logging(env={"LOG_FORMAT": "json"})
    assert isinstance(json_handler.formatter, JsonLogFormatter)
    text_handler = configure_logging(env={"LOG_FORMAT": "text"})
    assert not isinstance(text_handler.formatter, JsonLogFormatter)
    # Always stderr (OBS-004): the handler writes to a stream, never stdout.
    assert text_handler.stream is sys.stderr


# ---------------------------------------------------------------------------
# ARCH-008 — prompt primitive present (tools + resources + prompts)
# ---------------------------------------------------------------------------


def test_prompt_primitive_registered():
    prompts = asyncio.run(server.mcp.list_prompts())
    assert "plan_group_trip" in {p.name for p in prompts}


def test_prompt_renders_tool_guidance():
    text = server.plan_group_trip(origin="Zürich HB", destination="Bern", group_size="25")
    assert "transport_search_stop" in text
    assert "transport_trip_plan" in text
    assert "25" in text
