# Architecture Guidelines

## Sidecar Pod Pattern

All three services run as containers in a single Kubernetes pod. This is a deliberate architectural choice:

- **Localhost communication**: Services talk via `localhost` (no service discovery, no network overhead)
- **Atomic deployment**: All services deploy and scale together
- **Shared lifecycle**: If one container fails, the pod restarts
- **Startup ordering**: Health probes enforce the dependency chain

```text
embedding-service (port 8002)
      |
      v (health check passes)
mcp-discovery-service (port 8001)
      |
      v (health check passes)
lightspeed-stack (port 8080, internal)
      |
      v
reverse proxy (port 8000, public)
```

### When Adding a New Service

1. Add to `entrypoint.py`: subprocess start, health wait, signal handling
2. Add to `Dockerfile`: COPY source files, install dependencies
3. Add to `docker-compose.yml`: uses `network_mode: "service:lightspeed-stack"`
4. Add to `config/clowdapp.yaml`: as a sidecar container in the pod spec

## Entrypoint Orchestration

`entrypoint.py` is the single process that manages all others:

1. **Config rendering**: Reads template YAMLs, applies Clowder config, writes to `/app-root/`
2. **Subprocess management**: Starts each service as a subprocess with health checks
3. **Signal forwarding**: SIGTERM/SIGINT propagated to all children
4. **Proxy hosting**: Runs the reverse proxy in the main process (blocks until shutdown)

### Important: entrypoint.py is NOT a service

It does not expose any HTTP endpoints itself. It:
- Renders config files
- Starts subprocesses
- Runs the proxy (which IS an HTTP server)

## Reverse Proxy Pattern

`proxy.py` is a Starlette app that:
1. Strips the `/api/ai-assistant` prefix from incoming requests
2. Forwards to the LightSpeed backend on port 8080
3. Streams responses back to the client
4. Uses `httpx.AsyncClient` with 300s timeout for long AI inference calls

### Key Design Decisions

- **Streaming**: Uses `StreamingResponse` to avoid buffering large AI responses
- **Hop-by-hop headers**: Strips `host`, `transfer-encoding`, `content-length` headers
- **Catch-all routes**: All HTTP methods forwarded (GET, POST, PUT, DELETE, PATCH, OPTIONS, HEAD)
- **Error handling**: Returns 502 on backend connection failure

## MCP Integration Pattern

The system uses MCP (Model Context Protocol) at two levels:

### Level 1: Direct MCP Providers (run.yaml)

LightSpeed/llama-stack connects directly to MCP servers as tool providers:
- RBAC MCP server (cluster-internal)
- Notifications MCP server (cluster-internal)
- MCP Discovery server (localhost sidecar)

**Warning**: llama-stack tries ALL registered providers on each query. Unreachable providers cause 500 errors. Only enable providers reachable from the current environment.

### Level 2: MCP Discovery Service

The MCP Discovery Service is itself an MCP server that:
1. Reads `mcp_servers` from `lightspeed-stack.yaml`
2. Connects to each configured MCP server via Streamable HTTP transport
3. Discovers their tools (name, description, input schema)
4. Indexes tools in the vector store for semantic search
5. Exposes 4 discovery tools via the MCP protocol
6. Background-refreshes every 5 minutes

### Search Strategy

```text
Query -> Vector Store (semantic search via embeddings)
           |
           v (results found?)
         Yes -> return results
         No  -> Keyword search (substring matching on name/description/server)
```

## Database Strategy

### Development (Default)

- LightSpeed storage: SQLite files (`kv_store.db`, `sql_store.db`)
- Conversation cache: SQLite (`conversation-cache.db`)
- Embedding vectors: pgvector on PostgreSQL (via docker-compose)

### Production (Clowder)

When `CLOWDER_ENABLED=true`, `entrypoint.py` automatically:
1. Reads Clowder's database config (hostname, port, credentials, SSL)
2. Switches `run.yaml` storage backends from `kv_sqlite`/`sql_sqlite` to `kv_postgres`/`sql_postgres`
3. Switches `lightspeed-stack.yaml` conversation cache from `sqlite` to `postgres`
4. Exports `PG*` env vars for the embedding service
5. Writes RDS CA cert to `/tmp/rds-ca.crt` if provided

### pgvector Schema

The embedding service creates the following schema on startup:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE IF NOT EXISTS vector_stores (id TEXT PRIMARY KEY, dimension INTEGER DEFAULT 768);
CREATE TABLE IF NOT EXISTS vector_documents (
    id TEXT, store_id TEXT REFERENCES vector_stores(id) ON DELETE CASCADE,
    content TEXT, metadata JSONB, embedding vector(768),
    PRIMARY KEY (id, store_id)
);
CREATE INDEX ... USING hnsw (embedding vector_cosine_ops);
```

**Important**: Vector dimension is hardcoded to 768 (matching `all-mpnet-base-v2`). Changing embedding models requires a schema migration.

## Adding New Functionality

### Adding a New MCP Discovery Tool

1. Open `mcp-discovery-service/mcp_server.py`
2. Add a new method in `_register_tools()` with `@self.mcp.tool()` decorator
3. Add tests in `test_mcp_server.py`
4. The tool is automatically available via the MCP protocol

### Adding a New Embedding API Endpoint

1. Open `embedding-service/main.py`
2. Add a new FastAPI route (`@app.post(...)` or `@app.get(...)`)
3. Define Pydantic request/response models
4. Add tests in `test_main.py`

### Adding a New MCP Server to Discover

1. Edit `lightspeed-stack.yaml`:
   ```yaml
   mcp_servers:
     - name: "new-server"
       provider_id: "new-provider"
       url: "http://new-server:3001/mcp"
   ```
2. Also add as a provider in `run.yaml` under `providers.tool_runtime` if LightSpeed should call it directly
3. Ensure the server is reachable from the deployment environment

## Security Considerations

- **Authentication**: `rh-identity` module in LightSpeed Core (x-rh-identity header)
- **Internal ports**: Only port 8000 is exposed publicly. Ports 8001 and 8002 are pod-internal
- **Secrets**: Google credentials mounted from Kubernetes Secret, never baked into the image
- **DNS rebinding**: Disabled in MCP server for cluster compatibility (security handled by network policies)
- **Embedding model**: Pre-baked into the Docker image (`TRANSFORMERS_OFFLINE=1` at runtime)
