"""Integration tests for MCP configuration with Agent.

Tests full end-to-end flow: config → connect → execute → cleanup.
"""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from tyler import Agent, Thread, Message


@pytest.mark.asyncio
class TestMCPIntegration:
    """Integration tests for full MCP flow."""
    
    async def test_full_flow_agent_with_mcp(self):
        """Test complete flow: Agent(mcp={...}) → connect_mcp() → go() → cleanup()."""
        mcp_config = {
            "servers": [{
                "name": "test",
                "transport": "sse",
                "url": "https://example.com/mcp"
            }]
        }
        
        # Mock the tool implementation
        async def mock_search_tool(query: str) -> str:
            return f"Search results for: {query}"
        
        with patch('tyler.mcp.config_loader._load_mcp_config') as mock_load:
            mock_load.return_value = (
                [{
                    "definition": {
                        "type": "function",
                        "function": {
                            "name": "test_search",
                            "description": "Search documentation",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "query": {"type": "string", "description": "Search query"}
                                },
                                "required": ["query"]
                            }
                        }
                    },
                    "implementation": mock_search_tool
                }],
                AsyncMock()  # disconnect callback
            )
            
            # Step 1: Create agent with MCP config
            agent = Agent(
                name="TestAgent",
                model_name="gpt-4o-mini",
                mcp=mcp_config
            )
            
            assert not agent._mcp_connected
            
            # Step 2: Connect to MCP servers
            await agent.connect_mcp()
            
            assert agent._mcp_connected
            assert "test_search" in [t["function"]["name"] for t in agent._processed_tools]
            
            # Step 3: Use agent (would execute MCP tool)
            thread = Thread()
            thread.add_message(Message(role="user", content="Test message"))
            
            # Mock the step method to avoid real API call
            with patch.object(agent, 'step') as mock_step:
                # Mock response without tool calls (to avoid actual execution)
                mock_response = MagicMock()
                mock_response.choices = [MagicMock()]
                mock_response.choices[0].message.content = "Test response"
                mock_response.choices[0].message.tool_calls = None
                
                mock_step.return_value = (mock_response, {})
                
                result = await agent.run(thread)
                
                assert result.content is not None
            
            # Step 4: Cleanup
            await agent.cleanup()
            
            assert not agent._mcp_connected
    
    async def test_multiple_servers_integration(self):
        """Test agent with multiple MCP servers."""
        mcp_config = {
            "servers": [
                {"name": "server1", "transport": "sse", "url": "https://s1.com/mcp"},
                {"name": "server2", "transport": "sse", "url": "https://s2.com/mcp", "prefix": "s2"}
            ]
        }
        
        with patch('tyler.mcp.config_loader.MCPAdapter') as mock_adapter_class:
            mock_adapter = MagicMock()
            mock_adapter.connect = AsyncMock(return_value=True)
            mock_adapter.disconnect_all = AsyncMock()
            
            # Return different tools for each server
            def get_tools_side_effect(server_names=None):
                if server_names and "server1" in server_names:
                    return [{"definition": {"function": {"name": "tool1"}}, "implementation": AsyncMock()}]
                elif server_names and "server2" in server_names:
                    return [{"definition": {"function": {"name": "tool2"}}, "implementation": AsyncMock()}]
                return []
            
            mock_adapter.get_tools_for_agent.side_effect = get_tools_side_effect
            mock_adapter_class.return_value = mock_adapter
            
            agent = Agent(model_name="gpt-4o-mini", mcp=mcp_config)
            await agent.connect_mcp()
            
            # Verify both servers' tools are registered with correct namespaces
            tool_names = [t["function"]["name"] for t in agent._processed_tools]
            assert "server1_tool1" in tool_names
            assert "s2_tool2" in tool_names  # Custom prefix
            
            await agent.cleanup()
    
    async def test_tool_filtering_integration(self):
        """Test tool filtering works end-to-end."""
        mcp_config = {
            "servers": [{
                "name": "test",
                "transport": "sse",
                "url": "https://example.com/mcp",
                "include_tools": ["search"],
                "exclude_tools": ["delete"]
            }]
        }
        
        with patch('tyler.mcp.config_loader.MCPAdapter') as mock_adapter_class:
            mock_adapter = MagicMock()
            mock_adapter.connect = AsyncMock(return_value=True)
            mock_adapter.disconnect_all = AsyncMock()
            mock_adapter.get_tools_for_agent.return_value = [
                {"definition": {"function": {"name": "search"}}, "implementation": AsyncMock()},
                {"definition": {"function": {"name": "query"}}, "implementation": AsyncMock()},
                {"definition": {"function": {"name": "delete"}}, "implementation": AsyncMock()}
            ]
            mock_adapter_class.return_value = mock_adapter
            
            agent = Agent(model_name="gpt-4o-mini", mcp=mcp_config)
            await agent.connect_mcp()
            
            # Only test_search should be registered (included and not excluded)
            tool_names = [t["function"]["name"] for t in agent._processed_tools]
            assert "test_search" in tool_names
            assert "test_query" not in tool_names  # Not in include list
            assert "test_delete" not in tool_names  # In exclude list
            
            await agent.cleanup()
    
    async def test_fail_silent_integration(self):
        """Test fail_silent behavior with multiple servers."""
        mcp_config = {
            "servers": [
                {"name": "working", "transport": "sse", "url": "https://working.com/mcp"},
                {"name": "broken", "transport": "sse", "url": "https://broken.com/mcp", "fail_silent": True}
            ]
        }
        
        with patch('tyler.mcp.config_loader.MCPAdapter') as mock_adapter_class:
            mock_adapter = MagicMock()
            # First succeeds, second fails
            mock_adapter.connect = AsyncMock(side_effect=[True, False])
            mock_adapter.disconnect_all = AsyncMock()
            mock_adapter.get_tools_for_agent.return_value = [
                {"definition": {"function": {"name": "tool1"}}, "implementation": AsyncMock()}
            ]
            mock_adapter_class.return_value = mock_adapter
            
            agent = Agent(model_name="gpt-4o-mini", mcp=mcp_config)
            
            # Should not raise despite second server failing
            await agent.connect_mcp()
            
            # Should have tools from first server
            tool_names = [t["function"]["name"] for t in agent._processed_tools]
            assert "working_tool1" in tool_names
            
            await agent.cleanup()
    
    async def test_schema_validation_in_init(self):
        """Test that schema validation happens in Agent.__init__ (fail fast)."""
        invalid_config = {
            "servers": "not a list"  # Invalid
        }
        
        # Should raise immediately in __init__, not in connect_mcp()
        with pytest.raises(ValueError, match="must be a list"):
            agent = Agent(mcp=invalid_config)
    
    async def test_connection_error_in_connect_mcp(self):
        """Test that connection errors happen in connect_mcp() (fail fast)."""
        mcp_config = {
            "servers": [{
                "name": "broken",
                "transport": "sse",
                "url": "https://broken.com/mcp",
                "fail_silent": False
            }]
        }
        
        agent = Agent(model_name="gpt-4o-mini", mcp=mcp_config)
        
        with patch('tyler.mcp.config_loader._load_mcp_config') as mock_load:
            mock_load.side_effect = ValueError("Connection refused")
            
            # Error should happen here, not in agent.run()
            with pytest.raises(ValueError, match="Connection refused"):
                await agent.connect_mcp()
    
    async def test_system_prompt_regeneration(self):
        """Test that system prompt includes MCP tools after connect_mcp()."""
        mcp_config = {
            "servers": [{
                "name": "test",
                "transport": "sse",
                "url": "https://example.com/mcp"
            }]
        }
        
        with patch('tyler.mcp.config_loader._load_mcp_config') as mock_load:
            mock_load.return_value = (
                [{
                    "definition": {
                        "type": "function",
                        "function": {
                            "name": "mcp_search",
                            "description": "Search with MCP",
                            "parameters": {}
                        }
                    },
                    "implementation": AsyncMock()
                }],
                AsyncMock()
            )
            
            agent = Agent(model_name="gpt-4o-mini", tools=["web"], mcp=mcp_config)
            
            # System prompt before MCP
            initial_prompt = agent._system_prompt
            assert "mcp_search" not in initial_prompt
            
            # Connect MCP
            await agent.connect_mcp()
            
            # System prompt after MCP should include new tool
            updated_prompt = agent._system_prompt
            assert "mcp_search" in updated_prompt
            assert "Search with MCP" in updated_prompt
            
            await agent.cleanup()

