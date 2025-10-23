"""Tests for Agent MCP integration.

Tests Agent.connect_mcp() and Agent.cleanup() methods following TDD.
"""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from tyler import Agent, Thread, Message


class TestAgentMCPValidation:
    """Test Agent MCP config validation in __init__."""
    
    def test_agent_init_validates_mcp_config_schema(self):
        """Test Agent.__init__ validates MCP config and raises immediately on invalid schema."""
        invalid_config = {
            "servers": [{
                "name": "test",
                "transport": "sse"
                # Missing required 'url' field
            }]
        }
        
        # Should raise ValueError immediately in __init__
        with pytest.raises(ValueError, match="requires 'url' field"):
            agent = Agent(
                name="TestAgent",
                model_name="gpt-4o-mini",
                mcp=invalid_config
            )
    
    def test_agent_init_succeeds_with_valid_mcp_config(self):
        """Test Agent.__init__ succeeds with valid MCP config."""
        valid_config = {
            "servers": [{
                "name": "test",
                "transport": "sse",
                "url": "https://example.com/mcp"
            }]
        }
        
        # Should not raise
        agent = Agent(
            name="TestAgent",
            model_name="gpt-4o-mini",
            mcp=valid_config
        )
        
        assert agent.mcp == valid_config
        assert agent._mcp_connected == False
    
    def test_agent_init_without_mcp_config(self):
        """Test Agent.__init__ works normally without MCP config."""
        agent = Agent(
            name="TestAgent",
            model_name="gpt-4o-mini"
        )
        
        assert agent.mcp is None
        assert agent._mcp_connected == False


@pytest.mark.asyncio
class TestAgentConnectMCP:
    """Test Agent.connect_mcp() method."""
    
    async def test_connect_mcp_with_valid_config(self):
        """Test connect_mcp() connects to servers and registers tools."""
        mcp_config = {
            "servers": [{
                "name": "test",
                "transport": "sse",
                "url": "https://example.com/mcp"
            }]
        }
        
        agent = Agent(
            name="TestAgent",
            model_name="gpt-4o-mini",
            tools=["web"],
            mcp=mcp_config
        )
        
        # Mock _load_mcp_config
        with patch('tyler.mcp.config_loader._load_mcp_config') as mock_load:
            mock_load.return_value = (
                [{
                    "definition": {"type": "function", "function": {"name": "test_search", "description": "Search", "parameters": {}}},
                    "implementation": AsyncMock()
                }],
                AsyncMock()  # disconnect callback
            )
            
            # Before connect_mcp
            initial_tool_count = len(agent._processed_tools)
            assert not agent._mcp_connected
            
            # Connect to MCP
            await agent.connect_mcp()
            
            # After connect_mcp
            assert agent._mcp_connected
            assert len(agent._processed_tools) > initial_tool_count
            
            # Verify tool was added
            tool_names = [t["function"]["name"] for t in agent._processed_tools]
            assert "test_search" in tool_names
    
    async def test_connect_mcp_without_mcp_config(self):
        """Test connect_mcp() returns gracefully when no MCP config."""
        agent = Agent(name="TestAgent", model_name="gpt-4o-mini")
        
        # Should not raise, just log warning
        await agent.connect_mcp()
        
        assert not agent._mcp_connected
    
    async def test_connect_mcp_called_twice_is_idempotent(self):
        """Test calling connect_mcp() twice doesn't reconnect."""
        mcp_config = {
            "servers": [{
                "name": "test",
                "transport": "sse",
                "url": "https://example.com/mcp"
            }]
        }
        
        agent = Agent(
            name="TestAgent",
            model_name="gpt-4o-mini",
            mcp=mcp_config
        )
        
        with patch('tyler.mcp.config_loader._load_mcp_config') as mock_load:
            mock_load.return_value = (
                [{"definition": {"function": {"name": "test_tool", "description": "", "parameters": {}}}, "implementation": AsyncMock()}],
                AsyncMock()
            )
            
            # First call
            await agent.connect_mcp()
            assert mock_load.call_count == 1
            
            # Second call should skip (already connected)
            await agent.connect_mcp()
            assert mock_load.call_count == 1  # Still 1, not 2
    
    async def test_connect_mcp_connection_failure_fail_silent_false(self):
        """Test connect_mcp() raises exception when connection fails (fail_silent=false)."""
        mcp_config = {
            "servers": [{
                "name": "broken",
                "transport": "sse",
                "url": "https://broken.com/mcp",
                "fail_silent": False
            }]
        }
        
        agent = Agent(
            name="TestAgent",
            model_name="gpt-4o-mini",
            mcp=mcp_config
        )
        
        with patch('tyler.mcp.config_loader._load_mcp_config') as mock_load:
            mock_load.side_effect = ValueError("Failed to connect to MCP server 'broken'")
            
            # Should raise the error
            with pytest.raises(ValueError, match="Failed to connect"):
                await agent.connect_mcp()
            
            # Should not be marked as connected
            assert not agent._mcp_connected
    
    async def test_connect_mcp_updates_system_prompt_with_new_tools(self):
        """Test connect_mcp() regenerates system prompt with MCP tools."""
        mcp_config = {
            "servers": [{
                "name": "test",
                "transport": "sse",
                "url": "https://example.com/mcp"
            }]
        }
        
        agent = Agent(
            name="TestAgent",
            model_name="gpt-4o-mini",
            mcp=mcp_config
        )
        
        initial_prompt = agent._system_prompt
        
        with patch('tyler.mcp.config_loader._load_mcp_config') as mock_load:
            mock_load.return_value = (
                [{
                    "definition": {"type": "function", "function": {"name": "mcp_tool", "description": "MCP Tool", "parameters": {}}},
                    "implementation": AsyncMock()
                }],
                AsyncMock()
            )
            
            await agent.connect_mcp()
            
            # System prompt should be regenerated to include new tool
            assert agent._system_prompt != initial_prompt
            assert "mcp_tool" in agent._system_prompt


