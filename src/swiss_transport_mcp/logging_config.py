"""Logging configuration (OBS-003 / OBS-004).

Logging always goes to **stderr** so stdout stays reserved for the JSON-RPC
protocol stream on stdio transport (OBS-004). With ``LOG_FORMAT=json`` the
output is structured JSON carrying the RFC 5424 numeric severity alongside the
stdlib level name, which downstream collectors / SIEM can parse directly.
"""

from __future__ import annotations

import json
import logging
import sys
from collections.abc import Mapping

# stdlib level name → RFC 5424 (syslog) numeric severity.
_RFC5424_SEVERITY: dict[str, int] = {
    "CRITICAL": 2,  # crit
    "ERROR": 3,  # err
    "WARNING": 4,  # warning
    "INFO": 6,  # informational
    "DEBUG": 7,  # debug
}

_TEXT_FORMAT = "%(asctime)s %(name)s %(levelname)s: %(message)s"


class JsonLogFormatter(logging.Formatter):
    """Render log records as one JSON object per line, with RFC 5424 severity."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "severity": _RFC5424_SEVERITY.get(record.levelname, 6),
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(env: Mapping[str, str] | None = None) -> logging.Handler:
    """Configure root logging to stderr. Returns the installed handler.

    ``LOG_LEVEL`` sets the level (default INFO). ``LOG_FORMAT=json`` switches
    to structured JSON output; anything else uses a human-readable text format.
    """
    import os

    env = os.environ if env is None else env
    level = env.get("LOG_LEVEL", "INFO").upper()
    fmt = env.get("LOG_FORMAT", "text").strip().lower()

    handler = logging.StreamHandler(sys.stderr)
    if fmt == "json":
        handler.setFormatter(JsonLogFormatter())
    else:
        handler.setFormatter(logging.Formatter(_TEXT_FORMAT))

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)
    return handler
