"""Tests for MCP config loader.

Following TDD: These tests are written BEFORE implementation.
They should all fail initially, then pass as we implement.
"""
import pytest
import os
from unittest.mock import patch, AsyncMock, MagicMock
from tyler.mcp.config_loader import (
    _validate_mcp_config,
    _validate_server_config,
    _load_mcp_config,
    _substitute_env_vars,
    _apply_tool_filters,
    _namespace_tools
)


class TestValidation:
    """Test config validation functions."""
    
    def test_validate_mcp_config_missing_servers_key(self):
        """Test validation fails when 'servers' key is missing."""
        config = {"wrong_key": []}
        
        with pytest.raises(ValueError, match="must have 'servers' key"):
            _validate_mcp_config(config)
    
    def test_validate_mcp_config_servers_not_list(self):
        """Test validation fails when 'servers' is not a list."""
        config = {"servers": "not-a-list"}
        
        with pytest.raises(ValueError, match="must be a list"):
            _validate_mcp_config(config)
    
    def test_validate_mcp_config_valid(self):
        """Test validation passes with valid config."""
        config = {
            "servers": [{
                "name": "test",
                "transport": "sse",
                "url": "https://example.com/mcp"
            }]
        }
        
        # Should not raise
        _validate_mcp_config(config)
    
    def test_validate_server_config_missing_name(self):
        """Test server validation fails when 'name' is missing."""
        server = {"transport": "sse", "url": "https://example.com"}
        
        with pytest.raises(ValueError, match="missing required field 'name'"):
            _validate_server_config(server)
    
    def test_validate_server_config_missing_transport(self):
        """Test server validation fails when 'transport' is missing."""
        server = {"name": "test", "url": "https://example.com"}
        
        with pytest.raises(ValueError, match="missing required field 'transport'"):
            _validate_server_config(server)
    
    def test_validate_server_config_invalid_transport(self):
        """Test server validation fails with invalid transport type."""
        server = {
            "name": "test",
            "transport": "http",  # Invalid (should be 'streamablehttp')
            "url": "https://example.com"
        }
        
        with pytest.raises(ValueError, match="Invalid transport 'http'"):
            _validate_server_config(server)
    
    def test_validate_server_config_sse_missing_url(self):
        """Test SSE server validation fails when 'url' is missing."""
        server = {
            "name": "test",
            "transport": "sse"
            # Missing 'url'
        }
        
        with pytest.raises(ValueError, match="requires 'url' field"):
            _validate_server_config(server)
    
    def test_validate_server_config_websocket_missing_url(self):
        """Test WebSocket server validation fails when 'url' is missing."""
        server = {
            "name": "test",
            "transport": "websocket"
            # Missing 'url'
        }
        
        with pytest.raises(ValueError, match="requires 'url' field"):
            _validate_server_config(server)
    
    def test_validate_server_config_stdio_missing_command(self):
        """Test stdio server validation fails when 'command' is missing."""
        server = {
            "name": "test",
            "transport": "stdio"
            # Missing 'command'
        }
        
        with pytest.raises(ValueError, match="requires 'command' field"):
            _validate_server_config(server)
    
    def test_validate_server_config_valid_sse(self):
        """Test valid SSE server config."""
        server = {
            "name": "test",
            "transport": "sse",
            "url": "https://example.com/mcp"
        }
        
        # Should not raise
        _validate_server_config(server)
    
    def test_validate_server_config_valid_stdio(self):
        """Test valid stdio server config."""
        server = {
            "name": "test",
            "transport": "stdio",
            "command": "npx",
            "args": ["-y", "server"]
        }
        
        # Should not raise
        _validate_server_config(server)
    
    def test_validate_server_config_valid_streamablehttp(self):
        """Test valid streamablehttp server config (for Mintlify)."""
        server = {
            "name": "mintlify",
            "transport": "streamablehttp",
            "url": "https://slide.mintlify.app/mcp"
        }
        
        # Should not raise
        _validate_server_config(server)
    
    def test_validate_server_config_streamablehttp_missing_url(self):
        """Test streamablehttp server validation fails when 'url' is missing."""
        server = {
            "name": "test",
            "transport": "streamablehttp"
            # Missing 'url'
        }
        
        with pytest.raises(ValueError, match="requires 'url' field"):
            _validate_server_config(server)


