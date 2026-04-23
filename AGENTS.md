# HCC AI Assistant - Agent Reference

## Project Overview

HTTP-based AI assistant service for the Hybrid Cloud Console (HCC). Uses LightSpeed Core with Google Vertex AI (Gemini models) and MCP (Model Context Protocol) for tool discovery. All services are Python-based and run as sidecars in a single Kubernetes pod.

## Repository Structure

```text
hcc-ai-assistant/
├── entrypoint.py              # Main orchestrator: renders configs, starts all services
├── proxy.py                   # Starlette reverse proxy (strips /api/ai-assistant prefix)
├── lightspeed-stack.yaml      # LightSpeed Core config (MCP servers, auth, system prompt)
├── run.yaml                   # llama-stack run config (providers, storage, models)
├── Dockerfile                 # Multi-service container (base: lightspeed-stack-rhel9)
├── docker-compose.yml         # Local dev: postgres + all services
├── config/
│   └── clowdapp.yaml          # OpenShift ClowdApp deployment template
├── .tekton/
│   ├── hcc-ai-assistant-pull-request.yaml
│   └── hcc-ai-assistant-push.yaml
├── embedding-service/
│   ├── main.py                # FastAPI app: embeddings + pgvector storage
│   ├── pyproject.toml         # Dependencies and tool config
│   ├── test_main.py           # 19 tests (health, embeddings, vector CRUD)
│   ├── Dockerfile             # Standalone container (dev only)
│   └── README.md
├── mcp-discovery-service/
│   ├── main.py                # MCP indexer: config, vector store client, background refresh
│   ├── mcp_server.py          # FastMCP server: 4 discovery tools + health endpoint
│   ├── pyproject.toml         # Dependencies and tool config
│   ├── test_main.py           # 28 tests (config, vector store, indexer, search)
│   ├── test_mcp_server.py     # 25 tests (MCP tools, health, integration)
│   └── README.md
└── uv.lock                    # Root lockfile
```

## Architecture

### Sidecar Pod Architecture

All three services run in a single Kubernetes pod, communicating via `localhost`:

| Service | Port | Framework | Purpose |
|---------|------|-----------|---------|
| Reverse Proxy + LightSpeed Stack | 8000 (public) | Starlette + LightSpeed Core | API gateway, AI inference (Vertex AI/Gemini) |
| MCP Discovery Service | 8001 (internal) | FastMCP (MCP SDK) | Discovers and indexes MCP tools from configured servers |
| Embedding Service | 8002 (internal) | FastAPI | Text embeddings (sentence-transformers) + vector storage (pgvector) |

**Startup order** (enforced by health probes): embedding-service -> mcp-discovery-service -> lightspeed-stack

### Request Flow

```text
Client -> :8000/api/ai-assistant/* -> proxy.py (strips prefix) -> :8080 lightspeed-stack
                                                                      |
                                                                      v
                                                              :8001/mcp (MCP Discovery)
                                                                      |
                                                                      v
                                                              :8002 (Embedding Service)
```

### entrypoint.py Orchestration

1. Loads Clowder config (if `CLOWDER_ENABLED`)
2. Renders `run.yaml` and `lightspeed-stack.yaml` from templates to `/app-root/`
3. Applies Clowder DB config (switches sqlite -> postgres)
4. Exports `PG*` env vars for embedding service
5. Starts embedding-service subprocess (uvicorn)
6. Starts mcp-discovery-service subprocess
7. Starts lightspeed-stack subprocess
8. Runs reverse proxy (uvicorn, blocks until shutdown)
9. Handles SIGTERM/SIGINT: terminates all children

## Technology Stack

| Technology | Purpose |
|-----------|---------|
| Python 3.12 | All services |
| LightSpeed Core | AI inference framework (wraps llama-stack) |
| Google Vertex AI | LLM provider (Gemini models) |
| FastAPI | Embedding service web framework |
| Starlette | Reverse proxy + MCP server framework |
| FastMCP (MCP SDK) | MCP protocol server implementation |
| sentence-transformers | Text embedding generation (all-mpnet-base-v2, 768-dim) |
| pgvector / PostgreSQL | Vector storage and similarity search |
| psycopg2 | PostgreSQL driver |
| httpx | Async HTTP client |
| Pydantic | Data validation and serialization |
| uvicorn | ASGI server |
| PyYAML | YAML config parsing |
| Clowder (app-common-python) | OpenShift deployment config injection |
| Docker / Podman | Containerization |
| Tekton | CI/CD pipelines (Konflux) |
| pytest / pytest-asyncio | Testing framework |
| black | Code formatter (line-length=120) |
| ruff | Linter (line-length=120) |

