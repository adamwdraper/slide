"""Tests for the MCPServerManager."""

import os
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import asyncio
import subprocess
from typing import Dict, Any, List, Optional

from tyler.mcp.server_manager import MCPServerManager

@pytest.fixture
def mock_subprocess():
    """Mock the subprocess module."""
    with patch('tyler.mcp.server_manager.subprocess') as mock:
        mock.Popen.return_value = MagicMock()
        mock.Popen.return_value.poll.return_value = None  # Process is running
        mock.Popen.return_value.pid = 12345
        yield mock

@pytest.mark.asyncio
async def test_start_server(mock_subprocess):
    """Test starting an MCP server."""
    # Arrange
    manager = MCPServerManager()
    server_name = "test_server"
    config = {
        "name": server_name,
        "command": "test_command",
        "args": ["arg1", "arg2"],
        "env": {"TEST_ENV": "test_value"}
    }
    
    # Act
    result = await manager.start_server(server_name, config)
    
    # Assert
    assert result is True
    assert server_name in manager.processes
    assert server_name in manager.server_configs
    mock_subprocess.Popen.assert_called_once()
    
    # Verify the command and args were passed correctly
    call_args = mock_subprocess.Popen.call_args[0][0]
    assert call_args[0] == "test_command"
    assert call_args[1:] == ["arg1", "arg2"]

@pytest.mark.asyncio
async def test_start_server_missing_command():
    """Test starting an MCP server with missing command."""
    # Arrange
    manager = MCPServerManager()
    server_name = "test_server"
    config = {
        "name": server_name,
        "args": ["arg1", "arg2"]
    }
    
    # Act
    result = await manager.start_server(server_name, config)
    
    # Assert
    assert result is False
    assert server_name not in manager.processes
    assert server_name not in manager.server_configs

@pytest.mark.asyncio
async def test_start_server_missing_args():
    """Test starting an MCP server with missing args."""
    # Arrange
    manager = MCPServerManager()
    server_name = "test_server"
    config = {
        "name": server_name,
        "command": "test_command"
    }
    
    # Act
    result = await manager.start_server(server_name, config)
    
    # Assert
    assert result is False
    assert server_name not in manager.processes
    assert server_name not in manager.server_configs

@pytest.mark.asyncio
async def test_start_server_already_running(mock_subprocess):
    """Test starting an MCP server that is already running."""
    # Arrange
    manager = MCPServerManager()
    server_name = "test_server"
    config = {
        "name": server_name,
        "command": "test_command",
        "args": ["arg1", "arg2"]
    }
    
    # Start the server once
    await manager.start_server(server_name, config)
    mock_subprocess.Popen.reset_mock()
    
    # Act - try to start it again
    result = await manager.start_server(server_name, config)
    
    # Assert
    assert result is True
    mock_subprocess.Popen.assert_not_called()  # Should not call Popen again

@pytest.mark.asyncio
async def test_start_server_process_fails(mock_subprocess):
    """Test starting an MCP server where the process fails to start."""
    # Arrange
    manager = MCPServerManager()
    server_name = "test_server"
    config = {
        "name": server_name,
        "command": "test_command",
        "args": ["arg1", "arg2"]
    }
    
    # Make the process fail immediately
    mock_subprocess.Popen.return_value.poll.return_value = 1  # Process exited with error
    
    # Act
    result = await manager.start_server(server_name, config)
    
    # Assert
    assert result is False
    assert server_name not in manager.processes
    assert server_name not in manager.server_configs

@pytest.mark.asyncio
async def test_stop_server():
    """Test stopping an MCP server."""
    # Arrange
    manager = MCPServerManager()
    server_name = "test_server"
    
    # Create a mock process
    mock_process = MagicMock()
    mock_process.poll.return_value = None  # Process is running
    mock_process.terminate = MagicMock()
    mock_process.wait = MagicMock()  # Regular MagicMock, not AsyncMock
    
    # Add the process to the manager
    manager.processes[server_name] = mock_process
    manager.server_configs[server_name] = {"name": server_name}
    
    # Patch asyncio.to_thread to return a completed future
    with patch('asyncio.to_thread', new=AsyncMock(return_value=None)) as mock_to_thread:
        # Act
        result = await manager.stop_server(server_name)
        
        # Assert
        assert result is True
        mock_process.terminate.assert_called_once()
        mock_to_thread.assert_called_once_with(mock_process.wait)
        assert server_name not in manager.processes
        assert server_name not in manager.server_configs

@pytest.mark.asyncio
async def test_stop_server_not_running():
    """Test stopping an MCP server that is not running."""
    # Arrange
    manager = MCPServerManager()
    server_name = "test_server"
    
    # Act
    result = await manager.stop_server(server_name)
    
    # Assert
    assert result is False

@pytest.mark.asyncio
async def test_stop_server_already_exited():
    """Test stopping an MCP server that has already exited."""
    # Arrange
    manager = MCPServerManager()
    server_name = "test_server"
    
    # Create a mock process that has already exited
    mock_process = MagicMock()
    mock_process.poll.return_value = 0  # Process has exited
    mock_process.terminate = MagicMock()
    
    # Add the process to the manager
    manager.processes[server_name] = mock_process
    manager.server_configs[server_name] = {"name": server_name}
    
    # Act
    result = await manager.stop_server(server_name)
    
    # Assert
    assert result is True
    mock_process.terminate.assert_not_called()  # Should not try to terminate
    assert server_name not in manager.processes
    assert server_name not in manager.server_configs

@pytest.mark.asyncio
async def test_stop_all_servers():
    """Test stopping all MCP servers."""
    # Arrange
    manager = MCPServerManager()
    
    # Create mock processes
    mock_process1 = MagicMock()
    mock_process1.poll.return_value = None  # Process is running
    mock_process1.terminate = MagicMock()
    mock_process1.wait = MagicMock()  # Regular MagicMock, not AsyncMock
    
    mock_process2 = MagicMock()
    mock_process2.poll.return_value = None  # Process is running
    mock_process2.terminate = MagicMock()
    mock_process2.wait = MagicMock()  # Regular MagicMock, not AsyncMock
    
    # Add the processes to the manager
    manager.processes = {
        "server1": mock_process1,
        "server2": mock_process2
    }
    manager.server_configs = {
        "server1": {"name": "server1"},
        "server2": {"name": "server2"}
    }
    
    # Patch asyncio.to_thread to return a completed future
    with patch('asyncio.to_thread', new=AsyncMock(return_value=None)) as mock_to_thread:
        # Act
        await manager.stop_all_servers()
        
        # Assert
        mock_process1.terminate.assert_called_once()
        mock_process2.terminate.assert_called_once()
        assert mock_to_thread.call_count == 2
        assert len(manager.processes) == 0
        assert len(manager.server_configs) == 0 