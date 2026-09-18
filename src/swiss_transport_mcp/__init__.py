"""Swiss Transport MCP Server – Complete Swiss public transport data from opentransportdata.swiss.

10 tools covering journey planning (OJP), real-time departures, disruptions (SIRI-SX),
occupancy forecasts, ticket prices (OJP Fare), train formations, stop search,
and dataset catalog access via the Model Context Protocol.
"""

from importlib.metadata import PackageNotFoundError
from importlib.metadata import metadata as _distribution_metadata
from importlib.metadata import version as _distribution_version

_DISTRIBUTION = "swiss-transport-mcp"

try:
    # Read the version from the installed distribution metadata, which is built
    # from pyproject.toml. Hand-maintaining the literal here let the numbers
    # drift apart: pyproject said 0.3.3, this said 0.2.0. A value nobody
    # has to remember to bump cannot go stale.
    __version__ = _distribution_version(_DISTRIBUTION)
except PackageNotFoundError:
    # Running from the source tree without an install (e.g. a bare checkout).
    # Deliberately not a plausible-looking number: an obviously non-release
    # marker is better than a wrong version in the User-Agent.
    __version__ = "0.0.0+source"


def _project_url(label: str) -> str | None:
    """The ``[project.urls]`` entry called ``label``, or ``None``.

    Same reasoning as ``__version__``: the URL already exists in
    ``pyproject.toml``, and spec ``2026-07-28`` wants it on the wire
    (``Implementation.websiteUrl``). Copying it into ``src/`` would create a
    second place to remember — the drift that put a wrong version into the
    User-Agent across this portfolio.

    ``None`` from a bare checkout, which is honest: no metadata, no URL. The
    field is optional on the wire, so an absent value omits it rather than
    announcing a guess.
    """
    try:
        entries = _distribution_metadata(_DISTRIBUTION).get_all("Project-URL") or []
    except PackageNotFoundError:
        return None
    prefix = f"{label}, "
    for entry in entries:
        if entry.startswith(prefix):
            return entry[len(prefix) :].strip() or None
    return None


__homepage__ = _project_url("Homepage")
