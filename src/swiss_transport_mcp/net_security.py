"""Network egress hardening for all outbound HTTP traffic.

Closes three audit findings at the HTTP boundary:

- **SEC-004 (SSRF / HTTPS-Enforcement):** every outgoing URL is checked to use
  the ``https`` scheme and to target a host on an explicit allow-list before a
  request is sent. The server only ever talks to opentransportdata.swiss, so any
  other host is a misconfiguration or an injection attempt and is refused.
- **SEC-005 / SEC-004 (TLS verification):** ``TRANSPORT_SSL_VERIFY=false`` is no
  longer silently honoured. TLS verification stays ON in production; it can only
  be disabled when the process is explicitly marked as a dev environment.
- **SEC-021 (Egress allow-list):** the host allow-list is the single code-layer
  control that also constrains the ``TRANSPORT_CKAN_URL`` override.

The allow-list is the deterministic control. DNS-pinning against rebinding
(TOCTOU) is intentionally out of scope here and tracked separately (SEC-005);
restricting to known public hosts already removes the practical SSRF surface,
since no user/LLM-supplied URL ever reaches the HTTP client.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Mapping
from urllib.parse import urlparse

logger = logging.getLogger("swiss-transport-mcp")

# Every upstream request must go to one of these hosts. Keep this minimal:
# adding a host here is an explicit decision to allow egress to it.
ALLOWED_EGRESS_HOSTS: frozenset[str] = frozenset(
    {
        "api.opentransportdata.swiss",
        "data.opentransportdata.swiss",
    }
)

# Process environments in which disabling TLS verification is tolerated.
_DEV_ENV_VALUES: frozenset[str] = frozenset({"dev", "development", "local", "test"})


class EgressNotAllowedError(ValueError):
    """Raised when an outbound URL violates the egress policy (scheme/host)."""


def validate_egress_url(url: str, *, allowed_hosts: frozenset[str] = ALLOWED_EGRESS_HOSTS) -> str:
    """Return ``url`` unchanged if it is allowed, else raise.

    A URL is allowed only when its scheme is ``https`` and its host is on the
    allow-list. This is enforced at every call site before a request is issued.
    """
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise EgressNotAllowedError(
            f"Only https:// egress is allowed, got scheme '{parsed.scheme or '(none)'}' in {url!r}"
        )
    host = (parsed.hostname or "").lower()
    if host not in allowed_hosts:
        raise EgressNotAllowedError(
            f"Egress to host '{host}' is not permitted. Allowed hosts: {sorted(allowed_hosts)}"
        )
    return url


def resolve_ssl_verify(env: Mapping[str, str] | None = None) -> bool:
    """Decide whether httpx should verify TLS certificates.

    Defaults to ``True``. ``TRANSPORT_SSL_VERIFY=false`` is only honoured when
    the process is explicitly a dev environment (``MCP_ENV``/``ENV`` in
    ``{dev, development, local, test}``); otherwise the request to disable it is
    ignored and verification stays on. Either way the decision is logged so a
    misconfiguration is visible in the logs.
    """
    env = os.environ if env is None else env
    disabled = env.get("TRANSPORT_SSL_VERIFY", "true").strip().lower() == "false"
    if not disabled:
        return True

    app_env = env.get("MCP_ENV", env.get("ENV", "")).strip().lower()
    if app_env in _DEV_ENV_VALUES:
        logger.warning(
            "TLS verification DISABLED via TRANSPORT_SSL_VERIFY=false (MCP_ENV=%s). "
            "Never use this outside local development.",
            app_env or "(unset)",
        )
        return False

    logger.warning(
        "Ignoring TRANSPORT_SSL_VERIFY=false: TLS verification stays ON outside a "
        "dev environment. Set MCP_ENV=dev to allow disabling it locally."
    )
    return True
