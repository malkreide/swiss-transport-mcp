"""Tests for tool annotations (ARCH-009), tool-hash pinning (SEC-022) and the
stateless-HTTP resolver (SCALE-002/003)."""

import asyncio

from swiss_transport_mcp import server
from swiss_transport_mcp.tool_integrity import (
    fingerprint_tools,
    load_pinned_manifest,
    verify_integrity,
)


def _tools():
    return asyncio.run(server.mcp.list_tools())


# ---------------------------------------------------------------------------
# ARCH-009 — every tool declares annotations (incl. the extension tools)
# ---------------------------------------------------------------------------

def test_all_tools_declare_readonly_annotations():
    offenders = []
    for tool in _tools():
        ann = tool.annotations
        data = ann.model_dump() if hasattr(ann, "model_dump") else ann
        if not data or data.get("readOnlyHint") is not True:
            offenders.append(tool.name)
    assert not offenders, f"tools missing readOnlyHint annotation: {offenders}"


# ---------------------------------------------------------------------------
# SEC-022 — live tool surface matches the pinned manifest
# ---------------------------------------------------------------------------

def test_live_fingerprint_matches_pinned_manifest():
    pinned = load_pinned_manifest()
    assert pinned, "tool_manifest.json must exist (SEC-022 pin)"
    current = fingerprint_tools(_tools())
    result = verify_integrity(current, pinned)
    assert result["consistent"], (
        "Tool surface drifted from the pinned manifest. If intentional, "
        f"regenerate tool_manifest.json. Detail: {result}"
    )


def test_all_tools_in_transport_domain():
    # Tool names are not a single uniform prefix (transport_/get_transport_/
    # get_train_/get_ticket_/check_transport_), but all sit in the transport
    # domain — full prefix unification would be a breaking rename (ARCH-001).
    names = [t.name for t in _tools()]
    assert all(("transport" in n) or ("train" in n) or ("ticket" in n) for n in names), names


def test_verify_integrity_flags_drift():
    pinned = {"a": "h1", "b": "h2"}
    assert verify_integrity({"a": "h1", "b": "h2"}, pinned)["consistent"] is True
    changed = verify_integrity({"a": "h1", "b": "DIFFERENT"}, pinned)
    assert changed["consistent"] is False
    assert changed["changed"] == ["b"]
    moved = verify_integrity({"a": "h1", "c": "h3"}, pinned)
    assert moved["added"] == ["c"]
    assert moved["removed"] == ["b"]


# ---------------------------------------------------------------------------
# SCALE-002/003 — stateless resolver
# ---------------------------------------------------------------------------

def test_stateless_default_off():
    assert server._resolve_stateless(env={}) is False


def test_stateless_enabled_by_env():
    assert server._resolve_stateless(env={"MCP_STATELESS": "1"}) is True
    assert server._resolve_stateless(env={"MCP_STATELESS": "true"}) is True
    assert server._resolve_stateless(env={"MCP_STATELESS": "0"}) is False
