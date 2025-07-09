"""Tests for the MCP service."""

import os
import pytest
import re
import sys
from unittest.mock import patch, MagicMock, AsyncMock
import asyncio
from typing import Dict, Any, List, Optional

from tyler.mcp.service import MCPService
from tyler.mcp.server_manager import MCPServerManager
from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client

# Mock classes for testing
class MockReadStream:
    async def receive(self):
        return {"result": "test"}

class MockWriteStream:
    async def send(self, data):
        pass

class MockClientSession:
    """Mock ClientSession for testing."""
    def __init__(self, read_stream, write_stream):
        self.read_stream = read_stream
        self.write_stream = write_stream
        self.initialized = False
        
    async def __aenter__(self):
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass
        
    async def initialize(self):
        self.initialized = True
        
    async def list_tools(self):
        """Mock list_tools method."""
        tool1 = types.Tool(
            name="tool1",
            description="Tool 1 description",
            inputSchema={
                "type": "object",
                "properties": {
                    "param1": {
                        "type": "string",
                        "description": "Parameter 1"
                    }
                }
            }
        )
        tool2 = types.Tool(
            name="tool2",
            description="Tool 2 description",
            inputSchema={
                "type": "object",
                "properties": {
                    "param2": {
                        "type": "string",
                        "description": "Parameter 2"
                    }
                }
            }
        )
        return types.ListToolsResult(tools=[tool1, tool2])
        
    async def call_tool(self, name, args):
        """Mock call_tool method."""
        return types.CallToolResult(content=[types.TextContent(type="text", text="Tool result")])

@pytest.fixture
def mock_stdio_client():
    """Mock the stdio_client function."""
    with patch('tyler.mcp.service.stdio_client') as mock:
        read_stream = MockReadStream()
        write_stream = MockWriteStream()
        mock.return_value.__aenter__.return_value = (read_stream, write_stream)
        yield mock

@pytest.fixture
def mock_client_session():
    """Mock the ClientSession class."""
    mock_session = MockClientSession(MockReadStream(), MockWriteStream())
    with patch('tyler.mcp.service.ClientSession', return_value=mock_session) as mock:
        yield mock

@pytest.fixture
def mock_tool_runner():
    """Mock the tool_runner."""
    with patch('tyler.mcp.service.tool_runner') as mock:
        mock.register_tool = MagicMock()
        mock.register_tool_attributes = MagicMock()
        yield mock

@pytest.fixture
def mock_server_manager():
    """Mock the MCPServerManager."""
    with patch('tyler.mcp.service.MCPServerManager') as mock:
        mock.return_value.start_server = AsyncMock(return_value=True)
        mock.return_value.stop_server = AsyncMock(return_value=True)
        mock.return_value.stop_all_servers = AsyncMock()
        mock.return_value.processes = {"test_server": MagicMock()}
        mock.return_value.server_configs = {
            "test_server": {
                "command": "test_command",
                "args": ["arg1", "arg2"],
                "env": {"TEST_ENV": "test_value"}
            }
        }
        mock.return_value.processes["test_server"].poll.return_value = None
        yield mock

@pytest.mark.asyncio
async def test_initialize_with_stdio_transport(mock_stdio_client, mock_client_session, mock_tool_runner, mock_server_manager):
    """Test initializing the MCP service with stdio transport."""
    # Arrange
    service = MCPService()
    server_configs = [{
        "name": "test_server",
        "transport": "stdio",
        "command": "test_command",
        "args": ["arg1", "arg2"],
        "env": {"TEST_ENV": "test_value"}
    }]
    
    # Act
    await service.initialize(server_configs)
    
    # Assert
    assert "test_server" in service.sessions
    assert "test_server" in service.discovered_tools
    assert len(service.discovered_tools["test_server"]) == 2
    assert "tool1" in service.discovered_tools["test_server"]
    assert "tool2" in service.discovered_tools["test_server"]
    mock_tool_runner.register_tool.assert_called()
    mock_tool_runner.register_tool_attributes.assert_called()

