"""MCP client implementation for Tyler.

This module provides a clean interface for connecting to MCP servers
and discovering their tools. It does NOT manage server lifecycle.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any
from contextlib import AsyncExitStack
from datetime import timedelta

from mcp import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.client.sse import sse_client
from mcp.client.streamable_http import streamablehttp_client

# Import anyio for handling CancelledError
try:
    from anyio import CancelledError as AnyIOCancelledError
except ImportError:
    # Fallback if anyio is not available
    AnyIOCancelledError = None

# Import httpx for HTTP error handling
try:
    import httpx
except ImportError:
    httpx = None

try:
    from mcp.client.websocket import websocket_client
    WEBSOCKET_AVAILABLE = True
except ImportError:
    WEBSOCKET_AVAILABLE = False

logger = logging.getLogger(__name__)


class MCPClient:
    """Client for connecting to MCP servers.
    
    This client connects to already-running MCP servers and discovers
    their available tools. It does not manage server lifecycle.
    """
    
    def __init__(self):
        self.sessions: Dict[str, ClientSession] = {}
        self.exit_stacks: Dict[str, AsyncExitStack] = {}
        self._discovered_tools: Dict[str, List[Any]] = {}
        
    async def connect(self, name: str, transport: str, **kwargs) -> bool:
        """Connect to an MCP server.
        
        Args:
            name: Unique name for this connection
            transport: Transport type ('stdio', 'sse', 'websocket', 'streamablehttp')
            **kwargs: Transport-specific arguments:
                - stdio: command (str), args (List[str]), env (Dict[str, str])
                - sse: url (str), headers (Dict[str, str]) optional
                - websocket: url (str), headers (Dict[str, str]) optional
                - streamablehttp: url (str), headers (Dict[str, str]) optional
                - timeout: Connection timeout in seconds (default: 30)
                - max_retries: Maximum connection retry attempts (default: 3)
                
        Returns:
            bool: True if connection successful
        """
        # Extract config from kwargs
        timeout = kwargs.pop("timeout", 30)
        max_retries = kwargs.pop("max_retries", 3)
        
        # Retry loop for flaky connections  
        last_error = None
        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    delay = min(2 ** attempt, 10)  # Exponential backoff, max 10s
                    logger.debug(f"Retrying connection to '{name}' (attempt {attempt + 1}/{max_retries}) after {delay}s...")
                    await asyncio.sleep(delay)
                
                success = await self._connect_once(name, transport, timeout, **kwargs)
                if success:
                    return True
                # Connection returned False without exception - treat as failure
                last_error = RuntimeError("Connection returned False")
            except (asyncio.TimeoutError, asyncio.CancelledError) as e:
                last_error = e
                if attempt < max_retries - 1:
                    logger.warning(f"Connection attempt {attempt + 1} failed: {type(e).__name__}: {e}")
                    continue
                # Last attempt failed, fall through to error handling below
                break
            except Exception as e:
                last_error = e
                
                # Check if this is an HTTP error (server returned error status)
                if httpx and isinstance(e, httpx.HTTPStatusError):
                    # HTTP 5xx errors are server issues - don't retry immediately
                    logger.error(f"HTTP error {e.response.status_code} from server: {e}")
                    break
                
                if AnyIOCancelledError and isinstance(e, AnyIOCancelledError):
                    # Anyio cancellation - likely flaky server, retry
                    if attempt < max_retries - 1:
                        logger.warning(f"Connection attempt {attempt + 1} cancelled by server, will retry")
                        continue
                # For other exceptions, fail immediately (no retry)
                break
        
        # All retries exhausted or non-retryable error occurred
        return await self._handle_connection_error(name, last_error)
    
    async def _connect_once(self, name: str, transport: str, timeout: float, **kwargs) -> bool:
        """Single connection attempt (internal helper).
        
        Returns:
            bool: True if connection successful
            
        Raises:
            Various exceptions if connection fails
        """
        # Create a new exit stack for this attempt (don't reuse)
        exit_stack = AsyncExitStack()
        
        try:
            
            # Connect based on transport type
            if transport == "stdio":
                # For stdio, we connect to an existing process via command
                command = kwargs.get("command")
                args = kwargs.get("args", [])
                env = kwargs.get("env", {})
                
                if not command:
                    raise ValueError("'command' is required for stdio transport")
                
                server_params = StdioServerParameters(
                    command=command,
                    args=args,
                    env=env
                )
                
                transport_context = await exit_stack.enter_async_context(
                    stdio_client(server_params)
                )
                read_stream, write_stream = transport_context
                
            elif transport == "sse":
                url = kwargs.get("url")
                if not url:
                    raise ValueError("'url' is required for sse transport")
                    
                read_stream, write_stream = await exit_stack.enter_async_context(
                    sse_client(url)
                )
                
            elif transport == "streamablehttp":
                url = kwargs.get("url")
                if not url:
                    raise ValueError("'url' is required for streamablehttp transport")
                
                headers = kwargs.get("headers")
                
                # streamablehttp_client returns a 3-tuple: (read, write, get_session_id)
                # Pass timeout parameters to prevent premature cancellation
                # timeout: for HTTP operations (handshake, POST)
                # sse_read_timeout: for SSE streaming reads
                logger.debug(f"Creating streamablehttp transport to {url} with {timeout}s timeout")
                try:
                    transport_context = await exit_stack.enter_async_context(
                        streamablehttp_client(
                            url, 
                            headers=headers,
                            timeout=timeout,  # HTTP operation timeout
                            sse_read_timeout=max(timeout * 2, 60)  # SSE read timeout (at least 60s)
                        )
                    )
                    read_stream, write_stream, get_session_id = transport_context
                    logger.debug(f"Streamablehttp transport created successfully")
                except Exception as transport_err:
                    logger.debug(f"Streamablehttp transport error: {type(transport_err).__name__}: {transport_err}")
                    # Re-raise to be caught by outer exception handler
                    raise
                
            elif transport == "websocket" and WEBSOCKET_AVAILABLE:
                url = kwargs.get("url")
                if not url:
                    raise ValueError("'url' is required for websocket transport")
                    
                read_stream, write_stream = await exit_stack.enter_async_context(
                    websocket_client(url)
                )
                
            else:
                if transport == "websocket" and not WEBSOCKET_AVAILABLE:
                    raise ValueError("WebSocket transport not available. Install websockets package.")
                else:
                    raise ValueError(f"Unsupported transport: {transport}")
            
            # Create and initialize session
            # Note: Don't use read_timeout_seconds as it can interfere with slow servers
            # The fail_silent mechanism in config_loader handles unavailable servers
            logger.debug(f"Creating ClientSession")
            session = await exit_stack.enter_async_context(
                ClientSession(read_stream, write_stream)
            )
            
            # Initialize session
            logger.debug("Initializing MCP session...")
            await session.initialize()
            logger.debug("MCP session initialized successfully")
            
            self.sessions[name] = session
            
            # Discover tools (timeout is handled by session's read_timeout_seconds)
            await self._discover_tools(name)
            
            # Success! Store the exit stack for later cleanup
            self.exit_stacks[name] = exit_stack
            
            logger.info(f"Connected to MCP server '{name}' via {transport}")
            return True
            
        except Exception as e:
            # Clean up THIS attempt's resources
            try:
                await exit_stack.aclose()
            except RuntimeError as cleanup_err:
                # Ignore "Attempted to exit cancel scope in a different task" errors
                # This happens when the streamablehttp task group cancels
                if "cancel scope" not in str(cleanup_err):
                    logger.debug(f"Error during cleanup: {cleanup_err}")
            except Exception as cleanup_err:
                logger.debug(f"Error during cleanup: {cleanup_err}")
            
            # Remove any partial state
            if name in self.sessions:
                del self.sessions[name]
            if name in self.exit_stacks:
                del self.exit_stacks[name]
            
            # Re-raise to be handled by retry logic
            raise
    
    async def _handle_connection_error(self, name: str, error: Exception) -> bool:
        """Handle connection error and return False.
        
        Args:
            name: Server name
            error: The exception that occurred
            
        Returns:
            bool: Always False
        """
        import traceback
        
        if isinstance(error, (asyncio.TimeoutError, asyncio.CancelledError)):
            error_type = "timed out" if isinstance(error, asyncio.TimeoutError) else "was cancelled"
            logger.error(f"Connection to MCP server '{name}' {error_type}: {error}")
        elif AnyIOCancelledError and isinstance(error, AnyIOCancelledError):
            logger.error(
                f"Connection to MCP server '{name}' was cancelled (likely due to timeout or server unavailability)"
            )
        else:
            logger.error(f"Failed to connect to MCP server '{name}': {type(error).__name__}: {error}")
            logger.debug(f"Traceback: {traceback.format_exc()}")
        
        return False
    
    async def _discover_tools(self, name: str) -> None:
        """Discover tools from a connected server."""
        try:
            session = self.sessions[name]
            logger.debug(f"Calling list_tools() for server '{name}'")
            response = await session.list_tools()
            self._discovered_tools[name] = response.tools
            logger.info(f"Discovered {len(response.tools)} tools from server '{name}'")
            if response.tools:
                for tool in response.tools:
                    logger.debug(f"  Tool: {tool.name} - {tool.description[:60] if tool.description else 'No description'}...")
        except Exception as e:
            logger.error(f"Failed to discover tools from server '{name}': {e}")
            logger.debug(f"Tool discovery error details:", exc_info=True)
            self._discovered_tools[name] = []
    
    def get_tools(self, server_name: Optional[str] = None) -> List[Any]:
        """Get discovered tools from one or all servers.
        
        Args:
            server_name: Optional server name. If None, returns tools from all servers.
            
        Returns:
            List of MCP tool objects
        """
        if server_name:
            return self._discovered_tools.get(server_name, [])
        
        # Return all tools from all servers
        all_tools = []
        for tools in self._discovered_tools.values():
            all_tools.extend(tools)
        return all_tools
    
    async def call_tool(self, server_name: str, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Call a tool on a specific server.
        
        Args:
            server_name: Name of the server that has the tool
            tool_name: Name of the tool to call
            arguments: Tool arguments
            
        Returns:
            Tool execution result
        """
        logger.debug(f"call_tool: server={server_name}, tool={tool_name}, args={arguments}")
        session = self.sessions.get(server_name)
        if not session:
            available_servers = list(self.sessions.keys())
            raise ValueError(f"Not connected to server '{server_name}'. Available servers: {available_servers}")
        
        logger.debug(f"Found session for server '{server_name}', calling tool...")
        result = await session.call_tool(tool_name, arguments)
        logger.debug(f"Tool call completed successfully")
        return result
    
    async def disconnect(self, name: str) -> None:
        """Disconnect from a specific server."""
        if name in self.exit_stacks:
            try:
                await self.exit_stacks[name].aclose()
            except RuntimeError as e:
                # Ignore "generator didn't stop after athrow()" errors
                # This can happen if the connection never fully established
                if "generator didn't stop" not in str(e):
                    logger.debug(f"Error closing exit stack for '{name}': {e}")
            except Exception as e:
                logger.debug(f"Error closing exit stack for '{name}': {e}")
            finally:
                del self.exit_stacks[name]
            
        if name in self.sessions:
            del self.sessions[name]
            
        if name in self._discovered_tools:
            del self._discovered_tools[name]
            
        logger.info(f"Disconnected from MCP server '{name}'")
    
    async def disconnect_all(self) -> None:
        """Disconnect from all servers."""
        # Get all server names from both sessions and exit_stacks
        # (failed connections may have exit_stacks but no sessions)
        names = set(list(self.sessions.keys()) + list(self.exit_stacks.keys()))
        for name in names:
            await self.disconnect(name)
    
    def is_connected(self, name: str) -> bool:
        """Check if connected to a specific server."""
        return name in self.sessions
    
    def list_connections(self) -> List[str]:
        """List all active connections."""
        return list(self.sessions.keys()) 