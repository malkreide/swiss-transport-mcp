# Audit Trend — `swiss-transport-mcp`

Soll/Ist across all mcp-audit runs (catalog v0.5.0, `catalog_hash` `091f446b…`,
44 applicable checks each — fully reproducible).

| Run | Date (UTC) | pass | fail | partial | todo | Production-ready | Blocking |
|---|---|---:|---:|---:|---:|:--:|---|
| 1 — initial | 2026-06-03T064903-Z | 16 | 4 | 22 | 2 | ❌ NO | SEC-016 |
| 2 — post-remediation | 2026-06-03T082024-Z | 37 | 0 | 5 | 2 | ✅ YES | — |
| 3 — confirming | 2026-06-03T083922-Z | **41** | **0** | **1** | **2** | ✅ **YES** | — |

## What changed between runs

**Run 1 → 2** (PRs #2–#10): fixed the SEC-016 blocker plus the full hardening
sweep — egress allow-list/TLS guard (SEC-004/005/021), CORS (SDK-004), lifespan
+ pooling (SDK-001), typed returns (SDK-002), Context (SDK-003), Streamable HTTP
(SCALE-001), Docker (SEC-007/SCALE-004/006), stderr+JSON logging (OBS-003/004),
error masking (OBS-002), opt-in OTel (OBS-006), prompt (ARCH-008), version pins
(ARCH-012), test suite (OPS-001), and docs (SEC-008/009, .gitignore/SEC-013).

**Run 2 → 3** (PRs #12–#13): closed the remaining server-local partials —
ARCH-009 (annotations on all tools), SEC-022 (tool-hash pinning),
SCALE-002/003 (stateless mode removes sticky-LB need); and formally accepted
SEC-014/SEC-015 as residual risk (RA-001/RA-002).

## Final residual items

| Check | Status | Why it stays open |
|---|---|---|
| SEC-009 | partial | User-identity session binding needs auth; this server is `auth_model: none`. Residual impact negligible (read-only public data); documented mitigations in `SECURITY.md`. |
| SEC-014 | accepted (todo) | Gateway-level tool allow-listing — `RISK-ACCEPTANCES.md` RA-001. |
| SEC-015 | accepted (todo) | Gateway-level tool-poisoning detection — RA-002; local guard via SEC-022. |

No open `fail`. No `critical`/`high` blocker. The server is production-ready per
the catalogue, with the three residual items governed and time-bound for review.