## Key Configuration Files

### lightspeed-stack.yaml

LightSpeed Core configuration:
- `service`: host/port for the backend (8080 internal)
- `mcp_servers`: list of MCP servers to connect to (RBAC, Notifications, mcp-discovery)
- `authentication`: `rh-identity` module with health probe skip
- `conversation_cache`: sqlite (default) or postgres (via Clowder)
- `customization.system_prompt`: instructs the LLM to always use `recommend_tools` from mcp-discovery-server

### run.yaml

llama-stack configuration:
- `providers.inference`: google-vertex (Gemini) + sentence-transformers
- `providers.tool_runtime`: rag-runtime + MCP providers (RBAC, Notifications, mcp-discovery)
- `storage.backends`: kv_sqlite/sql_sqlite (default), switched to postgres by Clowder
- `registered_resources`: models, shields, vector_stores, tool_groups

### config/clowdapp.yaml

OpenShift deployment template:
- ClowdApp with database, feature flags, Kafka topic (`platform.chrome`)
- Single deployment (`api`) with public web service
- Vertex AI secret mounted at `/opt/secrets`
- Resource limits: 2 CPU, 6Gi memory; requests: 1 CPU, 4Gi memory

## MCP Discovery Tools

The MCP Discovery Service exposes 4 tools via the MCP protocol:

| Tool | Description | Key Parameters |
|------|-------------|---------------|
| `search_mcp_tools` | Semantic search for MCP tools | `query: str`, `limit: int` |
| `list_all_capabilities` | List all discovered capabilities | `server_name: Optional[str]` |
| `get_tool_schema` | Get detailed JSON schema for a tool | `tool_name: str`, `server_name: Optional[str]` |
| `recommend_tools` | Get tool recommendations for a task | `task: str`, `limit: int` |

Search uses semantic (vector) search first, falls back to keyword search.

## Embedding Service API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check (model loaded + DB connected) |
| `/v1/embeddings` | POST | Generate text embeddings (llama-stack compatible) |
| `/v1/vector_io/insert` | POST | Insert documents with embeddings |
| `/v1/vector_io/query` | POST | Cosine similarity search |
| `/v1/vector_io/stores` | GET | List vector stores |
| `/v1/vector_io/store/{id}` | DELETE | Delete a vector store |

## Environment Variables

### Entrypoint / Proxy

| Variable | Default | Description |
|----------|---------|-------------|
| `CLOWDER_ENABLED` | - | Enable Clowder config injection |
| `PROXY_BACKEND_URL` | `http://localhost:8080` | LightSpeed backend URL |
| `PROXY_STRIP_PREFIX` | `/api/ai-assistant` | Path prefix to strip |
| `PROXY_HOST` | `0.0.0.0` | Proxy listen host |
| `PROXY_PORT` | `8000` | Proxy listen port |
| `PROXY_LOG_LEVEL` | `warning` | Uvicorn log level |
| `EMBEDDING_SERVICE_PORT` | `8002` | Embedding service port |
| `MCP_DISCOVERY_SERVICE_PORT` | `8001` | MCP discovery port |
| `VERTEX_PROJECT` | - | Google Cloud project ID |
| `VERTEX_LOCATION` | - | Google Cloud region |
| `ALLOWED_MODEL` | - | Gemini model name |
| `GOOGLE_API_KEY` | - | Google API key |

### Database (set by Clowder or manually)

| Variable | Default | Description |
|----------|---------|-------------|
| `PGHOST` | `localhost` | PostgreSQL host |
| `PGPORT` | `5432` | PostgreSQL port |
| `PGDATABASE` | `hcc-ai-assistant` | Database name |
| `PGUSER` | `postgres` | Database user |
| `PGPASSWORD` | - | Database password |
| `PGSSLMODE` | - | SSL mode |

