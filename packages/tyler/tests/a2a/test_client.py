"""Tests for Tyler A2A client functionality."""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from typing import Dict, Any
from datetime import datetime

from tyler.a2a.client import A2AClient, A2AConnection, HAS_A2A


class TestA2AClient:
    """Test cases for A2AClient."""
    
    def test_import_error_without_a2a_sdk(self):
        """Test that client raises ImportError when a2a-sdk is not available."""
        with patch('tyler.a2a.client.HAS_A2A', False):
            with pytest.raises(ImportError, match="a2a-sdk is required"):
                A2AClient()
    
    @pytest.mark.skipif(not HAS_A2A, reason="a2a-sdk not available")
    def test_client_initialization(self):
        """Test client initialization."""
        client = A2AClient()
        assert client.connections == {}
        assert client._tasks == {}
    
    @pytest.mark.skipif(not HAS_A2A, reason="a2a-sdk not available")
    @pytest.mark.asyncio
    async def test_connect_success(self):
        """Test successful connection to A2A agent."""
        with patch('tyler.a2a.client.A2AHttpClient') as mock_http_client_class:
            # Mock the HTTP client instance
            mock_client_instance = AsyncMock()
            mock_http_client_class.return_value = mock_client_instance
            
            # Mock agent card
            mock_agent_card = Mock()
            mock_agent_card.name = "test_agent"
            mock_agent_card.capabilities = ["test"]
            mock_client_instance.get_agent_card.return_value = mock_agent_card
            
            client = A2AClient()
            result = await client.connect("test", "http://test.com")
            
            assert result is True
            assert "test" in client.connections
            
            connection = client.connections["test"]
            assert connection.name == "test"
            assert connection.base_url == "http://test.com"
            assert connection.agent_card == mock_agent_card
            assert connection.is_connected is True
            
            mock_http_client_class.assert_called_once_with(base_url="http://test.com")
            mock_client_instance.get_agent_card.assert_called_once()
    
    @pytest.mark.skipif(not HAS_A2A, reason="a2a-sdk not available")
    @pytest.mark.asyncio
    async def test_connect_failure(self):
        """Test connection failure."""
        with patch('tyler.a2a.client.A2AHttpClient') as mock_http_client_class:
            mock_client_instance = AsyncMock()
            mock_http_client_class.return_value = mock_client_instance
            mock_client_instance.get_agent_card.side_effect = Exception("Connection failed")
            
            client = A2AClient()
            result = await client.connect("test", "http://test.com")
            
            assert result is False
            assert "test" not in client.connections
    
    @pytest.mark.skipif(not HAS_A2A, reason="a2a-sdk not available")
    @pytest.mark.asyncio
    async def test_connect_duplicate_name(self):
        """Test connecting with duplicate name."""
        client = A2AClient()
        
        # Add existing connection
        existing_connection = A2AConnection(name="test", base_url="http://existing.com")
        client.connections["test"] = existing_connection
        
        result = await client.connect("test", "http://test.com")
        
        assert result is False
        # Original connection should remain
        assert client.connections["test"].base_url == "http://existing.com"
    
    @pytest.mark.skipif(not HAS_A2A, reason="a2a-sdk not available")
    @pytest.mark.asyncio
    async def test_disconnect_success(self):
        """Test successful disconnection."""
        client = A2AClient()
        
        # Add connection and tasks
        connection = A2AConnection(name="test", base_url="http://test.com", is_connected=True)
        client.connections["test"] = connection
        
        mock_task1 = Mock()
        mock_task1._connection_name = "test"
        mock_task2 = Mock()
        mock_task2._connection_name = "other"
        
        client._tasks = {"task1": mock_task1, "task2": mock_task2}
        
        with patch.object(client, 'cancel_task', new_callable=AsyncMock) as mock_cancel:
            await client.disconnect("test")
            
            assert "test" not in client.connections
            mock_cancel.assert_called_once_with("test", "task1")
            # task2 should remain since it belongs to different connection
            assert "task2" in client._tasks
    
    @pytest.mark.skipif(not HAS_A2A, reason="a2a-sdk not available")
    @pytest.mark.asyncio
    async def test_disconnect_not_found(self):
        """Test disconnecting from non-existent connection."""
        client = A2AClient()
        
        # Should not raise an error
        await client.disconnect("nonexistent")
    
    @pytest.mark.skipif(not HAS_A2A, reason="a2a-sdk not available")
    @pytest.mark.asyncio
    async def test_disconnect_all(self):
        """Test disconnecting from all connections."""
        client = A2AClient()
        
        # Add multiple connections
        client.connections["test1"] = A2AConnection(name="test1", base_url="http://test1.com")
        client.connections["test2"] = A2AConnection(name="test2", base_url="http://test2.com")
        
        with patch.object(client, 'disconnect', new_callable=AsyncMock) as mock_disconnect:
            await client.disconnect_all()
            
            assert mock_disconnect.call_count == 2
            mock_disconnect.assert_any_call("test1")
            mock_disconnect.assert_any_call("test2")
    
    @pytest.mark.skipif(not HAS_A2A, reason="a2a-sdk not available")
    def test_is_connected(self):
        """Test connection status check."""
        client = A2AClient()
        
        # Add connected and disconnected connections
        client.connections["connected"] = A2AConnection(
            name="connected", base_url="http://test.com", is_connected=True
        )
        client.connections["disconnected"] = A2AConnection(
            name="disconnected", base_url="http://test.com", is_connected=False
        )
        
        assert client.is_connected("connected") is True
        assert client.is_connected("disconnected") is False
        assert client.is_connected("nonexistent") is False
    
    @pytest.mark.skipif(not HAS_A2A, reason="a2a-sdk not available")
    def test_list_connections(self):
        """Test listing active connections."""
        client = A2AClient()
        
        # Add mixed connections
        client.connections["active1"] = A2AConnection(
            name="active1", base_url="http://test.com", is_connected=True
        )
        client.connections["active2"] = A2AConnection(
            name="active2", base_url="http://test.com", is_connected=True
        )
        client.connections["inactive"] = A2AConnection(
            name="inactive", base_url="http://test.com", is_connected=False
        )
        
        connections = client.list_connections()
        
        assert len(connections) == 2
        assert "active1" in connections
        assert "active2" in connections
        assert "inactive" not in connections
    
    @pytest.mark.skipif(not HAS_A2A, reason="a2a-sdk not available")
    def test_get_agent_card(self):
        """Test getting agent card."""
        client = A2AClient()
        
        mock_agent_card = Mock()
        connection = A2AConnection(
            name="test", base_url="http://test.com", agent_card=mock_agent_card
        )
        client.connections["test"] = connection
        
        result = client.get_agent_card("test")
        assert result == mock_agent_card
        
        # Test non-existent connection
        result = client.get_agent_card("nonexistent")
        assert result is None
    
    @pytest.mark.skipif(not HAS_A2A, reason="a2a-sdk not available")
    @pytest.mark.asyncio
    async def test_create_task_success(self):
        """Test successful task creation."""
        with patch('tyler.a2a.client.Message') as mock_message_class, \
             patch('tyler.a2a.client.TextPart') as mock_text_part_class:
            
            # Mock dependencies
            mock_text_part = Mock()
            mock_text_part_class.return_value = mock_text_part
            
            mock_message = Mock()
            mock_message_class.return_value = mock_message
            
            mock_client_instance = AsyncMock()
            mock_task = Mock()
            mock_task.task_id = "task_123"
            mock_client_instance.create_task.return_value = mock_task
            
            # Setup client with connection
            client = A2AClient()
            connection = A2AConnection(
                name="test", 
                base_url="http://test.com", 
                client=mock_client_instance,
                is_connected=True
            )
            client.connections["test"] = connection
            
            result = await client.create_task("test", "Test task content")
            
            assert result == "task_123"
            assert "task_123" in client._tasks
            
            # Verify task has connection reference
            stored_task = client._tasks["task_123"]
            assert stored_task._connection_name == "test"
            
            # Verify message creation
            mock_text_part_class.assert_called_once_with(text="Test task content")
            mock_message_class.assert_called_once_with(parts=[mock_text_part])
            mock_client_instance.create_task.assert_called_once_with(message=mock_message)
    
    @pytest.mark.skipif(not HAS_A2A, reason="a2a-sdk not available")
    @pytest.mark.asyncio
    async def test_create_task_agent_not_connected(self):
        """Test task creation with non-connected agent."""
        client = A2AClient()
        
        result = await client.create_task("nonexistent", "Test task")
        
        assert result is None
    
    @pytest.mark.skipif(not HAS_A2A, reason="a2a-sdk not available")
    @pytest.mark.asyncio
    async def test_create_task_failure(self):
        """Test task creation failure."""
        mock_client_instance = AsyncMock()
        mock_client_instance.create_task.side_effect = Exception("Task creation failed")
        
        client = A2AClient()
        connection = A2AConnection(
            name="test",
            base_url="http://test.com", 
            client=mock_client_instance,
            is_connected=True
        )
        client.connections["test"] = connection
        
        with patch('tyler.a2a.client.Message'), patch('tyler.a2a.client.TextPart'):
            result = await client.create_task("test", "Test task")
            
            assert result is None
    
    @pytest.mark.skipif(not HAS_A2A, reason="a2a-sdk not available")
    def test_extract_message_content(self):
        """Test message content extraction."""
        client = A2AClient()
        
        # Test message with text parts
        mock_part1 = Mock()
        mock_part1.text = "Hello"
        mock_part2 = Mock()
        mock_part2.text = "World"
        
        mock_message = Mock()
        mock_message.parts = [mock_part1, mock_part2]
        
        result = client._extract_message_content(mock_message)
        assert result == "Hello\nWorld"
        
        # Test message without parts
        mock_message_no_parts = Mock()
        mock_message_no_parts.parts = []
        
        result = client._extract_message_content(mock_message_no_parts)
        assert result == str(mock_message_no_parts)
        
        # Test message without parts attribute
        mock_message_no_attr = Mock(spec=[])  # No parts attribute
        
        result = client._extract_message_content(mock_message_no_attr)
        assert result == str(mock_message_no_attr)
    
    @pytest.mark.skipif(not HAS_A2A, reason="a2a-sdk not available")
    def test_get_connection_info(self):
        """Test getting connection information."""
        client = A2AClient()
        
        mock_agent_card = Mock()
        mock_agent_card.name = "Test Agent"
        mock_agent_card.version = "1.0.0"
        mock_agent_card.capabilities = ["test", "demo"]
        mock_agent_card.description = "Test description"
        
        connection = A2AConnection(
            name="test",
            base_url="http://test.com",
            agent_card=mock_agent_card,
            is_connected=True
        )
        client.connections["test"] = connection
        
        info = client.get_connection_info("test")
        
        assert info is not None
        assert info["name"] == "test"
        assert info["base_url"] == "http://test.com"
        assert info["is_connected"] is True
        assert info["agent_name"] == "Test Agent"
        assert info["agent_version"] == "1.0.0"
        assert info["capabilities"] == ["test", "demo"]
        assert info["description"] == "Test description"
        
        # Test non-existent connection
        info = client.get_connection_info("nonexistent")
        assert info is None


class TestA2AConnection:
    """Test cases for A2AConnection dataclass."""
    
    def test_connection_initialization(self):
        """Test connection initialization."""
        connection = A2AConnection(name="test", base_url="http://test.com")
        
        assert connection.name == "test"
        assert connection.base_url == "http://test.com"
        assert connection.agent_card is None
        assert connection.client is None
        assert connection.is_connected is False
    
    def test_connection_full_initialization(self):
        """Test connection with all parameters."""
        mock_agent_card = Mock()
        mock_client = Mock()
        
        connection = A2AConnection(
            name="test",
            base_url="http://test.com",
            agent_card=mock_agent_card,
            client=mock_client,
            is_connected=True
        )
        
        assert connection.name == "test"
        assert connection.base_url == "http://test.com"
        assert connection.agent_card == mock_agent_card
        assert connection.client == mock_client
        assert connection.is_connected is True