@pytest.mark.asyncio
class TestAgentCleanup:
    """Test Agent.cleanup() method."""
    
    async def test_cleanup_disconnects_mcp(self):
        """Test cleanup() calls MCP disconnect callback."""
        mcp_config = {
            "servers": [{
                "name": "test",
                "transport": "sse",
                "url": "https://example.com/mcp"
            }]
        }
        
        agent = Agent(
            name="TestAgent",
            model_name="gpt-4o-mini",
            mcp=mcp_config
        )
        
        mock_disconnect = AsyncMock()
        
        with patch('tyler.mcp.config_loader._load_mcp_config') as mock_load:
            mock_load.return_value = (
                [{"definition": {"function": {"name": "test_tool", "description": "", "parameters": {}}}, "implementation": AsyncMock()}],
                mock_disconnect
            )
            
            await agent.connect_mcp()
            assert agent._mcp_connected
            
            # Cleanup
            await agent.cleanup()
            
            # Verify disconnect was called
            mock_disconnect.assert_called_once()
            assert not agent._mcp_connected
    
    async def test_cleanup_without_mcp_connection(self):
        """Test cleanup() works even if MCP never connected."""
        agent = Agent(name="TestAgent", model_name="gpt-4o-mini")
        
        # Should not raise
        await agent.cleanup()
    
    async def test_cleanup_can_reconnect_after(self):
        """Test agent can reconnect after cleanup."""
        mcp_config = {
            "servers": [{
                "name": "test",
                "transport": "sse",
                "url": "https://example.com/mcp"
            }]
        }
        
        agent = Agent(
            name="TestAgent",
            model_name="gpt-4o-mini",
            mcp=mcp_config
        )
        
        with patch('tyler.mcp.config_loader._load_mcp_config') as mock_load:
            mock_load.return_value = (
                [{"definition": {"function": {"name": "test_tool", "description": "", "parameters": {}}}, "implementation": AsyncMock()}],
                AsyncMock()
            )
            
            # Connect, cleanup, connect again
            await agent.connect_mcp()
            assert agent._mcp_connected
            
            await agent.cleanup()
            assert not agent._mcp_connected
            
            await agent.connect_mcp()
            assert agent._mcp_connected
            
            # Should have called _load_mcp_config twice
            assert mock_load.call_count == 2

