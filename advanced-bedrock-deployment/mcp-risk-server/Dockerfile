# Dockerfile for MCP Risk Scoring Server
# Deployed to AgentCore Runtime and accessed via AgentCore Gateway

FROM python:3.12-slim

# Install uv for fast dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set working directory
WORKDIR /app

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies using uv
RUN uv sync --frozen --no-dev

# Copy application code
COPY server.py .

# Expose the MCP server port (AgentCore MCP protocol expects port 8000)
EXPOSE 8000

# Run the MCP server with streamable HTTP transport
CMD ["uv", "run", "python", "server.py"]