### MCP Discovery Service

| Variable | Default | Description |
|----------|---------|-------------|
| `HOST` | `0.0.0.0` | Server host |
| `PORT` | `8001` | Server port |
| `MCP_CONFIG_PATH` | `/app-root/lightspeed-stack.yaml` | MCP servers config path |
| `ENABLE_VECTOR_STORE` | `false` | Enable semantic search |
| `EMBEDDING_SERVICE_URL` | `http://localhost:8002` | Embedding service URL |
| `REFRESH_INTERVAL_MINUTES` | `5` | Background refresh interval |
| `LOG_LEVEL` | `INFO` | Logging level |

## Development Commands

```bash
# Local development (each service independently)
cd embedding-service && pip install -e ".[dev]" && uvicorn main:app --reload --port 8002
cd mcp-discovery-service && pip install -e ".[dev]" && python main.py

# Docker Compose (all services)
docker compose up -d --build
docker compose logs -f
docker compose down

# Run tests
cd embedding-service && pytest -v                    # 19 tests
cd mcp-discovery-service && pytest -v                # 53 tests

# Run tests with coverage
cd embedding-service && pytest --cov=main --cov-report=html
cd mcp-discovery-service && pytest --cov=main --cov=mcp_server --cov-report=html

# Code formatting
black .
ruff check .
ruff check --fix .
```

## Coding Conventions

1. **Line length**: 120 characters (both black and ruff)
2. **Python version**: 3.12+ (type hints, f-strings, match statements OK)
3. **Async**: Use `async/await` for all I/O operations. Both services use async frameworks (FastAPI, Starlette)
4. **Logging**: Structured logging with service prefix (`[embedding-service]`, `[mcp-discovery]`, `[entrypoint]`)
5. **Data models**: Pydantic BaseModel for request/response schemas
6. **Config**: Environment variables via `os.getenv()` with defaults, grouped in Config class (mcp-discovery) or module-level constants
7. **Error handling**: HTTP exceptions with descriptive messages; graceful degradation (vector -> keyword search fallback)
8. **Testing**: pytest with fixtures, `pytest-asyncio` for async tests, `unittest.mock` for mocking. Parametrized tests for multiple scenarios
9. **Database**: Connection pooling via `psycopg2.pool.ThreadedConnectionPool`. Always `get_conn()` / `put_conn()` pattern
10. **Dependencies**: Pinned in pyproject.toml with version ranges. `uv.lock` for reproducible builds

## Common Pitfalls

1. **Startup order matters**: Embedding service must be healthy before MCP discovery starts. MCP discovery must be healthy before LightSpeed. Health probes enforce this
2. **Clowder config changes DB backend**: In OpenShift, sqlite is replaced with postgres automatically. Test both paths
3. **MCP server unreachability**: LightSpeed Core will 500 on queries if any registered MCP provider is unreachable. Only enable providers reachable from the current environment
4. **Vector dimension mismatch**: Embedding model outputs 768-dim vectors. pgvector schema is hardcoded to `vector(768)`. Changing models requires schema migration
5. **Network namespace in docker-compose**: Services share `lightspeed-stack`'s network via `network_mode`. Use `localhost` not service names
6. **DNS rebinding protection**: Disabled in MCP server for Kubernetes compatibility (service hostnames, FQDN variations)
7. **Secrets**: Never commit `.env`, `service-account-key.json`, or Google credentials. Use Clowder secrets in production

## Documentation Index

| Document | Description |
|----------|-------------|
| [README.md](./README.md) | Project overview, quick start, architecture |
| [embedding-service/README.md](./embedding-service/README.md) | Embedding service API, config, troubleshooting |
| [mcp-discovery-service/README.md](./mcp-discovery-service/README.md) | MCP discovery tools, protocol, search modes |
| [docs/testing-guidelines.md](./docs/testing-guidelines.md) | Testing patterns and conventions |
| [docs/architecture-guidelines.md](./docs/architecture-guidelines.md) | Architecture decisions and patterns |
| [docs/deployment-guidelines.md](./docs/deployment-guidelines.md) | Deployment config and operations |
