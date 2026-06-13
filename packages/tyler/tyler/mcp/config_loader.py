"""MCP configuration loader for Tyler.

This module provides internal functions for loading MCP server configurations
and connecting to servers using the official MCP SDK's ClientSessionGroup.

NOT A PUBLIC API - use Agent(mcp={...}) with agent.connect_mcp() instead.
"""
import os
import re
import logging
import asyncio
import hashlib
import inspect
from contextlib import AsyncExitStack
from datetime import timedelta
from typing import Dict, List, Any, Callable, Awaitable, Tuple, Optional, TYPE_CHECKING
from urllib.parse import urlparse

from mcp.client.session_group import (
    ClientSessionGroup,
    StdioServerParameters,
    SseServerParameters,
    StreamableHttpParameters,
)

if TYPE_CHECKING:
    from tyler.utils.tool_runner import ToolContext

logger = logging.getLogger(__name__)

# Regex pattern for environment variable substitution: ${VAR_NAME}
ENV_VAR_PATTERN = r'\$\{([^}]+)\}'
OPENAI_FUNCTION_NAME_MAX_LENGTH = 64
OPENAI_FUNCTION_NAME_PATTERN = r'[^a-zA-Z0-9_]'
SUPPORTED_TRANSPORTS = ("stdio", "streamablehttp", "sse")
LIST_OPTION_FIELDS = ("args", "include_tools", "exclude_tools")
DICT_OPTION_FIELDS = ("env", "headers")
POSITIVE_NUMBER_FIELDS = (
    "timeout_seconds",
    "sse_read_timeout_seconds",
    "tool_timeout_seconds",
)
STRING_OPTION_FIELDS = ("cwd", "encoding")
ENCODING_ERROR_HANDLERS = ("strict", "ignore", "replace")

# Internal parameter name for ToolContext injection.
# Uses a unique name that won't collide with real MCP tool parameters.
# This allows MCP tools to have parameters named 'ctx', 'context', etc.
_AGENT_CONTEXT_PARAM = '_agent_ctx'


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
                        "transport": "stdio|sse|streamablehttp",
                        "url": "https://...",  # for sse/streamablehttp
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
    if not isinstance(config, dict):
        raise ValueError("MCP config must be a dict")

    if "servers" not in config:
        raise ValueError("MCP config must have 'servers' key")
    
    if not isinstance(config["servers"], list):
        raise ValueError("MCP 'servers' must be a list")
    
    # Validate each server
    for server in config["servers"]:
        _validate_server_config(server)


def _validate_list_field(server_name: str, server: Dict[str, Any], field: str) -> None:
    """Validate optional list-valued server fields."""
    if field in server and not isinstance(server[field], list):
        raise ValueError(f"Server '{server_name}' field '{field}' must be a list")


def _validate_dict_field(server_name: str, server: Dict[str, Any], field: str) -> None:
    """Validate optional dict-valued server fields."""
    if field in server and not isinstance(server[field], dict):
        raise ValueError(f"Server '{server_name}' field '{field}' must be a dict")


def _validate_positive_number_field(server_name: str, server: Dict[str, Any], field: str) -> None:
    """Validate optional positive numeric server fields."""
    if field not in server:
        return
    value = server[field]
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        raise ValueError(f"Server '{server_name}' field '{field}' must be a positive number")


def _validate_url_scheme(server_name: str, transport: str, url: str) -> None:
    """Validate HTTP transport URL schemes while allowing unresolved env placeholders."""
    if re.search(ENV_VAR_PATTERN, url):
        return

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(
            f"Server '{server_name}' with transport '{transport}' must use http or https URL scheme"
        )


