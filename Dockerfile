FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl \
        ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# Install uv for fast Python package management
RUN curl -LsSf https://astral.sh/uv/0.9.29/install.sh | sh
ENV PATH="/root/.local/bin:${PATH}"

WORKDIR /app

# Copy dependency files first for better caching
COPY requirements.txt pyproject.toml ./

# Install dependencies
RUN uv pip install --system -r requirements.txt

# Copy application code
COPY src/ ./src/

# Install the package in editable mode
RUN uv pip install --system -e .

# Environment variables (can be overridden at runtime)
ENV SURE_API_URL=""
ENV SURE_API_KEY=""
ENV SURE_ACCESS_TOKEN=""
ENV SURE_TIMEOUT="30"
ENV SURE_VERIFY_SSL="true"
ENV MCP_HOST="0.0.0.0"
ENV PORT="8000"
ENV MCP_PATH="/mcp"
ENV MCP_JSON_RESPONSE="true"
ENV MCP_STATELESS_HTTP="true"
ENV MCP_AUTH_TOKEN=""

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl --fail --silent http://127.0.0.1:${PORT}/health >/dev/null || exit 1

# Run the MCP server using Streamable HTTP transport
CMD ["python", "-m", "sure_mcp_server.server"]
