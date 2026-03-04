FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY pyproject.toml README.md ./
COPY src/ src/
RUN pip install --no-cache-dir -e .

# Expose port for SSE transport
EXPOSE 8000

# Default to SSE for cloud deployment
ENV MCP_TRANSPORT=sse
ENV MCP_HOST=0.0.0.0
ENV MCP_PORT=8000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
    CMD python -c "import swiss_transport_mcp; print('ok')" || exit 1

# Run server
CMD ["swiss-transport-mcp"]
