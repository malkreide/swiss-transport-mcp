"""HTTP client for opentransportdata.swiss APIs.

Handles two fundamentally different API styles:
- OJP: XML SOAP-like (POST with XML body to single endpoint)
- CKAN: REST/JSON (GET with query parameters)

Both require Bearer token authentication from the API-Manager.
"""

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger("swiss-transport-mcp")

# API endpoints
OJP_V2_URL = "https://api.opentransportdata.swiss/ojp20"
OJP_V1_URL = "https://api.opentransportdata.swiss/ojp2020"
CKAN_API_URL = "https://api.opentransportdata.swiss/ckan-api"

# Timeouts
DEFAULT_TIMEOUT = 30.0
OJP_TIMEOUT = 45.0  # OJP trip calculations can take longer


def _get_api_key(env_var: str) -> str | None:
    """Get API key from environment variable."""
    return os.environ.get(env_var)


def _get_ojp_key() -> str:
    """Get OJP API key, with fallback."""
    key = _get_api_key("TRANSPORT_OJP_API_KEY")
    if not key:
        key = _get_api_key("TRANSPORT_API_KEY")  # Unified key fallback
    if not key:
        raise ValueError(
            "No OJP API key found. Set TRANSPORT_OJP_API_KEY or TRANSPORT_API_KEY. "
            "Get a free key at https://api-manager.opentransportdata.swiss/"
        )
    return key


def _get_ckan_key() -> str:
    """Get CKAN API key, with fallback."""
    key = _get_api_key("TRANSPORT_CKAN_API_KEY")
    if not key:
        key = _get_api_key("TRANSPORT_API_KEY")
    if not key:
        raise ValueError(
            "No CKAN API key found. Set TRANSPORT_CKAN_API_KEY or TRANSPORT_API_KEY. "
            "Get a free key at https://api-manager.opentransportdata.swiss/"
        )
    return key


# ---------------------------------------------------------------------------
# OJP API (XML/SOAP)
# ---------------------------------------------------------------------------

async def ojp_request(xml_body: str, version: str = "v2") -> str:
    """Send an OJP XML request and return the XML response.

    Args:
        xml_body: Complete OJP XML request string
        version: "v1" for OJP 1.0, "v2" for OJP 2.0

    Returns:
        Raw XML response string

    Raises:
        httpx.HTTPStatusError: On HTTP errors
        ValueError: On missing API key
    """
    url = OJP_V2_URL if version == "v2" else OJP_V1_URL
    api_key = _get_ojp_key()

    headers = {
        "Content-Type": "application/xml",
        "Authorization": f"Bearer {api_key}",
    }

    verify = os.environ.get("TRANSPORT_SSL_VERIFY", "true").lower() != "false"
    async with httpx.AsyncClient(timeout=OJP_TIMEOUT, verify=verify) as client:
        response = await client.post(url, content=xml_body, headers=headers)
        response.raise_for_status()
        return response.text


# ---------------------------------------------------------------------------
# CKAN API (REST/JSON)
# ---------------------------------------------------------------------------

async def ckan_request(action: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    """Make a CKAN API request.

    Args:
        action: CKAN action (e.g., "package_list", "package_show")
        params: Query parameters

    Returns:
        Parsed JSON response dict

    Raises:
        httpx.HTTPStatusError: On HTTP errors
        ValueError: On missing API key or CKAN errors
    """
    ckan_url = os.environ.get("TRANSPORT_CKAN_URL", CKAN_API_URL)
    url = f"{ckan_url}/{action}"

    # CKAN may work without auth on some endpoints
    headers = {}
    try:
        api_key = _get_ckan_key()
        headers["Authorization"] = f"Bearer {api_key}"
    except ValueError:
        logger.info("No CKAN API key configured – trying without auth")

    verify = os.environ.get("TRANSPORT_SSL_VERIFY", "true").lower() != "false"
    async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, verify=verify) as client:
        response = await client.get(url, params=params or {}, headers=headers)

        if response.status_code == 403:
            raise ValueError(
                "CKAN API returned 403 Forbidden. The CKAN datasets API may "
                "require a separate subscription on api-manager.opentransportdata.swiss. "
                "Subscribe to the 'CKAN' API product in the API Manager portal."
            )

        response.raise_for_status()
        data = response.json()

        if not data.get("success"):
            error = data.get("error", {})
            msg = error.get("message", str(error))
            raise ValueError(f"CKAN API error: {msg}")

        return data.get("result", {})


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

def handle_api_error(e: Exception) -> str:
    """Format API errors into user-friendly messages."""
    if isinstance(e, httpx.HTTPStatusError):
        status = e.response.status_code
        if status == 401:
            return (
                "Error: Authentication failed (401). Your API key may be invalid or expired. "
                "Get a new key at https://api-manager.opentransportdata.swiss/"
            )
        elif status == 403:
            return "Error: Access forbidden (403). Your API key may not have access to this API."
        elif status == 429:
            return "Error: Rate limit exceeded (429). Please wait a moment before retrying."
        elif status == 500:
            return "Error: Server error (500). The opentransportdata.swiss service may be experiencing issues."
        else:
            return f"Error: HTTP {status} – {e.response.text[:200] if e.response.text else 'No details'}"
    elif isinstance(e, httpx.TimeoutException):
        return "Error: Request timed out. The OJP service may be busy – try again in a few seconds."
    elif isinstance(e, ValueError):
        return f"Error: {str(e)}"
    else:
        return f"Error: {type(e).__name__} – {str(e)}"
