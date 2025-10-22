import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from tyler import Agent


@pytest.mark.asyncio
async def test_agent_mcp_connects_and_registers_tools():
    # Prepare fake MCP tool returned by adapter
    fake_tool = {
        "definition": {
            "type": "function",
            "function": {
                "name": "wandb__search",
                "description": "Search docs",
                "parameters": {"type": "object", "properties": {}}
            }
        },
        "implementation": AsyncMock(return_value="ok"),
        "attributes": {"source": "mcp", "server_name": "wandb", "original_name": "search"}
    }

    with patch("tyler.mcp.adapter.MCPAdapter") as MockAdapter:
        instance = MockAdapter.return_value
        instance.connect = AsyncMock(return_value=True)
        instance.get_tools_for_agent.return_value = [fake_tool]

        # Build agent with MCP config
        agent = Agent(
            model_name="gpt-4.1",
            mcp={
                "connect_on_init": True,
                "servers": [
                    {"name": "wandb", "transport": "sse", "url": "https://docs.wandb.ai/mcp"}
                ]
            }
        )

        # MCPAdapter should have been instantiated and connect called
        MockAdapter.assert_called_once()
        instance.connect.assert_awaited()

        # Tools should include our MCP tool in processed tools
        names = [t["function"]["name"] for t in agent._processed_tools]
        assert any(n == "wandb__search" for n in names)


@pytest.mark.asyncio
async def test_agent_mcp_handles_failed_connections():
    with patch("tyler.mcp.adapter.MCPAdapter") as MockAdapter:
        instance = MockAdapter.return_value
        instance.connect = AsyncMock(return_value=False)
        instance.get_tools_for_agent.return_value = []

        agent = Agent(
            model_name="gpt-4.1",
            mcp={
                "connect_on_init": True,
                "servers": [
                    {"name": "s1", "transport": "sse", "url": "https://bad.example/mcp"}
                ]
            }
        )

        # Should not raise; no tools added
        assert all("mcp_server" not in (t.get("attributes") or {}) for t in agent._processed_tools)


