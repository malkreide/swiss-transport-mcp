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


def test_availability_probe_requires_the_sdk_not_just_the_api():
    """Regression guard for a trap mcp 2.x introduced.

    mcp 2.x depends on ``opentelemetry-api``, so ``from opentelemetry import
    trace`` now succeeds without the ``otel`` extra. If ``_OTEL_AVAILABLE``
    probed only that, ``configure_tracing()`` would skip its
    warn-and-stay-disabled branch and blow up on the SDK imports instead —
    breaking this module's documented "no crash" promise at server startup.

    So the flag must track the SDK, which is what ``configure_tracing()``
    actually imports.
    """
    import importlib.util

    sdk_present = importlib.util.find_spec("opentelemetry.sdk") is not None
    assert tracing._OTEL_AVAILABLE is sdk_present


def test_enabling_without_the_sdk_never_raises():
    """The promise itself: requesting tracing without the extra must not crash.

    Passes trivially once the extra is installed; the value is in the run where
    it is not — which is exactly what CI does.
    """
    try:
        assert configure_tracing(env={"OTEL_TRACES_ENABLED": "1"}) is tracing._OTEL_AVAILABLE
    finally:
        configure_tracing(env={})


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