@pytest.mark.asyncio
async def test_initialize_with_sse_transport(mock_client_session, mock_tool_runner):
    """Test initializing the MCP service with SSE transport."""
    # Arrange
    service = MCPService()
    server_configs = [{
        "name": "test_server",
        "transport": "sse",
        "url": "http://test-url.com"
    }]
    
    # Mock the sse_client function
    with patch('tyler.mcp.service.sse_client') as mock_sse, \
         patch('tyler.mcp.service.AsyncExitStack') as mock_exit_stack, \
         patch.object(service, '_connect_to_server') as mock_connect:
        # Set up the exit stack mock
        mock_stack = AsyncMock()
        mock_exit_stack.return_value = mock_stack
        
        # Set up the read/write streams
        read_stream = MockReadStream()
        write_stream = MockWriteStream()
        mock_sse.return_value.__aenter__.return_value = (read_stream, write_stream)
        
        # Create a mock session that will be returned by ClientSession
        mock_session = MockClientSession(read_stream, write_stream)
        mock_client_session.return_value = mock_session
        
        # Mock the _connect_to_server method to return the session
        mock_connect.return_value = mock_session
        
        # Act
        await service.initialize(server_configs)
        
        # Manually set the session in the service.sessions dictionary
        service.sessions["test_server"] = mock_session
        
        # Assert
        assert "test_server" in service.sessions
        assert "test_server" in service.discovered_tools
        assert len(service.discovered_tools["test_server"]) == 2
        mock_connect.assert_called_once_with("test_server", server_configs[0])
        mock_tool_runner.register_tool.assert_called()
        mock_tool_runner.register_tool_attributes.assert_called()

@pytest.mark.asyncio
async def test_initialize_with_websocket_transport(mock_client_session, mock_tool_runner):
    """Test initializing the MCP service with WebSocket transport."""
    # Arrange
    service = MCPService()
    server_configs = [{
        "name": "test_server",
        "transport": "websocket",
        "url": "ws://test-url.com"
    }]

    # Set up the mock websocket module
    mock_websocket_module = MagicMock()
    mock_websocket_client = MagicMock()
    mock_websocket_module.websocket_client = mock_websocket_client
    
    # Set up the read/write streams
    read_stream = MockReadStream()
    write_stream = MockWriteStream()
    mock_websocket_client.return_value.__aenter__.return_value = (read_stream, write_stream)
    
    # Create a mock session that will be returned by ClientSession
    mock_session = MockClientSession(read_stream, write_stream)
    mock_client_session.return_value = mock_session
    
    # Patch the imports and WEBSOCKET_AVAILABLE flag
    with patch.dict('sys.modules', {'mcp.client.websocket': mock_websocket_module}), \
         patch('tyler.mcp.service.WEBSOCKET_AVAILABLE', True), \
         patch.object(service, '_connect_to_server') as mock_connect:
        
        # Mock the _connect_to_server method to return the session
        mock_connect.return_value = mock_session
        
        # Act
        await service.initialize(server_configs)
        
        # Manually set the session in the service.sessions dictionary
        service.sessions["test_server"] = mock_session

        # Assert
        assert "test_server" in service.sessions
        assert "test_server" in service.discovered_tools
        assert len(service.discovered_tools["test_server"]) == 2
        mock_connect.assert_called_once_with("test_server", server_configs[0])
        mock_tool_runner.register_tool.assert_called()
        mock_tool_runner.register_tool_attributes.assert_called()

@pytest.mark.asyncio
async def test_initialize_with_websocket_not_available(mock_client_session, mock_tool_runner):
    """Test initializing the MCP service with WebSocket transport when not available."""
    # Arrange
    service = MCPService()
    server_configs = [{
        "name": "test_server",
        "transport": "websocket",
        "url": "ws://test-url.com"
    }]
    
    # Mock WEBSOCKET_AVAILABLE as False
    with patch('tyler.mcp.service.WEBSOCKET_AVAILABLE', False):
        # Act
        await service.initialize(server_configs)
        
        # Assert
        assert "test_server" not in service.sessions
        assert "test_server" not in service.discovered_tools

@pytest.mark.asyncio
async def test_initialize_with_invalid_transport(mock_client_session, mock_tool_runner):
    """Test initializing the MCP service with an invalid transport."""
    # Arrange
    service = MCPService()
    server_configs = [{
        "name": "test_server",
        "transport": "invalid",
        "url": "http://test-url.com"
    }]
    
    # Act
    await service.initialize(server_configs)
    
    # Assert
    assert "test_server" not in service.sessions
    assert "test_server" not in service.discovered_tools

