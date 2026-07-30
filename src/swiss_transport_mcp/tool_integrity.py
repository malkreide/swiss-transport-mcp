"""Tool-hash pinning + integrity verification (SEC-022).

A "rug pull" is when a tool's behaviour-defining surface (name, input/output
schema, annotations) silently changes after a client has already approved it.
This module pins a SHA-256 fingerprint per tool in a committed manifest
(``tool_manifest.json``) and verifies the live tool set against it:

- at **startup** (logged as a warning if drift is detected), and
- in **CI** via a test that fails if the live fingerprint diverges from the
  committed manifest — forcing any tool-surface change to be an explicit,
  reviewed manifest update.

Combined with the mandatory ``transport_`` / ``get_transport_`` namespace
prefix, this is the SEC-022 control.
"""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger("swiss-transport-mcp")

MANIFEST_PATH = Path(__file__).parent / "tool_manifest.json"


def _annotations_dict(annotations: Any) -> Any:
    if annotations is None:
        return None
    if hasattr(annotations, "model_dump"):
        return annotations.model_dump(exclude_none=True, by_alias=True)
    if isinstance(annotations, dict):
        return annotations
    return str(annotations)


def fingerprint_tools(tools: list[Any]) -> dict[str, str]:
    """Return ``{tool_name: sha256}`` over each tool's behaviour-defining surface.

    The fingerprint covers name, input schema, output schema and annotations —
    the parts a client relies on when approving a tool. Description text is
    intentionally excluded so doc tweaks don't trip the pin.
    """
    fingerprints: dict[str, str] = {}
    for tool in tools:
        material = json.dumps(
            {
                "name": tool.name,
                "inputSchema": getattr(tool, "input_schema", None),
                "outputSchema": getattr(tool, "output_schema", None),
                "annotations": _annotations_dict(getattr(tool, "annotations", None)),
            },
            sort_keys=True,
            ensure_ascii=False,
            default=str,
        )
        fingerprints[tool.name] = hashlib.sha256(material.encode("utf-8")).hexdigest()
    return fingerprints


def load_pinned_manifest(path: Path = MANIFEST_PATH) -> dict[str, str]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def verify_integrity(current: dict[str, str], pinned: dict[str, str]) -> dict[str, Any]:
    """Compare live fingerprints against the pinned manifest."""
    added = sorted(set(current) - set(pinned))
    removed = sorted(set(pinned) - set(current))
    changed = sorted(k for k in current if k in pinned and current[k] != pinned[k])
    return {
        "consistent": not (added or removed or changed),
        "added": added,
        "removed": removed,
        "changed": changed,
    }


def write_manifest(fingerprints: dict[str, str], path: Path = MANIFEST_PATH) -> None:
    """Persist a manifest (used to (re)generate the pin after a reviewed change)."""
    path.write_text(
        json.dumps(fingerprints, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def check_tools_against_manifest(tools: list[Any]) -> dict[str, Any]:
    """Fingerprint ``tools`` and verify against the committed manifest.

    Logs a warning on drift (possible rug-pull or an un-pinned change). Returns
    the verification result for programmatic use.
    """
    pinned = load_pinned_manifest()
    if not pinned:
        logger.warning("No tool_manifest.json found – tool-hash pinning (SEC-022) inactive.")
        return {"consistent": False, "added": [], "removed": [], "changed": [], "no_manifest": True}

    result = verify_integrity(fingerprint_tools(tools), pinned)
    if not result["consistent"]:
        logger.warning(
            "Tool integrity drift (SEC-022): added=%s removed=%s changed=%s. "
            "If this change is intentional, regenerate tool_manifest.json.",
            result["added"], result["removed"], result["changed"],
        )
    return result
