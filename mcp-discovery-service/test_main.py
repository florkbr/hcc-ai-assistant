"""
Tests for MCP Discovery Service - Main Module
Uses pytest with modern best practices and fixtures for test setup.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, mock_open
import json
from datetime import datetime
from httpx import AsyncClient

from main import (
    Config,
    MCPServer,
    MCPCapability,
    MCPServersConfig,
    VectorStoreClient,
    MCPIndexer
)


# ============================================================================
# TEST DATA FIXTURES
# ============================================================================

@pytest.fixture
def sample_config_yaml():
    """Sample MCP servers YAML configuration"""
    return """
mcp_servers:
  - name: test-server-1
    provider_id: test-provider
    url: http://localhost:9000/mcp
  - name: test-server-2
    provider_id: another-provider
    url: http://localhost:9001/mcp
"""


@pytest.fixture
def empty_config_yaml():
    """Empty MCP servers configuration (all commented out)"""
    return """
mcp_servers:
# - name: test-server
#   provider_id: test
#   url: http://localhost:9000/mcp
"""


@pytest.fixture
def sample_capabilities():
    """Sample MCP capabilities for testing"""
    return [
        MCPCapability(
            server_name="test-server-1",
            tool_name="search_files",
            description="Search for files in a directory",
            input_schema={"type": "object", "properties": {"query": {"type": "string"}}}
        ),
        MCPCapability(
            server_name="test-server-1",
            tool_name="read_file",
            description="Read contents of a file",
            input_schema={"type": "object", "properties": {"path": {"type": "string"}}}
        ),
        MCPCapability(
            server_name="test-server-2",
            tool_name="create_issue",
            description="Create a new issue in the tracker",
            input_schema={"type": "object", "properties": {"title": {"type": "string"}}}
        ),
    ]


@pytest.fixture
def sample_mcp_server():
    """Sample MCP server configuration"""
    return MCPServer(
        name="test-server",
        provider_id="test-provider",
        url="http://localhost:9000/mcp"
    )


@pytest.fixture
def mock_http_response():
    """Factory for creating mock HTTP responses"""
    def _create_response(status=200, json_data=None):
        response = MagicMock()
        response.status_code = status
        response.json.return_value = json_data or {}
        response.raise_for_status = MagicMock()
        return response
    return _create_response


# ============================================================================
# MOCK FIXTURES
# ============================================================================

@pytest.fixture
def mock_httpx_client(mock_http_response):
    """Mock httpx AsyncClient for VectorStoreClient"""
    client = AsyncMock()

    # Default: embedding response
    client.post.return_value = mock_http_response(
        json_data={"data": [{"embedding": [0.1, 0.2, 0.3], "index": 0}]}
    )

    return client


@pytest.fixture
def mock_mcp_session():
    """Mock MCP ClientSession"""
    session = AsyncMock()

    # Mock list_tools response
    tool_mock_1 = MagicMock()
    tool_mock_1.name = "test_tool"
    tool_mock_1.description = "A test tool"
    tool_mock_1.inputSchema = {"type": "object"}

    session.list_tools.return_value = MagicMock(tools=[tool_mock_1])
    session.initialize.return_value = None

    return session


# ============================================================================
# CONFIG TESTS
# ============================================================================

def test_config_defaults():
    """Test Config class uses correct default values"""
    config = Config()
    assert config.HOST == "0.0.0.0"
    assert config.PORT == 8000
    assert config.REFRESH_INTERVAL_MINUTES == 5
    assert config.VECTOR_STORE_ID == "mcp-capabilities-store"


def test_config_from_env(monkeypatch):
    """Test Config reads from environment variables"""
    monkeypatch.setenv("HOST", "127.0.0.1")
    monkeypatch.setenv("PORT", "9000")
    monkeypatch.setenv("ENABLE_VECTOR_STORE", "true")
    monkeypatch.setenv("REFRESH_INTERVAL_MINUTES", "10")

    # Need to reload the module to pick up new env vars
    import importlib
    import main as main_module
    importlib.reload(main_module)

    config = main_module.Config()
    assert config.HOST == "127.0.0.1"
    assert config.PORT == 9000
    assert config.ENABLE_VECTOR_STORE is True
    assert config.REFRESH_INTERVAL_MINUTES == 10

    # Reload again to restore defaults for other tests
    importlib.reload(main_module)


# ============================================================================
# DATA MODEL TESTS
# ============================================================================

def test_mcp_server_model(sample_mcp_server):
    """Test MCPServer data model"""
    assert sample_mcp_server.name == "test-server"
    assert sample_mcp_server.provider_id == "test-provider"
    assert sample_mcp_server.url == "http://localhost:9000/mcp"


def test_mcp_capability_model():
    """Test MCPCapability data model"""
    cap = MCPCapability(
        server_name="test-server",
        tool_name="test_tool",
        description="Test description",
        input_schema={"type": "object"}
    )
    assert cap.server_name == "test-server"
    assert cap.tool_name == "test_tool"
    assert cap.description == "Test description"


def test_mcp_servers_config_empty():
    """Test MCPServersConfig with no servers"""
    config = MCPServersConfig(mcp_servers=[])
    assert len(config.mcp_servers) == 0


# ============================================================================
# VECTOR STORE CLIENT TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_vector_store_generate_embedding(mock_httpx_client):
    """Test generating a single embedding"""
    with patch('main.httpx.AsyncClient', return_value=mock_httpx_client):
        client = VectorStoreClient(
            base_url="http://localhost:8001",
            vector_store_id="test-store",
            embedding_model="test-model"
        )

        embedding = await client.generate_embedding("test text")

        assert embedding == [0.1, 0.2, 0.3]
        mock_httpx_client.post.assert_called_once()


@pytest.mark.asyncio
async def test_vector_store_insert_capabilities(mock_httpx_client, sample_capabilities, mock_http_response):
    """Test inserting capabilities into vector store"""
    # Mock both embeddings and insert responses
    mock_httpx_client.post.side_effect = [
        mock_http_response(json_data={
            "data": [
                {"embedding": [0.1, 0.2, 0.3], "index": i}
                for i in range(len(sample_capabilities))
            ]
        }),
        mock_http_response(json_data={"status": "success"})
    ]

    with patch('main.httpx.AsyncClient', return_value=mock_httpx_client):
        client = VectorStoreClient(
            base_url="http://localhost:8001",
            vector_store_id="test-store",
            embedding_model="test-model"
        )

        await client.insert_capabilities(sample_capabilities)

        assert mock_httpx_client.post.call_count == 2


@pytest.mark.asyncio
async def test_vector_store_insert_empty_capabilities(mock_httpx_client):
    """Test inserting empty capabilities list"""
    with patch('main.httpx.AsyncClient', return_value=mock_httpx_client):
        client = VectorStoreClient(
            base_url="http://localhost:8001",
            vector_store_id="test-store",
            embedding_model="test-model"
        )

        await client.insert_capabilities([])

        # Should not call API if capabilities are empty
        mock_httpx_client.post.assert_not_called()


@pytest.mark.asyncio
async def test_vector_store_search_similar(mock_httpx_client, mock_http_response):
    """Test searching for similar capabilities"""
    # Mock embedding and query responses
    mock_httpx_client.post.side_effect = [
        mock_http_response(json_data={"data": [{"embedding": [0.1, 0.2, 0.3]}]}),
        mock_http_response(json_data={
            "results": [{
                "document_id": "server1::tool1",
                "score": 0.9,
                "content": "test content",
                "metadata": {
                    "tool_name": "tool1",
                    "server_name": "server1",
                    "description": "A test tool"
                }
            }]
        })
    ]

    with patch('main.httpx.AsyncClient', return_value=mock_httpx_client):
        client = VectorStoreClient(
            base_url="http://localhost:8001",
            vector_store_id="test-store",
            embedding_model="test-model"
        )

        results = await client.search_similar("test query", k=5)

        assert len(results) == 1
        assert results[0].tool_name == "tool1"
        assert results[0].server_name == "server1"


# ============================================================================
# MCP INDEXER TESTS
# ============================================================================

def test_indexer_initialization():
    """Test MCPIndexer initializes with empty capabilities"""
    indexer = MCPIndexer()
    assert len(indexer.capabilities) == 0
    assert indexer.last_refresh_time is not None


def test_indexer_load_config(sample_config_yaml, tmp_path):
    """Test loading MCP servers from YAML config"""
    config_file = tmp_path / "lightspeed-stack.yaml"
    config_file.write_text(sample_config_yaml)

    with patch('main.config.MCP_CONFIG_PATH', str(config_file)):
        indexer = MCPIndexer()
        mcp_config = indexer.load_config()

        assert len(mcp_config.mcp_servers) == 2
        assert mcp_config.mcp_servers[0].name == "test-server-1"
        assert mcp_config.mcp_servers[1].name == "test-server-2"


def test_indexer_load_empty_config(empty_config_yaml, tmp_path):
    """Test loading config with all servers commented out"""
    config_file = tmp_path / "lightspeed-stack.yaml"
    config_file.write_text(empty_config_yaml)

    with patch('main.config.MCP_CONFIG_PATH', str(config_file)):
        indexer = MCPIndexer()
        mcp_config = indexer.load_config()

        assert len(mcp_config.mcp_servers) == 0


@pytest.mark.asyncio
async def test_indexer_discover_capabilities(mock_mcp_session, sample_mcp_server):
    """Test discovering capabilities from an MCP server"""
    with patch('main.streamablehttp_client') as mock_transport, \
         patch('main.ClientSession') as mock_session_class:
        # Mock the context manager for transport
        mock_transport.return_value.__aenter__.return_value = (
            AsyncMock(), AsyncMock(), None
        )
        mock_session_class.return_value.__aenter__.return_value = mock_mcp_session

        indexer = MCPIndexer()
        capabilities = await indexer.discover_capabilities(sample_mcp_server)

        assert len(capabilities) == 1
        assert capabilities[0].tool_name == "test_tool"
        assert capabilities[0].server_name == "test-server"


@pytest.mark.asyncio
async def test_indexer_discover_capabilities_error(sample_mcp_server):
    """Test handling errors during capability discovery"""
    with patch('main.streamablehttp_client', side_effect=Exception("Connection failed")):
        indexer = MCPIndexer()
        capabilities = await indexer.discover_capabilities(sample_mcp_server)

        # Should return empty list on error
        assert len(capabilities) == 0


def test_indexer_keyword_search(sample_capabilities):
    """Test keyword-based search"""
    indexer = MCPIndexer()
    indexer.capabilities = sample_capabilities

    # Search by tool name
    results = indexer.search_keyword("search", limit=10)
    assert len(results) == 1
    assert results[0].tool_name == "search_files"

    # Search by description
    results = indexer.search_keyword("issue", limit=10)
    assert len(results) == 1
    assert results[0].tool_name == "create_issue"

    # Search by server name
    results = indexer.search_keyword("test-server-1", limit=10)
    assert len(results) == 2


def test_indexer_keyword_search_limit(sample_capabilities):
    """Test keyword search respects limit parameter"""
    indexer = MCPIndexer()
    indexer.capabilities = sample_capabilities

    results = indexer.search_keyword("test", limit=1)
    assert len(results) == 1


@pytest.mark.asyncio
async def test_indexer_search_with_vector_store(mock_httpx_client, mock_http_response):
    """Test search uses vector store when available"""
    # Mock vector store responses
    mock_httpx_client.post.side_effect = [
        mock_http_response(json_data={"data": [{"embedding": [0.1, 0.2, 0.3]}]}),
        mock_http_response(json_data={
            "results": [{
                "metadata": {
                    "tool_name": "tool1",
                    "server_name": "server1",
                    "description": "desc"
                }
            }]
        })
    ]

    with patch('main.httpx.AsyncClient', return_value=mock_httpx_client), \
         patch('main.config.ENABLE_VECTOR_STORE', True):

        indexer = MCPIndexer()
        results, method = await indexer.search("test query", limit=5)

        assert method == "semantic search"
        assert len(results) == 1


@pytest.mark.asyncio
async def test_indexer_search_fallback_to_keyword(sample_capabilities):
    """Test search falls back to keyword search when vector store fails"""
    indexer = MCPIndexer()
    indexer.capabilities = sample_capabilities
    indexer.vector_store = None

    results, method = await indexer.search("search", limit=10)

    assert method == "keyword search"
    assert len(results) > 0


@pytest.mark.asyncio
async def test_indexer_save_capabilities(sample_capabilities, tmp_path):
    """Test saving capabilities to disk"""
    cache_file = tmp_path / "capabilities.json"

    with patch('main.config.CAPABILITIES_CACHE_PATH', str(cache_file)):
        indexer = MCPIndexer()
        indexer.capabilities = sample_capabilities
        await indexer.save_capabilities()

        assert cache_file.exists()
        data = json.loads(cache_file.read_text())
        assert len(data) == 3


@pytest.mark.asyncio
async def test_indexer_refresh_index(sample_config_yaml, tmp_path, mock_mcp_session):
    """Test full index refresh process"""
    config_file = tmp_path / "lightspeed-stack.yaml"
    config_file.write_text(sample_config_yaml)
    cache_file = tmp_path / "capabilities.json"

    with patch('main.config.MCP_CONFIG_PATH', str(config_file)), \
         patch('main.config.CAPABILITIES_CACHE_PATH', str(cache_file)), \
         patch('main.streamablehttp_client') as mock_transport, \
         patch('main.ClientSession') as mock_session_class:

        # Mock transport and session
        mock_transport.return_value.__aenter__.return_value = (
            AsyncMock(), AsyncMock(), None
        )
        mock_session_class.return_value.__aenter__.return_value = mock_mcp_session

        indexer = MCPIndexer()
        await indexer.refresh_index()

        # Should have discovered capabilities from servers
        assert len(indexer.capabilities) > 0
        assert cache_file.exists()


# ============================================================================
# PARAMETRIZED TESTS
# ============================================================================

@pytest.mark.parametrize("search_term,expected_tool", [
    ("search", "search_files"),
    ("read", "read_file"),
    ("issue", "create_issue"),
])
def test_keyword_search_various_terms(sample_capabilities, search_term, expected_tool):
    """Test keyword search with various search terms"""
    indexer = MCPIndexer()
    indexer.capabilities = sample_capabilities

    results = indexer.search_keyword(search_term, limit=10)
    assert len(results) > 0
    assert any(cap.tool_name == expected_tool for cap in results)


@pytest.mark.parametrize("limit", [1, 5, 10, 100])
def test_keyword_search_various_limits(sample_capabilities, limit):
    """Test keyword search with various limit values"""
    indexer = MCPIndexer()
    indexer.capabilities = sample_capabilities

    results = indexer.search_keyword("test", limit=limit)
    assert len(results) <= limit
    assert len(results) <= len(sample_capabilities)
