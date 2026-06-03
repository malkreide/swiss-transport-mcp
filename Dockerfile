# syntax=docker/dockerfile:1

# ---------------------------------------------------------------------------
# Stage 1: builder – install the package into an isolated virtualenv
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /build

# Create a self-contained venv we can copy verbatim into the runtime stage.
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy only what is needed to build the wheel first (better layer caching).
COPY pyproject.toml README.md LICENSE ./
COPY src ./src

RUN pip install --upgrade pip && pip install .

# ---------------------------------------------------------------------------
# Stage 2: runtime – minimal, non-root, only the venv + source
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

# SEC-007: run as an unprivileged user with a minimal image surface.
RUN useradd --create-home --uid 10001 appuser

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    # Container networking is isolated → binding to all interfaces is intended.
    MCP_TRANSPORT=streamable-http \
    MCP_HOST=0.0.0.0 \
    MCP_PORT=8000

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app
USER appuser

EXPOSE 8000

# Default to the Streamable HTTP transport for cloud/container deployment.
CMD ["swiss-transport-mcp"]
