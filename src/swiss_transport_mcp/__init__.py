"""Swiss Transport MCP Server – Complete Swiss public transport data from opentransportdata.swiss.

10 tools covering journey planning (OJP), real-time departures, disruptions (SIRI-SX),
occupancy forecasts, ticket prices (OJP Fare), train formations, stop search,
and dataset catalog access via the Model Context Protocol.
"""

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _distribution_version

try:
    # Read the version from the installed distribution metadata, which is built
    # from pyproject.toml. Hand-maintaining the literal here let the numbers
    # drift apart: pyproject said 0.3.3, this said 0.2.0. A value nobody
    # has to remember to bump cannot go stale.
    __version__ = _distribution_version("swiss-transport-mcp")
except PackageNotFoundError:
    # Running from the source tree without an install (e.g. a bare checkout).
    # Deliberately not a plausible-looking number: an obviously non-release
    # marker is better than a wrong version in the User-Agent.
    __version__ = "0.0.0+source"
