"""MCP configuration loader for Tyler.

This module provides internal functions for loading MCP server configurations
and connecting to servers. It's used by Agent.connect_mcp() and the CLI.

NOT A PUBLIC API - use Agent(mcp={...}) with agent.connect_mcp() instead.
"""
import os
import re
import logging
import copy
from typing import Dict, List, Any, Callable, Awaitable, Tuple, Optional
import asyncio

from .adapter import MCPAdapter

logger = logging.getLogger(__name__)

# Regex pattern for environment variable substitution: ${VAR_NAME}
ENV_VAR_PATTERN = r'\$\{([^}]+)\}'


def _validate_mcp_config(config: Dict[str, Any]) -> None:
    """
    Validate MCP config schema (sync validation).
    
    Called from Agent.__init__ to fail fast on invalid config.
    
    Args:
        config: MCP configuration dict with this structure:
            {
                "servers": [
                    {
                        "name": "server_name",
                        "transport": "sse|websocket|stdio",
                        "url": "https://...",  # for sse/websocket
                        "command": "...",      # for stdio
                        ...
                    }
                ]
            }
    
    Raises:
        ValueError: If config schema is invalid
    
    Example:
        config = {"servers": [{"name": "test", "transport": "sse", "url": "https://..."}]}
        _validate_mcp_config(config)  # Validates, raises if invalid
    """
    if "servers" not in config:
        raise ValueError("MCP config must have 'servers' key")
    
    if not isinstance(config["servers"], list):
        raise ValueError("MCP 'servers' must be a list")
    
    # Validate each server
    for server in config["servers"]:
        _validate_server_config(server)


def _validate_server_config(server: Dict[str, Any]) -> None:
    """
    Validate a single server configuration.
    
    Args:
        server: Server config dict
    
    Raises:
        ValueError: If server config is invalid
    """
    # Required fields
    if "name" not in server:
        raise ValueError("Server config missing required field 'name'")
    
    if "transport" not in server:
        raise ValueError(f"Server '{server['name']}' missing required field 'transport'")
    
    transport = server["transport"]
    
    # Validate transport type
    if transport not in ["stdio", "sse", "websocket", "streamablehttp"]:
        raise ValueError(
            f"Invalid transport '{transport}'. Must be one of: stdio, sse, websocket, streamablehttp"
        )
    
    # Transport-specific required fields
    if transport in ["sse", "websocket", "streamablehttp"]:
        if "url" not in server:
            raise ValueError(
                f"Server '{server['name']}' with transport '{transport}' requires 'url' field"
            )
    elif transport == "stdio":
        if "command" not in server:
            raise ValueError(
                f"Server '{server['name']}' with transport 'stdio' requires 'command' field"
            )


