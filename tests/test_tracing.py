"""Tests for opt-in OpenTelemetry tracing (OBS-006).

The CI environment does not install the ``otel`` extra, so these assert the
default no-op behaviour: tracing stays disabled and ``span()`` is a safe,
zero-overhead context manager. The activation path is covered conditionally
when OpenTelemetry happens to be installed.
"""

import pytest

from swiss_transport_mcp import tracing
from swiss_transport_mcp.tracing import configure_tracing, span


def test_tracing_disabled_by_default():
    assert configure_tracing(env={}) is False


def test_enabling_without_otel_warns_and_stays_disabled():
    # Without the otel extra, requesting tracing must not crash.
    result = configure_tracing(env={"OTEL_TRACES_ENABLED": "1"})
    if tracing._OTEL_AVAILABLE:
        assert result is True
    else:
        assert result is False


def test_span_is_noop_when_disabled():
    configure_tracing(env={})  # ensure disabled
    with span("unit.test", **{"some.attr": "value"}) as sp:
        # Disabled → yields None and does nothing.
        assert sp is None


@pytest.mark.parametrize("value,expected", [("1", True), ("true", True), ("on", True), ("0", False), ("", False)])
def test_truthy_parsing(value, expected):
    assert tracing._is_truthy(value) is expected


@pytest.mark.skipif(not tracing._OTEL_AVAILABLE, reason="otel extra not installed")
def test_active_tracing_creates_real_span():
    assert configure_tracing(env={"OTEL_TRACES_ENABLED": "1"}) is True
    try:
        with span("unit.test", **{"k": "v"}) as sp:
            assert sp is not None
    finally:
        # Flush + stop the background processor while stderr is still open, so
        # there is no export-at-shutdown noise; then reset the disabled flag.
        tracing._otel_trace.get_tracer_provider().shutdown()
        configure_tracing(env={})