class TestEnvVarSubstitution:
    """Test environment variable substitution."""
    
    def test_substitute_env_vars_simple_string(self):
        """Test substitution in simple string."""
        os.environ["TEST_VAR"] = "test_value"
        
        result = _substitute_env_vars("${TEST_VAR}")
        assert result == "test_value"
        
        del os.environ["TEST_VAR"]
    
    def test_substitute_env_vars_in_dict(self):
        """Test substitution in nested dict."""
        os.environ["TEST_TOKEN"] = "secret123"
        
        config = {
            "url": "https://example.com",
            "headers": {
                "Authorization": "Bearer ${TEST_TOKEN}"
            }
        }
        
        result = _substitute_env_vars(config)
        assert result["headers"]["Authorization"] == "Bearer secret123"
        
        del os.environ["TEST_TOKEN"]
    
    def test_substitute_env_vars_in_list(self):
        """Test substitution in lists."""
        os.environ["TEST_PATH"] = "/test/path"
        
        config = {"args": ["--path", "${TEST_PATH}"]}
        
        result = _substitute_env_vars(config)
        assert result["args"][1] == "/test/path"
        
        del os.environ["TEST_PATH"]
    
    def test_substitute_env_vars_missing_var_keeps_original(self):
        """Test missing env var keeps original string."""
        result = _substitute_env_vars("${NONEXISTENT_VAR}")
        assert result == "${NONEXISTENT_VAR}"
    
    def test_substitute_env_vars_multiple_in_string(self):
        """Test multiple env vars in single string."""
        os.environ["USER"] = "adam"
        os.environ["HOST"] = "localhost"
        
        result = _substitute_env_vars("${USER}@${HOST}")
        assert result == "adam@localhost"
        
        del os.environ["USER"]
        del os.environ["HOST"]


class TestToolFiltering:
    """Test tool filtering logic."""
    
    def test_apply_tool_filters_no_filters(self):
        """Test all tools pass through when no filters specified."""
        tools = [
            {"definition": {"function": {"name": "tool1"}}},
            {"definition": {"function": {"name": "tool2"}}},
            {"definition": {"function": {"name": "tool3"}}}
        ]
        server = {"name": "test"}  # No include/exclude
        
        result = _apply_tool_filters(tools, server)
        assert len(result) == 3
    
    def test_apply_tool_filters_include_only(self):
        """Test include_tools whitelist."""
        tools = [
            {"definition": {"function": {"name": "tool1"}}},
            {"definition": {"function": {"name": "tool2"}}},
            {"definition": {"function": {"name": "tool3"}}}
        ]
        server = {"name": "test", "include_tools": ["tool1", "tool3"]}
        
        result = _apply_tool_filters(tools, server)
        assert len(result) == 2
        names = [t["definition"]["function"]["name"] for t in result]
        assert "tool1" in names
        assert "tool3" in names
        assert "tool2" not in names
    
    def test_apply_tool_filters_exclude_only(self):
        """Test exclude_tools blacklist."""
        tools = [
            {"definition": {"function": {"name": "tool1"}}},
            {"definition": {"function": {"name": "tool2"}}},
            {"definition": {"function": {"name": "tool3"}}}
        ]
        server = {"name": "test", "exclude_tools": ["tool2"]}
        
        result = _apply_tool_filters(tools, server)
        assert len(result) == 2
        names = [t["definition"]["function"]["name"] for t in result]
        assert "tool1" in names
        assert "tool3" in names
        assert "tool2" not in names
    
    def test_apply_tool_filters_include_and_exclude(self):
        """Test include and exclude together (include first, then exclude)."""
        tools = [
            {"definition": {"function": {"name": "tool1"}}},
            {"definition": {"function": {"name": "tool2"}}},
            {"definition": {"function": {"name": "tool3"}}}
        ]
        server = {
            "name": "test",
            "include_tools": ["tool1", "tool2"],
            "exclude_tools": ["tool2"]
        }
        
        result = _apply_tool_filters(tools, server)
        # tool1 included and not excluded → keep
        # tool2 included BUT excluded → remove
        # tool3 not included → remove
        assert len(result) == 1
        assert result[0]["definition"]["function"]["name"] == "tool1"


