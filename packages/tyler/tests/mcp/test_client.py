"""Tests for the MCP client."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from tyler.mcp.client import MCPClient


@pytest.mark.asyncio
async def test_client_connect_stdio():
    """Test connecting via stdio transport."""
    client = MCPClient()
    
    # Mock the stdio_client and ClientSession
    mock_session = AsyncMock()
    mock_session.initialize = AsyncMock()
    mock_session.list_tools = AsyncMock(return_value=MagicMock(tools=[]))
    
    with patch('tyler.mcp.client.stdio_client') as mock_stdio:
        with patch('tyler.mcp.client.ClientSession') as mock_session_class:
            # Configure mocks
            mock_stdio.return_value.__aenter__.return_value = (MagicMock(), MagicMock())
            mock_session_class.return_value.__aenter__.return_value = mock_session
            
            # Connect
            connected = await client.connect(
                name="test",
                transport="stdio",
                command="test-command",
                args=["arg1", "arg2"]
            )
            
            assert connected is True
            assert "test" in client.sessions
            assert client.is_connected("test")


@pytest.mark.asyncio
async def test_client_connect_sse():
    """Test connecting via SSE transport."""
    client = MCPClient()
    
    # Mock the sse_client and ClientSession
    mock_session = AsyncMock()
    mock_session.initialize = AsyncMock()
    mock_session.list_tools = AsyncMock(return_value=MagicMock(tools=[]))
    
    with patch('tyler.mcp.client.sse_client') as mock_sse:
        with patch('tyler.mcp.client.ClientSession') as mock_session_class:
            # Configure mocks
            mock_sse.return_value.__aenter__.return_value = (MagicMock(), MagicMock())
            mock_session_class.return_value.__aenter__.return_value = mock_session
            
            # Connect
            connected = await client.connect(
                name="test",
                transport="sse",
                url="http://localhost:3000/sse"
            )
            
            assert connected is True
            assert "test" in client.sessions


@pytest.mark.asyncio
async def test_client_connect_invalid_transport():
    """Test connecting with invalid transport."""
    client = MCPClient()
    
    connected = await client.connect(
        name="test",
        transport="invalid",
        url="http://localhost:3000"
    )
    
    assert connected is False
    assert not client.is_connected("test")


@pytest.mark.asyncio
async def test_client_get_tools():
    """Test getting tools from connected servers."""
    client = MCPClient()
    
    # Mock tools
    mock_tool1 = MagicMock()
    mock_tool1.name = "tool1"
    mock_tool1.description = "Test tool 1"
    
    mock_tool2 = MagicMock()
    mock_tool2.name = "tool2"
    mock_tool2.description = "Test tool 2"
    
    # Set up discovered tools
    client._discovered_tools = {
        "server1": [mock_tool1],
        "server2": [mock_tool2]
    }
    
    # Get tools from specific server
    tools = client.get_tools("server1")
    assert len(tools) == 1
    assert tools[0].name == "tool1"
    
    # Get all tools
    all_tools = client.get_tools()
    assert len(all_tools) == 2


@pytest.mark.asyncio
async def test_client_call_tool():
    """Test calling a tool on a server."""
    client = MCPClient()
    
    # Mock session
    mock_session = AsyncMock()
    mock_result = MagicMock(content=[MagicMock(text="Tool result")])
    mock_session.call_tool = AsyncMock(return_value=mock_result)
    
    client.sessions["test"] = mock_session
    
    # Call tool
    result = await client.call_tool("test", "my_tool", {"arg": "value"})
    
    assert result == mock_result
    mock_session.call_tool.assert_called_once_with("my_tool", {"arg": "value"})


@pytest.mark.asyncio
async def test_client_call_tool_not_connected():
    """Test calling a tool when not connected."""
    client = MCPClient()
    
    with pytest.raises(ValueError, match="Not connected to server 'test'"):
        await client.call_tool("test", "my_tool", {})


@pytest.mark.asyncio
async def test_client_disconnect():
    """Test disconnecting from a server."""
    client = MCPClient()
    
    # Set up a mock connection
    mock_exit_stack = AsyncMock()
    client.exit_stacks["test"] = mock_exit_stack
    client.sessions["test"] = MagicMock()
    client._discovered_tools["test"] = []
    
    # Disconnect
    await client.disconnect("test")
    
    # Verify cleanup
    assert "test" not in client.exit_stacks
    assert "test" not in client.sessions
    assert "test" not in client._discovered_tools
    mock_exit_stack.aclose.assert_called_once()


@pytest.mark.asyncio
async def test_client_disconnect_all():
    """Test disconnecting from all servers."""
    client = MCPClient()
    
    # Set up mock connections
    for name in ["test1", "test2"]:
        client.exit_stacks[name] = AsyncMock()
        client.sessions[name] = MagicMock()
        client._discovered_tools[name] = []
    
    # Disconnect all
    await client.disconnect_all()
    
    # Verify all cleaned up
    assert len(client.exit_stacks) == 0
    assert len(client.sessions) == 0
    assert len(client._discovered_tools) == 0 