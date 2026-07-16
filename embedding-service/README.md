# Embedding Service

Unified embedding generation and vector storage service compatible with llama-stack APIs.

## Overview

This service combines two functionalities in one:
1. **Embedding Generation**: Convert text to vector embeddings using sentence-transformers
2. **Vector Storage**: Store and query embeddings using pgvector (PostgreSQL)

## Features

- **Unified Service**: Single container for embeddings + vector storage
- **Compatible APIs**: Implements llama-stack's `/v1/embeddings` and `/v1/vector_io/*` APIs
- **Production Ready**: Health checks, error handling, structured logging
- **Persistent Storage**: pgvector on PostgreSQL
- **Lightweight**: ~1.5GB memory footprint

## Technology Stack

- **FastAPI**: High-performance async web framework
- **sentence-transformers**: Text embedding generation
- **pgvector**: Vector storage extension for PostgreSQL
- **psycopg2**: PostgreSQL database driver
- **Model**: sentence-transformers/all-mpnet-base-v2 (768-dimensional embeddings)

## API Endpoints

### Embeddings

#### POST /v1/embeddings
Generate embeddings for text inputs.

**Request:**
```json
{
  "input": ["text to embed", "another text"],
  "model": "sentence-transformers/all-mpnet-base-v2"
}
```

**Response:**
```json
{
  "data": [
    {
      "embedding": [0.123, 0.456, ...],
      "index": 0
    }
  ],
  "model": "sentence-transformers/all-mpnet-base-v2",
  "usage": {
    "total_tokens": 42
  }
}
```

### Vector Storage

#### POST /v1/vector_io/insert
Insert documents with embeddings.

**Request:**
```json
{
  "vector_store_id": "mcp-capabilities-store",
  "documents": [
    {
      "document_id": "doc1",
      "content": "description",
      "metadata": {"key": "value"}
    }
  ],
  "embeddings": [[0.123, 0.456, ...]]
}
```

#### POST /v1/vector_io/query
Query for similar documents.

**Request:**
```json
{
  "vector_store_id": "mcp-capabilities-store",
  "query": [0.123, 0.456, ...],
  "k": 10
}
```

**Response:**
```json
{
  "results": [
    {
      "document_id": "doc1",
      "score": 0.95,
      "content": "description",
      "metadata": {"key": "value"}
    }
  ]
}
```

#### GET /v1/vector_io/stores
List all vector stores.

#### DELETE /v1/vector_io/store/{id}
Delete a vector store.

### Health

#### GET /health
Service health check.

**Response:**
```json
{
  "status": "healthy",
  "embedding_model_loaded": true,
  "pgvector_connected": true,
  "model": "sentence-transformers/all-mpnet-base-v2"
}
```

## Development

### Local Testing

```bash
cd embedding-service

# Create virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -e ".[dev]"

# Run the service (default port 8002)
uvicorn main:app --reload --port 8002

# Or use PORT environment variable
PORT=8002 uvicorn main:app --reload --port $PORT

# Test health
curl http://localhost:8002/health

# Test embeddings
curl -X POST http://localhost:8002/v1/embeddings \
  -H "Content-Type: application/json" \
  -d '{"input": ["test"]}'
```

### Docker Build

```bash
docker build -t embedding-service:latest .

# Run with defaults (host=0.0.0.0, port=8002)
# Note: A PostgreSQL instance with pgvector extension must be available
docker run -p 8002:8002 embedding-service:latest

# Override port
docker run -p 9000:9000 -e PORT=9000 embedding-service:latest

# Use IPv6/dual-stack
docker run -p 8002:8002 -e HOST=:: embedding-service:latest
```

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
pytest --cov=main --cov-report=html
open htmlcov/index.html

# Run specific test
pytest test_main.py::test_health_endpoint

# Run tests matching pattern
pytest -k "embedding"
```

### Test Coverage

- ✅ Health & service info endpoints
- ✅ Embedding generation (various input sizes)
- ✅ Vector storage insert/query/delete operations
- ✅ Error handling and validation
- ✅ Edge cases and parametrized tests

### Test Structure

See [Testing Guidelines](../docs/testing-guidelines.md) for test patterns and conventions.

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `HOST` | `0.0.0.0` | Server host (use `::` for IPv6/dual-stack) |
| `PORT` | `8002` | Server port |
| `LOG_LEVEL` | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |
| `PGHOST` | `localhost` | PostgreSQL host |
| `PGPORT` | `5432` | PostgreSQL port |
| `PGDATABASE` | `hcc-ai-assistant` | Database name |
| `PGUSER` | `postgres` | Database user |
| `PGPASSWORD` | - | Database password |
| `PGSSLMODE` | `prefer` | SSL mode |

**Note on HOST values:**
- `0.0.0.0` - IPv4 only (default, works in most environments)
- `::` - IPv6/dual-stack (use for IPv6-only or dual-stack OpenShift clusters)

### Storage

The service connects to a PostgreSQL database with the pgvector extension installed. Vector data is stored in PostgreSQL tables using the `vector(768)` column type for cosine similarity search. The `PG*` environment variables above configure the database connection.

## Deployment Architecture

See [Architecture Guidelines](../docs/architecture-guidelines.md) for deployment architecture details.

## Performance

- **Startup Time**: 5-10 seconds (model loading)
- **Embedding Generation**: ~10-50ms per text (CPU), ~5ms (GPU)
- **Vector Query**: ~5-20ms
- **Memory**: ~1.5GB (model + pgvector)
- **Concurrent Requests**: Supported via FastAPI async

## Resource Requirements

See [Deployment Guidelines](../docs/deployment-guidelines.md) for resource requirements.

## Troubleshooting

### Model Loading Fails

**Solution**: Ensure sufficient memory and internet connectivity during first startup (model download).

### pgvector Connection Errors

**Solution**: Verify that PostgreSQL is running and reachable using the `PG*` environment variables. Ensure the `pgvector` extension is installed (`CREATE EXTENSION IF NOT EXISTS vector;`).

### Out of Memory

**Solution**: Increase container memory limits to at least 2GB.
