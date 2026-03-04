"""
Tests for MCP Discovery Server - MCP Protocol Implementation
Uses pytest with modern best practices and fixtures for test setup.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import json
from datetime import datetime

from mcp_server import MCPDiscoveryServer
from main import MCPCapability, MCPIndexer


# ============================================================================
# TEST DATA FIXTURES
# ============================================================================

@pytest.fixture
def sample_capabilities():
    """Sample capabilities for testing"""
    return [
        MCPCapability(
            server_name="test-server-1",
            tool_name="search_files",
            description="Search for files in a directory using patterns",
            input_schema={
                "type": "object",
                "properties": {
                    "pattern": {"type": "string"},
                    "directory": {"type": "string"}
                },
                "required": ["pattern"]
            }
        ),
        MCPCapability(
            server_name="test-server-1",
            tool_name="read_file",
            description="Read the contents of a file",
            input_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string"}
                },
                "required": ["path"]
            }
        ),
        MCPCapability(
            server_name="test-server-2",
            tool_name="create_jira_issue",
            description="Create a new JIRA issue in the project",
            input_schema={
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "priority": {"type": "string"}
                },
                "required": ["title"]
            }
        ),
    ]


@pytest.fixture
def fixed_datetime():
    """Fixed datetime for consistent testing"""
    return datetime(2024, 1, 1, 12, 0, 0)


# ============================================================================
# MOCK FIXTURES
# ============================================================================

@pytest.fixture
def mock_indexer(sample_capabilities, fixed_datetime):
    """Mock MCPIndexer with sample capabilities"""
    indexer = MagicMock(spec=MCPIndexer)
    indexer.capabilities = sample_capabilities
    indexer.last_refresh_time = fixed_datetime

    # Mock async search method
    async def mock_search(query, limit):
        # Simple keyword matching for testing - check each word in query
        query_words = query.lower().split()
        results = [
            cap for cap in sample_capabilities
            if any(word in cap.tool_name.lower() or word in cap.description.lower()
                   for word in query_words)
        ][:limit]
        return results, "keyword search"

    indexer.search = AsyncMock(side_effect=mock_search)
    return indexer


@pytest.fixture
def mcp_server(mock_indexer):
    """Create MCPDiscoveryServer instance with mock indexer"""
    return MCPDiscoveryServer(mock_indexer)


@pytest.fixture
def mcp_tools(mcp_server):
    """Extract registered tools from MCP server"""
    return mcp_server.mcp._tool_manager._tools


def get_tool_by_name(tools, name):
    """Helper to get a tool by name from the tools dict"""
    for tool in tools.values():
        if tool.name == name:
            return tool
    return None


# ============================================================================
# INITIALIZATION TESTS
# ============================================================================

def test_mcp_server_initialization(mock_indexer):
    """Test MCPDiscoveryServer initializes correctly"""
    server = MCPDiscoveryServer(mock_indexer)

    assert server.indexer == mock_indexer
    assert server.mcp is not None
    assert server.mcp.name == "mcp-discovery-server"


def test_mcp_server_registers_tools(mcp_tools):
    """Test that all required tools are registered"""
    expected_tools = {
        "search_mcp_tools",
        "list_all_capabilities",
        "get_tool_schema",
        "recommend_tools"
    }

    registered_tool_names = {tool.name for tool in mcp_tools.values()}
    assert expected_tools.issubset(registered_tool_names)


# ============================================================================
# SEARCH_MCP_TOOLS TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_search_mcp_tools_success(mcp_tools, mock_indexer):
    """Test searching for MCP tools"""
    search_tool = get_tool_by_name(mcp_tools, "search_mcp_tools")
    assert search_tool is not None

    result = await search_tool.fn(query="search", limit=10)

    assert isinstance(result, str)
    assert "Found" in result
    assert "search" in result.lower()
    mock_indexer.search.assert_called_once_with("search", 10)


@pytest.mark.asyncio
async def test_search_mcp_tools_with_results(mcp_tools):
    """Test search returns formatted results"""
    search_tool = get_tool_by_name(mcp_tools, "search_mcp_tools")

    result = await search_tool.fn(query="file", limit=10)

    assert "search_files" in result or "read_file" in result
    assert "Found" in result
    # Should contain JSON-formatted capabilities
    assert "{" in result and "}" in result


@pytest.mark.asyncio
async def test_search_mcp_tools_no_results(mcp_tools, mock_indexer):
    """Test search with no matching results"""
    # Override mock to return no results
    mock_indexer.search.return_value = ([], "keyword search")

    search_tool = get_tool_by_name(mcp_tools, "search_mcp_tools")
    result = await search_tool.fn(query="nonexistent", limit=10)

    assert "Found 0" in result


@pytest.mark.asyncio
@pytest.mark.parametrize("limit", [1, 5, 10, 20])
async def test_search_mcp_tools_various_limits(mcp_tools, mock_indexer, limit):
    """Test search with various limit values"""
    search_tool = get_tool_by_name(mcp_tools, "search_mcp_tools")

    await search_tool.fn(query="test", limit=limit)

    # Verify limit was passed to indexer
    mock_indexer.search.assert_called_with("test", limit)


# ============================================================================
# LIST_ALL_CAPABILITIES TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_list_all_capabilities_no_filter(mcp_tools, sample_capabilities):
    """Test listing all capabilities without filter"""
    list_tool = get_tool_by_name(mcp_tools, "list_all_capabilities")

    result = await list_tool.fn(server_name=None)

    assert isinstance(result, str)
    assert "Total MCP capabilities: 3" in result
    assert "2024-01-01" in result  # Last refresh time
    # Should contain all capabilities
    for cap in sample_capabilities:
        assert cap.tool_name in result


@pytest.mark.asyncio
async def test_list_all_capabilities_with_filter(mcp_tools):
    """Test listing capabilities filtered by server name"""
    list_tool = get_tool_by_name(mcp_tools, "list_all_capabilities")

    result = await list_tool.fn(server_name="test-server-1")

    assert "search_files" in result
    assert "read_file" in result
    assert "create_jira_issue" not in result  # From different server


@pytest.mark.asyncio
async def test_list_all_capabilities_nonexistent_server(mcp_tools):
    """Test listing with non-existent server filter"""
    list_tool = get_tool_by_name(mcp_tools, "list_all_capabilities")

    result = await list_tool.fn(server_name="nonexistent-server")

    assert "Total MCP capabilities: 0" in result


# ============================================================================
# GET_TOOL_SCHEMA TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_get_tool_schema_found(mcp_tools):
    """Test getting schema for an existing tool"""
    schema_tool = get_tool_by_name(mcp_tools, "get_tool_schema")

    result = await schema_tool.fn(tool_name="search_files", server_name=None)

    assert isinstance(result, str)
    assert "search_files" in result
    assert "input_schema" in result
    assert "pattern" in result  # From the schema


@pytest.mark.asyncio
async def test_get_tool_schema_with_server_filter(mcp_tools):
    """Test getting schema with server name filter"""
    schema_tool = get_tool_by_name(mcp_tools, "get_tool_schema")

    result = await schema_tool.fn(tool_name="search_files", server_name="test-server-1")

    assert "search_files" in result
    assert "test-server-1" in result


@pytest.mark.asyncio
async def test_get_tool_schema_not_found(mcp_tools):
    """Test getting schema for non-existent tool"""
    schema_tool = get_tool_by_name(mcp_tools, "get_tool_schema")

    result = await schema_tool.fn(tool_name="nonexistent_tool", server_name=None)

    assert "not found" in result


@pytest.mark.asyncio
async def test_get_tool_schema_wrong_server(mcp_tools):
    """Test getting schema with wrong server name"""
    schema_tool = get_tool_by_name(mcp_tools, "get_tool_schema")

    result = await schema_tool.fn(tool_name="search_files", server_name="wrong-server")

    assert "not found" in result


# ============================================================================
# RECOMMEND_TOOLS TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_recommend_tools_success(mcp_tools, mock_indexer):
    """Test getting tool recommendations"""
    recommend_tool = get_tool_by_name(mcp_tools, "recommend_tools")

    result = await recommend_tool.fn(task="I need to search for files", limit=5)

    assert isinstance(result, str)
    assert "Recommended" in result
    assert "search" in result.lower()
    mock_indexer.search.assert_called_with("I need to search for files", 5)


@pytest.mark.asyncio
async def test_recommend_tools_no_recommendations(mcp_tools, mock_indexer):
    """Test recommendations when no tools match"""
    # Override mock to return no results
    mock_indexer.search.return_value = ([], "keyword search")

    recommend_tool = get_tool_by_name(mcp_tools, "recommend_tools")
    result = await recommend_tool.fn(task="completely unrelated task", limit=5)

    assert "No tool recommendations" in result


@pytest.mark.asyncio
@pytest.mark.parametrize("task,expected_in_result", [
    ("search for files", "search"),
    ("read a file", "read"),
    ("create an issue", "issue"),
])
async def test_recommend_tools_various_tasks(mcp_tools, task, expected_in_result):
    """Test recommendations for various task descriptions"""
    recommend_tool = get_tool_by_name(mcp_tools, "recommend_tools")

    result = await recommend_tool.fn(task=task, limit=5)

    assert expected_in_result in result.lower()


@pytest.mark.asyncio
async def test_recommend_tools_custom_limit(mcp_tools, mock_indexer):
    """Test recommendations with custom limit"""
    recommend_tool = get_tool_by_name(mcp_tools, "recommend_tools")

    await recommend_tool.fn(task="test task", limit=3)

    mock_indexer.search.assert_called_with("test task", 3)


# ============================================================================
# HEALTH CHECK TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_health_check_endpoint(mcp_server, fixed_datetime):
    """Test health check endpoint returns correct data"""
    from starlette.testclient import TestClient

    app = mcp_server.create_app()
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["total_capabilities"] == 3
    assert data["server"] == "mcp-discovery-service"
    assert data["protocol"] == "mcp"
    assert "last_refresh" in data


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_all_tools_callable(mcp_tools):
    """Test that all registered tools can be called"""
    expected_tools = [
        "search_mcp_tools",
        "list_all_capabilities",
        "get_tool_schema",
        "recommend_tools"
    ]

    for tool_name in expected_tools:
        tool = get_tool_by_name(mcp_tools, tool_name)
        assert tool is not None, f"Tool {tool_name} not found"
        assert callable(tool.fn), f"Tool {tool_name} is not callable"


@pytest.mark.asyncio
async def test_tool_descriptions_present(mcp_tools):
    """Test that all tools have descriptions"""
    for tool in mcp_tools.values():
        if tool.name.startswith(("search_", "list_", "get_", "recommend_")):
            assert tool.description is not None
            assert len(tool.description) > 0


@pytest.mark.asyncio
async def test_tool_parameters_defined(mcp_tools):
    """Test that tools have proper parameter definitions"""
    search_tool = get_tool_by_name(mcp_tools, "search_mcp_tools")
    # The tool should have parameters defined in its function signature
    assert search_tool.fn is not None

    # Test calling with required parameters works
    result = await search_tool.fn(query="test")
    assert isinstance(result, str)
