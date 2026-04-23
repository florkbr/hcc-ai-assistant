# Testing Guidelines

## Overview

This project has two independently testable Python services, each with their own test suite, dependencies, and pytest configuration.

| Service | Test File(s) | Test Count | Key Patterns |
|---------|-------------|------------|--------------|
| embedding-service | `test_main.py` | 19 | FastAPI TestClient, async fixtures, DB mocking |
| mcp-discovery-service | `test_main.py`, `test_mcp_server.py` | 53 | MCP session mocking, httpx mocking, async indexer |

## Running Tests

```bash
# Embedding service
cd embedding-service
pip install -e ".[dev]"
pytest -v

# MCP discovery service
cd mcp-discovery-service
pip install -e ".[dev]"
pytest -v

# With coverage
pytest --cov=main --cov-report=html
pytest --cov=main --cov=mcp_server --cov-report=html

# Run specific test
pytest test_main.py::test_health_endpoint
pytest -k "search"  # Pattern matching
```

## Test Configuration

Both services use `pyproject.toml` for pytest configuration:

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["."]
python_files = ["test_*.py"]
addopts = ["-v", "--strict-markers", "--tb=short"]
markers = ["asyncio: mark test as async"]
```

Key: `asyncio_mode = "auto"` means async test functions are detected automatically without needing `@pytest.mark.asyncio` on every test (though the marker is still valid).

## Test Patterns

### Fixture-Based Setup

Tests use pytest fixtures instead of setUp/tearDown. Common fixtures:

```python
@pytest.fixture
def sample_capabilities():
    """Reusable test data"""
    return [MCPCapability(...), ...]

@pytest.fixture
def mock_httpx_client():
    """Mock external HTTP calls"""
    client = AsyncMock()
    client.post.return_value = mock_response(...)
    return client
```

### Async Test Functions

Both services are async. Use `pytest-asyncio`:

```python
@pytest.mark.asyncio
async def test_vector_store_search(mock_httpx_client):
    results = await client.search_similar("query", k=5)
    assert len(results) == 1
```

### Parametrized Tests

Use `@pytest.mark.parametrize` for testing multiple scenarios:

```python
@pytest.mark.parametrize("search_term,expected_tool", [
    ("search", "search_files"),
    ("read", "read_file"),
    ("issue", "create_issue"),
])
def test_keyword_search_various_terms(sample_capabilities, search_term, expected_tool):
    ...
```

### Mocking External Dependencies

#### Embedding Service - Database Mocking

The embedding service uses pgvector/PostgreSQL. Tests mock the connection pool:

```python
@pytest.fixture
def mock_db_pool(mock_connection):
    pool = MagicMock()
    pool.getconn.return_value = mock_connection
    return pool

@pytest.fixture
async def test_app(mock_sentence_transformer, mock_db_pool):
    with patch('main.SentenceTransformer', return_value=mock_sentence_transformer), \
         patch('main.psycopg2.pool.ThreadedConnectionPool', return_value=mock_db_pool), \
         patch('main.register_vector'):
        from main import app
        async with app.router.lifespan_context(app):
            yield app
```

#### MCP Discovery - MCP Session Mocking

The MCP discovery service connects to MCP servers. Tests mock the transport and session:

```python
with patch('main.streamablehttp_client') as mock_transport, \
     patch('main.ClientSession') as mock_session_class:
    mock_transport.return_value.__aenter__.return_value = (AsyncMock(), AsyncMock(), None)
    mock_session_class.return_value.__aenter__.return_value = mock_mcp_session
```

#### HTTP Response Factory

Use a factory fixture for creating mock HTTP responses:

```python
@pytest.fixture
def mock_http_response():
    def _create_response(status=200, json_data=None):
        response = MagicMock()
        response.status_code = status
        response.json.return_value = json_data or {}
        response.raise_for_status = MagicMock()
        return response
    return _create_response
```

### FastAPI Test Client

The embedding service uses httpx's `ASGITransport` for async testing:

```python
@pytest.fixture
async def client(test_app):
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
```

The MCP discovery service uses Starlette's `TestClient` for health checks:

```python
from starlette.testclient import TestClient
app = mcp_server.create_app()
client = TestClient(app)
response = client.get("/health")
```

## Writing New Tests

### Checklist

1. Place test files next to the source: `test_<module>.py`
2. Use fixtures for test data and mocks (no inline setup)
3. Mock all external dependencies (DB, HTTP, MCP sessions)
4. Use `tmp_path` fixture for file operations
5. Add parametrized tests for boundary conditions
6. Test both success and error paths
7. Test graceful degradation (e.g., vector search -> keyword fallback)

### Naming Convention

```text
test_<component>_<scenario>
test_health_endpoint
test_vector_store_search_similar
test_indexer_keyword_search_limit
test_recommend_tools_no_recommendations
```

### What to Test

| Category | Examples |
|----------|---------|
| Health endpoints | Service status, dependency checks |
| Request validation | Empty input, mismatched counts, missing fields |
| Happy paths | Embedding generation, vector insert/query, MCP tool calls |
| Error handling | Connection failures, missing stores, invalid schemas |
| Fallback behavior | Vector search failing -> keyword search |
| Config loading | Default values, environment variable overrides |
| Edge cases | Empty capabilities list, non-existent servers/tools |
