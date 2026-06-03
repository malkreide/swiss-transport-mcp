"""Tests for the network egress hardening (SEC-004, SEC-005, SEC-021)."""

import pytest

from swiss_transport_mcp.net_security import (
    ALLOWED_EGRESS_HOSTS,
    EgressNotAllowedError,
    resolve_ssl_verify,
    validate_egress_url,
)

# ---------------------------------------------------------------------------
# validate_egress_url — HTTPS enforcement + host allow-list
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "url",
    [
        "https://api.opentransportdata.swiss/ojp20",
        "https://api.opentransportdata.swiss/ckan-api/package_list",
        "https://data.opentransportdata.swiss/dataset/x",
    ],
)
def test_allows_listed_https_hosts(url):
    assert validate_egress_url(url) == url


def test_rejects_non_https_scheme():
    with pytest.raises(EgressNotAllowedError, match="https"):
        validate_egress_url("http://api.opentransportdata.swiss/ojp20")


def test_rejects_file_and_other_schemes():
    with pytest.raises(EgressNotAllowedError):
        validate_egress_url("file:///etc/passwd")


@pytest.mark.parametrize(
    "url",
    [
        "https://evil.example.com/steal",
        "https://api.opentransportdata.swiss.evil.com/x",  # suffix trick
        "https://169.254.169.254/latest/meta-data/",        # cloud metadata
        "https://127.0.0.1/admin",                          # localhost
        "https://10.0.0.5/internal",                        # private range
    ],
)
def test_rejects_offsite_and_internal_hosts(url):
    with pytest.raises(EgressNotAllowedError, match="not permitted"):
        validate_egress_url(url)


def test_host_match_is_case_insensitive():
    assert validate_egress_url("https://API.OpenTransportData.swiss/ojp20")


def test_allowlist_is_minimal():
    # Guard: only opentransportdata.swiss hosts are permitted.
    assert all(h.endswith("opentransportdata.swiss") for h in ALLOWED_EGRESS_HOSTS)


# ---------------------------------------------------------------------------
# resolve_ssl_verify — TLS verification guard
# ---------------------------------------------------------------------------

def test_ssl_verify_default_true():
    assert resolve_ssl_verify(env={}) is True


def test_ssl_verify_true_when_explicitly_true():
    assert resolve_ssl_verify(env={"TRANSPORT_SSL_VERIFY": "true"}) is True


def test_ssl_verify_disable_ignored_in_production():
    # No dev marker → disabling is refused, verification stays ON.
    assert resolve_ssl_verify(env={"TRANSPORT_SSL_VERIFY": "false"}) is True
    assert (
        resolve_ssl_verify(env={"TRANSPORT_SSL_VERIFY": "false", "MCP_ENV": "production"})
        is True
    )


@pytest.mark.parametrize("dev_env", ["dev", "development", "local", "test"])
def test_ssl_verify_disable_allowed_in_dev(dev_env):
    assert (
        resolve_ssl_verify(env={"TRANSPORT_SSL_VERIFY": "false", "MCP_ENV": dev_env})
        is False
    )


def test_ssl_verify_honours_env_alias():
    assert (
        resolve_ssl_verify(env={"TRANSPORT_SSL_VERIFY": "false", "ENV": "dev"}) is False
    )