def _substitute_env_vars(obj: Any) -> Any:
    """
    Recursively substitute environment variables in config values.
    
    Supports ${VAR_NAME} syntax. Multiple variables in one string are supported.
    Missing variables are left as-is.
    
    Args:
        obj: Config object (dict, list, str, or other)
    
    Returns:
        Object with environment variables substituted
    """
    if isinstance(obj, dict):
        return {k: _substitute_env_vars(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_substitute_env_vars(item) for item in obj]
    elif isinstance(obj, str):
        # Substitute environment variables using ${VAR_NAME} pattern
        def replacer(match):
            var_name = match.group(1)
            return os.getenv(var_name, match.group(0))  # Return original if not found
        
        return re.sub(ENV_VAR_PATTERN, replacer, obj)
    
    return obj


def _apply_tool_filters(tools: List[Dict], server: Dict) -> List[Dict]:
    """
    Filter tools based on include/exclude lists.
    
    Filters match against the original MCP tool names (before namespacing).
    
    Args:
        tools: List of tool dicts (using original MCP names, not yet namespaced)
        server: Server config with optional include_tools/exclude_tools
    
    Returns:
        Filtered list of tools
    """
    include = server.get("include_tools")
    exclude = server.get("exclude_tools", [])
    
    filtered = tools
    
    # Apply include filter (whitelist)
    if include is not None:
        filtered = [
            t for t in filtered
            if t["definition"]["function"]["name"] in include
        ]
    
    # Apply exclude filter (blacklist)
    if exclude:
        filtered = [
            t for t in filtered
            if t["definition"]["function"]["name"] not in exclude
        ]
    
    return filtered


def _namespace_tools(tools: List[Dict], prefix: str) -> List[Dict]:
    """
    Add namespace prefix to tool names.
    
    Creates copies of tools with namespaced names to avoid collisions.
    
    Args:
        tools: List of tool dicts
        prefix: Namespace prefix (server name or custom prefix)
    
    Returns:
        List of tools with namespaced names (originals unchanged)
    """
    # Sanitize prefix (alphanumeric + underscore only)
    clean_prefix = re.sub(r'[^a-zA-Z0-9_]', '_', prefix)
    
    namespaced = []
    for tool in tools:
        # Deep copy to avoid mutating original
        tool_copy = copy.deepcopy(tool)
        
        # Get original name
        original_name = tool_copy["definition"]["function"]["name"]
        
        # Create namespaced name (single underscore)
        new_name = f"{clean_prefix}_{original_name}"
        
        # Update name in definition
        tool_copy["definition"]["function"]["name"] = new_name
        
        namespaced.append(tool_copy)
    
    return namespaced


async def _load_mcp_config(
    config: Dict[str, Any]
) -> Tuple[List[Dict[str, Any]], Callable[[], Awaitable[None]]]:
    """
    Internal helper to load MCP configuration.
    
    NOT A PUBLIC API - used by Agent.connect_mcp() and CLI.
    
    Args:
        config: Dict with "servers" key containing server configs.
                Schema validation should already be done.
    
    Returns:
        Tuple of (tool_definitions, disconnect_callback):
        - tool_definitions: List of Tyler tool dicts ready for Agent
        - disconnect_callback: Async function to call for cleanup
    
    Raises:
        ValueError: If server connection fails and fail_silent=False
    """
    # Create shared MCPAdapter instance
    adapter = MCPAdapter()
    
    # Substitute environment variables
    config = _substitute_env_vars(config)
    
    all_tools = []
    
    # Connect to each server
    for server in config["servers"]:
        name = server["name"]
        transport = server["transport"]
        fail_silent = server.get("fail_silent", True)
        
        # Build connection kwargs
        kwargs = {}
        if transport in ["sse", "websocket", "streamablehttp"]:
            kwargs["url"] = server["url"]
            if "headers" in server:
                kwargs["headers"] = server["headers"]
        elif transport == "stdio":
            kwargs["command"] = server["command"]
            kwargs["args"] = server.get("args", [])
            kwargs["env"] = server.get("env", {})
        
        # Attempt connection
        try:
            logger.info(f"Connecting to MCP server '{name}' via {transport}...")
            connected = await adapter.connect(name, transport, **kwargs)
            
            if not connected:
                msg = f"Failed to connect to MCP server '{name}'"
                if fail_silent:
                    logger.warning(msg)
                    continue
                else:
                    raise ValueError(msg)
            
            logger.info(f"Connected to MCP server '{name}'")
            
            # Get tools from this server
            server_tools = adapter.get_tools_for_agent([name])
            
            # Apply filters
            filtered_tools = _apply_tool_filters(server_tools, server)
            
            # Namespace tools
            prefix = server.get("prefix", name)  # Use custom prefix or server name
            namespaced_tools = _namespace_tools(filtered_tools, prefix)
            
            all_tools.extend(namespaced_tools)
            
            logger.info(
                f"Registered {len(namespaced_tools)} tools from MCP server '{name}'"
            )
            
        except Exception as e:
            msg = f"Error connecting to MCP server '{name}': {e}"
            if fail_silent:
                logger.warning(msg)
                continue
            else:
                raise ValueError(msg) from e
    
    # Create disconnect callback
    async def disconnect_callback():
        """Disconnect from all MCP servers."""
        await adapter.disconnect_all()
    
    return all_tools, disconnect_callback

