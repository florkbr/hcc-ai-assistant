# MCP Discovery Service

Python implementation of the MCP Discovery Service - discovers and indexes MCP tools with vector embeddings using the official Model Context Protocol.

## Features

- **MCP Protocol Server**: Full MCP protocol implementation using official Python SDK
- **MCP Discovery**: Automatically discovers tools from configured MCP servers
- **Vector Embeddings**: Semantic search using embedding-service for embeddings
- **Keyword Fallback**: Falls back to keyword search if vector search unavailable
- **Background Refresh**: Automatically refreshes capabilities every 5 minutes
- **4 MCP Tools**: Exposes discovery capabilities via MCP protocol

## Quick Start

### Local Development

```bash
cd mcp-discovery-service

# Create virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -e ".[dev]"

# Run the service
python main.py
```

### Docker

```bash
docker build -t mcp-discovery-service:latest .

# Run with defaults (host=0.0.0.0, port=8001)
docker run -p 8001:8001 \
  -v $(pwd)/../lightspeed-stack.yaml:/app-root/lightspeed-stack.yaml:ro \
  -e ENABLE_VECTOR_STORE=true \
  -e EMBEDDING_SERVICE_URL=http://embedding-service:8002 \
  mcp-discovery-service:latest

# Override port
docker run -p 9000:9000 \
  -e PORT=9000 \
  -v $(pwd)/../lightspeed-stack.yaml:/app-root/lightspeed-stack.yaml:ro \
  mcp-discovery-service:latest

# Use IPv6/dual-stack
docker run -p 8001:8001 \
  -e HOST=:: \
  -v $(pwd)/../lightspeed-stack.yaml:/app-root/lightspeed-stack.yaml:ro \
  mcp-discovery-service:latest
```

### Docker Compose

See [Deployment Guidelines](../docs/deployment-guidelines.md) for Docker Compose setup.

## MCP Protocol

The service runs a full MCP protocol server on port 8001 using Streamable HTTP transport from the official Python MCP SDK.

### Health Check Endpoint

**GET /health** - Kubernetes health probe

**Response:**
```json
{
  "status": "healthy",
  "total_capabilities": 42,
  "last_refresh": "2026-03-05T10:30:00",
  "server": "mcp-discovery-service",
  "protocol": "mcp"
}
```

### MCP Tools

The service exposes 4 MCP tools accessible via the MCP protocol:

1. **search_mcp_tools** - Semantic search for MCP tools
   - Uses vector embeddings for natural language queries
   - Falls back to keyword search if vector store unavailable

2. **list_all_capabilities** - List all discovered MCP tools
   - Returns complete list of indexed capabilities
   - Includes tool names, descriptions, schemas

3. **get_tool_schema** - Get detailed schema for a specific tool
   - Fetch full JSON schema for any discovered tool
   - Useful for understanding tool parameters

4. **recommend_tools** - Get tool recommendations based on task
   - Provide a task description, get relevant tool suggestions
   - Uses semantic search to find best matches

### Integration with LightSpeed Core

LightSpeed Core automatically discovers and uses these MCP tools. When users ask questions like "What MCP tools are available?", the LLM will:

1. Connect to mcp-discovery-service via MCP protocol
2. Use the appropriate MCP tool (e.g., `search_mcp_tools`)
3. Receive tool information
4. Provide answer to user

No manual API calls needed - the MCP protocol handles everything.

## Configuration

Environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `HOST` | `0.0.0.0` | Server host (use `::` for IPv6/dual-stack) |
| `PORT` | `8001` | Server port |
| `MCP_CONFIG_PATH` | `/app-root/lightspeed-stack.yaml` | MCP servers config (reads mcp_servers section) |
| `CAPABILITIES_CACHE_PATH` | `/app-root/data/mcp-capabilities.json` | JSON cache file for capabilities |
| `REFRESH_INTERVAL_MINUTES` | 5 | Auto-refresh interval |
| `LOG_LEVEL` | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |
| `ENABLE_VECTOR_STORE` | `false` | Enable semantic search via the embedding service |
| `EMBEDDING_SERVICE_URL` | `http://localhost:8002` | Embedding service URL (localhost in K8s/sidecar) |
| `EMBEDDING_SERVICE_TIMEOUT` | `120` | Timeout in seconds for embedding service requests |
| `VECTOR_STORE_ID` | `mcp-capabilities-store` | Vector store ID for the embedding service |
| `EMBEDDING_MODEL` | `sentence-transformers/all-mpnet-base-v2` | Embedding model |