def _validate_server_config(server: Dict[str, Any]) -> None:
    """
    Validate a single server configuration.
    
    Args:
        server: Server config dict
    
    Raises:
        ValueError: If server config is invalid
    """
    if not isinstance(server, dict):
        raise ValueError("Server config must be a dict")

    # Required fields
    if "name" not in server:
        raise ValueError("Server config missing required field 'name'")

    if not isinstance(server["name"], str) or not server["name"].strip():
        raise ValueError("Server config field 'name' must be a non-empty string")

    server_name = server["name"]
    
    if "transport" not in server:
        raise ValueError(f"Server '{server_name}' missing required field 'transport'")
    
    transport = server["transport"]
    if not isinstance(transport, str):
        raise ValueError(f"Server '{server_name}' field 'transport' must be a string")
    
    # Validate transport type
    if transport not in SUPPORTED_TRANSPORTS:
        raise ValueError(
            f"Invalid transport '{transport}'. Must be one of: stdio, sse, streamablehttp"
        )

    for field in LIST_OPTION_FIELDS:
        _validate_list_field(server_name, server, field)

    for field in DICT_OPTION_FIELDS:
        _validate_dict_field(server_name, server, field)

    if "max_retries" in server:
        max_retries = server["max_retries"]
        if isinstance(max_retries, bool) or not isinstance(max_retries, int) or max_retries <= 0:
            raise ValueError(f"Server '{server_name}' field 'max_retries' must be a positive integer")

    for field in POSITIVE_NUMBER_FIELDS:
        _validate_positive_number_field(server_name, server, field)

    if "fail_silent" in server and not isinstance(server["fail_silent"], bool):
        raise ValueError(f"Server '{server_name}' field 'fail_silent' must be a boolean")

    if "terminate_on_close" in server and not isinstance(server["terminate_on_close"], bool):
        raise ValueError(f"Server '{server_name}' field 'terminate_on_close' must be a boolean")

    for field in STRING_OPTION_FIELDS:
        if field in server and not isinstance(server[field], str):
            raise ValueError(f"Server '{server_name}' field '{field}' must be a string")

    if "encoding_error_handler" in server and server["encoding_error_handler"] not in ENCODING_ERROR_HANDLERS:
        raise ValueError(
            f"Server '{server_name}' field 'encoding_error_handler' must be one of: "
            f"{', '.join(ENCODING_ERROR_HANDLERS)}"
        )
    
    # Transport-specific required fields
    if transport in ["sse", "streamablehttp"]:
        if "url" not in server:
            raise ValueError(
                f"Server '{server_name}' with transport '{transport}' requires 'url' field"
            )
        if not isinstance(server["url"], str) or not server["url"].strip():
            raise ValueError(f"Server '{server_name}' field 'url' must be a non-empty string")
        _validate_url_scheme(server_name, transport, server["url"])
    elif transport == "stdio":
        if "command" not in server:
            raise ValueError(
                f"Server '{server_name}' with transport 'stdio' requires 'command' field"
            )
        if not isinstance(server["command"], str) or not server["command"].strip():
            raise ValueError(f"Server '{server_name}' field 'command' must be a non-empty string")


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


def _build_server_params(server: Dict[str, Any]):
    """
    Convert Tyler server config to SDK parameter types.
    
    Args:
        server: Server config dict with transport, url/command, etc.
    
    Returns:
        SDK ServerParameters (StdioServerParameters, SseServerParameters, or StreamableHttpParameters)
    """
    transport = server["transport"]
    
    if transport == "stdio":
        return StdioServerParameters(**_supported_kwargs(
            StdioServerParameters,
            {
                "command": server["command"],
                "args": server.get("args", []),
                "env": server.get("env"),
                "cwd": server.get("cwd"),
                "encoding": server.get("encoding", "utf-8"),
                "encoding_error_handler": server.get("encoding_error_handler", "strict"),
            },
        ))
    elif transport == "sse":
        return SseServerParameters(**_supported_kwargs(
            SseServerParameters,
            {
                "url": server["url"],
                "headers": server.get("headers"),
                "timeout": server.get("timeout_seconds", 5),
                "sse_read_timeout": server.get("sse_read_timeout_seconds", 300),
            },
        ))
    else:  # streamablehttp
        timeout = timedelta(seconds=server.get("timeout_seconds", 30))
        sse_read_timeout = timedelta(seconds=server.get("sse_read_timeout_seconds", 300))
        return StreamableHttpParameters(**_supported_kwargs(
            StreamableHttpParameters,
            {
                "url": server["url"],
                "headers": server.get("headers"),
                "timeout": timeout,
                "sse_read_timeout": sse_read_timeout,
                "terminate_on_close": server.get("terminate_on_close", True),
            },
        ))


def _supported_kwargs(callable_obj: Callable[..., Any], kwargs: Dict[str, Any]) -> Dict[str, Any]:
    """Return only keyword arguments supported by an SDK constructor/function."""
    supported = set(inspect.signature(callable_obj).parameters)
    return {key: value for key, value in kwargs.items() if key in supported}


def _sanitize_tool_name(name: str) -> str:
    """Sanitize a Tyler-exposed MCP tool name for OpenAI function-name constraints."""
    sanitized = re.sub(OPENAI_FUNCTION_NAME_PATTERN, "_", str(name))
    sanitized = re.sub(r"_+", "_", sanitized).strip("_")
    if not sanitized:
        sanitized = "mcp_tool"

    if len(sanitized) > OPENAI_FUNCTION_NAME_MAX_LENGTH:
        digest = hashlib.sha1(sanitized.encode("utf-8")).hexdigest()[:8]
        prefix_len = OPENAI_FUNCTION_NAME_MAX_LENGTH - len(digest) - 1
        sanitized = f"{sanitized[:prefix_len]}_{digest}"

    return sanitized


