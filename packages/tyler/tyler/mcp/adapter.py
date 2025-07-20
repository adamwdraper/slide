"""Tyler MCP adapter for converting MCP tools to Tyler format.

This module adapts MCP tools to work with Tyler's tool system.
"""

import re
import logging
from typing import Dict, List, Any, Optional

from .client import MCPClient
from ..utils.tool_runner import tool_runner

logger = logging.getLogger(__name__)


class MCPAdapter:
    """Adapter that converts MCP tools to Tyler's tool format.
    
    This adapter handles the conversion between MCP's tool format
    and Tyler's internal tool representation.
    """
    
    def __init__(self, mcp_client: Optional[MCPClient] = None):
        """Initialize the adapter.
        
        Args:
            mcp_client: Optional MCP client instance. If not provided, creates a new one.
        """
        self.client = mcp_client or MCPClient()
        self._registered_tools: Dict[str, str] = {}  # tyler_name -> server_name
        
    async def connect(self, name: str, transport: str, **kwargs) -> bool:
        """Connect to an MCP server and register its tools with Tyler.
        
        Args:
            name: Unique name for this connection
            transport: Transport type ('stdio', 'sse', 'websocket')
            **kwargs: Transport-specific arguments
            
        Returns:
            bool: True if connection successful and tools registered
        """
        # Connect to the server
        connected = await self.client.connect(name, transport, **kwargs)
        if not connected:
            return False
            
        # Register tools with Tyler
        try:
            await self._register_server_tools(name)
            return True
        except Exception as e:
            logger.error(f"Failed to register tools from server '{name}': {e}")
            await self.client.disconnect(name)
            return False
    
    async def _register_server_tools(self, server_name: str) -> None:
        """Register all tools from a server with Tyler's tool runner."""
        tools = self.client.get_tools(server_name)
        
        for tool in tools:
            tyler_tool = self._convert_to_tyler_format(server_name, tool)
            tool_name = tyler_tool["definition"]["function"]["name"]
            
            # Register with tool runner
            tool_runner.register_tool(
                name=tool_name,
                implementation=tyler_tool["implementation"],
                definition=tyler_tool["definition"]["function"]
            )
            
            # Register attributes
            if "attributes" in tyler_tool:
                tool_runner.register_tool_attributes(tool_name, tyler_tool["attributes"])
            
            # Track registration
            self._registered_tools[tool_name] = server_name
            
        logger.info(f"Registered {len(tools)} tools from server '{server_name}'")
    
    def _convert_to_tyler_format(self, server_name: str, mcp_tool: Any) -> Dict[str, Any]:
        """Convert an MCP tool to Tyler's tool format.
        
        Args:
            server_name: Name of the server providing the tool
            mcp_tool: MCP tool object
            
        Returns:
            Tyler tool definition dictionary
        """
        # Create a safe, namespaced tool name
        tyler_name = self._create_tyler_name(server_name, mcp_tool.name)
        
        # Create the Tyler tool definition
        tyler_tool = {
            "definition": {
                "type": "function",
                "function": {
                    "name": tyler_name,
                    "description": mcp_tool.description,
                    "parameters": mcp_tool.inputSchema
                }
            },
            "implementation": self._create_tool_implementation(server_name, mcp_tool.name),
            "attributes": {
                "source": "mcp",
                "server_name": server_name,
                "original_name": mcp_tool.name,
                "mcp_server": server_name
            }
        }
        
        return tyler_tool
    
    def _create_tyler_name(self, server_name: str, tool_name: str) -> str:
        """Create a Tyler-safe tool name with server namespace.
        
        Args:
            server_name: Name of the server
            tool_name: Original tool name
            
        Returns:
            Tyler-safe namespaced tool name
        """
        # Clean server name and tool name
        clean_server = re.sub(r'[^a-zA-Z0-9_]', '_', server_name)
        clean_tool = re.sub(r'[^a-zA-Z0-9_]', '_', tool_name)
        
        # Create namespaced name
        tyler_name = f"{clean_server}__{clean_tool}"
        
        # Ensure it starts with a letter or underscore
        if tyler_name and tyler_name[0].isdigit():
            tyler_name = f"_{tyler_name}"
            
        return tyler_name
    
    def _create_tool_implementation(self, server_name: str, tool_name: str):
        """Create a function that calls the MCP tool.
        
        Args:
            server_name: Name of the server
            tool_name: Name of the tool
            
        Returns:
            Async function that calls the MCP tool
        """
        async def call_mcp_tool(**kwargs):
            """Call the MCP tool with the provided arguments."""
            try:
                result = await self.client.call_tool(server_name, tool_name, kwargs)
                
                # Extract content from MCP response
                if hasattr(result, 'content') and result.content:
                    # Convert MCP content objects to simple strings/data
                    contents = []
                    for content in result.content:
                        if hasattr(content, 'text'):
                            contents.append(content.text)
                        else:
                            contents.append(str(content))
                    
                    # Return single item if only one, otherwise return list
                    return contents[0] if len(contents) == 1 else contents
                
                return str(result)
                
            except Exception as e:
                error_msg = f"Error calling MCP tool {server_name}.{tool_name}: {e}"
                logger.error(error_msg)
                raise ValueError(error_msg)
        
        # Set function metadata for better debugging
        call_mcp_tool.__name__ = f"mcp_{server_name}_{tool_name}"
        call_mcp_tool.__doc__ = f"MCP tool: {tool_name} from server {server_name}"
        
        return call_mcp_tool
    
    def get_tools_for_agent(self, server_names: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Get Tyler-formatted tools for use with an Agent.
        
        Args:
            server_names: Optional list of server names. If None, returns tools from all servers.
            
        Returns:
            List of Tyler tool definitions ready for use with Agent
        """
        tyler_tools = []
        
        # Determine which servers to get tools from
        if server_names is None:
            servers = self.client.list_connections()
        else:
            servers = [s for s in server_names if self.client.is_connected(s)]
        
        # Convert all tools from selected servers
        for server_name in servers:
            mcp_tools = self.client.get_tools(server_name)
            for mcp_tool in mcp_tools:
                tyler_tool = self._convert_to_tyler_format(server_name, mcp_tool)
                tyler_tools.append(tyler_tool)
        
        return tyler_tools
    
    async def disconnect(self, name: str) -> None:
        """Disconnect from a server and unregister its tools.
        
        Args:
            name: Name of the server to disconnect from
        """
        # Unregister tools
        tools_to_remove = [
            tool_name for tool_name, server_name in self._registered_tools.items()
            if server_name == name
        ]
        
        for tool_name in tools_to_remove:
            # Note: tool_runner doesn't have unregister, so we just track it
            del self._registered_tools[tool_name]
        
        # Disconnect from server
        await self.client.disconnect(name)
        
    async def disconnect_all(self) -> None:
        """Disconnect from all servers and clean up."""
        self._registered_tools.clear()
        await self.client.disconnect_all() 