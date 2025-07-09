"""Utility functions for MCP integration."""

import logging
from typing import Dict, List, Any, Optional

from .service import MCPService

logger = logging.getLogger(__name__)

# Global MCP service instance
_mcp_service: Optional[MCPService] = None


def get_mcp_service() -> Optional[MCPService]:
    """Get the global MCP service instance.
    
    Returns:
        Optional[MCPService]: The global MCP service instance, or None if not initialized
    """
    return _mcp_service


async def initialize_mcp_service(server_configs: List[Dict[str, Any]]) -> MCPService:
    """Initialize the global MCP service with the provided server configurations.
    
    Args:
        server_configs: List of server configuration dictionaries
        
    Returns:
        MCPService: The initialized MCP service
    """
    global _mcp_service
    
    if _mcp_service is not None:
        logger.warning("MCP service already initialized, reinitializing")
        await _mcp_service.cleanup()
        
    _mcp_service = MCPService()
    await _mcp_service.cleanup()
    
    # Initialize the service
    await _mcp_service.initialize(server_configs)
    
    return _mcp_service


async def cleanup_mcp_service() -> None:
    """Clean up the global MCP service."""
    global _mcp_service
    
    if _mcp_service is not None:
        await _mcp_service.cleanup()
        _mcp_service = None 