def _json_safe(value: Any) -> Any:
    """Convert SDK/Pydantic/dataclass-like values to JSON-serializable structures."""
    try:
        from unittest.mock import Mock
        if isinstance(value, Mock):
            return None
    except Exception:
        pass

    if value is None or isinstance(value, (str, int, float, bool)):
        return value

    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}

    if isinstance(value, (list, tuple, set)):
        return [_json_safe(v) for v in value]

    if hasattr(value, "model_dump") and callable(value.model_dump):
        try:
            return value.model_dump(mode="json", by_alias=True, exclude_none=True)
        except TypeError:
            return value.model_dump()

    if hasattr(value, "dict") and callable(value.dict):
        try:
            return value.dict(by_alias=True, exclude_none=True)
        except TypeError:
            return value.dict()

    if hasattr(value, "__dict__"):
        return {
            key: _json_safe(val)
            for key, val in vars(value).items()
            if not key.startswith("_") and not callable(val)
        }

    return str(value)


def _get_optional_tool_attr(tool: Any, *names: str) -> Any:
    """Read optional SDK tool metadata without treating MagicMock fallbacks as real values."""
    for name in names:
        if isinstance(tool, dict) and name in tool:
            return tool[name]
        try:
            value = getattr(tool, name)
        except AttributeError:
            continue
        safe_value = _json_safe(value)
        if safe_value is not None:
            return value
    return None


def _serialize_mcp_tool_result(result: Any) -> Any:
    """Serialize an MCP CallToolResult into Tyler-safe tool output."""
    if getattr(result, "isError", False) is True:
        error_content = _serialize_mcp_content(getattr(result, "content", []))
        raise ValueError(error_content)

    structured_content = getattr(result, "structuredContent", None)
    if structured_content is not None:
        return _json_safe(structured_content)

    content = getattr(result, "content", None)
    if content:
        return _serialize_mcp_content(content)

    return ""


def _serialize_mcp_content(content: Any) -> Any:
    """Serialize MCP content items, returning plain text directly when simple."""
    serialized = []
    for item in content:
        text = getattr(item, "text", None)
        if isinstance(text, str):
            serialized.append(text)
        else:
            serialized.append(_json_safe(item))

    if len(serialized) == 1:
        return serialized[0]
    return serialized


def _create_tool_implementation(
    group: ClientSessionGroup,
    sdk_tool_name: str,
    display_name: str,
    tool_timeout_seconds: Optional[float] = None,
):
    """
    Create a closure that calls the SDK's call_tool with the SDK-namespaced tool name.
    
    Args:
        group: The ClientSessionGroup managing the MCP connections
        sdk_tool_name: The SDK-namespaced tool name (e.g., "_0_search") used for routing
        display_name: Human-readable name for logging (e.g., "search")
    
    Returns:
        Async function that executes the MCP tool.
        The function accepts an optional '_agent_ctx' parameter (ToolContext) to receive
        progress callbacks for long-running operations. Uses a unique name to avoid
        collisions with MCP tools that have parameters named 'ctx' or 'context'.
    """
    async def call_mcp_tool(_agent_ctx: Optional["ToolContext"] = None, **kwargs):
        """Call the MCP tool with the provided arguments.
        
        Args:
            _agent_ctx: Optional ToolContext with progress_callback for progress updates
            **kwargs: Arguments to pass to the MCP tool (passed through unmodified)
        """
        try:
            # Pass all kwargs through to the MCP tool - no filtering needed since
            # our context parameter uses a unique name (_agent_ctx) that won't collide
            logger.debug(f"Calling MCP tool '{display_name}' (sdk: {sdk_tool_name}) with args: {kwargs}")
            
            # Extract progress callback from context if available
            progress_callback = None
            if _agent_ctx is not None and hasattr(_agent_ctx, 'progress_callback') and _agent_ctx.progress_callback is not None:
                progress_callback = _agent_ctx.progress_callback
                logger.debug(f"MCP tool '{display_name}' will use progress callback")
            
            call_kwargs = {"progress_callback": progress_callback}
            if tool_timeout_seconds is not None:
                call_kwargs["read_timeout_seconds"] = timedelta(seconds=tool_timeout_seconds)

            result = await group.call_tool(sdk_tool_name, kwargs, **call_kwargs)
            logger.debug(f"MCP tool '{display_name}' returned: {type(result)}")
            
            return _serialize_mcp_tool_result(result)
            
        except Exception as e:
            error_msg = f"Error calling MCP tool '{display_name}': {e}"
            logger.error(error_msg)
            logger.debug("MCP tool error details:", exc_info=True)
            raise ValueError(error_msg) from e
    
    # Set function metadata for better debugging
    call_mcp_tool.__name__ = _sanitize_tool_name(f"mcp_{display_name}")
    call_mcp_tool.__doc__ = f"MCP tool: {display_name}"
    # Mark as MCP tool so ToolRunner skips weave.op wrapping
    # (MCP SDK already provides its own Weave tracing)
    call_mcp_tool._is_mcp_tool = True
    
    return call_mcp_tool


