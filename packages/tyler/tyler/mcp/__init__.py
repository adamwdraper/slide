"""MCP (Model Context Protocol) integration for Tyler.

This module provides MCP integration using the official MCP SDK's ClientSessionGroup.
It does NOT manage server lifecycle - servers should be started and managed externally.

Usage:
    Use Agent(mcp={...}) with agent.connect_mcp() for the recommended API.
    The config_loader functions are internal and not part of the public API.
"""

from .config_loader import _validate_mcp_config, _load_mcp_config

__all__ = ["_validate_mcp_config", "_load_mcp_config"]
