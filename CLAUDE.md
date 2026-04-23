@AGENTS.md

## Commands

```bash
# Run tests (embedding service - 19 tests)
cd embedding-service && pip install -e ".[dev]" && pytest -v

# Run tests (MCP discovery service - 53 tests)
cd mcp-discovery-service && pip install -e ".[dev]" && pytest -v

# Run tests with coverage
cd embedding-service && pytest --cov=main --cov-report=html
cd mcp-discovery-service && pytest --cov=main --cov=mcp_server --cov-report=html

# Format code
black .

# Lint
ruff check .
ruff check --fix .

# Start all services locally (Docker Compose)
docker compose up -d --build

# Health checks
curl http://localhost:8000/health  # Proxy + LightSpeed
curl http://localhost:8001/health  # MCP Discovery
curl http://localhost:8002/health  # Embedding Service
```

## Git Conventions

- Branch format: `bot/<TICKET-KEY>` or `feature/<description>`
- Commit format: `type(scope): description` (conventional commits)
- Scopes: `proxy`, `embedding`, `mcp-discovery`, `config`, `docker`, `ci`
- Types: `feat`, `fix`, `docs`, `chore`, `refactor`, `test`

## Key Files

- `entrypoint.py` - Main orchestrator (starts all services)
- `proxy.py` - Reverse proxy (strips /api/ai-assistant prefix)
- `lightspeed-stack.yaml` - LightSpeed Core config (MCP servers, auth, prompts)
- `run.yaml` - llama-stack config (providers, storage, models)
- `config/clowdapp.yaml` - OpenShift deployment template
- `embedding-service/main.py` - Embedding + vector storage API
- `mcp-discovery-service/main.py` - MCP tool indexer
- `mcp-discovery-service/mcp_server.py` - MCP protocol server (4 tools)
