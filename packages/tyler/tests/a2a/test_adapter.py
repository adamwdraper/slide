"""Tests for Tyler A2A adapter functionality."""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from typing import Dict, Any

from tyler.a2a.adapter import A2AAdapter, HAS_A2A


class TestA2AAdapter:
    """Test cases for A2AAdapter."""
    
    def test_import_error_without_a2a_sdk(self):
        """Test that adapter raises ImportError when a2a-sdk is not available."""
        with patch('tyler.a2a.adapter.HAS_A2A', False):
            with pytest.raises(ImportError, match="a2a-sdk is required"):
                A2AAdapter()
    
    @pytest.mark.skipif(not HAS_A2A, reason="a2a-sdk not available")
    def test_adapter_initialization(self):
        """Test adapter initialization."""
        adapter = A2AAdapter()
        assert adapter.client is not None
        assert adapter._registered_tools == {}
    
    @pytest.mark.skipif(not HAS_A2A, reason="a2a-sdk not available")
    def test_adapter_with_custom_client(self):
        """Test adapter initialization with custom client."""
        from tyler.a2a.client import A2AClient
        
        mock_client = Mock(spec=A2AClient)
        adapter = A2AAdapter(a2a_client=mock_client)
        assert adapter.client is mock_client
    
    @pytest.mark.skipif(not HAS_A2A, reason="a2a-sdk not available")
    @pytest.mark.asyncio
    async def test_connect_success(self):
        """Test successful connection to A2A agent."""
        mock_client = AsyncMock()
        mock_client.connect.return_value = True
        
        # Mock agent card
        mock_agent_card = Mock()
        mock_agent_card.name = "test_agent"
        mock_agent_card.description = "Test agent"
        mock_agent_card.capabilities = ["test_capability"]
        mock_client.get_agent_card.return_value = mock_agent_card
        
        adapter = A2AAdapter(a2a_client=mock_client)
        
        with patch.object(adapter, '_register_agent_capabilities', new_callable=AsyncMock) as mock_register:
            result = await adapter.connect("test_agent", "http://test.com")
            
            assert result is True
            mock_client.connect.assert_called_once_with("test_agent", "http://test.com")
            mock_register.assert_called_once_with("test_agent")
    
    @pytest.mark.skipif(not HAS_A2A, reason="a2a-sdk not available") 
    @pytest.mark.asyncio
    async def test_connect_failure(self):
        """Test connection failure."""
        mock_client = AsyncMock()
        mock_client.connect.return_value = False
        
        adapter = A2AAdapter(a2a_client=mock_client)
        
        result = await adapter.connect("test_agent", "http://test.com")
        
        assert result is False
        mock_client.connect.assert_called_once_with("test_agent", "http://test.com")
    
    @pytest.mark.skipif(not HAS_A2A, reason="a2a-sdk not available")
    @pytest.mark.asyncio
    async def test_connect_registration_failure(self):
        """Test connection success but registration failure."""
        mock_client = AsyncMock()
        mock_client.connect.return_value = True
        mock_client.disconnect = AsyncMock()
        
        adapter = A2AAdapter(a2a_client=mock_client)
        
        with patch.object(adapter, '_register_agent_capabilities', new_callable=AsyncMock) as mock_register:
            mock_register.side_effect = Exception("Registration failed")
            
            result = await adapter.connect("test_agent", "http://test.com")
            
            assert result is False
            mock_client.disconnect.assert_called_once_with("test_agent")
    
    @pytest.mark.skipif(not HAS_A2A, reason="a2a-sdk not available")
    def test_create_tyler_name(self):
        """Test Tyler tool name creation."""
        adapter = A2AAdapter()
        
        # Test normal name
        result = adapter._create_tyler_name("research_agent")
        assert result == "delegate_to_research_agent"
        
        # Test name with special characters
        result = adapter._create_tyler_name("agent-with-dashes")
        assert result == "delegate_to_agent_with_dashes"
        
        # Test name starting with number
        result = adapter._create_tyler_name("2nd_agent")
        assert result == "_delegate_to_2nd_agent"
    
    @pytest.mark.skipif(not HAS_A2A, reason="a2a-sdk not available")
    def test_create_delegation_tool(self):
        """Test delegation tool creation."""
        adapter = A2AAdapter()
        
        # Mock agent card
        mock_agent_card = Mock()
        mock_agent_card.name = "test_agent"
        mock_agent_card.description = "Test agent for research"
        mock_agent_card.capabilities = ["research", "analysis"]
        
        result = adapter._create_delegation_tool("test_agent", mock_agent_card)
        
        assert result["definition"]["type"] == "function"
        assert result["definition"]["function"]["name"] == "delegate_to_test_agent"
        assert "research, analysis" in result["definition"]["function"]["description"]
        assert "task_description" in result["definition"]["function"]["parameters"]["properties"]
        assert result["attributes"]["source"] == "a2a"
        assert result["attributes"]["agent_name"] == "test_agent"
        assert result["attributes"]["delegation_tool"] is True
    
    @pytest.mark.skipif(not HAS_A2A, reason="a2a-sdk not available")
    @pytest.mark.asyncio
    async def test_delegation_implementation(self):
        """Test delegation function implementation."""
        mock_client = AsyncMock()
        mock_client.create_task.return_value = "task_123"
        
        adapter = A2AAdapter(a2a_client=mock_client)
        
        # Create delegation function
        delegate_func = adapter._create_delegation_implementation("test_agent")
        
        # Test synchronous delegation
        with patch.object(adapter, '_handle_sync_response', new_callable=AsyncMock) as mock_sync:
            mock_sync.return_value = "Task completed successfully"
            
            result = await delegate_func(
                task_description="Test task",
                context="Test context",
                stream_response=False
            )
            
            mock_client.create_task.assert_called_once()
            mock_sync.assert_called_once_with("test_agent", "task_123", "Test task\n\nContext: Test context")
            assert result == "Task completed successfully"
    
    @pytest.mark.skipif(not HAS_A2A, reason="a2a-sdk not available")
    @pytest.mark.asyncio
    async def test_delegation_implementation_streaming(self):
        """Test streaming delegation function implementation."""
        mock_client = AsyncMock()
        mock_client.create_task.return_value = "task_123"
        
        adapter = A2AAdapter(a2a_client=mock_client)
        
        # Create delegation function
        delegate_func = adapter._create_delegation_implementation("test_agent")
        
        # Test streaming delegation
        with patch.object(adapter, '_handle_streaming_response', new_callable=AsyncMock) as mock_stream:
            mock_stream.return_value = iter(["chunk1", "chunk2", "chunk3"])
            
            result = await delegate_func(
                task_description="Test task", 
                stream_response=True
            )
            
            mock_client.create_task.assert_called_once()
            mock_stream.assert_called_once()
            # Result should be the streaming iterator
            assert result is not None
    
    @pytest.mark.skipif(not HAS_A2A, reason="a2a-sdk not available")
    @pytest.mark.asyncio
    async def test_delegation_task_creation_failure(self):
        """Test delegation when task creation fails."""
        mock_client = AsyncMock()
        mock_client.create_task.return_value = None  # Task creation failed
        
        adapter = A2AAdapter(a2a_client=mock_client)
        
        # Create delegation function
        delegate_func = adapter._create_delegation_implementation("test_agent")
        
        result = await delegate_func(task_description="Test task")
        
        assert "Failed to create task" in result
        assert "test_agent" in result
    
    @pytest.mark.skipif(not HAS_A2A, reason="a2a-sdk not available")
    def test_get_tools_for_agent(self):
        """Test getting tools for agents."""
        mock_client = Mock()
        mock_client.list_connections.return_value = ["agent1", "agent2"]
        mock_client.is_connected.return_value = True
        
        # Mock agent cards
        mock_agent_card1 = Mock()
        mock_agent_card1.name = "agent1"
        mock_agent_card1.description = "First agent"
        mock_agent_card1.capabilities = ["cap1"]
        
        mock_agent_card2 = Mock()
        mock_agent_card2.name = "agent2" 
        mock_agent_card2.description = "Second agent"
        mock_agent_card2.capabilities = ["cap2"]
        
        mock_client.get_agent_card.side_effect = [mock_agent_card1, mock_agent_card2]
        
        adapter = A2AAdapter(a2a_client=mock_client)
        
        tools = adapter.get_tools_for_agent()
        
        assert len(tools) == 2
        assert tools[0]["definition"]["function"]["name"] == "delegate_to_agent1"
        assert tools[1]["definition"]["function"]["name"] == "delegate_to_agent2"
    
    @pytest.mark.skipif(not HAS_A2A, reason="a2a-sdk not available")
    def test_get_tools_for_specific_agents(self):
        """Test getting tools for specific agents."""
        mock_client = Mock()
        mock_client.is_connected.side_effect = lambda name: name == "agent1"
        
        mock_agent_card = Mock()
        mock_agent_card.name = "agent1"
        mock_agent_card.description = "Test agent"
        mock_agent_card.capabilities = ["test"]
        
        mock_client.get_agent_card.return_value = mock_agent_card
        
        adapter = A2AAdapter(a2a_client=mock_client)
        
        tools = adapter.get_tools_for_agent(["agent1", "agent2"])
        
        assert len(tools) == 1
        assert tools[0]["definition"]["function"]["name"] == "delegate_to_agent1"
    
    @pytest.mark.skipif(not HAS_A2A, reason="a2a-sdk not available")
    @pytest.mark.asyncio
    async def test_disconnect(self):
        """Test disconnecting from agent."""
        mock_client = AsyncMock()
        
        adapter = A2AAdapter(a2a_client=mock_client)
        adapter._registered_tools = {"delegate_to_agent1": "agent1", "delegate_to_agent2": "agent2"}
        
        await adapter.disconnect("agent1")
        
        mock_client.disconnect.assert_called_once_with("agent1")
        assert "delegate_to_agent1" not in adapter._registered_tools
        assert "delegate_to_agent2" in adapter._registered_tools
    
    @pytest.mark.skipif(not HAS_A2A, reason="a2a-sdk not available")
    @pytest.mark.asyncio
    async def test_disconnect_all(self):
        """Test disconnecting from all agents."""
        mock_client = AsyncMock()
        
        adapter = A2AAdapter(a2a_client=mock_client)
        adapter._registered_tools = {"tool1": "agent1", "tool2": "agent2"}
        
        await adapter.disconnect_all()
        
        mock_client.disconnect_all.assert_called_once()
        assert adapter._registered_tools == {}
    
    @pytest.mark.skipif(not HAS_A2A, reason="a2a-sdk not available")
    def test_list_connected_agents(self):
        """Test listing connected agents."""
        mock_client = Mock()
        mock_client.list_connections.return_value = ["agent1", "agent2"]
        mock_client.get_connection_info.side_effect = [
            {"name": "agent1", "status": "connected"},
            {"name": "agent2", "status": "connected"}
        ]
        
        adapter = A2AAdapter(a2a_client=mock_client)
        
        agents = adapter.list_connected_agents()
        
        assert len(agents) == 2
        assert agents[0]["name"] == "agent1"
        assert agents[1]["name"] == "agent2"
    
    @pytest.mark.skipif(not HAS_A2A, reason="a2a-sdk not available")
    @pytest.mark.asyncio
    async def test_get_agent_status(self):
        """Test getting agent status."""
        mock_client = Mock()
        mock_client.is_connected.return_value = True
        mock_client.get_connection_info.return_value = {"name": "agent1", "status": "connected"}
        mock_client._tasks = {
            "task1": Mock(_connection_name="agent1"),
            "task2": Mock(_connection_name="agent2")
        }
        
        adapter = A2AAdapter(a2a_client=mock_client)
        
        status = await adapter.get_agent_status("agent1")
        
        assert status is not None
        assert status["name"] == "agent1"
        assert status["active_tasks"] == 1  # Only task1 belongs to agent1
    
    @pytest.mark.skipif(not HAS_A2A, reason="a2a-sdk not available")
    @pytest.mark.asyncio
    async def test_get_agent_status_not_connected(self):
        """Test getting status for disconnected agent."""
        mock_client = Mock()
        mock_client.is_connected.return_value = False
        
        adapter = A2AAdapter(a2a_client=mock_client)
        
        status = await adapter.get_agent_status("agent1")
        
        assert status is None