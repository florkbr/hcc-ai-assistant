# AI Assistant Service

HTTP-based AI assistant service using LightSpeed stack with Google Vertex AI and MCP (Model Context Protocol) discovery capabilities.

## Overview

This project provides a production-ready AI assistant with:
- **Google Vertex AI** integration via LightSpeed Core
- **MCP Tool Discovery** - automatically discovers and indexes available MCP tools
- **Vector Embeddings** - semantic search powered by sentence-transformers + pgvector
- **Subprocess Architecture** - all services run in a single container, communicating via localhost

All services are built with **Python** for a unified development experience.

## Architecture

All three services run as subprocesses within a single container, managed by `entrypoint.py`:

```
┌────────────────────────────────────────────────┐
│ Container: api                                 │
│                                                │
│  ┌──────────────────────┐                     │
│  │ Reverse Proxy        │  port 8000          │
│  │ + LightSpeed Stack   │◄────────────────────┤─ Public
│  │ - Google Vertex AI   │                     │
│  │ - RAG capabilities   │                     │
│  │ - Conversation cache │                     │
│  └───────┬──────────────┘                     │
│          │ localhost:8001/mcp                 │
│          ▼                                     │
│  ┌──────────────────────┐                     │
│  │ MCP Discovery        │  port 8001          │
│  │ (Python/FastMCP)     │                     │
│  │ - MCP Server         │                     │
│  │ - 4 MCP Tools        │                     │
│  │ - Tool Discovery     │                     │
│  └───────┬──────────────┘                     │
│          │ localhost:8002                     │
│          ▼                                     │
│  ┌──────────────────────┐                     │
│  │ Embedding Service    │  port 8002          │
│  │ (Python/FastAPI)     │                     │
│  │ - Embeddings         │                     │
│  │ - Vector Store       │                     │
│  │ - pgvector           │                     │
│  └──────────────────────┘                     │
└────────────────────────────────────────────────┘
```

**Startup Order**: embedding-service -> mcp-discovery-service -> lightspeed-stack

For architecture decisions and patterns, see [Architecture Guidelines](./docs/architecture-guidelines.md).

## Quick Start

### Docker Compose (Recommended for Local Development)

```bash
# Copy environment template
cp .env.example .env

# Edit .env with your values:
# VERTEX_PROJECT=your-project-id
# VERTEX_LOCATION=your-location
# ALLOWED_MODEL=your-model-name
# GOOGLE_API_KEY=your-api-key

# Start all services
docker compose up -d --build

# Check health of all services
curl http://localhost:8000/liveness   # Proxy liveness
curl http://localhost:8000/readiness  # Proxy readiness (checks backend)
curl http://localhost:8001/health     # MCP Discovery
curl http://localhost:8002/health     # Embedding Service
```

Services will be available at:
- **LightSpeed Stack**: http://localhost:8000
- **MCP Discovery**: http://localhost:8001
- **Embedding Service**: http://localhost:8002

### Test the AI Assistant

```bash
curl -X POST http://localhost:8000/v1/query \
  -H "Content-Type: application/json" \
  -H "x-rh-identity: test" \
  -d '{
    "query": "What MCP tools are available?",
    "provider": "google-vertex",
    "model": "google-vertex/google/gemini-2.5-flash"
  }'
```

The LLM will automatically discover and use MCP tools to answer questions.

## Services

### 1. LightSpeed Stack (Port 8000)
Main AI assistant service powered by Google Vertex AI.
- Google Vertex AI integration (Gemini models)
- RAG (Retrieval Augmented Generation)
- Conversation caching
- MCP tool discovery integration

### 2. MCP Discovery Service (Port 8001)
Discovers and indexes MCP tools from configured servers, exposing them via the MCP protocol.
- Full MCP protocol server (FastMCP SDK)
- 4 MCP tools: search, list, get_schema, recommend
- Vector-based semantic search + keyword fallback
- Background refresh every 5 minutes

[Full Documentation](./mcp-discovery-service/README.md)

### 3. Embedding Service (Port 8002)
Unified service for text embeddings and vector storage.
- Text embeddings via sentence-transformers
- Vector storage via pgvector (PostgreSQL)
- llama-stack compatible API

[Full Documentation](./embedding-service/README.md)

## Configuration

### Required Environment Variables

Create a `.env` file with:

```bash
# Google Cloud / Vertex AI
VERTEX_PROJECT=your-project-id
VERTEX_LOCATION=your-location
ALLOWED_MODEL=gemini-2.5-flash
GOOGLE_API_KEY=your-api-key

# Optional: Enable vector embeddings (enabled by default in docker-compose)
ENABLE_VECTOR_STORE=true
```

For the full list of environment variables, see [AGENTS.md](./AGENTS.md#environment-variables).

### MCP Server Configuration

MCP servers to discover are configured in `lightspeed-stack.yaml` (the `mcp_servers` section):

```yaml
mcp_servers:
  - name: "my-mcp-server"
    provider_id: "my-mcp-provider"
    url: "http://my-mcp-server:3001/mcp"
```

Only `mcp-discovery-server` is statically configured. Other servers (RBAC, Notifications, etc.) are injected dynamically via the `CLOWDER_MCP_SERVER_CONFIGS` env var at startup.

### Adding MCP Servers Locally

To register MCP servers for local development, edit `local_mcp_server_configs.json` in the project root:

```json
{
  "my-mcp-server": {
    "provider_id": "my-mcp-provider",
    "url": "http://localhost:9000/mcp/",
    "headers": ["x-rh-identity"]
  }
}
```

Each entry requires:
- **key**: A unique server name (e.g. `"my-mcp-server"`)
- **`provider_id`**: Unique provider identifier used in the LightSpeed stack tool runtime
- **`url`**: The MCP server endpoint URL

Optional fields:
- **`headers`**: List of HTTP headers to forward to the MCP server
- **`clowder_app`**: Clowder application name for automatic URL resolution in-cluster
- **`clowder_service`**: Clowder service name (used with `clowder_app` to match the correct endpoint)
- **`mcp_server_path`**: Path appended to the resolved Clowder URL (default: `"/"`)

The entrypoint loads this file as a fallback when the `CLOWDER_MCP_SERVER_CONFIGS` environment variable is not set. In deployed environments, the env var is populated from a ConfigMap via app-interface.

## Development

For local development setup and deployment instructions, see [Deployment Guidelines](./docs/deployment-guidelines.md).

For testing instructions, see [Testing Guidelines](./docs/testing-guidelines.md).

For code style and commands, see [CLAUDE.md](./CLAUDE.md).

## Contributing

### Pull Requests

1. Create a feature branch
2. Add tests for new functionality
3. Ensure all tests pass (`pytest`)
4. Format code (`black .`)
5. Update relevant READMEs

## License

See LICENSE file for details.
