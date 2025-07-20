"""MCP (Model Context Protocol) integration for Tyler.

This module provides a clean interface for connecting Tyler agents
to MCP servers. It does NOT manage server lifecycle - servers should
be started and managed externally.
"""

from .client import MCPClient
from .adapter import MCPAdapter

__all__ = ["MCPClient", "MCPAdapter"] 