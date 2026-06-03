# Risk Acceptance Register

Formal record of audit findings that are **accepted as residual risk** rather
than remediated in this repository, because the appropriate control lives at
the portfolio / MCP-gateway layer. Each acceptance is time-bound by explicit
re-evaluation triggers.

| Field | Value |
|---|---|
| Server | `swiss-transport-mcp` |
| Audit catalog | mcp-audit v0.5.0 (`catalog_hash` `091f446b…`) |
| Risk owner | Hayal Oezkan ([@malkreide](https://github.com/malkreide)) |
| Decision date | 2026-06-03 |
| Next review | 2026-12-03, or earlier on any trigger below |
| Server profile | read-only · Public Open Data · no PII · `auth_model: none` · single trusted upstream (`opentransportdata.swiss`) |

---

## RA-001 — SEC-014: Tool allow-listing via an MCP gateway

| | |
|---|---|
| **Finding** | SEC-014 (severity: medium) |
| **Status** | `accepted-risk` |
| **Decision** | Accepted at the server level; to be implemented at the gateway. |

**Rationale.** A per-tool allow-list is a property of the MCP host/gateway that
aggregates multiple servers, not of a single server exposing a fixed, fully
read-only tool set. Implementing it here would not constrain a compromised host
and would duplicate a control that belongs one layer up.

**Compensating controls already in place.**
- All 11 tools are read-only (`readOnlyHint`, no write/destructive operations).
- Egress is restricted to an HTTPS allow-list (`opentransportdata.swiss`) — a
  tool cannot reach arbitrary hosts even if invoked (SEC-004/021).
- The tool surface is hash-pinned and drift-checked (SEC-022).

**Residual risk.** Low. Worst case is unrestricted invocation of read-only,
public-data queries.

---

## RA-002 — SEC-015: Pre-flight tool-poisoning detection

| | |
|---|---|
| **Finding** | SEC-015 (severity: medium) |
| **Status** | `accepted-risk` |
| **Decision** | Accepted at the server level; cross-server detection belongs to the gateway/host. |

**Rationale.** Tool-poisoning / rug-pull detection across servers is a
supply-chain and host responsibility. This server registers no tools
dynamically or from remote sources; its tool definitions ship from this
version-controlled repository.

**Compensating controls already in place.**
- **SEC-022 tool-hash pinning** (`src/swiss_transport_mcp/tool_manifest.json`)
  fingerprints every tool's behaviour-defining surface and verifies it at
  startup and in CI — any local drift is detected and must be a reviewed change.
- No dynamic/remote tool registration exists in the codebase.

**Residual risk.** Low for this server in isolation; the cross-server detection
gap is owned at the portfolio level.

---

## Re-evaluation triggers

Both acceptances above are **void** and the controls must be implemented if the
server ever:

1. gains **write** capability or starts processing **PII**, or
2. registers tools **dynamically** / from remote sources, or
3. is aggregated behind a shared MCP gateway — at which point SEC-014 and
   SEC-015 are implemented **there**, and these acceptances are closed.

See [`../SECURITY.md`](../SECURITY.md) for the broader security posture.
