"""MCP client implementation for Tyler.

This module provides a clean interface for connecting to MCP servers
and discovering their tools. It does NOT manage server lifecycle.
"""

import logging
from typing import Dict, List, Optional, Any
from contextlib import AsyncExitStack

from mcp import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.client.sse import sse_client

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
            transport: Transport type ('stdio', 'sse', 'websocket')
            **kwargs: Transport-specific arguments:
                - stdio: command (str), args (List[str]), env (Dict[str, str])
                - sse: url (str)
                - websocket: url (str)
                
        Returns:
            bool: True if connection successful
        """
        try:
            # Create exit stack for resource management
            exit_stack = AsyncExitStack()
            self.exit_stacks[name] = exit_stack
            
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
            session = await exit_stack.enter_async_context(
                ClientSession(read_stream, write_stream)
            )
            await session.initialize()
            
            self.sessions[name] = session
            
            # Discover tools
            await self._discover_tools(name)
            
            logger.info(f"Connected to MCP server '{name}' via {transport}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to MCP server '{name}': {e}")
            # Clean up on failure
            if name in self.exit_stacks:
                await self.exit_stacks[name].aclose()
                del self.exit_stacks[name]
            return False
    
    async def _discover_tools(self, name: str) -> None:
        """Discover tools from a connected server."""
        try:
            session = self.sessions[name]
            response = await session.list_tools()
            self._discovered_tools[name] = response.tools
            logger.info(f"Discovered {len(response.tools)} tools from server '{name}'")
        except Exception as e:
            logger.error(f"Failed to discover tools from server '{name}': {e}")
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
        session = self.sessions.get(server_name)
        if not session:
            raise ValueError(f"Not connected to server '{server_name}'")
            
        result = await session.call_tool(tool_name, arguments)
        return result
    
    async def disconnect(self, name: str) -> None:
        """Disconnect from a specific server."""
        if name in self.exit_stacks:
            await self.exit_stacks[name].aclose()
            del self.exit_stacks[name]
            
        if name in self.sessions:
            del self.sessions[name]
            
        if name in self._discovered_tools:
            del self._discovered_tools[name]
            
        logger.info(f"Disconnected from MCP server '{name}'")
    
    async def disconnect_all(self) -> None:
        """Disconnect from all servers."""
        names = list(self.sessions.keys())
        for name in names:
            await self.disconnect(name)
    
    def is_connected(self, name: str) -> bool:
        """Check if connected to a specific server."""
        return name in self.sessions
    
    def list_connections(self) -> List[str]:
        """List all active connections."""
        return list(self.sessions.keys()) 