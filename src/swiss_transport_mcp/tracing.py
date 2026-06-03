"""Optional OpenTelemetry tracing (OBS-006).

Tracing is **opt-in and a no-op by default**: it activates only when
``OTEL_TRACES_ENABLED`` is truthy *and* the ``otel`` extra is installed
(``pip install 'swiss-transport-mcp[otel]'``). Without both, ``span()`` is a
zero-overhead null context, so the default install carries no extra dependency
and no runtime cost.

Spans are emitted around each upstream HTTP call (the work every tool does),
giving per-request latency/status traces. The built-in exporter writes to
**stderr** (never stdout – that stays reserved for the stdio JSON-RPC stream).
"""

from __future__ import annotations

import logging
import os
import sys
from collections.abc import Iterator, Mapping
from contextlib import contextmanager

logger = logging.getLogger("swiss-transport-mcp")

try:  # the otel extra may not be installed
    from opentelemetry import trace as _otel_trace

    _OTEL_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised only without the extra
    _OTEL_AVAILABLE = False

_enabled = False


def _is_truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in ("1", "true", "yes", "on")


def configure_tracing(env: Mapping[str, str] | None = None) -> bool:
    """Set up tracing if requested and available. Returns whether it is active.

    Activated by ``OTEL_TRACES_ENABLED=1``. Requires the ``otel`` extra; if it
    is missing, logs a warning and stays disabled (no crash).
    """
    global _enabled
    env = os.environ if env is None else env

    if not _is_truthy(env.get("OTEL_TRACES_ENABLED")):
        _enabled = False
        return False

    if not _OTEL_AVAILABLE:
        logger.warning(
            "OTEL_TRACES_ENABLED is set but OpenTelemetry is not installed. "
            "Install the extra: pip install 'swiss-transport-mcp[otel]'."
        )
        _enabled = False
        return False

    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

    provider = TracerProvider(
        resource=Resource.create({"service.name": "swiss-transport-mcp"})
    )
    # stderr exporter so stdout stays clean for the stdio transport (OBS-004).
    provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter(out=sys.stderr)))
    _otel_trace.set_tracer_provider(provider)
    _enabled = True
    logger.info("OpenTelemetry tracing enabled (stderr console exporter).")
    return True


@contextmanager
def span(name: str, **attributes: object) -> Iterator[object | None]:
    """Start a span if tracing is active, else a zero-overhead no-op."""
    if not (_enabled and _OTEL_AVAILABLE):
        yield None
        return
    tracer = _otel_trace.get_tracer("swiss-transport-mcp")
    with tracer.start_as_current_span(name) as current:
        for key, value in attributes.items():
            if value is not None:
                current.set_attribute(key, value)
        yield current