class TestToolNamespacing:
    """Test tool namespacing logic."""
    
    def test_namespace_tools_default(self):
        """Test namespacing with server name."""
        tools = [
            {"definition": {"type": "function", "function": {"name": "search"}}},
            {"definition": {"type": "function", "function": {"name": "query"}}}
        ]
        prefix = "mintlify"
        
        result = _namespace_tools(tools, prefix)
        
        assert len(result) == 2
        assert result[0]["definition"]["function"]["name"] == "mintlify_search"
        assert result[1]["definition"]["function"]["name"] == "mintlify_query"
    
    def test_namespace_tools_custom_prefix(self):
        """Test namespacing with custom prefix."""
        tools = [
            {"definition": {"type": "function", "function": {"name": "search"}}}
        ]
        prefix = "docs"
        
        result = _namespace_tools(tools, prefix)
        
        assert result[0]["definition"]["function"]["name"] == "docs_search"
    
    def test_namespace_tools_sanitizes_special_chars(self):
        """Test prefix sanitization (special chars → underscores)."""
        tools = [
            {"definition": {"type": "function", "function": {"name": "search"}}}
        ]
        prefix = "my-server.name"
        
        result = _namespace_tools(tools, prefix)
        
        # Special chars should be replaced with underscores
        assert result[0]["definition"]["function"]["name"] == "my_server_name_search"
    
    def test_namespace_tools_preserves_original(self):
        """Test original tools are not mutated."""
        original_tool = {"definition": {"type": "function", "function": {"name": "search"}}}
        tools = [original_tool]
        
        result = _namespace_tools(tools, "prefix")
        
        # Original should be unchanged
        assert original_tool["definition"]["function"]["name"] == "search"
        # Result should be namespaced
        assert result[0]["definition"]["function"]["name"] == "prefix_search"