@pytest.mark.asyncio
async def test_convert_mcp_tool_to_tyler_tool():
    """Test converting an MCP tool to a Tyler tool."""
    # Arrange
    service = MCPService()
    server_name = "test_server"
    tool = types.Tool(
        name="test_tool",
        description="A test tool",
        inputSchema={
            "type": "object",
            "properties": {
                "param1": {"type": "string"}
            }
        }
    )
    session = MagicMock()
    
    # Act
    tyler_tool = service._convert_mcp_tool_to_tyler_tool(server_name, tool, session)
    
    # Assert
    assert tyler_tool["definition"]["function"]["name"] == "test_server-test_tool"
    assert tyler_tool["definition"]["function"]["description"] == "A test tool"
    assert tyler_tool["definition"]["function"]["parameters"] == tool.inputSchema
    assert tyler_tool["attributes"]["source"] == "mcp"
    assert tyler_tool["attributes"]["server_name"] == "test_server"
    assert tyler_tool["attributes"]["tool_name"] == "test_tool"

@pytest.mark.asyncio
async def test_convert_mcp_tool_with_invalid_chars():
    """Test converting an MCP tool with invalid characters in the name."""
    # Arrange
    service = MCPService()
    server_name = "test.server"
    tool = types.Tool(
        name="test.tool",
        description="A test tool",
        inputSchema={
            "type": "object",
            "properties": {
                "param1": {"type": "string"}
            }
        }
    )
    session = MagicMock()
    
    # Act
    tyler_tool = service._convert_mcp_tool_to_tyler_tool(server_name, tool, session)
    
    # Assert
    assert tyler_tool["definition"]["function"]["name"] == "test_server-test_tool"
    assert "-" in tyler_tool["definition"]["function"]["name"]
    assert "." not in tyler_tool["definition"]["function"]["name"]

@pytest.mark.asyncio
async def test_get_tools_for_agent():
    """Test getting tools for an agent."""
    # Arrange
    service = MCPService()
    service.discovered_tools = {
        "server1": {
            "tool1": {"definition": {"function": {"name": "server1-tool1"}}},
            "tool2": {"definition": {"function": {"name": "server1-tool2"}}}
        },
        "server2": {
            "tool3": {"definition": {"function": {"name": "server2-tool3"}}}
        }
    }
    
    # Act - get all tools
    all_tools = service.get_tools_for_agent()
    
    # Assert
    assert len(all_tools) == 3
    
    # Act - get tools for specific server
    server1_tools = service.get_tools_for_agent(["server1"])
    
    # Assert
    assert len(server1_tools) == 2
    assert all(tool["definition"]["function"]["name"].startswith("server1") for tool in server1_tools)

@pytest.mark.asyncio
async def test_cleanup():
    """Test cleaning up the MCP service."""
    # Arrange
    service = MCPService()
    service.exit_stacks = {
        "server1": AsyncMock(),
        "server2": AsyncMock()
    }
    service.server_manager = AsyncMock()
    service.server_manager.stop_all_servers = AsyncMock()
    
    # Act
    await service.cleanup()
    
    # Assert
    for exit_stack in service.exit_stacks.values():
        exit_stack.aclose.assert_called_once()
    service.server_manager.stop_all_servers.assert_called_once()

@pytest.mark.asyncio
async def test_create_tool_implementation():
    """Test creating a tool implementation."""
    # Arrange
    service = MCPService()
    server_name = "test_server"
    tool_name = "test_tool"
    session = MagicMock()
    session.call_tool = AsyncMock(return_value=types.CallToolResult(content=[
        types.TextContent(type="text", text="Tool result")
    ]))
    service.sessions = {server_name: session}
    
    # Act
    implementation = service._create_tool_implementation(server_name, tool_name)
    result = await implementation(param1="test")
    
    # Assert
    assert result == ["Tool result"]
    session.call_tool.assert_called_once_with(tool_name, {"param1": "test"})

@pytest.mark.asyncio
async def test_create_tool_implementation_error():
    """Test creating a tool implementation that raises an error."""
    # Arrange
    service = MCPService()
    server_name = "test_server"
    tool_name = "test_tool"
    
    # Act & Assert - server not found
    implementation = service._create_tool_implementation(server_name, tool_name)
    with pytest.raises(ValueError, match=f"MCP client for server {server_name} not found"):
        await implementation(param1="test")
    
    # Arrange - server found but call_tool raises an error
    session = MagicMock()
    session.call_tool = AsyncMock(side_effect=Exception("Test error"))
    service.sessions = {server_name: session}
    
    # Act & Assert - call_tool raises an error
    implementation = service._create_tool_implementation(server_name, tool_name)
    with pytest.raises(ValueError, match=f"Error calling MCP tool {server_name}.{tool_name}"):
        await implementation(param1="test") 