**Note on HOST values:**
- `0.0.0.0` - IPv4 only (default, works in most environments)
- `::` - IPv6/dual-stack (use for IPv6-only or dual-stack OpenShift clusters)

## MCP Servers Configuration

The service reads MCP servers from `lightspeed-stack.yaml` (the `mcp_servers` section):

```yaml
mcp_servers:
  - name: "example-mcp-server"
    provider_id: "example-provider"
    url: "http://example-server:3001/mcp"
```

In Kubernetes/OpenShift, this is managed via ConfigMap (mounted as lightspeed-stack.yaml).

## Architecture

See [Architecture Guidelines](../docs/architecture-guidelines.md) for the system architecture and sidecar pattern.

## Search Modes

### 1. Semantic Search (when ENABLE_VECTOR_STORE=true)
- Uses vector embeddings for semantic understanding
- Calls embedding-service to generate query embedding
- Queries vector store for similar tools
- Best for natural language queries

### 2. Keyword Search (fallback)
- Case-insensitive substring matching
- Searches tool names, descriptions, server names
- Fast and reliable
- Always available as fallback

## Testing

### Running Tests

The service includes comprehensive test coverage using pytest with modern best practices.

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run all tests
pytest

# Run with verbose output
pytest -v

# Run with coverage
pytest --cov=main --cov=mcp_server --cov-report=html
open htmlcov/index.html

# Run specific test file
pytest test_main.py
pytest test_mcp_server.py

# Run specific test
pytest test_main.py::test_config_defaults

# Run tests matching pattern
pytest -k "search"  # All search-related tests
pytest -k "vector"  # All vector-related tests
```

### Test Coverage

#### Core Service Logic (`test_main.py`)
- ✅ Configuration & environment variables
- ✅ Vector Store Client (embeddings, insertions, searches)
- ✅ MCP Indexer (config loading, capability discovery, keyword & semantic search)
- ✅ Capability persistence and refresh cycles

#### MCP Protocol Server (`test_mcp_server.py`)
- ✅ MCP server initialization and tool registration
- ✅ All 4 MCP tools (search, list, get_schema, recommend)
- ✅ Health checks and integration tests

See [Testing Guidelines](../docs/testing-guidelines.md) for test patterns and conventions.

## Development

See [CLAUDE.md](../CLAUDE.md) for code style commands and conventions.

## Dependencies

- **mcp**: Official Python MCP SDK for protocol implementation
- **starlette**: ASGI web framework for MCP server
- **uvicorn**: ASGI server
- **httpx**: HTTP client for embedding-service calls
- **PyYAML**: YAML configuration parsing
- **Pydantic**: Data validation

## Deployment

See [Deployment Guidelines](../docs/deployment-guidelines.md) for Kubernetes/OpenShift deployment and resource requirements.

## Troubleshooting

### Vector Search Not Working

**Symptoms**: Logs show "falling back to keyword search"

**Solution**:
```bash
# Check if embedding-service is reachable (via localhost in sidecar setup)
curl http://localhost:8002/health

# Check environment variables
echo $ENABLE_VECTOR_STORE  # Should be "true"
echo $EMBEDDING_SERVICE_URL  # Should be "http://localhost:8002"

# Check logs
docker compose logs lightspeed-stack | grep -i vector
```

### No Capabilities Found

**Symptoms**: Empty capabilities list in logs

**Solution**:
```bash
# Check MCP servers config
cat /app-root/lightspeed-stack.yaml

# Check if MCP servers are reachable
curl http://example-mcp-server:3001/mcp

# Check discovery logs
docker compose logs lightspeed-stack | grep -i discover
```

### MCP Protocol Connection Issues

**Symptoms**: LightSpeed Core can't connect to MCP server

**Solution**:
```bash
# Verify MCP server is running (port 8001, exposed via lightspeed-stack)
curl http://localhost:8001/health

# Check MCP port in docker-compose
docker-compose ps

# In sidecar setup, verify connectivity via localhost
docker-compose exec lightspeed-stack curl http://localhost:8001/health
```
