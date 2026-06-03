# Security Policy & Posture

`swiss-transport-mcp` was hardened against the internal MCP best-practice audit
catalogue. This document summarises the security posture and records the
**accepted-risk** decisions for controls that are deliberately handled at the
portfolio/gateway layer rather than inside this single server.

## Reporting a vulnerability

Please open a private security advisory on the GitHub repository, or contact the
maintainer listed in `README.md`. Do not file public issues for exploitable
vulnerabilities.

## Posture summary

This is a **read-only**, **no-PII**, **public-open-data** MCP server. All 11
tools only query opentransportdata.swiss. Hardening already in place:

| Area | Control |
|---|---|
| Egress | HTTPS-enforced allow-list to `opentransportdata.swiss` only (SEC-004/021) |
| TLS | Verification on by default; only disablable in a `dev` environment (SEC-005) |
| Binding | Network transports default to `127.0.0.1` (SEC-016) |
| Transport | Streamable HTTP with CORS exposing only `Mcp-Session-Id` (SDK-004) |
| Input | Pydantic v2 strict validation + XML escaping at all boundaries (SEC-018) |
| Secrets | Env-vars only, `.gitignore` guards `.env`, no hardcoded secrets (ARCH-005/SEC-013) |
| Errors | Upstream bodies logged to stderr, never forwarded to the model (OBS-002) |
| Stdout | Reserved for the JSON-RPC stream; logging pinned to stderr (OBS-004) |

See `audits/` for the full report and `CHANGELOG.md` for the hardening history.

## Accepted risks (portfolio-level controls)

The following audit checks are **not** implemented inside this server by design.
They are portfolio-wide concerns best enforced at an MCP gateway / host layer,
and the residual risk here is low because the server is read-only and only
reaches a single trusted public-data provider.

### SEC-014 — Tool allow-listing via an MCP gateway

**Status:** accepted risk (portfolio-level).
A per-tool allow-list belongs to the MCP host/gateway that aggregates multiple
servers, not to an individual server that exposes a fixed, read-only tool set.
If/when a central gateway is introduced for the portfolio, tool allow-listing
should be configured there. Until then, the risk is bounded: every tool is
read-only and constrained by the egress allow-list above.

### SEC-015 — Pre-flight tool-poisoning detection

**Status:** accepted risk (portfolio-level).
Tool-poisoning (malicious tool descriptions / rug-pulls) is a supply-chain and
host-side concern. This server's tool definitions are version-controlled, namespace
-prefixed (`transport_*` / `get_transport_*`), and shipped from this repository;
there is no dynamic/remote tool registration. Detection of poisoned tools across
servers is again a gateway/host responsibility and is tracked at the portfolio
level rather than duplicated per server.

## Re-evaluation triggers

These acceptances should be revisited if the server ever:

- gains **write** capability or starts processing **PII**, or
- registers tools **dynamically** / from remote sources, or
- is aggregated behind a shared MCP gateway (then implement SEC-014/015 there).