@pytest.mark.asyncio
class TestLoadMCPConfig:
    """Test main config loading function."""
    
    async def test_load_mcp_config_single_server(self):
        """Test loading config with single server."""
        config = {
            "servers": [{
                "name": "test",
                "transport": "sse",
                "url": "https://example.com/mcp"
            }]
        }
        
        # Mock MCPAdapter
        with patch('tyler.mcp.config_loader.MCPAdapter') as mock_adapter_class:
            mock_adapter = MagicMock()
            mock_adapter.connect = AsyncMock(return_value=True)
            mock_adapter.disconnect_all = AsyncMock()
            mock_adapter.get_tools_for_agent.return_value = [  # Sync method!
                {
                    "definition": {"type": "function", "function": {"name": "search"}},
                    "implementation": AsyncMock()
                }
            ]
            mock_adapter_class.return_value = mock_adapter
            
            tools, disconnect = await _load_mcp_config(config)
            
            # Verify connection
            mock_adapter.connect.assert_called_once_with(
                "test", "sse", url="https://example.com/mcp"
            )
            
            # Verify tools returned with namespace
            assert len(tools) == 1
            assert tools[0]["definition"]["function"]["name"] == "test_search"
            
            # Verify disconnect callback works
            assert callable(disconnect)
            await disconnect()
            mock_adapter.disconnect_all.assert_called_once()
    
    async def test_load_mcp_config_multiple_servers(self):
        """Test loading config with multiple servers."""
        config = {
            "servers": [
                {"name": "server1", "transport": "sse", "url": "https://s1.com/mcp"},
                {"name": "server2", "transport": "sse", "url": "https://s2.com/mcp"}
            ]
        }
        
        with patch('tyler.mcp.config_loader.MCPAdapter') as mock_adapter_class:
            mock_adapter = MagicMock()
            mock_adapter.connect = AsyncMock(return_value=True)
            mock_adapter.disconnect_all = AsyncMock()
            
            # Different tools from each server
            def get_tools_side_effect(server_names=None):
                if server_names and "server1" in server_names:
                    return [{"definition": {"function": {"name": "tool1"}}}]
                elif server_names and "server2" in server_names:
                    return [{"definition": {"function": {"name": "tool2"}}}]
                return []
            
            mock_adapter.get_tools_for_agent.side_effect = get_tools_side_effect  # Sync method!
            mock_adapter_class.return_value = mock_adapter
            
            tools, disconnect = await _load_mcp_config(config)
            
            # Should have tools from both servers
            assert len(tools) == 2
            names = [t["definition"]["function"]["name"] for t in tools]
            assert "server1_tool1" in names
            assert "server2_tool2" in names
    
    async def test_load_mcp_config_with_custom_prefix(self):
        """Test custom prefix override."""
        config = {
            "servers": [{
                "name": "mintlify",
                "transport": "sse",
                "url": "https://example.com/mcp",
                "prefix": "docs"  # Custom prefix
            }]
        }
        
        with patch('tyler.mcp.config_loader.MCPAdapter') as mock_adapter_class:
            mock_adapter = MagicMock()
            mock_adapter.connect = AsyncMock(return_value=True)
            mock_adapter.disconnect_all = AsyncMock()
            mock_adapter.get_tools_for_agent.return_value = [  # Sync method!
                {"definition": {"function": {"name": "search"}}}
            ]
            mock_adapter_class.return_value = mock_adapter
            
            tools, _ = await _load_mcp_config(config)
            
            # Should use custom prefix
            assert tools[0]["definition"]["function"]["name"] == "docs_search"
    
    async def test_load_mcp_config_with_tool_filters(self):
        """Test tool filtering during load."""
        config = {
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
            mock_adapter.get_tools_for_agent.return_value = [  # Sync method!
                {"definition": {"function": {"name": "search"}}},
                {"definition": {"function": {"name": "query"}}},
                {"definition": {"function": {"name": "delete"}}}
            ]
            mock_adapter_class.return_value = mock_adapter
            
            tools, _ = await _load_mcp_config(config)
            
            # Only 'search' should remain
            assert len(tools) == 1
            assert "search" in tools[0]["definition"]["function"]["name"]
    
    async def test_load_mcp_config_connection_failure_fail_silent_true(self):
        """Test graceful degradation when server fails to connect (fail_silent=true)."""
        config = {
            "servers": [
                {"name": "working", "transport": "sse", "url": "https://working.com/mcp"},
                {"name": "broken", "transport": "sse", "url": "https://broken.com/mcp", "fail_silent": True}
            ]
        }
        
        with patch('tyler.mcp.config_loader.MCPAdapter') as mock_adapter_class:
            mock_adapter = MagicMock()
            # First server succeeds, second fails
            mock_adapter.connect = AsyncMock(side_effect=[True, False])
            mock_adapter.disconnect_all = AsyncMock()
            mock_adapter.get_tools_for_agent.return_value = [  # Sync method!
                {"definition": {"function": {"name": "tool1"}}}
            ]
            mock_adapter_class.return_value = mock_adapter
            
            # Should not raise despite second server failing
            tools, _ = await _load_mcp_config(config)
            
            # Should have tools from first server only
            assert len(tools) > 0
    
    async def test_load_mcp_config_connection_failure_fail_silent_false(self):
        """Test error raised when server fails to connect (fail_silent=false)."""
        config = {
            "servers": [{
                "name": "broken",
                "transport": "sse",
                "url": "https://broken.com/mcp",
                "fail_silent": False
            }]
        }
        
        with patch('tyler.mcp.config_loader.MCPAdapter') as mock_adapter_class:
            mock_adapter = MagicMock()
            mock_adapter.connect = AsyncMock(return_value=False)
            mock_adapter.disconnect_all = AsyncMock()
            mock_adapter_class.return_value = mock_adapter
            
            # Should raise ValueError
            with pytest.raises(ValueError, match="Failed to connect"):
                await _load_mcp_config(config)
    
    async def test_load_mcp_config_env_var_substitution(self):
        """Test environment variables are substituted in config."""
        os.environ["MCP_URL"] = "https://example.com/mcp"
        os.environ["MCP_TOKEN"] = "secret123"
        
        config = {
            "servers": [{
                "name": "test",
                "transport": "sse",
                "url": "${MCP_URL}",
                "headers": {
                    "Authorization": "Bearer ${MCP_TOKEN}"
                }
            }]
        }
        
        with patch('tyler.mcp.config_loader.MCPAdapter') as mock_adapter_class:
            mock_adapter = MagicMock()
            mock_adapter.connect = AsyncMock(return_value=True)
            mock_adapter.disconnect_all = AsyncMock()
            mock_adapter.get_tools_for_agent.return_value = []  # Sync method!
            mock_adapter_class.return_value = mock_adapter
            
            await _load_mcp_config(config)
            
            # Verify substitution happened
            call_kwargs = mock_adapter.connect.call_args[1]
            assert call_kwargs["url"] == "https://example.com/mcp"
            assert call_kwargs["headers"]["Authorization"] == "Bearer secret123"
        
        del os.environ["MCP_URL"]
        del os.environ["MCP_TOKEN"]


class TestEdgeCases:
    """Test edge cases and error handling."""
    
    async def test_load_mcp_config_empty_servers_list(self):
        """Test empty servers list returns empty tools."""
        config = {"servers": []}
        
        tools, disconnect = await _load_mcp_config(config)
        
        assert tools == []
        await disconnect()  # Should not raise
    
    async def test_load_mcp_config_server_with_no_tools(self):
        """Test server that returns no tools."""
        config = {
            "servers": [{
                "name": "test",
                "transport": "sse",
                "url": "https://example.com/mcp"
            }]
        }
        
        with patch('tyler.mcp.config_loader.MCPAdapter') as mock_adapter_class:
            mock_adapter = MagicMock()
            mock_adapter.connect = AsyncMock(return_value=True)
            mock_adapter.disconnect_all = AsyncMock()
            mock_adapter.get_tools_for_agent.return_value = []  # Sync method! No tools
            mock_adapter_class.return_value = mock_adapter
            
            tools, _ = await _load_mcp_config(config)
            
            assert tools == []

