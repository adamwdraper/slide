"""Tests for the Tyler MCP adapter."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from tyler.mcp.adapter import MCPAdapter


@pytest.fixture
def mock_mcp_tool():
    """Create a mock MCP tool."""
    tool = MagicMock()
    tool.name = "test_tool"
    tool.description = "A test tool"
    tool.inputSchema = {
        "type": "object",
        "properties": {
            "arg1": {"type": "string"},
            "arg2": {"type": "number"}
        },
        "required": ["arg1"]
    }
    return tool


@pytest.mark.asyncio
async def test_adapter_connect():
    """Test connecting through the adapter."""
    adapter = MCPAdapter()
    
    # Mock the client connect and tool discovery
    with patch.object(adapter.client, 'connect', return_value=True) as mock_connect:
        with patch.object(adapter, '_register_server_tools') as mock_register:
            connected = await adapter.connect(
                name="test",
                transport="stdio",
                command="test-command"
            )
            
            assert connected is True
            mock_connect.assert_called_once_with(
                "test",
                "stdio",
                command="test-command"
            )
            mock_register.assert_called_once_with("test")


@pytest.mark.asyncio
async def test_adapter_connect_failure():
    """Test handling connection failure."""
    adapter = MCPAdapter()
    
    # Mock connection failure
    with patch.object(adapter.client, 'connect', return_value=False):
        connected = await adapter.connect(
            name="test",
            transport="stdio",
            command="test-command"
        )
        
        assert connected is False


def test_convert_to_tyler_format(mock_mcp_tool):
    """Test converting MCP tool to Tyler format."""
    adapter = MCPAdapter()
    
    tyler_tool = adapter._convert_to_tyler_format("test_server", mock_mcp_tool)
    
    # Check structure
    assert "definition" in tyler_tool
    assert "implementation" in tyler_tool
    assert "attributes" in tyler_tool
    
    # Check definition
    definition = tyler_tool["definition"]["function"]
    assert definition["name"] == "test_tool"  # Original name (not namespaced by adapter)
    assert definition["description"] == "A test tool"
    assert definition["parameters"] == mock_mcp_tool.inputSchema
    
    # Check attributes
    attrs = tyler_tool["attributes"]
    assert attrs["source"] == "mcp"
    assert attrs["server_name"] == "test_server"
    assert attrs["original_name"] == "test_tool"


def test_create_tyler_name():
    """Test creating Tyler-safe tool names."""
    adapter = MCPAdapter()
    
    # Test normal case
    name = adapter._create_tyler_name("server", "tool")
    assert name == "server_tool"  # Single underscore
    
    # Test with special characters
    name = adapter._create_tyler_name("my-server", "tool.name")
    assert name == "my_server_tool_name"  # Single underscore separator
    
    # Test starting with number
    name = adapter._create_tyler_name("123", "456")
    assert name == "_123_456"  # Single underscore separator


@pytest.mark.asyncio
async def test_tool_implementation():
    """Test the generated tool implementation function."""
    adapter = MCPAdapter()
    
    # Mock the client call_tool
    mock_result = MagicMock()
    mock_result.content = [MagicMock(text="Result text")]
    
    with patch.object(adapter.client, 'call_tool', return_value=mock_result) as mock_call:
        # Get the implementation function
        impl = adapter._create_tool_implementation("server", "tool")
        
        # Call it
        result = await impl(arg1="value1", arg2=42)
        
        assert result == "Result text"
        mock_call.assert_called_once_with("server", "tool", {"arg1": "value1", "arg2": 42})


@pytest.mark.asyncio
async def test_tool_implementation_multiple_contents():
    """Test tool implementation with multiple content items."""
    adapter = MCPAdapter()
    
    # Mock multiple content items
    mock_result = MagicMock()
    mock_result.content = [
        MagicMock(text="Result 1"),
        MagicMock(text="Result 2")
    ]
    
    with patch.object(adapter.client, 'call_tool', return_value=mock_result):
        impl = adapter._create_tool_implementation("server", "tool")
        result = await impl()
        
        assert result == ["Result 1", "Result 2"]


@pytest.mark.asyncio
async def test_register_server_tools(mock_mcp_tool):
    """Test registering tools from a server."""
    adapter = MCPAdapter()
    
    # Mock client.get_tools
    with patch.object(adapter.client, 'get_tools', return_value=[mock_mcp_tool]):
        with patch('tyler.mcp.adapter.tool_runner') as mock_runner:
            await adapter._register_server_tools("test_server")
            
            # Verify tool was registered
            mock_runner.register_tool.assert_called_once()
            call_args = mock_runner.register_tool.call_args
            
            assert call_args.kwargs["name"] == "test_tool"  # Original name (not namespaced by adapter)
            assert callable(call_args.kwargs["implementation"])
            assert call_args.kwargs["definition"]["name"] == "test_tool"  # Original name
            
            # Verify attributes were registered
            mock_runner.register_tool_attributes.assert_called_once()


def test_get_tools_for_agent(mock_mcp_tool):
    """Test getting tools formatted for Tyler agents."""
    adapter = MCPAdapter()
    
    # Mock connected servers and tools
    with patch.object(adapter.client, 'list_connections', return_value=["server1", "server2"]):
        with patch.object(adapter.client, 'get_tools') as mock_get_tools:
            mock_get_tools.side_effect = lambda s: [mock_mcp_tool] if s == "server1" else []
            
            # Get all tools
            tools = adapter.get_tools_for_agent()
            assert len(tools) == 1
            assert tools[0]["definition"]["function"]["name"] == "test_tool"  # Original name (not namespaced by adapter)
            
            # Get tools from specific server
            with patch.object(adapter.client, 'is_connected', return_value=True):
                tools = adapter.get_tools_for_agent(["server1"])
                assert len(tools) == 1
            
            # Get tools from non-connected server
            with patch.object(adapter.client, 'is_connected', return_value=False):
                tools = adapter.get_tools_for_agent(["server3"])
                assert len(tools) == 0


@pytest.mark.asyncio
async def test_disconnect():
    """Test disconnecting from a server."""
    adapter = MCPAdapter()
    
    # Set up registered tools
    adapter._registered_tools = {
        "server1__tool1": "server1",
        "server1__tool2": "server1",
        "server2__tool1": "server2"
    }
    
    # Disconnect from server1
    with patch.object(adapter.client, 'disconnect') as mock_disconnect:
        await adapter.disconnect("server1")
        
        # Verify tools were unregistered
        assert "server1__tool1" not in adapter._registered_tools
        assert "server1__tool2" not in adapter._registered_tools
        assert "server2__tool1" in adapter._registered_tools
        
        # Verify client disconnect was called
        mock_disconnect.assert_called_once_with("server1")


@pytest.mark.asyncio
async def test_disconnect_all():
    """Test disconnecting from all servers."""
    adapter = MCPAdapter()
    
    # Set up registered tools
    adapter._registered_tools = {
        "server1__tool1": "server1",
        "server2__tool1": "server2"
    }
    
    with patch.object(adapter.client, 'disconnect_all') as mock_disconnect_all:
        await adapter.disconnect_all()
        
        # Verify all tools were cleared
        assert len(adapter._registered_tools) == 0
        
        # Verify client disconnect_all was called
        mock_disconnect_all.assert_called_once() 