# Embedding Service

Unified embedding generation and vector storage service compatible with llama-stack APIs.

## Overview

This service combines two functionalities in one:
1. **Embedding Generation**: Convert text to vector embeddings using sentence-transformers
2. **Vector Storage**: Store and query embeddings using ChromaDB

## Features

- **Unified Service**: Single container for embeddings + vector storage
- **Compatible APIs**: Implements llama-stack's `/v1/embeddings` and `/v1/vector_io/*` APIs
- **Production Ready**: Health checks, error handling, structured logging
- **Persistent Storage**: ChromaDB with disk persistence
- **Lightweight**: ~1.5GB memory footprint

## Technology Stack

- **FastAPI**: High-performance async web framework
- **sentence-transformers**: Text embedding generation
- **ChromaDB**: Vector database with similarity search
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
  "chroma_initialized": true,
  "model": "sentence-transformers/all-mpnet-base-v2",
  "collections": ["store1", "store2"]
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
docker run -p 8002:8002 -v $(pwd)/data:/app/data embedding-service:latest

# Override port
docker run -p 9000:9000 -e PORT=9000 -v $(pwd)/data:/app/data embedding-service:latest

# Use IPv6/dual-stack
docker run -p 8002:8002 -e HOST=:: -v $(pwd)/data:/app/data embedding-service:latest
```

## Testing

### Running Tests

The service includes comprehensive test coverage (19 tests) using pytest with modern best practices.

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

Tests use modern pytest patterns:
- **Fixtures**: Centralized test data and mocks (equivalent to `beforeEach`)
- **Parametrized tests**: Multiple scenarios tested efficiently
- **Async support**: Full async/await testing with pytest-asyncio
- **Mocking**: External dependencies (SentenceTransformer, ChromaDB) mocked for fast tests

### Continuous Integration

Add to your CI pipeline:

```yaml
- name: Run Tests
  run: |
    pip install -e ".[dev]"
    pytest --cov=main --cov-report=xml
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `HOST` | `0.0.0.0` | Server host (use `::` for IPv6/dual-stack) |
| `PORT` | `8002` | Server port |
| `LOG_LEVEL` | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |

**Note on HOST values:**
- `0.0.0.0` - IPv4 only (default, works in most environments)
- `::` - IPv6/dual-stack (use for IPv6-only or dual-stack OpenShift clusters)

### Storage

- **ChromaDB Data**: `/app/data/chroma/`
- **Volume Mount**: Mount `/app/data` for persistent storage

## Deployment Architecture

### Kubernetes/OpenShift (Sidecar)

In production, this service runs as a **sidecar container** in the same pod as lightspeed-stack and mcp-discovery-service. All services communicate via `localhost`:

- **Port**: 8002 (internal to pod)
- **Access**: `http://localhost:8002` from other containers in the pod
- **Startup Order**: embedding-service starts first (required by mcp-discovery-service)

### Docker Compose (Simulated Sidecar)

Uses `network_mode: "service:lightspeed-stack"` to share network namespace, simulating Kubernetes pod behavior.

## Performance

- **Startup Time**: 5-10 seconds (model loading)
- **Embedding Generation**: ~10-50ms per text (CPU), ~5ms (GPU)
- **Vector Query**: ~5-20ms
- **Memory**: ~1.5GB (model + ChromaDB)
- **Concurrent Requests**: Supported via FastAPI async

## Resource Requirements

**Minimum**:
- CPU: 1 core
- Memory: 1GB

**Recommended**:
- CPU: 2 cores
- Memory: 2GB
- Storage: 10GB for vector data

## Troubleshooting

### Model Loading Fails

**Solution**: Ensure sufficient memory and internet connectivity during first startup (model download).

### ChromaDB Errors

**Solution**: Check that `/app/data` is writable and has sufficient disk space.

### Out of Memory

**Solution**: Increase container memory limits to at least 2GB.
