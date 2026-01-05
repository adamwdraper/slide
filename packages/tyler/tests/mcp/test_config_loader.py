"""Tests for MCP config loader.

Tests the config validation, environment variable substitution,
and the SDK-based ClientSessionGroup integration.
"""
import pytest
import os
from unittest.mock import patch, AsyncMock, MagicMock
from tyler.mcp.config_loader import (
    _validate_mcp_config,
    _validate_server_config,
    _load_mcp_config,
    _substitute_env_vars,
    _build_server_params,
    _create_tool_implementation,
    _convert_tools_for_agent,
)
from mcp.client.session_group import (
    StdioServerParameters,
    SseServerParameters,
    StreamableHttpParameters,
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
    
    def test_validate_server_config_websocket_not_supported(self):
        """Test WebSocket transport is not supported by ClientSessionGroup."""
        server = {
            "name": "test",
            "transport": "websocket",
            "url": "wss://example.com/mcp"
        }
        
        # websocket transport is not supported - SDK's ClientSessionGroup doesn't have it
        with pytest.raises(ValueError, match="Invalid transport"):
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


class TestBuildServerParams:
    """Test server parameter building."""
    
    def test_build_stdio_params(self):
        """Test building StdioServerParameters."""
        server = {
            "name": "test",
            "transport": "stdio",
            "command": "npx",
            "args": ["-y", "server"],
            "env": {"NODE_ENV": "production"}
        }
        
        params = _build_server_params(server)
        
        assert isinstance(params, StdioServerParameters)
        assert params.command == "npx"
        assert params.args == ["-y", "server"]
        assert params.env == {"NODE_ENV": "production"}
    
    def test_build_sse_params(self):
        """Test building SseServerParameters."""
        server = {
            "name": "test",
            "transport": "sse",
            "url": "https://example.com/mcp",
            "headers": {"Authorization": "Bearer token"}
        }
        
        params = _build_server_params(server)
        
        assert isinstance(params, SseServerParameters)
        assert params.url == "https://example.com/mcp"
        assert params.headers == {"Authorization": "Bearer token"}
    
    def test_build_streamablehttp_params(self):
        """Test building StreamableHttpParameters."""
        server = {
            "name": "test",
            "transport": "streamablehttp",
            "url": "https://example.com/mcp",
            "headers": {"X-API-Key": "key123"}
        }
        
        params = _build_server_params(server)
        
        assert isinstance(params, StreamableHttpParameters)
        assert params.url == "https://example.com/mcp"
        assert params.headers == {"X-API-Key": "key123"}


class TestToolConversion:
    """Test tool conversion to Tyler format."""
    
    def test_convert_tools_with_prefix(self):
        """Test tools are converted with prefix."""
        mock_group = MagicMock()
        mock_tool = MagicMock()
        mock_tool.name = "search"  # Original tool name
        mock_tool.description = "A test tool"
        mock_tool.inputSchema = {"type": "object", "properties": {}}
        # Dict key is SDK-namespaced, tool.name is original
        mock_group.tools = {"_0_search": mock_tool}
        
        new_sdk_tool_names = {"_0_search"}
        
        tools = _convert_tools_for_agent(
            mock_group, new_sdk_tool_names, "docs", None, []
        )
        
        assert len(tools) == 1
        assert tools[0]["definition"]["function"]["name"] == "docs_search"
        assert tools[0]["definition"]["function"]["description"] == "A test tool"
        assert tools[0]["attributes"]["source"] == "mcp"
        assert tools[0]["attributes"]["mcp_original_name"] == "search"
        assert tools[0]["attributes"]["mcp_sdk_name"] == "_0_search"
    
    def test_convert_tools_with_include_filter(self):
        """Test include_tools filter uses original names."""
        mock_group = MagicMock()
        mock_tool1 = MagicMock()
        mock_tool1.name = "tool1"  # Original name
        mock_tool1.description = "Tool 1"
        mock_tool1.inputSchema = {}
        mock_tool2 = MagicMock()
        mock_tool2.name = "tool2"  # Original name
        mock_tool2.description = "Tool 2"
        mock_tool2.inputSchema = {}
        # SDK-namespaced keys
        mock_group.tools = {"_0_tool1": mock_tool1, "_0_tool2": mock_tool2}
        
        new_sdk_tool_names = {"_0_tool1", "_0_tool2"}
        
        # Include filter uses original name "tool1"
        tools = _convert_tools_for_agent(
            mock_group, new_sdk_tool_names, "server", ["tool1"], []
        )
        
        assert len(tools) == 1
        assert tools[0]["definition"]["function"]["name"] == "server_tool1"
    
    def test_convert_tools_with_exclude_filter(self):
        """Test exclude_tools filter uses original names."""
        mock_group = MagicMock()
        mock_tool1 = MagicMock()
        mock_tool1.name = "tool1"  # Original name
        mock_tool1.description = "Tool 1"
        mock_tool1.inputSchema = {}
        mock_tool2 = MagicMock()
        mock_tool2.name = "tool2"  # Original name
        mock_tool2.description = "Tool 2"
        mock_tool2.inputSchema = {}
        # SDK-namespaced keys
        mock_group.tools = {"_0_tool1": mock_tool1, "_0_tool2": mock_tool2}
        
        new_sdk_tool_names = {"_0_tool1", "_0_tool2"}
        
        # Exclude filter uses original name "tool2"
        tools = _convert_tools_for_agent(
            mock_group, new_sdk_tool_names, "server", None, ["tool2"]
        )
        
        assert len(tools) == 1
        assert tools[0]["definition"]["function"]["name"] == "server_tool1"
    
    def test_convert_tools_sanitizes_prefix(self):
        """Test prefix with special characters is sanitized."""
        mock_group = MagicMock()
        mock_tool = MagicMock()
        mock_tool.name = "search"  # Original name
        mock_tool.description = "Test"
        mock_tool.inputSchema = {}
        mock_group.tools = {"_0_search": mock_tool}
        
        new_sdk_tool_names = {"_0_search"}
        
        tools = _convert_tools_for_agent(
            mock_group, new_sdk_tool_names, "my-server.name", None, []
        )
        
        assert tools[0]["definition"]["function"]["name"] == "my_server_name_search"


class TestToolImplementation:
    """Test tool implementation creation."""
    
    @pytest.mark.asyncio
    async def test_tool_implementation_returns_text_content(self):
        """Test tool implementation extracts text from content."""
        mock_group = MagicMock()
        mock_result = MagicMock()
        mock_result.structuredContent = None
        mock_content = MagicMock()
        mock_content.text = "Result text"
        mock_result.content = [mock_content]
        mock_group.call_tool = AsyncMock(return_value=mock_result)
        
        # sdk_tool_name is used for routing, display_name for logging
        impl = _create_tool_implementation(mock_group, "_0_test_tool", "test_tool")
        result = await impl(arg1="value")
        
        assert result == "Result text"
        # Should call with SDK-namespaced name for correct routing
        mock_group.call_tool.assert_called_once_with(
            "_0_test_tool", {"arg1": "value"}, progress_callback=None
        )
    
    @pytest.mark.asyncio
    async def test_tool_implementation_returns_structured_content(self):
        """Test tool implementation prefers structuredContent."""
        mock_group = MagicMock()
        mock_result = MagicMock()
        mock_result.structuredContent = {"data": "structured"}
        mock_result.content = [MagicMock(text="fallback")]
        mock_group.call_tool = AsyncMock(return_value=mock_result)
        
        impl = _create_tool_implementation(mock_group, "_0_test_tool", "test_tool")
        result = await impl()
        
        assert result == {"data": "structured"}
    
    @pytest.mark.asyncio
    async def test_tool_implementation_returns_multiple_contents(self):
        """Test tool implementation returns list for multiple content items."""
        mock_group = MagicMock()
        mock_result = MagicMock()
        mock_result.structuredContent = None
        mock_result.content = [
            MagicMock(text="Result 1"),
            MagicMock(text="Result 2")
        ]
        mock_group.call_tool = AsyncMock(return_value=mock_result)
        
        impl = _create_tool_implementation(mock_group, "_0_test_tool", "test_tool")
        result = await impl()
        
        assert result == ["Result 1", "Result 2"]
    
    @pytest.mark.asyncio
    async def test_tool_implementation_passes_progress_callback(self):
        """Test tool implementation passes progress callback from context to SDK."""
        from tyler.utils.tool_runner import ToolContext
        
        mock_group = MagicMock()
        mock_result = MagicMock()
        mock_result.structuredContent = None
        mock_content = MagicMock()
        mock_content.text = "Result text"
        mock_result.content = [mock_content]
        mock_group.call_tool = AsyncMock(return_value=mock_result)
        
        # Create a progress callback
        progress_calls = []
        async def progress_cb(progress, total=None, message=None):
            progress_calls.append((progress, total, message))
        
        # Create tool context with progress callback
        ctx = ToolContext(
            tool_name="test_tool",
            tool_call_id="call_123",
            progress_callback=progress_cb
        )
        
        impl = _create_tool_implementation(mock_group, "_0_test_tool", "test_tool")
        result = await impl(ctx=ctx, arg1="value")
        
        assert result == "Result text"
        # Verify progress callback was passed to SDK
        mock_group.call_tool.assert_called_once()
        call_args = mock_group.call_tool.call_args
        assert call_args.kwargs.get("progress_callback") == progress_cb
    
    @pytest.mark.asyncio
    async def test_tool_implementation_works_without_context(self):
        """Test tool implementation works when no context is provided."""
        mock_group = MagicMock()
        mock_result = MagicMock()
        mock_result.structuredContent = None
        mock_content = MagicMock()
        mock_content.text = "Result text"
        mock_result.content = [mock_content]
        mock_group.call_tool = AsyncMock(return_value=mock_result)
        
        impl = _create_tool_implementation(mock_group, "_0_test_tool", "test_tool")
        # No ctx passed
        result = await impl(arg1="value")
        
        assert result == "Result text"
        # Verify progress callback is None when no context
        mock_group.call_tool.assert_called_once()
        call_args = mock_group.call_tool.call_args
        assert call_args.kwargs.get("progress_callback") is None


@pytest.mark.asyncio
class TestLoadMCPConfig:
    """Test main config loading function."""
    
    async def test_load_mcp_config_empty_servers(self):
        """Test loading config with empty servers list."""
        config = {"servers": []}
        
        tools, disconnect = await _load_mcp_config(config)
        
        assert tools == []
        await disconnect()  # Should not raise
    
    async def test_load_mcp_config_connection_success(self):
        """Test loading config with successful connection."""
        config = {
            "servers": [{
                "name": "test",
                "transport": "sse",
                "url": "https://example.com/mcp"
            }]
        }
        
        mock_tool = MagicMock()
        mock_tool.name = "search"
        mock_tool.description = "Test tool"
        mock_tool.inputSchema = {}
        
        with patch('tyler.mcp.config_loader.ClientSessionGroup') as mock_group_class, \
             patch('tyler.mcp.config_loader.AsyncExitStack') as mock_stack_class:
            
            mock_group = MagicMock()
            mock_group.tools = {}
            mock_group.connect_to_server = AsyncMock()
            mock_group_class.return_value = mock_group
            
            mock_stack = MagicMock()
            mock_stack.__aenter__ = AsyncMock()
            mock_stack.aclose = AsyncMock()
            mock_stack_class.return_value = mock_stack
            
            async def connect_side_effect(params):
                mock_group.tools = {"_0_search": mock_tool}
            mock_group.connect_to_server.side_effect = connect_side_effect
            
            tools, disconnect = await _load_mcp_config(config)
            
            mock_group.connect_to_server.assert_called_once()
            assert len(tools) == 1
            assert tools[0]["definition"]["function"]["name"] == "test_search"
            assert tools[0]["attributes"]["mcp_sdk_name"] == "_0_search"
            
            await disconnect()
            mock_stack.aclose.assert_called_once()
    
    async def test_load_mcp_config_connection_failure_fail_silent_true(self):
        """Test graceful degradation when server fails to connect."""
        config = {
            "servers": [{
                "name": "broken",
                "transport": "sse",
                "url": "https://broken.com/mcp",
                "fail_silent": True,
                "max_retries": 1
            }]
        }
        
        with patch('tyler.mcp.config_loader.ClientSessionGroup') as mock_group_class:
            mock_group = MagicMock()
            mock_group.tools = {}
            mock_group.connect_to_server = AsyncMock(side_effect=Exception("Connection failed"))
            mock_group_class.return_value = mock_group
            
            with patch('tyler.mcp.config_loader.AsyncExitStack') as mock_stack_class:
                mock_stack = MagicMock()
                mock_stack.__aenter__ = AsyncMock()
                mock_stack.aclose = AsyncMock()
                mock_stack_class.return_value = mock_stack
                
                tools, disconnect = await _load_mcp_config(config)
                
                assert tools == []
                await disconnect()
    
    async def test_load_mcp_config_connection_failure_fail_silent_false(self):
        """Test error raised when server fails with fail_silent=False."""
        config = {
            "servers": [{
                "name": "broken",
                "transport": "sse",
                "url": "https://broken.com/mcp",
                "fail_silent": False,
                "max_retries": 1
            }]
        }
        
        with patch('tyler.mcp.config_loader.ClientSessionGroup') as mock_group_class:
            mock_group = MagicMock()
            mock_group.tools = {}
            mock_group.connect_to_server = AsyncMock(side_effect=Exception("Connection failed"))
            mock_group_class.return_value = mock_group
            
            with patch('tyler.mcp.config_loader.AsyncExitStack') as mock_stack_class:
                mock_stack = MagicMock()
                mock_stack.__aenter__ = AsyncMock()
                mock_stack.aclose = AsyncMock()
                mock_stack_class.return_value = mock_stack
                
            with pytest.raises(ValueError, match="Failed to connect"):
                await _load_mcp_config(config)
    
    async def test_load_mcp_config_custom_prefix(self):
        """Test custom prefix is used."""
        config = {
            "servers": [{
                "name": "mintlify",
                "transport": "sse",
                "url": "https://example.com/mcp",
                "prefix": "docs"
            }]
        }
        
        mock_tool = MagicMock()
        mock_tool.name = "search"  # Original tool name
        mock_tool.description = "Search"
        mock_tool.inputSchema = {}
        
        with patch('tyler.mcp.config_loader.ClientSessionGroup') as mock_group_class:
            mock_group = MagicMock()
            mock_group.tools = {}
            
            async def connect_side_effect(params):
                # SDK stores with namespaced key
                mock_group.tools = {"_0_search": mock_tool}
            mock_group.connect_to_server = AsyncMock(side_effect=connect_side_effect)
            mock_group_class.return_value = mock_group
            
            with patch('tyler.mcp.config_loader.AsyncExitStack') as mock_stack_class:
                mock_stack = MagicMock()
                mock_stack.__aenter__ = AsyncMock()
                mock_stack.aclose = AsyncMock()
                mock_stack_class.return_value = mock_stack
                
                tools, _ = await _load_mcp_config(config)
                
                # Tyler uses custom prefix "docs", not the SDK namespace
                assert tools[0]["definition"]["function"]["name"] == "docs_search"
    
    async def test_load_mcp_config_env_var_substitution(self):
        """Test environment variables are substituted."""
        os.environ["MCP_URL"] = "https://example.com/mcp"
        
        config = {
            "servers": [{
                "name": "test",
                "transport": "sse",
                "url": "${MCP_URL}"
            }]
        }
        
        with patch('tyler.mcp.config_loader.ClientSessionGroup') as mock_group_class, \
             patch('tyler.mcp.config_loader.AsyncExitStack') as mock_stack_class:
            
            mock_group = MagicMock()
            mock_group.tools = {}
            mock_group.connect_to_server = AsyncMock()
            mock_group_class.return_value = mock_group
            
            mock_stack = MagicMock()
            mock_stack.__aenter__ = AsyncMock()
            mock_stack.aclose = AsyncMock()
            mock_stack_class.return_value = mock_stack
            
            await _load_mcp_config(config)
            
            call_args = mock_group.connect_to_server.call_args[0][0]
            assert call_args.url == "https://example.com/mcp"
        
        del os.environ["MCP_URL"]
    
    async def test_load_mcp_config_tool_collision_avoidance(self):
        """Test that tools with same name from different servers are correctly distinguished.
        
        This tests the fix for a bug where without component_name_hook, two servers
        with the same tool name (e.g., both have "search") would overwrite each other
        in group.tools, causing tools to silently call the wrong server.
        """
        config = {
            "servers": [
                {
                    "name": "server1",
                    "transport": "sse",
                    "url": "https://server1.com/mcp"
                },
                {
                    "name": "server2",
                "transport": "sse",
                    "url": "https://server2.com/mcp"
                }
            ]
        }
        
        # Both servers have a tool named "search"
        mock_tool1 = MagicMock()
        mock_tool1.name = "search"
        mock_tool1.description = "Search server1"
        mock_tool1.inputSchema = {}
        
        mock_tool2 = MagicMock()
        mock_tool2.name = "search"
        mock_tool2.description = "Search server2"
        mock_tool2.inputSchema = {}
        
        connection_count = [0]
        
        with patch('tyler.mcp.config_loader.ClientSessionGroup') as mock_group_class:
            mock_group = MagicMock()
            mock_group.tools = {}
            
            async def connect_side_effect(params):
                # Simulate SDK behavior with component_name_hook
                # Each connection gets a unique prefix
                if connection_count[0] == 0:
                    mock_group.tools["_0_search"] = mock_tool1
                else:
                    mock_group.tools["_1_search"] = mock_tool2
                connection_count[0] += 1
            
            mock_group.connect_to_server = AsyncMock(side_effect=connect_side_effect)
            mock_group_class.return_value = mock_group
            
            with patch('tyler.mcp.config_loader.AsyncExitStack') as mock_stack_class:
                mock_stack = MagicMock()
                mock_stack.__aenter__ = AsyncMock()
                mock_stack.aclose = AsyncMock()
                mock_stack_class.return_value = mock_stack
                
                tools, _ = await _load_mcp_config(config)
                
                # Should have 2 tools with different prefixes
                assert len(tools) == 2
                
                tool_names = [t["definition"]["function"]["name"] for t in tools]
                assert "server1_search" in tool_names
                assert "server2_search" in tool_names
                
                # Each tool should have its own SDK name for correct routing
                sdk_names = [t["attributes"]["mcp_sdk_name"] for t in tools]
                assert "_0_search" in sdk_names
                assert "_1_search" in sdk_names