def _convert_tools_for_agent(
    group: ClientSessionGroup,
    new_sdk_tool_names: set,
    prefix: str,
    include_tools: Optional[List[str]],
    exclude_tools: List[str],
    server_name: Optional[str] = None,
    tool_timeout_seconds: Optional[float] = None,
    transport: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Convert SDK tools to Tyler format with prefix and filtering.
    
    Args:
        group: The ClientSessionGroup with discovered tools
        new_sdk_tool_names: Set of SDK-namespaced tool names just added (e.g., {"_0_search"})
        prefix: Namespace prefix for Tyler tool names
        include_tools: Optional whitelist of original tool names to include
        exclude_tools: List of original tool names to exclude
    
    Returns:
        List of Tyler tool definitions ready for Agent
    """
    tyler_tools = []
    
    for sdk_tool_name, tool in group.tools.items():
        # Only process tools from this server (by SDK-namespaced name)
        if sdk_tool_name not in new_sdk_tool_names:
            continue
        
        # tool.name is the original tool name (e.g., "search")
        original_name = tool.name
        
        # Apply include filter (whitelist) - uses original name
        if include_tools is not None and original_name not in include_tools:
            continue
        
        # Apply exclude filter (blacklist) - uses original name
        if original_name in exclude_tools:
            continue
        
        # Create a provider-compatible name for Tyler (e.g., "myserver_search").
        prefixed_name = _sanitize_tool_name(f"{prefix}_{original_name}")

        attributes = {
            "source": "mcp",
            "mcp_server_name": server_name or prefix,
            "mcp_original_name": original_name,
            "mcp_sdk_name": sdk_tool_name,
            "mcp_exposed_name": prefixed_name,
        }
        if transport:
            attributes["mcp_transport"] = transport

        optional_metadata = {
            "mcp_output_schema": _get_optional_tool_attr(tool, "outputSchema"),
            "mcp_annotations": _get_optional_tool_attr(tool, "annotations"),
            "mcp_icons": _get_optional_tool_attr(tool, "icons"),
            "mcp_execution": _get_optional_tool_attr(tool, "execution"),
            "mcp_meta": _get_optional_tool_attr(tool, "meta", "_meta"),
        }
        for attr_name, attr_value in optional_metadata.items():
            safe_value = _json_safe(attr_value)
            if safe_value is not None:
                attributes[attr_name] = safe_value

        if "mcp_execution" in attributes:
            attributes["mcp_execution_metadata"] = attributes["mcp_execution"]

        if tool_timeout_seconds is not None:
            attributes["mcp_tool_timeout_seconds"] = tool_timeout_seconds

        tyler_tool = {
            "definition": {
                "type": "function",
                "function": {
                    "name": prefixed_name,
                    "description": tool.description,
                    "parameters": tool.inputSchema,
                }
            },
            # Closure uses SDK-namespaced name for correct routing
            "implementation": _create_tool_implementation(
                group,
                sdk_tool_name,
                original_name,
                tool_timeout_seconds=tool_timeout_seconds,
            ),
            "attributes": attributes,
        }
        if tool_timeout_seconds is not None:
            tyler_tool["timeout"] = tool_timeout_seconds

        tyler_tools.append(tyler_tool)
    
    return tyler_tools


async def _load_mcp_config(
    config: Dict[str, Any]
) -> Tuple[List[Dict[str, Any]], Callable[[], Awaitable[None]]]:
    """
    Load MCP configuration using SDK's ClientSessionGroup directly.
    
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
    # Substitute environment variables and validate resolved values.
    config = _substitute_env_vars(config)
    _validate_mcp_config(config)
    
    # Connection counter for SDK-level namespacing to avoid tool collisions
    # When two servers have tools with the same name (e.g., both have "search"),
    # without namespacing, the second server's tools would overwrite the first's
    # in group.tools dict, causing incorrect tool routing.
    connection_counter = [0]  # Use list to allow mutation in closure
    
    def component_name_hook(name: str, server_info) -> str:
        """Prefix tool names with connection index to avoid SDK-level collisions."""
        return f"_{connection_counter[0]}_{name}"
    
    # Create SDK ClientSessionGroup with component_name_hook for collision avoidance
    exit_stack = AsyncExitStack()
    group = ClientSessionGroup(exit_stack=exit_stack, component_name_hook=component_name_hook)
    
    # Track whether we successfully return (to avoid double-cleanup)
    returned_successfully = False
    
    try:
        await exit_stack.__aenter__()
        
        all_tools = []
        seen_prefixed_names = {}  # prefixed_name -> server_name for collision detection
        
        # Connect to each server
        for server in config["servers"]:
            name = server["name"]
            transport = server["transport"]
            fail_silent = server.get("fail_silent", True)
            max_retries = server.get("max_retries", 3)
            prefix = server.get("prefix", name)  # Use custom prefix or server name
            include_tools = server.get("include_tools")
            exclude_tools = server.get("exclude_tools", [])
            tool_timeout_seconds = server.get("tool_timeout_seconds")
            
            # Build SDK server parameters
            params = _build_server_params(server)
            
            # Track tools before connection to know what was added by this server
            # (SDK namespaces tools with connection_counter via component_name_hook)
            tools_before = set(group.tools.keys())
            
            # Retry loop with exponential backoff
            connected = False
            last_error = None
            
            for attempt in range(max_retries):
                try:
                    if attempt > 0:
                        delay = min(2 ** attempt, 10)  # Exponential backoff: 2s, 4s, 8s, 10s max
                        logger.debug(f"Retrying connection to '{name}' (attempt {attempt + 1}/{max_retries}) after {delay}s...")
                        await asyncio.sleep(delay)
                    
                    logger.info(f"Connecting to MCP server '{name}' via {transport}...")
                    await group.connect_to_server(params)
                    connected = True
                    logger.info(f"Connected to MCP server '{name}'")
                    # Increment counter AFTER successful connection so next server gets different prefix
                    connection_counter[0] += 1
                    break
                    
                except Exception as e:
                    last_error = e
                    logger.warning(f"Connection attempt {attempt + 1} to '{name}' failed: {e}")
                    if attempt == max_retries - 1:
                        # Last attempt failed
                        if fail_silent:
                            logger.warning(f"Failed to connect to MCP server '{name}' after {max_retries} attempts: {last_error}")
                        else:
                            raise ValueError(f"Failed to connect to MCP server '{name}': {last_error}") from last_error
            
            if connected:
                # Get newly added tools (SDK-namespaced, e.g., "_0_search", "_1_search")
                new_sdk_tool_names = set(group.tools.keys()) - tools_before
                
                # Convert tools with this server's prefix and filters
                server_tools = _convert_tools_for_agent(
                    group,
                    new_sdk_tool_names,
                    prefix,
                    include_tools,
                    exclude_tools,
                    server_name=name,
                    tool_timeout_seconds=tool_timeout_seconds,
                    transport=transport,
                )
                
                # Check for prefixed name collisions with tools from previous servers
                # Note: Duplicate names in all_tools list will cause the later registration
                # to override the earlier one when tools are registered with ToolRunner
                for tool in server_tools:
                    prefixed_name = tool["definition"]["function"]["name"]
                    if prefixed_name in seen_prefixed_names:
                        logger.warning(
                            f"Tool name collision: '{prefixed_name}' from server '{name}' "
                            f"conflicts with same-named tool from server '{seen_prefixed_names[prefixed_name]}'. "
                            f"Only the later tool will be available. Consider using unique prefixes."
                        )
                    seen_prefixed_names[prefixed_name] = name
                
                all_tools.extend(server_tools)
                
                logger.info(f"Registered {len(server_tools)} tools from MCP server '{name}'")
        
        # Create disconnect callback that closes the exit stack
        async def disconnect_callback():
            """Disconnect from all MCP servers."""
            try:
                await exit_stack.aclose()
            except Exception as e:
                logger.warning(f"Error during MCP disconnect: {e}")
        
        returned_successfully = True
        return all_tools, disconnect_callback
    
    finally:
        # If we didn't return successfully, clean up the exit stack
        # (on success, the caller is responsible for calling disconnect_callback)
        if not returned_successfully:
            try:
                await exit_stack.aclose()
            except Exception as e:
                logger.warning(f"Error cleaning up exit stack after failure: {e}")
